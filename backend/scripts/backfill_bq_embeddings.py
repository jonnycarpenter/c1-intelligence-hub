"""
BigQuery Chunk Embeddings Backfill Script
=========================================

Generates embeddings for all existing articles in BigQuery and stores them
in the article_chunk_embeddings table with intelligent chunking:

- Earnings transcripts: Speaker-turn chunking with overlap for Q&A context
- SEC filings: Section-based chunking (Business, Risk Factors, MD&A, etc.)
- Long articles: Paragraph-based chunking with overlap
- Short articles: Single chunk with full content

Uses Vertex AI text-embedding-004 for production-grade embeddings (768 dimensions).

Usage:
    python scripts/backfill_bq_embeddings.py
    
Options:
    --batch-size    Number of articles to process per batch (default: 5)
    --limit         Max articles to process (default: all)
    --source-type   Only process articles from specific source (e.g., 'sec_filing')
    --dry-run       Show what would be processed without actually embedding
"""

import os
import sys
import asyncio
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.logger import get_logger
from app.db.bq_vector_store import BigQueryVectorStore, EmbeddingGenerator
from app.db.gcp_storage import gcp_config
from app.models.corpus import CorpusItem, ContentSource, Priority

logger = get_logger(__name__)


class ArticleForEmbedding:
    """
    Lightweight article representation for embedding generation.
    
    Includes all metadata needed for intelligent chunking:
    - For earnings: transcript_split, ticker, quarter, year
    - For SEC filings: sections, ticker, form_type
    - For all: full_text for chunking decisions
    """
    
    def __init__(self, row: Dict[str, Any]):
        self.id = row.get("id", "")
        self.title = row.get("title", "")
        self.summary = row.get("summary", "")
        self.full_text = row.get("full_text", "")
        self.url = row.get("url", "")
        self.published_at = row.get("published_at")
        
        # Build source object - use source_name if available, fall back to source_type
        source_name = row.get("source_name") or row.get("source_type", "")
        source_type = row.get("source_type", "")
        self.source = type('Source', (), {
            'name': source_name,
            'source_type': source_type
        })()
        
        # Category and priority as strings
        self.category = row.get("category", "general") or "general"
        self.priority_str = row.get("priority", "medium") or "medium"
        
        # For compatibility with embedding generator that expects .value attribute
        self.primary_category = type('Category', (), {'value': self.category})()
        self.priority = type('Priority', (), {'value': self.priority_str})()
        
        # Additional fields for embedding text
        companies = row.get("companies_mentioned", "")
        self.companies_mentioned = companies.split(",") if isinstance(companies, str) and companies else []
        self.industries = []
        
        # Raw metadata for chunking (JSON from BigQuery)
        raw_metadata = row.get("raw_metadata")
        if isinstance(raw_metadata, str):
            import json
            try:
                self.metadata = json.loads(raw_metadata)
            except:
                self.metadata = {}
        elif isinstance(raw_metadata, dict):
            self.metadata = raw_metadata
        else:
            self.metadata = {}
        
        # Also expose as raw_data for compatibility
        self.raw_data = self.metadata


async def get_existing_embedding_ids(bq_store: BigQueryVectorStore) -> set:
    """Get set of article IDs that already have chunk embeddings."""
    try:
        table_id = f"{bq_store.config.full_dataset_id}.{bq_store.EMBEDDINGS_TABLE}"
        # Get distinct article_ids (since each article may have multiple chunks)
        query = f"SELECT DISTINCT article_id FROM `{table_id}`"
        
        job = bq_store.client.query(query)
        results = job.result()
        
        return {row.article_id for row in results}
    except Exception as e:
        logger.warning(f"Could not fetch existing embeddings: {e}")
        return set()


