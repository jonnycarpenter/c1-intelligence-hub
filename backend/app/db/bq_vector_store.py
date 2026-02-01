"""
BigQuery Vector Store
=====================

Production-ready vector search using BigQuery's native VECTOR_SEARCH.

This is the ONLY vector store - all embeddings are stored in BigQuery.

Features:
- Durable storage with automatic backups
- Scales automatically with BigQuery
- Integrates with existing BigQuery data
- Single source of truth for articles + embeddings
- Supports hybrid search (metadata + semantic)
- Uses Vertex AI for embeddings (text-embedding-005)

Usage:
    store = BigQueryVectorStore()
    await store.initialize()
    
    # Add items with embeddings
    await store.add_items(corpus_items)
    
    # Search
    results = await store.search("carbon fiber supply chain issues", limit=10)
"""

import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from app.utils.logger import get_logger
from app.db.gcp_storage import gcp_config, GCPConfig
from app.utils.chunking import (
    DocumentChunk,
    chunk_earnings_transcript,
    chunk_sec_filing,
    _chunk_raw_text,
)

logger = get_logger(__name__)


# Embedding dimensions for different models
EMBEDDING_DIMENSIONS = {
    "text-embedding-004": 768,
    "text-embedding-005": 768,
    "textembedding-gecko": 768,
    "local": 384,  # For sentence-transformers fallback
}

DEFAULT_EMBEDDING_MODEL = "text-embedding-004"
DEFAULT_DIMENSIONS = EMBEDDING_DIMENSIONS[DEFAULT_EMBEDDING_MODEL]


class EmbeddingGenerator:
    """
    Generates embeddings using Vertex AI or local models.
    
    Falls back gracefully:
    1. Vertex AI text-embedding-004 (production)
    2. Local sentence-transformers (development)
    """
    
    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL):
        self.model_name = model_name
        self._vertex_model = None
        self._local_model = None
        self._available = False
        self.dimensions = EMBEDDING_DIMENSIONS.get(model_name, DEFAULT_DIMENSIONS)
    
    async def initialize(self):
        """Initialize the embedding model."""
        # Try Vertex AI first
        if await self._init_vertex_ai():
            logger.info(f"Using Vertex AI embeddings: {self.model_name}")
            return
        
        # Fall back to local model
        if await self._init_local():
            logger.info("Using local sentence-transformers embeddings")
            return
        
        logger.warning("No embedding model available - vector search disabled")
    
    async def _init_vertex_ai(self) -> bool:
        """Initialize Vertex AI embedding model."""
        try:
            from vertexai.language_models import TextEmbeddingModel
            import vertexai
            
            project_id = os.getenv("GCP_PROJECT_ID", gcp_config.project_id)
            location = os.getenv("GCP_LOCATION", "us-central1")
            
            if not project_id:
                return False
            
            vertexai.init(project=project_id, location=location)
            self._vertex_model = TextEmbeddingModel.from_pretrained(self.model_name)
            self._available = True
            return True
            
        except Exception as e:
            logger.debug(f"Vertex AI not available: {e}")
            return False
    
    async def _init_local(self) -> bool:
        """Initialize local sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer
            
            self._local_model = SentenceTransformer("all-MiniLM-L6-v2")
            self.model_name = "local"
            self.dimensions = 384
            self._available = True
            return True
            
        except Exception as e:
            logger.debug(f"Local embeddings not available: {e}")
            return False
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        if not self._available:
            return []
        
        # Clean and truncate texts
        texts = [self._prepare_text(t) for t in texts]
        
        if self._vertex_model:
            return await self._embed_vertex(texts)
        elif self._local_model:
            return self._embed_local(texts)
        return []
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        results = await self.embed_texts([text])
        return results[0] if results else []
    
    async def _embed_vertex(self, texts: List[str], max_retries: int = 3) -> List[List[float]]:
        """Generate embeddings using Vertex AI with retry logic."""
        import asyncio
        
        # Vertex AI has batch limits, process in chunks
        batch_size = 250
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_success = False
            
            # Retry loop for transient errors
            for attempt in range(max_retries):
                try:
                    embeddings = self._vertex_model.get_embeddings(batch)
                    all_embeddings.extend([e.values for e in embeddings])
                    batch_success = True
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    error_str = str(e)
                    # Retry on 500 Internal errors or rate limits
                    if ("500" in error_str or "INTERNAL" in error_str or 
                        "429" in error_str or "RESOURCE_EXHAUSTED" in error_str):
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) + 1  # 2, 3, 5 seconds
                            logger.warning(f"Vertex AI error (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                            await asyncio.sleep(wait_time)
                            continue
                    
                    # Non-retryable error or max retries exceeded
                    logger.error(f"Vertex AI embedding error: {e}")
                    break  # Exit retry loop on non-retryable error
            
            if not batch_success:
                # If this batch failed, return empty to signal failure
                return []
        
        return all_embeddings
    
    def _embed_local(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using local model."""
        try:
            embeddings = self._local_model.encode(texts, convert_to_numpy=True)
            return [e.tolist() for e in embeddings]
        except Exception as e:
            logger.error(f"Local embedding error: {e}")
            return []
    
    def _prepare_text(self, text: str, max_length: int = 8000) -> str:
        """Prepare text for embedding."""
        if not text:
            return ""
        # Truncate to avoid token limits
        return text[:max_length].strip()


