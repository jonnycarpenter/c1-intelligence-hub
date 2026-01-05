"""
Vector Store - BigQuery Only
============================

This module provides the vector store interface for semantic search.
All data is stored in BigQuery using Vertex AI embeddings.

NOTE: ChromaDB has been removed. BigQuery is the only vector store.
"""

from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_vector_store():
    """
    Get the vector store singleton.
    
    DEPRECATED: Use get_production_vector_store() instead.
    This function exists for backwards compatibility.
    """
    from app.db.bq_vector_store import get_bq_vector_store
    logger.warning("get_vector_store() is deprecated - use get_production_vector_store()")
    return get_bq_vector_store()


async def get_production_vector_store():
    """
    Get the production-ready vector store.
    
    ALWAYS uses BigQuery article_embeddings with Vertex AI embeddings.
    
    Usage:
        store = await get_production_vector_store()
        results = await store.search("query")
    """
    from app.db.bq_vector_store import get_bq_vector_store
    
    logger.info("Using BigQuery vector store")
    store = get_bq_vector_store()
    if not store._initialized:
        await store.initialize()
    return store


# For backwards compatibility - VectorStore is now BigQueryVectorStore
# Import it lazily to avoid circular imports
def __getattr__(name):
    if name == "VectorStore":
        from app.db.bq_vector_store import BigQueryVectorStore
        return BigQueryVectorStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
