#!/usr/bin/env python3
"""
ChromaDB Re-indexing Script
===========================

Re-indexes all corpus items from SQLite into ChromaDB with smart chunking.

This script:
1. Reads all corpus_items from SQLite
2. Converts them to CorpusItem objects  
3. Applies the new chunking logic (earnings by speaker, SEC by section)
4. Upserts to ChromaDB

Run from backend directory:
    python scripts/reindex_chromadb.py

Options:
    --clear         Clear existing ChromaDB data before re-indexing
    --source-type   Only re-index specific source types (earnings, sec_filing, etc.)
    --dry-run       Show what would be indexed without actually doing it
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiosqlite
from app.db.database import Database
from app.db.vector_store import VectorStore, get_vector_store
from app.models.corpus import CorpusItem, ContentSource, Priority, ContentCategory as Category
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def load_corpus_items_from_sqlite(source_type: str = None) -> list:
    """Load all corpus items from SQLite database."""
    db = Database()
    await db.initialize()
    
    query = """
        SELECT 
            id, title, url, summary, full_text, 
            source_name, source_type, primary_category, priority,
            published_at, ingested_at, relevance_score,
            companies_mentioned, materials_mentioned, industries
        FROM corpus_items
    """
    params = []
    
    if source_type:
        query += " WHERE source_type = ?"
        params.append(source_type)
    
    query += " ORDER BY published_at DESC"
    
    async with aiosqlite.connect(db.db_path) as conn:
        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
    
    items = []
    for row in rows:
        try:
            # Parse JSON fields
            import json
            companies = json.loads(row[12]) if row[12] else []
            materials = json.loads(row[13]) if row[13] else []
            industries_raw = json.loads(row[14]) if row[14] else []
            metadata = {}  # metadata column doesn't exist in schema
            
            # Parse dates
            published_at = None
            if row[9]:
                try:
                    published_at = datetime.fromisoformat(row[9].replace('Z', '+00:00'))
                except:
                    pass
            
            ingested_at = None
            if row[10]:
                try:
                    ingested_at = datetime.fromisoformat(row[10].replace('Z', '+00:00'))
                except:
                    pass
            
            # Create ContentSource
            source = ContentSource(
                name=row[5] or "Unknown",
                source_type=row[6] or "unknown",
                url=row[2] or "",  # Use item URL as source URL
            )
            
            # Parse category
            category = None
            if row[7]:
                try:
                    category = Category(row[7])
                except:
                    category = Category.MARKET
            
            # Parse priority
            priority = Priority.MEDIUM
            if row[8]:
                try:
                    priority = Priority(row[8])
                except:
                    pass
            
            # Create CorpusItem
            item = CorpusItem(
                id=row[0],
                title=row[1] or "",
                url=row[2] or "",
                summary=row[3] or "",
                full_text=row[4] or "",
                source=source,
                primary_category=category,
                priority=priority,
                published_at=published_at,
                ingested_at=ingested_at,
                relevance_score=row[11] or 0.5,
                companies_mentioned=companies,
                materials_mentioned=materials,
                metadata=metadata,
            )
            items.append(item)
            
        except Exception as e:
            logger.warning(f"Error parsing corpus item {row[0]}: {e}")
            continue
    
    return items


async def reindex_chromadb(
    clear: bool = False,
    source_type: str = None,
    dry_run: bool = False,
):
    """Re-index all corpus items into ChromaDB with smart chunking."""
    
    print("=" * 60)
    print("ChromaDB Re-indexing Script")
    print("=" * 60)
    
    # Load items from SQLite
    print(f"\n📂 Loading corpus items from SQLite...")
    if source_type:
        print(f"   (filtering to source_type: {source_type})")
    
    items = await load_corpus_items_from_sqlite(source_type)
    print(f"   Found {len(items)} items")
    
    if not items:
        print("No items to index. Exiting.")
        return
    
    # Show breakdown by source type
    source_counts = {}
    for item in items:
        st = item.source.source_type if item.source else "unknown"
        source_counts[st] = source_counts.get(st, 0) + 1
    
    print("\n📊 Items by source type:")
    for st, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"   {st}: {count}")
    
    # Count items that will be chunked
    chunked_count = 0
    for item in items:
        st = item.source.source_type if item.source else ""
        if st == "earnings":
            chunked_count += 1
        elif st == "sec_filing" and item.full_text and len(item.full_text) > 3000:
            chunked_count += 1
        elif item.full_text and len(item.full_text) > 4000:
            chunked_count += 1
    
    print(f"\n📦 Items that will be chunked: {chunked_count}")
    
    if dry_run:
        print("\n🏃 DRY RUN - not actually indexing")
        return
    
    # Initialize vector store
    print("\n🔧 Initializing ChromaDB...")
    store = get_vector_store()
    await store.initialize()
    
    if not store.is_available:
        print("❌ ChromaDB not available. Exiting.")
        return
    
    current_count = store._collection.count()
    print(f"   Current ChromaDB count: {current_count}")
    
    # Clear if requested
    if clear:
        print("\n🗑️  Clearing existing ChromaDB data...")
        await store.clear()
        print("   Cleared.")
    
    # Re-index in batches
    print("\n📥 Indexing items...")
    batch_size = 50
    total_vectors = 0
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        added = await store.add_items(batch)
        total_vectors += added
        print(f"   Processed {min(i + batch_size, len(items))}/{len(items)} items...")
    
    # Final count
    final_count = store._collection.count()
    print(f"\n✅ Re-indexing complete!")
    print(f"   Items processed: {len(items)}")
    print(f"   Vectors in ChromaDB: {final_count}")
    print(f"   (increase from {current_count} due to chunking)")


def main():
    parser = argparse.ArgumentParser(description="Re-index ChromaDB from SQLite")
    parser.add_argument("--clear", action="store_true", help="Clear existing data before re-indexing")
    parser.add_argument("--source-type", type=str, help="Only re-index specific source type (e.g., earnings, sec_filing)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be indexed without actually doing it")
    
    args = parser.parse_args()
    
    asyncio.run(reindex_chromadb(
        clear=args.clear,
        source_type=args.source_type,
        dry_run=args.dry_run,
    ))


if __name__ == "__main__":
    main()