class BigQueryVectorStore:
    """
    BigQuery-backed vector store using native VECTOR_SEARCH.
    
    Uses a dedicated table with embedding column that joins
    with the existing digest_items/articles tables.
    
    Supports intelligent chunking for different document types:
    - Earnings transcripts: Speaker-turn chunking with overlap
    - SEC filings: Section-based chunking (Business, Risk Factors, MD&A, etc.)
    - Long articles: Paragraph-based chunking with overlap
    
    Handles dimension mismatches gracefully - if query embeddings have
    different dimensions than stored embeddings (e.g., Vertex AI 768d vs
    local model 384d), mismatched embeddings are skipped with a warning.
    """
    
    EMBEDDINGS_TABLE = "article_chunk_embeddings"  # Chunk-level embeddings
    
    def __init__(self, config: Optional[GCPConfig] = None):
        self.config = config or gcp_config
        self._client = None
        self._embedder = EmbeddingGenerator()
        self._initialized = False
        self._available = False
        self._stored_dimensions: Optional[int] = None  # Track stored embedding dimensions
    
    @property
    def client(self):
        """Lazy-load BigQuery client."""
        if self._client is None:
            try:
                from google.cloud import bigquery
                self._client = bigquery.Client(project=self.config.project_id)
            except ImportError:
                raise ImportError("google-cloud-bigquery required")
        return self._client
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    async def initialize(self):
        """Initialize the vector store and create necessary tables."""
        if self._initialized:
            return
        
        # Initialize embedder
        await self._embedder.initialize()
        
        if not self._embedder.is_available:
            logger.warning("Embedding model not available - vector search disabled")
            return
        
        # Create embeddings table
        await self._create_embeddings_table()
        
        # Check for dimension mismatch between current embedder and stored embeddings
        await self._validate_embedding_dimensions()
        
        self._initialized = True
        self._available = True
        
        count = await self.get_count()
        logger.info(f"BigQuery vector store initialized with {count} embeddings")
    
    async def _validate_embedding_dimensions(self):
        """
        Validate that current embedder dimensions match stored embeddings.
        
        If there's a mismatch (e.g., switched from Vertex AI to local model),
        warn the user but allow operation to continue.
        """
        try:
            table_id = f"{self.config.full_dataset_id}.{self.EMBEDDINGS_TABLE}"
            query = f"""
            SELECT ARRAY_LENGTH(embedding) as dim, embedding_model, COUNT(*) as cnt
            FROM `{table_id}`
            WHERE embedding IS NOT NULL
            GROUP BY ARRAY_LENGTH(embedding), embedding_model
            LIMIT 5
            """
            
            job = self.client.query(query)
            rows = list(job.result())
            
            if not rows:
                logger.info("No existing embeddings - dimension validation skipped")
                return
            
            current_dim = self._embedder.dimensions
            current_model = self._embedder.model_name
            
            for row in rows:
                stored_dim = row.dim
                stored_model = row.embedding_model
                count = row.cnt
                
                if stored_dim != current_dim:
                    logger.warning(
                        f"⚠️ DIMENSION MISMATCH: Stored embeddings have {stored_dim}d "
                        f"(from {stored_model}, {count} items) but current embedder "
                        f"uses {current_dim}d ({current_model}). "
                        f"Semantic search will skip mismatched embeddings."
                    )
                    # Store the expected dimension for filtering during search
                    self._stored_dimensions = stored_dim
                else:
                    logger.info(f"Embedding dimensions match: {current_dim}d ({current_model})")
                    
        except Exception as e:
            logger.debug(f"Could not validate embedding dimensions: {e}")
    
    async def _create_embeddings_table(self):
        """Create the chunk embeddings table with vector column."""
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.{self.EMBEDDINGS_TABLE}"
        
        # Schema with ARRAY<FLOAT64> for embeddings - chunk-level storage
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),  # chunk_id
            bigquery.SchemaField("article_id", "STRING", mode="REQUIRED"),  # parent article
            bigquery.SchemaField("chunk_index", "INT64"),  # Position in document
            bigquery.SchemaField("total_chunks", "INT64"),  # Total chunks for document
            bigquery.SchemaField("chunk_type", "STRING"),  # earnings_dialogue, sec_filing, text_chunk
            bigquery.SchemaField("chunk_text", "STRING"),  # The actual text embedded
            bigquery.SchemaField("title", "STRING"),  # Parent article title
            bigquery.SchemaField("content_hash", "STRING"),  # For dedup
            bigquery.SchemaField("embedding", "FLOAT64", mode="REPEATED"),  # Vector
            bigquery.SchemaField("embedding_model", "STRING"),
            bigquery.SchemaField("category", "STRING"),
            bigquery.SchemaField("priority", "STRING"),
            bigquery.SchemaField("source_type", "STRING"),
            bigquery.SchemaField("published_at", "TIMESTAMP"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            # Chunk-specific metadata (JSON for flexibility)
            bigquery.SchemaField("chunk_metadata", "JSON"),  # speakers, section_name, ticker, etc.
        ]
        
        table = bigquery.Table(table_id, schema=schema)
        table.clustering_fields = ["source_type", "chunk_type"]
        
        try:
            self.client.create_table(table)
            logger.info(f"Created embeddings table: {table_id}")
            
            # Create vector index for fast similarity search
            await self._create_vector_index()
            
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Embeddings table already exists: {table_id}")
            else:
                raise
    
    async def _create_vector_index(self):
        """Create a vector index for fast similarity search."""
        table_id = f"{self.config.full_dataset_id}.{self.EMBEDDINGS_TABLE}"
        index_name = f"{self.EMBEDDINGS_TABLE}_embedding_idx"
        
        # BigQuery vector index DDL
        query = f"""
        CREATE VECTOR INDEX IF NOT EXISTS `{index_name}`
        ON `{table_id}`(embedding)
        OPTIONS(
            index_type = 'IVF',
            distance_type = 'COSINE',
            ivf_options = '{{"num_lists": 100}}'
        )
        """
        
        try:
            job = self.client.query(query)
            job.result()  # Wait for completion
            logger.info(f"Created vector index: {index_name}")
        except Exception as e:
            # Vector index might not be available in all regions/tiers
            logger.warning(f"Could not create vector index (will use brute force): {e}")
    
    async def add_item(self, item) -> bool:
        """Add a single item to the vector store."""
        return await self.add_items([item]) > 0
    
    def _chunk_item(self, item) -> List[DocumentChunk]:
        """
        Chunk an item based on its source type.
        
        Returns a list of DocumentChunk objects. For short items,
        returns a single chunk containing the whole document.
        """
        source_type = ""
        if hasattr(item, 'source'):
            if hasattr(item.source, 'source_type'):
                source_type = item.source.source_type or ""
            elif hasattr(item.source, 'name'):
                source_type = item.source.name or ""
        
        # Build base metadata
        base_metadata = {
            "article_id": item.id if hasattr(item, 'id') else "",
            "title": item.title if hasattr(item, 'title') else "",
            "source_type": source_type,
            "category": self._get_category(item),
            "priority": self._get_priority(item),
        }
        
        # Get raw metadata if available
        raw_data = {}
        if hasattr(item, 'metadata') and item.metadata:
            raw_data = item.metadata
        elif hasattr(item, 'raw_data') and item.raw_data:
            raw_data = item.raw_data
        
        # Earnings transcripts - speaker-turn chunking
        if source_type in ("earnings", "earnings_transcript", "earnings"):
            transcript_split = raw_data.get("transcript_split", [])
            ticker = raw_data.get("ticker", "")
            quarter = raw_data.get("quarter", 0)
            year = raw_data.get("year", 0)
            
            company_name = ""
            if hasattr(item, 'title') and item.title:
                parts = item.title.split(" Q")
                if parts:
                    company_name = parts[0]
            
            full_text = item.full_text if hasattr(item, 'full_text') else ""
            
            if transcript_split or (full_text and len(full_text) > 3000):
                return chunk_earnings_transcript(
                    transcript_id=item.id,
                    ticker=ticker,
                    company_name=company_name,
                    quarter=quarter,
                    year=year,
                    transcript_split=transcript_split,
                    full_text=full_text or "",
                    base_metadata=base_metadata,
                )
        
        # SEC filings - section-based chunking
        if source_type == "sec_filing":
            ticker = raw_data.get("ticker", "")
            filing_type = raw_data.get("form_type", "SEC Filing")
            sections = raw_data.get("sections", {})
            
            company_name = ""
            if hasattr(item, 'title') and item.title:
                parts = item.title.split(" - ")
                if parts:
                    company_name = parts[0]
            
            full_text = item.full_text if hasattr(item, 'full_text') else ""
            
            if not sections and full_text:
                sections = {"full": full_text}
            
            if sections:
                return chunk_sec_filing(
                    filing_id=item.id,
                    ticker=ticker,
                    company_name=company_name,
                    filing_type=filing_type,
                    sections=sections,
                    base_metadata=base_metadata,
                )
        
        # Long text - simple chunking with overlap
        full_text = item.full_text if hasattr(item, 'full_text') else ""
        if full_text and len(full_text) > 4000:
            context = f"{item.title}\n\n" if hasattr(item, 'title') and item.title else ""
            return _chunk_raw_text(
                doc_id=item.id,
                text=full_text,
                base_metadata=base_metadata,
                context_prefix=context,
            )
        
        # Short content - single chunk
        text = self._build_document_text(item)
        return [DocumentChunk(
            chunk_id=f"{item.id}_chunk_0",
            parent_id=item.id,
            text=text,
            metadata={**base_metadata, "chunk_type": "full_document"},
            chunk_index=0,
            total_chunks=1,
        )]
    
    def _get_category(self, item) -> str:
        """Extract category string from item."""
        if hasattr(item, 'primary_category') and item.primary_category:
            if hasattr(item.primary_category, 'value'):
                return item.primary_category.value
            return str(item.primary_category)
        if hasattr(item, 'category') and item.category:
            return str(item.category)
        return "general"
    
    def _get_priority(self, item) -> str:
        """Extract priority string from item."""
        if hasattr(item, 'priority') and item.priority:
            if hasattr(item.priority, 'value'):
                return item.priority.value
            return str(item.priority)
        return "medium"
    
    async def add_items(self, items: List[Any]) -> int:
        """
        Add multiple items to the vector store with intelligent chunking.
        
        For each item:
        1. Determines document type (earnings, SEC filing, general)
        2. Applies appropriate chunking strategy
        3. Generates embeddings for each chunk
        4. Stores chunks with full metadata for retrieval
        """
        if not self._available or not items:
            return 0
        
        try:
            # Chunk all items
            all_chunks: List[tuple] = []  # (item, chunk) pairs
            for item in items:
                chunks = self._chunk_item(item)
                for chunk in chunks:
                    all_chunks.append((item, chunk))
            
            if not all_chunks:
                return 0
            
            logger.info(f"Processing {len(items)} items → {len(all_chunks)} chunks")
            
            # Build texts for embedding (just chunk text)
            texts = [chunk.text for _, chunk in all_chunks]
            
            # Generate embeddings in batches to avoid token limits
            # Some chunks (especially SEC filings) can be 2000+ tokens, so use small batches
            batch_size = 5  # Reduced from 10 to handle large chunks safely
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                batch_embeddings = await self._embedder.embed_texts(batch_texts)
                if batch_embeddings:
                    all_embeddings.extend(batch_embeddings)
                else:
                    # Fill with None for failed batches
                    all_embeddings.extend([None] * len(batch_texts))
            
            if not all_embeddings:
                logger.error("All embedding batches failed")
                return 0
            
            # Prepare rows for BigQuery
            rows = []
            for (item, chunk), embedding in zip(all_chunks, all_embeddings):
                if embedding is None:
                    continue
                
                content_hash = hashlib.md5(chunk.text.encode()).hexdigest()
                
                # Get source_type from chunk metadata or item
                source_type = chunk.metadata.get("source_type", "")
                if not source_type and hasattr(item, 'source'):
                    if hasattr(item.source, 'name'):
                        source_type = item.source.name
                    elif hasattr(item.source, 'source_type'):
                        source_type = item.source.source_type
                
                rows.append({
                    "id": chunk.chunk_id,
                    "article_id": chunk.parent_id,
                    "chunk_index": chunk.chunk_index,
                    "total_chunks": chunk.total_chunks,
                    "chunk_type": chunk.metadata.get("chunk_type", "text_chunk"),
                    "chunk_text": chunk.text[:10000],  # Limit text storage
                    "title": (item.title[:500] if hasattr(item, 'title') and item.title else ""),
                    "content_hash": content_hash,
                    "embedding": embedding,
                    "embedding_model": self._embedder.model_name,
                    "category": self._get_category(item),
                    "priority": self._get_priority(item),
                    "source_type": source_type,
                    "published_at": (item.published_at.isoformat() 
                                    if hasattr(item, 'published_at') and item.published_at else None),
                    "created_at": datetime.utcnow().isoformat(),
                    "chunk_metadata": json.dumps({
                        k: v for k, v in chunk.metadata.items()
                        if k not in ("article_id", "title", "source_type", "category", "priority")
                    }),
                })
            
            if not rows:
                logger.warning("No valid embeddings generated")
                return 0
            
            # Insert into BigQuery in smaller batches to avoid SSL timeouts
            # Each embedding row is ~6KB JSON, so keep batches small
            table_id = f"{self.config.full_dataset_id}.{self.EMBEDDINGS_TABLE}"
            insert_batch_size = 5  # Small batches to avoid SSL timeout
            total_inserted = 0
            total_errors = 0
            
            for i in range(0, len(rows), insert_batch_size):
                batch_rows = rows[i:i + insert_batch_size]
                
                # Retry logic for transient failures
                for attempt in range(3):
                    try:
                        errors = self.client.insert_rows_json(table_id, batch_rows)
                        if errors:
                            logger.warning(f"Insert batch {i//insert_batch_size + 1} errors: {errors[:2]}")
                            total_errors += len(errors)
                        total_inserted += len(batch_rows) - len(errors) if errors else len(batch_rows)
                        break  # Success, exit retry loop
                    except Exception as insert_err:
                        if attempt < 2:
                            logger.warning(f"Insert attempt {attempt + 1} failed, retrying: {insert_err}")
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        else:
                            logger.error(f"Insert batch failed after 3 attempts: {insert_err}")
                            total_errors += len(batch_rows)
            
            if total_errors:
                logger.warning(f"Inserted {total_inserted} chunks with {total_errors} errors")
            else:
                logger.info(f"Added {total_inserted} chunk embeddings from {len(items)} items")
            return total_inserted
            
        except Exception as e:
            logger.error(f"Error adding items to vector store: {e}")
            return 0
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        where: Optional[Dict[str, Any]] = None,
        hours: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search using BigQuery VECTOR_SEARCH.
        
        Args:
            query: Search query text
            limit: Max results
            where: Metadata filters (category, priority, source_type)
            hours: Only search items from last N hours (relative)
            date_from: Start of date range (absolute, e.g., 'Q4 2025')
            date_to: End of date range (absolute)
        """
        if not self._available:
            return []
        
        try:
            # Generate query embedding
            query_embedding = await self._embedder.embed_text(query)
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []
            
            # Build the search query
            results = await self._vector_search(
                query_embedding=query_embedding,
                limit=limit,
                where=where,
                hours=hours,
                date_from=date_from,
                date_to=date_to,
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []
    
    async def _vector_search(
        self,
        query_embedding: List[float],
        limit: int,
        where: Optional[Dict[str, Any]] = None,
        hours: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Execute BigQuery VECTOR_SEARCH."""
        table_id = f"{self.config.full_dataset_id}.{self.EMBEDDINGS_TABLE}"
        
        # Build WHERE clause
        where_clauses = []
        if where:
            if "category" in where:
                where_clauses.append(f"base.category = '{where['category']}'")
            if "priority" in where:
                where_clauses.append(f"base.priority = '{where['priority']}'")
            if "source_type" in where:
                where_clauses.append(f"base.source_type = '{where['source_type']}'")
        
        # Time filtering: absolute date range takes precedence over relative hours
        if date_from:
            where_clauses.append(f"base.published_at >= TIMESTAMP('{date_from.isoformat()}')")
        if date_to:
            where_clauses.append(f"base.published_at <= TIMESTAMP('{date_to.isoformat()}')")
        if hours and not date_from and not date_to:
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            where_clauses.append(f"base.published_at >= TIMESTAMP('{cutoff}')")
        
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        
        # Convert embedding to SQL array literal
        embedding_str = ", ".join(str(x) for x in query_embedding)
        
        # BigQuery VECTOR_SEARCH query
        # Using ML.DISTANCE for cosine similarity
        # Include chunk_text for actual content (critical for ad-hoc agent responses)
        query = f"""
        WITH query_embedding AS (
            SELECT [{embedding_str}] AS embedding
        )
        SELECT
            base.article_id,
            base.title,
            base.chunk_text,
            base.category,
            base.priority,
            base.source_type,
            base.published_at,
            ML.DISTANCE(base.embedding, query.embedding, 'COSINE') AS distance
        FROM `{table_id}` base
        CROSS JOIN query_embedding query
        {where_sql}
        ORDER BY distance ASC
        LIMIT {limit}
        """
        
        try:
            job = self.client.query(query)
            rows = list(job.result())
            
            results = []
            for row in rows:
                # Convert distance to relevance score (cosine distance to similarity)
                distance = float(row.distance) if row.distance else 1.0
                relevance = 1.0 - distance  # Cosine similarity
                
                results.append({
                    "id": row.article_id,
                    "title": row.title,
                    "document": row.chunk_text or "",  # Actual content for agent responses
                    "metadata": {
                        "title": row.title,  # Also in metadata for backwards compatibility
                        "category": row.category,
                        "priority": row.priority,
                        "source_type": row.source_type,
                        "published_at": row.published_at.isoformat() if row.published_at else None,
                    },
                    "distance": distance,
                    "relevance_score": relevance,
                })
            
            return results
            
        except Exception as e:
            logger.error(f"BigQuery VECTOR_SEARCH error: {e}")
            # Fallback to brute force if vector index not available
            return await self._brute_force_search(query_embedding, limit, where, hours)
    
    async def _brute_force_search(
        self,
        query_embedding: List[float],
        limit: int,
        where: Optional[Dict[str, Any]] = None,
        hours: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fallback brute-force search without vector index."""
        table_id = f"{self.config.full_dataset_id}.{self.EMBEDDINGS_TABLE}"
        
        # Build WHERE clause
        where_clauses = []
        if where:
            if "category" in where:
                where_clauses.append(f"category = '{where['category']}'")
            if "priority" in where:
                where_clauses.append(f"priority = '{where['priority']}'")
        
        if hours:
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            where_clauses.append(f"published_at >= TIMESTAMP('{cutoff}')")
        
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        
        # Fetch all embeddings (limited for performance)
        query = f"""
        SELECT article_id, title, chunk_text, category, priority, source_type, published_at, embedding
        FROM `{table_id}`
        {where_sql}
        ORDER BY published_at DESC
        LIMIT 1000
        """
        
        try:
            job = self.client.query(query)
            rows = list(job.result())
            
            if not rows:
                return []
            
            # Calculate cosine similarity in Python
            import numpy as np
            
            query_vec = np.array(query_embedding)
            query_norm = np.linalg.norm(query_vec)
            
            scored_results = []
            skipped_dimension_mismatch = 0
            
            for row in rows:
                if row.embedding:
                    doc_vec = np.array(row.embedding)
                    
                    # Skip embeddings with mismatched dimensions
                    if len(doc_vec) != len(query_vec):
                        skipped_dimension_mismatch += 1
                        continue
                    
                    doc_norm = np.linalg.norm(doc_vec)
                    if doc_norm > 0 and query_norm > 0:
                        similarity = np.dot(query_vec, doc_vec) / (query_norm * doc_norm)
                        distance = 1.0 - similarity
                        scored_results.append((row, distance, similarity))
            
            if skipped_dimension_mismatch > 0:
                logger.warning(
                    f"Skipped {skipped_dimension_mismatch} embeddings due to dimension mismatch "
                    f"(query: {len(query_vec)}d, expected: {self._embedder.dimensions}d)"
                )
            
            # Sort by similarity (descending)
            scored_results.sort(key=lambda x: x[2], reverse=True)
            
            results = []
            for row, distance, similarity in scored_results[:limit]:
                results.append({
                    "id": row.article_id,
                    "title": row.title,
                    "document": row.chunk_text or "",  # Actual content for agent responses
                    "metadata": {
                        "title": row.title,  # Also in metadata for backwards compatibility
                        "category": row.category,
                        "priority": row.priority,
                        "source_type": row.source_type,
                        "published_at": row.published_at.isoformat() if row.published_at else None,
                    },
                    "distance": distance,
                    "relevance_score": similarity,
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Brute force search error: {e}")
            return []
    
    async def search_by_category(
        self,
        query: str,
        category: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search within a specific category."""
        return await self.search(query, limit, where={"category": category})
    
    async def search_by_priority(
        self,
        query: str,
        priority: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search for items with a specific priority."""
        return await self.search(query, limit, where={"priority": priority})
    
    async def search_recent(
        self,
        query: str,
        hours: int = 72,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search recent items."""
        return await self.search(query, limit, hours=hours)
    
    async def get_count(self) -> int:
        """Get number of embeddings in the store."""
        if not self._available:
            return 0
        
        try:
            table_id = f"{self.config.full_dataset_id}.{self.EMBEDDINGS_TABLE}"
            query = f"SELECT COUNT(*) as count FROM `{table_id}`"
            job = self.client.query(query)
            rows = list(job.result())
            return rows[0].count if rows else 0
        except Exception:
            return 0
    
    async def delete_item(self, article_id: str) -> bool:
        """Delete an item from the vector store."""
        if not self._available:
            return False
        
        try:
            table_id = f"{self.config.full_dataset_id}.{self.EMBEDDINGS_TABLE}"
            query = f"DELETE FROM `{table_id}` WHERE article_id = '{article_id}'"
            job = self.client.query(query)
            job.result()
            return True
        except Exception as e:
            logger.error(f"Error deleting from vector store: {e}")
            return False
    
    async def clear(self):
        """Clear all embeddings (use with caution!)."""
        if not self._available:
            return
        
        try:
            table_id = f"{self.config.full_dataset_id}.{self.EMBEDDINGS_TABLE}"
            query = f"DELETE FROM `{table_id}` WHERE TRUE"
            job = self.client.query(query)
            job.result()
            logger.info("Vector store cleared")
        except Exception as e:
            logger.error(f"Error clearing vector store: {e}")
    
    def _build_document_text(self, item) -> str:
        """Build text document for embedding."""
        parts = []
        
        if hasattr(item, 'title') and item.title:
            parts.append(item.title)
        
        if hasattr(item, 'summary') and item.summary:
            parts.append(item.summary)
        
        if hasattr(item, 'companies_mentioned') and item.companies_mentioned:
            parts.append(f"Companies: {', '.join(item.companies_mentioned[:10])}")
        
        if hasattr(item, 'materials_mentioned') and item.materials_mentioned:
            parts.append(f"Materials: {', '.join(item.materials_mentioned[:10])}")
        
        if hasattr(item, 'industries') and item.industries:
            industries = [i.value if hasattr(i, 'value') else str(i) for i in item.industries[:5]]
            parts.append(f"Industries: {', '.join(industries)}")
        
        if hasattr(item, 'full_text') and item.full_text:
            parts.append(item.full_text[:2000])
        
        return "\n".join(parts)


# Singleton instance
_bq_vector_store: Optional[BigQueryVectorStore] = None


def get_bq_vector_store() -> BigQueryVectorStore:
    """Get the BigQuery vector store singleton."""
    global _bq_vector_store
    if _bq_vector_store is None:
        _bq_vector_store = BigQueryVectorStore()
    return _bq_vector_store


# Note: Use get_production_vector_store() from app.db.vector_store for environment-aware
# vector store selection. get_bq_vector_store() is for direct BigQuery access only.
