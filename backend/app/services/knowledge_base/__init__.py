"""
Knowledge Base Services
=======================

Wikipedia-based foundational knowledge for agent grounding.
"""

from app.services.knowledge_base.seeder import KnowledgeBaseSeeder, get_seeder
from app.services.knowledge_base.wikipedia_client import WikipediaClient
from app.services.knowledge_base.vector_store import KnowledgeVectorStore, get_knowledge_store

__all__ = [
    "KnowledgeBaseSeeder",
    "get_seeder",
    "WikipediaClient",
    "KnowledgeVectorStore",
    "get_knowledge_store",
]
