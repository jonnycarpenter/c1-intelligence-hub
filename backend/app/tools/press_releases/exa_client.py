"""
Exa.ai Client for Press Releases and Web Search

Exa provides clean, reliable published dates - critical for:
- 72-hour digest feed (Pulse tab)
- 30-day executive summaries

This client mirrors the TavilyClient interface for easy drop-in replacement.
"""

import httpx
from typing import List, Optional
from datetime import datetime
from app.config.settings import settings
from .models import SearchResult

class ExaClient:
    """
    Exa.ai search client with interface compatible with TavilyClient.
    
    Key advantage: Exa returns clean `publishedDate` on all results,
    eliminating the need for date extraction heuristics.
    """
    BASE_URL = "https://api.exa.ai"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.exa_api_key
        self.client = httpx.Client(timeout=30.0)
    
    def search(
        self,
        query: str,
        max_results: int = 10,
        search_depth: str = "advanced",  # Maps to useAutoprompt for Exa
        include_domains: List[str] = None,
        num_days: int = None,  # Filter to last N days
        start_published_date: str = None,  # ISO format: "2025-01-01T00:00:00.000Z"
        end_published_date: str = None,
        category: str = None,  # Exa category: "news", "company", "research paper", etc.
    ) -> List[SearchResult]:
        """
        Search using Exa API.
        
        Args:
            query: Search query
            max_results: Number of results (default 10)
            search_depth: "basic" or "advanced" (maps to useAutoprompt)
            include_domains: List of domains to restrict search to
            num_days: Filter to results from last N days
            start_published_date: ISO datetime for date range start
            end_published_date: ISO datetime for date range end
            category: Exa category filter - "news", "company", "research paper", 
                      "financial report", etc. for improved relevance
            
        Returns:
            List of SearchResult objects with clean published_date
        """
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "numResults": max_results,
            "useAutoprompt": search_depth == "advanced",
            "type": "neural",  # Neural search for better relevance
            "contents": {
                "text": {"maxCharacters": 2000},  # Get text content
                "highlights": True,  # Get relevant highlights
            }
        }
        
        # Category filtering - improves relevance for specific content types
        if category:
            payload["category"] = category
        
        # Domain filtering
        if include_domains:
            payload["includeDomains"] = include_domains
        
        # Date filtering - Exa supports multiple approaches
        if num_days:
            # Use startPublishedDate based on days back
            from datetime import timedelta
            start_date = datetime.utcnow() - timedelta(days=num_days)
            payload["startPublishedDate"] = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
        elif start_published_date:
            payload["startPublishedDate"] = start_published_date
            if end_published_date:
                payload["endPublishedDate"] = end_published_date
        
        response = self.client.post(
            f"{self.BASE_URL}/search",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        for item in data.get("results", []):
            # Exa returns publishedDate in ISO format - clean and reliable!
            published_date = item.get("publishedDate")
            
            # Build snippet from highlights or text
            highlights = item.get("highlights", [])
            text = item.get("text", "")
            snippet = " ... ".join(highlights) if highlights else text[:500]
            
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=snippet,
                score=item.get("score", 0.0),
                published_date=published_date
            ))
        
        return results
    
    def search_news(
        self,
        query: str,
        max_results: int = 10,
        num_days: int = 7,
        include_domains: List[str] = None,
    ) -> List[SearchResult]:
        """
        Search for news articles with date filtering.
        
        Optimized for recent news with reliable dates.
        """
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Calculate date range
        from datetime import timedelta
        start_date = datetime.utcnow() - timedelta(days=num_days)
        
        payload = {
            "query": query,
            "numResults": max_results,
            "useAutoprompt": True,
            "type": "neural",
            "category": "news",  # Exa news category for better news results
            "startPublishedDate": start_date.strftime("%Y-%m-%dT00:00:00.000Z"),
            "contents": {
                "text": {"maxCharacters": 2000},
                "highlights": True,
            }
        }
        
        if include_domains:
            payload["includeDomains"] = include_domains
        
        response = self.client.post(
            f"{self.BASE_URL}/search",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        for item in data.get("results", []):
            published_date = item.get("publishedDate")
            highlights = item.get("highlights", [])
            text = item.get("text", "")
            snippet = " ... ".join(highlights) if highlights else text[:500]
            
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=snippet,
                score=item.get("score", 0.0),
                published_date=published_date
            ))
        
        return results
    
    def extract(self, url: str) -> Optional[str]:
        """
        Extract content from a URL using Exa's contents API.
        
        Args:
            url: URL to extract content from
            
        Returns:
            Extracted text content or None
        """
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "ids": [url],  # Exa uses URL as ID for contents endpoint
            "text": True,
        }
        
        try:
            response = self.client.post(
                f"{self.BASE_URL}/contents",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])
            
            if results and len(results) > 0:
                return results[0].get("text", "")
            return None
            
        except Exception:
            # Fallback: try find_similar with the URL to get content
            try:
                response = self.client.post(
                    f"{self.BASE_URL}/find-similar",
                    headers=headers,
                    json={
                        "url": url,
                        "numResults": 1,
                        "contents": {"text": True}
                    }
                )
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
                if results:
                    return results[0].get("text", "")
            except Exception:
                pass
            return None
    
    def get_contents(self, urls: List[str]) -> List[dict]:
        """
        Get contents for multiple URLs.
        
        Args:
            urls: List of URLs to get content for
            
        Returns:
            List of dicts with url, title, text, publishedDate
        """
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "urls": urls,
            "text": True,
        }
        
        response = self.client.post(
            f"{self.BASE_URL}/contents",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get("results", [])
    
    def find_similar(
        self,
        url: str,
        max_results: int = 10,
        include_domains: List[str] = None,
    ) -> List[SearchResult]:
        """
        Find similar content to a given URL.
        
        Useful for finding related articles or competitor content.
        """
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "url": url,
            "numResults": max_results,
            "contents": {
                "text": {"maxCharacters": 2000},
                "highlights": True,
            }
        }
        
        if include_domains:
            payload["includeDomains"] = include_domains
        
        response = self.client.post(
            f"{self.BASE_URL}/find-similar",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        for item in data.get("results", []):
            published_date = item.get("publishedDate")
            highlights = item.get("highlights", [])
            text = item.get("text", "")
            snippet = " ... ".join(highlights) if highlights else text[:500]
            
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=snippet,
                score=item.get("score", 0.0),
                published_date=published_date
            ))
        
        return results
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
