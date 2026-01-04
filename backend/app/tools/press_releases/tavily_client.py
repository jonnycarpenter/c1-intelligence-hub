
import httpx
from typing import List, Optional
from app.config.settings import settings
from .models import SearchResult

class TavilyClient:
    BASE_URL = "https://api.tavily.com"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.tavily_api_key
        self.client = httpx.Client(timeout=30.0)
    
    def search(
        self,
        query: str,
        max_results: int = 10,
        search_depth: str = "advanced",
        include_domains: List[str] = None
    ) -> List[SearchResult]:
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
        }
        if include_domains:
            payload["include_domains"] = include_domains
        
        response = self.client.post(f"{self.BASE_URL}/search", json=payload)
        response.raise_for_status()
        
        data = response.json()
        results = []
        for item in data.get("results", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                score=item.get("score", 0.0),
                published_date=item.get("published_date")
            ))
        return results
    
    def extract(self, url: str) -> Optional[str]:
        payload = {
            "api_key": self.api_key,
            "urls": [url]
        }
        response = self.client.post(f"{self.BASE_URL}/extract", json=payload)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        if results and len(results) > 0:
            return results[0].get("raw_content", "")
        return None
    
    def close(self):
        self.client.close()
