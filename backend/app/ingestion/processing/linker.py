import logging
from typing import List, Dict, Any
from dataclasses import dataclass

from app.models.corpus import EntityMention

logger = logging.getLogger(__name__)

class EntityLinker:
    """
    Links content to tracked entities.
    """
    
    def __init__(self):
        self._entities: Dict[str, Dict] = {}  # id -> entity data
        self._name_index: Dict[str, str] = {}  # lowercase name/alias -> id
    
    async def load_entities(self, storage=None):
        """Load all tracked entities from BigQuery.
        
        Args:
            storage: BigQuery storage instance (optional, will be fetched if not provided)
        """
        try:
            # Use provided storage or fetch from BigQuery
            if storage is None:
                from app.db.gcp_storage import get_storage
                storage = await get_storage()
            
            # Load companies (which includes competitors, OEMs, suppliers, etc.)
            companies = await storage.get_companies()
            for company in companies:
                entity_id = company.get("id") or company.get("name", "").lower().replace(" ", "_")
                if not entity_id:
                    continue
                
                entity_type = company.get("type", "company").lower()
                
                self._entities[entity_id] = {
                    "id": entity_id,
                    "name": company.get("name"),
                    "type": entity_type,
                    "aliases": [],  # BigQuery companies table doesn't have aliases yet
                    "ticker": company.get("ticker"),
                }
                
                # Index by name
                name = company.get("name")
                if name:
                    self._name_index[name.lower()] = entity_id
                
                # Index by ticker
                ticker = company.get("ticker")
                if ticker:
                    self._name_index[ticker.lower()] = entity_id
            
            # Load materials
            materials = await storage.get_materials()
            for material in materials:
                entity_id = material.get("id") or material.get("name", "").lower().replace(" ", "_")
                if not entity_id:
                    continue
                
                self._entities[entity_id] = {
                    "id": entity_id,
                    "name": material.get("name"),
                    "type": "material",
                    "aliases": [],
                    "ticker": None,
                }
                
                name = material.get("name")
                if name:
                    self._name_index[name.lower()] = entity_id
            
            logger.info(f"Loaded {len(self._entities)} entities with {len(self._name_index)} name variants from BigQuery")
            
        except Exception as e:
            logger.warning(f"Error loading entities from BigQuery: {e}")
            # Continue with empty entities - linking will be skipped
    
    def find_mentions(self, text: str) -> List[EntityMention]:
        """Find all entity mentions in text"""
        if not text:
            return []
        
        mentions = []
        text_lower = text.lower()
        found_ids = set()
        
        # Sort by length (longest first)
        sorted_names = sorted(self._name_index.keys(), key=len, reverse=True)
        
        for name in sorted_names:
            if name in text_lower:
                entity_id = self._name_index[name]
                
                if entity_id in found_ids:
                    continue
                found_ids.add(entity_id)
                
                entity = self._entities.get(entity_id)
                if not entity:
                    continue
                
                # Extract context (surrounding text)
                idx = text_lower.find(name)
                start = max(0, idx - 50)
                end = min(len(text), idx + len(name) + 50)
                context = text[start:end]
                
                mentions.append(EntityMention(
                    entity_id=entity_id,
                    entity_name=entity["name"],
                    entity_type=entity["type"],
                    confidence=1.0 if len(name) > 5 else 0.8,
                    context=context,
                ))
        
        return mentions
    
    def link_article(self, article) -> List[EntityMention]:
        """Find all entity mentions in an article"""
        text = f"{article.title}\n{article.summary or ''}\n{article.full_text or ''}"
        return self.find_mentions(text)