async def fetch_articles_for_embedding(
    bq_store: BigQueryVectorStore,
    existing_ids: set,
    source_type: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[ArticleForEmbedding]:
    """Fetch articles from BigQuery that need embeddings."""
    
    # Query articles table (has full content for embedding)
    table_id = f"{bq_store.config.full_dataset_id}.articles"
    
    where_clauses = []
    if source_type:
        where_clauses.append(f"source_type = '{source_type}'")
    
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    limit_sql = f"LIMIT {limit}" if limit else ""
    
    query = f"""
    SELECT 
        id,
        title,
        summary,
        full_text,
        url,
        source_name,
        source_type,
        category,
        published_at,
        companies_mentioned,
        topics
    FROM `{table_id}`
    {where_sql}
    ORDER BY fetched_at DESC
    {limit_sql}
    """
    
    try:
        job = bq_store.client.query(query)
        results = job.result()
        
        articles = []
        for row in results:
            row_dict = dict(row)
            # Skip if already has embedding
            if row_dict.get("id") in existing_ids:
                continue
            articles.append(ArticleForEmbedding(row_dict))
        
        return articles
        
    except Exception as e:
        logger.error(f"Error fetching articles: {e}")
        return []


async def backfill_embeddings(
    batch_size: int = 50,
    limit: Optional[int] = None,
    source_type: Optional[str] = None,
    dry_run: bool = False,
):
    """Main backfill function."""
    
    print("\n" + "=" * 60)
    print("BigQuery Embeddings Backfill")
    print("=" * 60)
    print(f"Batch size: {batch_size}")
    print(f"Limit: {limit or 'All'}")
    print(f"Source type filter: {source_type or 'All'}")
    print(f"Dry run: {dry_run}")
    print("")
    
    # Initialize BigQuery vector store
    print("🔧 Initializing BigQuery vector store...")
    bq_store = BigQueryVectorStore()
    await bq_store.initialize()
    
    if not bq_store.is_available:
        print("❌ BigQuery vector store not available. Check Vertex AI configuration.")
        return
    
    print(f"   Embedding model: {bq_store._embedder.model_name}")
    print(f"   Dimensions: {bq_store._embedder.dimensions}")
    
    # Get existing embeddings
    print("\n📊 Checking existing embeddings...")
    existing_ids = await get_existing_embedding_ids(bq_store)
    print(f"   Already embedded: {len(existing_ids)} articles")
    
    # Fetch articles needing embeddings
    print("\n📥 Fetching articles to embed...")
    articles = await fetch_articles_for_embedding(
        bq_store,
        existing_ids,
        source_type=source_type,
        limit=limit,
    )
    print(f"   Articles to process: {len(articles)}")
    
    if not articles:
        print("\n✅ No articles need embedding. All done!")
        return
    
    if dry_run:
        print("\n🔍 DRY RUN - Would process these articles:")
        for i, article in enumerate(articles[:20]):
            text_len = len(article.full_text) if article.full_text else 0
            est_chunks = max(1, text_len // 1500)  # Rough estimate
            print(f"   {i+1}. [{article.source.source_type}] {article.title[:50]}... ({text_len:,} chars → ~{est_chunks} chunks)")
        if len(articles) > 20:
            print(f"   ... and {len(articles) - 20} more")
        
        # Estimate total chunks
        total_chars = sum(len(a.full_text or "") for a in articles)
        est_total_chunks = sum(max(1, len(a.full_text or "") // 1500) for a in articles)
        print(f"\n   Total content: {total_chars:,} characters")
        print(f"   Estimated chunks: ~{est_total_chunks:,}")
        return
    
    # Process in batches
    print(f"\n🚀 Processing {len(articles)} articles in batches of {batch_size}...")
    
    total_embedded = 0
    total_errors = 0
    start_time = datetime.utcnow()
    
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(articles) + batch_size - 1) // batch_size
        
        print(f"\n   Batch {batch_num}/{total_batches} ({len(batch)} articles)...")
        
        try:
            count = await bq_store.add_items(batch)
            total_embedded += count
            print(f"   ✓ Embedded {count} articles")
            
        except Exception as e:
            total_errors += len(batch)
            print(f"   ✗ Error: {e}")
        
        # Rate limiting for Vertex AI
        if i + batch_size < len(articles):
            await asyncio.sleep(1)  # Brief pause between batches
    
    # Summary
    elapsed = (datetime.utcnow() - start_time).total_seconds()
    print("\n" + "=" * 60)
    print("CHUNK EMBEDDINGS BACKFILL COMPLETE")
    print("=" * 60)
    print(f"   Articles processed: {len(articles)}")
    print(f"   Chunk embeddings created: {total_embedded}")
    print(f"   Articles with errors: {total_errors}")
    print(f"   Time elapsed: {elapsed:.1f}s")
    if elapsed > 0:
        print(f"   Rate: {total_embedded / elapsed:.1f} chunks/sec")
    
    # Verify final count
    final_count = await bq_store.get_count()
    print(f"\n   Total chunk embeddings in BigQuery: {final_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill BigQuery chunk embeddings")
    parser.add_argument("--batch-size", type=int, default=5,
                        help="Articles per batch (default: 5, each article generates multiple chunks)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max articles to process (default: all)")
    parser.add_argument("--source-type", type=str, default=None,
                        help="Filter by source type (e.g., 'sec_filing', 'earnings')")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be processed without embedding")
    
    args = parser.parse_args()
    
    asyncio.run(backfill_embeddings(
        batch_size=args.batch_size,
        limit=args.limit,
        source_type=args.source_type,
        dry_run=args.dry_run,
    ))
