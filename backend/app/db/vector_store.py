"""
ChromaDB Vector Store
=====================

Vector database for semantic search over corpus items.
"""

import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.models.corpus import CorpusItem
from app.utils.logger import get_logger
from app.utils.chunking import chunk_earnings_transcript, chunk_sec_filing, DocumentChunk

logger = get_logger(__name__)

# Lazy import chromadb to allow graceful degradation
chromadb = None


def _ensure_chromadb():
    """Lazy import chromadb."""
    global chromadb
    if chromadb is None:
        try:
            import chromadb as _chromadb
            chromadb = _chromadb
        except ImportError:
            logger.warning("chromadb not installed - vector search will be disabled")
            return False
    return True


class VectorStore:
    """
    ChromaDB-backed vector store for semantic search.
    
    Features:
    - Automatic embedding generation
    - Metadata filtering
    - Semantic similarity search
    - Graceful degradation if ChromaDB unavailable
    
    Usage:
        store = VectorStore()
        await store.initialize()
        
        # Add items
        await store.add_items(corpus_items)
        
        # Search
        results = await store.search("carbon fiber supply chain issues", limit=10)
    """
    
    COLLECTION_NAME = "corpus_items"
    
    def __init__(self, persist_directory: Optional[str] = None):
        self.persist_directory = persist_directory or os.getenv(
            "CHROMA_PERSIST_DIR",
            str(Path(__file__).parent.parent.parent / "data" / "chroma")
        )
        self._client = None
        self._collection = None
        self._available = False
    
    @property
    def is_available(self) -> bool:
        """Check if vector store is available."""
        return self._available
    
    async def initialize(self):
        """Initialize the ChromaDB client and collection."""
        if not _ensure_chromadb():
            logger.warning("Vector store unavailable - chromadb not installed")
            return
        
        try:
            # Ensure directory exists
            Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
            
            # Create persistent client
            self._client = chromadb.PersistentClient(path=self.persist_directory)
            
            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={
                    "description": "C1 Intelligence Hub corpus items",
                    "created_at": datetime.utcnow().isoformat(),
                },
            )
            
            self._available = True
            count = self._collection.count()
            logger.info(f"Vector store initialized with {count} items")
            
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            self._available = False
    
    async def add_item(self, item: CorpusItem) -> bool:
        """Add a single corpus item to the vector store."""
        if not self._available:
            return False
        
        try:
            # Build document text for embedding
            doc_text = self._build_document_text(item)
            
            # Build metadata
            metadata = self._build_metadata(item)
            
            # Add to collection
            self._collection.add(
                ids=[item.id],
                documents=[doc_text],
                metadatas=[metadata],
            )
            
            return True
            
        except Exception as e:
            # Might be duplicate ID
            if "already exists" in str(e).lower():
                return await self.update_item(item)
            logger.warning(f"Error adding item to vector store: {e}")
            return False
    
    async def add_items(self, items: List[CorpusItem]) -> int:
        """
        Add multiple corpus items to the vector store.
        
        Long documents (earnings transcripts, SEC filings) are automatically
        chunked to optimize semantic search quality.
        """
        if not self._available or not items:
            return 0
        
        try:
            all_ids = []
            all_documents = []
            all_metadatas = []
            
            for item in items:
                # Check if this item needs chunking
                chunks = self._maybe_chunk_item(item)
                
                if chunks:
                    # Add each chunk separately
                    for chunk in chunks:
                        all_ids.append(chunk.chunk_id)
                        all_documents.append(chunk.text)
                        all_metadatas.append(chunk.metadata)
                else:
                    # Regular item - add as-is
                    all_ids.append(item.id)
                    all_documents.append(self._build_document_text(item))
                    all_metadatas.append(self._build_metadata(item))
            
            # Upsert to handle potential duplicates
            self._collection.upsert(
                ids=all_ids,
                documents=all_documents,
                metadatas=all_metadatas,
            )
            
            logger.info(f"Added {len(all_ids)} vectors ({len(items)} items, chunked where needed)")
            return len(items)
            
        except Exception as e:
            logger.error(f"Error adding items to vector store: {e}")
            return 0
    
    def _maybe_chunk_item(self, item: CorpusItem) -> Optional[List[DocumentChunk]]:
        """
        Check if an item needs chunking and chunk it if so.
        
        Returns None if no chunking needed, otherwise returns list of chunks.
        """
        source_type = item.source.source_type if item.source else ""
        
        # Earnings transcripts - chunk by speaker turns
        if source_type in ("earnings", "earnings_transcript"):
            return self._chunk_earnings(item)
        
        # SEC filings - chunk by section
        if source_type == "sec_filing" and item.full_text and len(item.full_text) > 3000:
            return self._chunk_sec_filing(item)
        
        # For other long documents, simple text chunking
        if item.full_text and len(item.full_text) > 4000:
            return self._chunk_long_text(item)
        
        return None
    
    def _chunk_earnings(self, item: CorpusItem) -> List[DocumentChunk]:
        """Chunk an earnings transcript by speaker turns."""
        # Extract structured data from metadata/raw_data
        raw_data = item.metadata or {}
        transcript_split = raw_data.get("transcript_split", [])
        
        # Extract company info
        ticker = raw_data.get("ticker", "")
        quarter = raw_data.get("quarter", 0)
        year = raw_data.get("year", 0)
        
        # Get company name from title or source
        company_name = ""
        if item.title:
            # Title format: "Company Name Q1 2025 Earnings Call"
            parts = item.title.split(" Q")
            if parts:
                company_name = parts[0]
        
        base_metadata = self._build_metadata(item)
        
        return chunk_earnings_transcript(
            transcript_id=item.id,
            ticker=ticker,
            company_name=company_name,
            quarter=quarter,
            year=year,
            transcript_split=transcript_split,
            full_text=item.full_text or "",
            base_metadata=base_metadata,
        )
    
    def _chunk_sec_filing(self, item: CorpusItem) -> List[DocumentChunk]:
        """Chunk a SEC filing by section."""
        raw_data = item.metadata or {}
        
        ticker = raw_data.get("ticker", "")
        filing_type = raw_data.get("form_type", "SEC Filing")
        
        company_name = ""
        if item.title:
            parts = item.title.split(" - ")
            if parts:
                company_name = parts[0]
        
        # SEC filings may have sections in metadata, or we chunk the full text
        sections = raw_data.get("sections", {})
        if not sections and item.full_text:
            sections = {"full": item.full_text}
        
        base_metadata = self._build_metadata(item)
        
        return chunk_sec_filing(
            filing_id=item.id,
            ticker=ticker,
            company_name=company_name,
            filing_type=filing_type,
            sections=sections,
            base_metadata=base_metadata,
        )
    
    def _chunk_long_text(self, item: CorpusItem) -> List[DocumentChunk]:
        """Simple chunking for other long documents."""
        from app.utils.chunking import _chunk_raw_text
        
        base_metadata = self._build_metadata(item)
        context = f"{item.title}\n\n" if item.title else ""
        
        return _chunk_raw_text(
            doc_id=item.id,
            text=item.full_text or item.summary or "",
            base_metadata=base_metadata,
            context_prefix=context,
        )
    
    async def update_item(self, item: CorpusItem) -> bool:
        """Update an existing item in the vector store."""
        if not self._available:
            return False
        
        try:
            doc_text = self._build_document_text(item)
            metadata = self._build_metadata(item)
            
            self._collection.update(
                ids=[item.id],
                documents=[doc_text],
                metadatas=[metadata],
            )
            
            return True
            
        except Exception as e:
            logger.warning(f"Error updating item in vector store: {e}")
            return False
    
    async def delete_item(self, item_id: str) -> bool:
        """Delete an item from the vector store."""
        if not self._available:
            return False
        
        try:
            self._collection.delete(ids=[item_id])
            return True
        except Exception as e:
            logger.warning(f"Error deleting item from vector store: {e}")
            return False
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        neighbor_radius: int = 1,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for items semantically similar to the query.
        
        Args:
            query: The search query
            limit: Maximum number of results
            where: Metadata filters (e.g., {"category": "competitor"})
            where_document: Document text filters
            neighbor_radius: Expand results by concatenating +/- N neighbor chunks
            date_from: Start date filter (ISO format) - not implemented for ChromaDB
            date_to: End date filter (ISO format) - not implemented for ChromaDB
        
        Returns:
            List of results with id, document, metadata, and distance
        
        Note:
            date_from and date_to are accepted for API compatibility with BigQuery
            but are not implemented for ChromaDB local development.
        """
        if not self._available:
            return []
        
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=limit,
                where=where,
                where_document=where_document,
                include=["documents", "metadatas", "distances"],
            )
            
            # Format results
            formatted = []
            if results and results.get("ids"):
                for i, doc_id in enumerate(results["ids"][0]):
                    formatted.append({
                        "id": doc_id,
                        "document": results["documents"][0][i] if results.get("documents") else None,
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                        "distance": results["distances"][0][i] if results.get("distances") else None,
                        "relevance_score": 1.0 - (results["distances"][0][i] / 2.0) if results.get("distances") else 0.5,
                    })

            # Neighbor expansion: concatenate +/- neighbors for specific chunk types
            if formatted and neighbor_radius > 0:
                # Collect neighbor ids to fetch in batch
                neighbor_ids = []
                for r in formatted:
                    meta = r.get("metadata", {})
                    chunk_type = meta.get("chunk_type")
                    if chunk_type not in {"earnings_dialogue", "sec_filing"}:
                        continue
                    prev_id = meta.get("prev_chunk_id")
                    next_id = meta.get("next_chunk_id")
                    if prev_id:
                        neighbor_ids.append(prev_id)
                    if next_id:
                        neighbor_ids.append(next_id)

                # Dedup and fetch
                neighbor_ids = list({i for i in neighbor_ids if i})
                id_to_doc = {}
                id_to_meta = {}
                if neighbor_ids:
                    fetched = self._collection.get(ids=neighbor_ids, include=["documents", "metadatas"])
                    if fetched and fetched.get("ids"):
                        for i, nid in enumerate(fetched["ids"]):
                            try:
                                id_to_doc[nid] = fetched["documents"][i] if fetched.get("documents") else None
                                id_to_meta[nid] = fetched["metadatas"][i] if fetched.get("metadatas") else {}
                            except Exception:
                                continue

                # Build expanded documents
                for r in formatted:
                    meta = r.get("metadata", {})
                    chunk_type = meta.get("chunk_type")
                    if chunk_type not in {"earnings_dialogue", "sec_filing"}:
                        continue
                    main_doc = r.get("document") or ""
                    pieces = []
                    neighbor_list = []
                    prev_id = meta.get("prev_chunk_id")
                    next_id = meta.get("next_chunk_id")
                    if prev_id and prev_id in id_to_doc:
                        pieces.append(id_to_doc[prev_id])
                        neighbor_list.append(prev_id)
                    pieces.append(main_doc)
                    if next_id and next_id in id_to_doc:
                        pieces.append(id_to_doc[next_id])
                        neighbor_list.append(next_id)
                    expanded = "\n\n".join([p for p in pieces if p])
                    if expanded:
                        r["original_document"] = main_doc
                        r["document"] = expanded
                        r["neighbor_ids"] = neighbor_list
                        r["expanded_neighbors"] = True
            
            return formatted
            
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []
    
    async def search_by_category(
        self,
        query: str,
        category: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search within a specific category."""
        return await self.search(
            query=query,
            limit=limit,
            where={"category": category},
        )
    
    async def search_by_priority(
        self,
        query: str,
        priority: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search for items with a specific priority."""
        return await self.search(
            query=query,
            limit=limit,
            where={"priority": priority},
        )
    
    async def search_recent(
        self,
        query: str,
        hours: int = 72,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search recent items.
        
        Note: ChromaDB doesn't support time-based filtering natively.
        We store timestamp in metadata and filter post-query.
        """
        # Get more results to account for filtering
        results = await self.search(query=query, limit=limit * 3)
        
        if not results:
            return []
        
        # Filter by time
        cutoff = datetime.utcnow().timestamp() - (hours * 3600)
        filtered = [
            r for r in results
            if r.get("metadata", {}).get("published_timestamp", 0) >= cutoff
        ]
        
        return filtered[:limit]
    
    async def get_count(self) -> int:
        """Get the number of items in the vector store."""
        if not self._available:
            return 0
        try:
            return self._collection.count()
        except Exception:
            return 0
    
    async def clear(self):
        """Clear all items from the vector store."""
        if not self._available:
            return
        
        try:
            self._client.delete_collection(self.COLLECTION_NAME)
            self._collection = self._client.create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "C1 Intelligence Hub corpus items"},
            )
            logger.info("Vector store cleared")
        except Exception as e:
            logger.error(f"Error clearing vector store: {e}")
    
    def _build_document_text(self, item: CorpusItem) -> str:
        """Build the text document for embedding."""
        parts = [
            item.title,
            item.summary or "",
        ]
        
        # Add entity mentions
        if item.companies_mentioned:
            parts.append(f"Companies: {', '.join(item.companies_mentioned[:10])}")
        if item.materials_mentioned:
            parts.append(f"Materials: {', '.join(item.materials_mentioned[:10])}")
        
        # Add industries
        if item.industries:
            parts.append(f"Industries: {', '.join(i.value for i in item.industries[:5])}")
        
        # Add full text if available (truncated)
        if item.full_text:
            parts.append(item.full_text[:2000])
        
        return "\n".join(parts)
    
    def _build_metadata(self, item: CorpusItem) -> Dict[str, Any]:
        """Build metadata for the item."""
        metadata = {
            "title": item.title[:500] if item.title else "",
            "url": item.url or "",
            "source_name": item.source.name if item.source else "",
            "category": item.primary_category.value if item.primary_category else "general",
            "priority": item.priority.value if item.priority else "medium",
            "relevance_score": item.relevance_score or 0.5,
        }
        
        # Add timestamp for time-based filtering
        if item.published_at:
            metadata["published_timestamp"] = item.published_at.timestamp()
        if item.ingested_at:
            metadata["ingested_timestamp"] = item.ingested_at.timestamp()
        
        # Add searchable entities (limited for metadata size)
        if item.companies_mentioned:
            metadata["companies"] = ",".join(item.companies_mentioned[:5])
        if item.industries:
            metadata["industries"] = ",".join(i.value for i in item.industries[:3])
        
        return metadata


# Singleton instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """
    Get the vector store singleton.
    
    For production (GCP), use get_production_vector_store() which
    returns BigQueryVectorStore for durable storage.
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


async def get_production_vector_store():
    """
    Get the production-ready vector store.
    
    In production (GCP): Uses BigQuery article_embeddings with Vertex AI embeddings
    In development: Falls back to ChromaDB for local testing
    
    Usage:
        store = await get_production_vector_store()
        results = await store.search("query")
    """
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "production":
        # Use BigQuery vector store in production
        from app.db.bq_vector_store import get_bq_vector_store
        logger.info("Using BigQuery vector store (production)")
        store = get_bq_vector_store()
        if not store._initialized:
            await store.initialize()
        return store
    else:
        # Use ChromaDB locally for development
        logger.info("Using ChromaDB vector store (development)")
        store = get_vector_store()
        if not store._available:
            await store.initialize()
        return store
