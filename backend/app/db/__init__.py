"""Database layer for C1 Intelligence Hub.

Storage Architecture:
- BigQuery: All structured data (articles, digest_items, embeddings, etc.)
- No SQLite or ChromaDB - BigQuery is the only storage backend
"""

from app.db.database import Database, get_db
from app.db.vector_store import get_vector_store, get_production_vector_store
from app.db.bq_vector_store import BigQueryVectorStore, get_bq_vector_store

__all__ = [
    "Database", 
    "get_db", 
    "get_vector_store",
    "get_production_vector_store",
    "BigQueryVectorStore",
    "get_bq_vector_store",
]
