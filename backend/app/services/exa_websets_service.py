"""
Exa.ai Websets Service for Pipeline Full List Building

Provides async webset creation for comprehensive, enriched prospect lists.
Unlike instant search, websets:
- Run asynchronously (1-5 minutes)
- Provide deep enrichment (employee count, funding, contacts)
- Are persistent and can be retrieved later
- Include AI-verified results

Storage:
- Webset IDs stored in local SQLite
- Results cached for retrieval
"""

import os
import json
import sqlite3
import aiohttp
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path

from app.utils.logger import get_logger
from app.services.logo_service import logo_service, extract_domain

logger = get_logger(__name__)

# =============================================================================
# Configuration
# =============================================================================

EXA_API_KEY = os.getenv("EXA_API_KEY")
EXA_WEBSETS_BASE_URL = "https://api.exa.ai/websets"

# SQLite path for webset storage
WEBSETS_DB_PATH = Path(os.getenv("DATA_DIR", str(Path(__file__).parent.parent.parent / "data"))) / "pipeline_websets.db"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class WebsetItem:
    """A single item from a webset result."""
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    logo_url: Optional[str] = None
    
    # Enrichment data
    employee_count: Optional[str] = None
    funding_info: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    
    # Source tracking
    exa_id: Optional[str] = None
    relevance_score: Optional[float] = None


@dataclass
class WebsetStatus:
    """Status of a webset creation job."""
    webset_id: str
    status: str  # "running", "completed", "failed", "idle"
    progress: Optional[int] = None  # Percentage 0-100
    total_items: Optional[int] = None
    completed_items: Optional[int] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class WebsetResult:
    """Complete result of a webset with all items."""
    webset_id: str
    name: str
    status: str
    total_count: int
    items: List[WebsetItem] = field(default_factory=list)
    created_at: Optional[str] = None
    query_description: Optional[str] = None


# =============================================================================
# SQLite Storage for Webset Tracking
# =============================================================================

def _init_websets_db():
    """Initialize SQLite database for tracking websets."""
    WEBSETS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(WEBSETS_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS websets (
            webset_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            query_description TEXT,
            status TEXT DEFAULT 'running',
            total_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            results_json TEXT,
            error_message TEXT
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_websets_status ON websets(status)
    """)
    
    conn.commit()
    conn.close()
    logger.info(f"Websets database initialized at {WEBSETS_DB_PATH}")


def _save_webset_record(
    webset_id: str,
    name: str,
    query_description: str,
    status: str = "running"
):
    """Save a new webset record to SQLite."""
    _init_websets_db()  # Ensure DB exists
    conn = sqlite3.connect(WEBSETS_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO websets (webset_id, name, query_description, status, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (webset_id, name, query_description, status, datetime.utcnow().isoformat()))
    
    conn.commit()
    conn.close()
    logger.info(f"Saved webset record: {webset_id}")


def _update_webset_status(
    webset_id: str,
    status: str,
    total_count: int = 0,
    results_json: Optional[str] = None,
    error_message: Optional[str] = None
):
    """Update webset status and results in SQLite."""
    conn = sqlite3.connect(WEBSETS_DB_PATH)
    cursor = conn.cursor()
    
    if status == "completed":
        cursor.execute("""
            UPDATE websets 
            SET status = ?, total_count = ?, results_json = ?, completed_at = ?
            WHERE webset_id = ?
        """, (status, total_count, results_json, datetime.utcnow().isoformat(), webset_id))
    elif status == "failed":
        cursor.execute("""
            UPDATE websets 
            SET status = ?, error_message = ?, completed_at = ?
            WHERE webset_id = ?
        """, (status, error_message, datetime.utcnow().isoformat(), webset_id))
    else:
        cursor.execute("""
            UPDATE websets SET status = ? WHERE webset_id = ?
        """, (status, webset_id))
    
    conn.commit()
    conn.close()


def _get_webset_record(webset_id: str) -> Optional[Dict[str, Any]]:
    """Get a webset record from SQLite."""
    try:
        conn = sqlite3.connect(WEBSETS_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM websets WHERE webset_id = ?", (webset_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"Error fetching webset record: {e}")
        return None


def get_all_websets() -> List[Dict[str, Any]]:
    """Get all webset records from SQLite."""
    try:
        _init_websets_db()  # Ensure DB exists
        conn = sqlite3.connect(WEBSETS_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT webset_id, name, query_description, status, total_count, created_at, completed_at
            FROM websets
            ORDER BY created_at DESC
            LIMIT 50
        """)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching all websets: {e}")
        return []


# =============================================================================
# Exa Websets API Client
# =============================================================================

class ExaWebsetsService:
    """
    Service for interacting with Exa.ai Websets API.
    
    Websets are async jobs that build comprehensive, enriched company lists.
    """
    
    def __init__(self):
        self.api_key = EXA_API_KEY
        self.base_url = EXA_WEBSETS_BASE_URL
        
        if not self.api_key:
            logger.warning("EXA_API_KEY not set - Websets API will not work")
    
    async def create_company_webset(
        self,
        query: str,
        name: str,
        max_results: int = 100,
        enrichments: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Create a new webset for company discovery.
        
        Args:
            query: Natural language description of companies to find
            name: Display name for this webset
            max_results: Maximum number of results (default 100)
            enrichments: List of enrichment types to include
                Options: "employee_count", "funding", "location", "linkedin", "emails"
        
        Returns:
            webset_id if successful, None if failed
        """
        if not self.api_key:
            logger.error("Cannot create webset: EXA_API_KEY not set")
            return None
        
        # Default enrichments if not specified
        if enrichments is None:
            enrichments = ["employee_count", "location", "linkedin"]
        
        # Build the search criteria for companies
        search_criteria = {
            "description": query,
            "entity": {
                "type": "company"
            }
        }
        
        # Build enrichment specifications
        enrichment_specs = []
        for e in enrichments:
            if e == "employee_count":
                enrichment_specs.append({
                    "description": "Number of employees at the company",
                    "format": "string"
                })
            elif e == "funding":
                enrichment_specs.append({
                    "description": "Total funding raised and recent funding rounds",
                    "format": "string"
                })
            elif e == "location":
                enrichment_specs.append({
                    "description": "Company headquarters location (city, state/country)",
                    "format": "string"
                })
            elif e == "linkedin":
                enrichment_specs.append({
                    "description": "Company LinkedIn profile URL",
                    "format": "url"
                })
        
        payload = {
            "search": search_criteria,
            "count": max_results,
            "enrichments": enrichment_specs if enrichment_specs else None
        }
        
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        logger.info(f"Creating webset: {name}")
        logger.debug(f"Webset payload: {json.dumps(payload, indent=2)}")
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json"
                }
                
                async with session.post(
                    f"{self.base_url}",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200 or response.status == 201:
                        data = await response.json()
                        webset_id = data.get("id")
                        
                        if webset_id:
                            # Save to local storage
                            _save_webset_record(
                                webset_id=webset_id,
                                name=name,
                                query_description=query,
                                status="running"
                            )
                            logger.info(f"Created webset {webset_id} for: {name}")
                            return webset_id
                        else:
                            logger.error(f"No webset ID in response: {data}")
                            return None
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to create webset: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error creating webset: {e}")
            return None
    
    async def get_webset_status(self, webset_id: str) -> Optional[WebsetStatus]:
        """
        Get the current status of a webset.
        
        Args:
            webset_id: The webset ID to check
        
        Returns:
            WebsetStatus object with current state
        """
        if not self.api_key:
            logger.error("Cannot check webset: EXA_API_KEY not set")
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"x-api-key": self.api_key}
                
                async with session.get(
                    f"{self.base_url}/{webset_id}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        status = WebsetStatus(
                            webset_id=webset_id,
                            status=data.get("status", "unknown"),
                            progress=data.get("progress"),
                            total_items=data.get("count"),
                            completed_items=data.get("completedCount"),
                            created_at=data.get("createdAt"),
                            completed_at=data.get("completedAt")
                        )
                        
                        # Update local storage if completed
                        if status.status == "completed":
                            _update_webset_status(webset_id, "completed", status.total_items or 0)
                        elif status.status == "failed":
                            _update_webset_status(webset_id, "failed", error_message=data.get("error"))
                        
                        return status
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to get webset status: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error checking webset status: {e}")
            return None
    
    async def get_webset_results(
        self, 
        webset_id: str,
        include_enrichments: bool = True
    ) -> Optional[WebsetResult]:
        """
        Get the results of a completed webset.
        
        Args:
            webset_id: The webset ID to fetch results for
            include_enrichments: Whether to include enrichment data
        
        Returns:
            WebsetResult with all items and enrichments
        """
        if not self.api_key:
            logger.error("Cannot fetch webset results: EXA_API_KEY not set")
            return None
        
        # Check local cache first
        local_record = _get_webset_record(webset_id)
        if local_record and local_record.get("results_json"):
            try:
                cached_data = json.loads(local_record["results_json"])
                logger.info(f"Returning cached webset results for {webset_id}")
                return WebsetResult(
                    webset_id=webset_id,
                    name=local_record.get("name", ""),
                    status="completed",
                    total_count=len(cached_data),
                    items=[WebsetItem(**item) for item in cached_data],
                    query_description=local_record.get("query_description")
                )
            except Exception as e:
                logger.warning(f"Failed to load cached results: {e}")
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"x-api-key": self.api_key}
                
                # First get webset info
                async with session.get(
                    f"{self.base_url}/{webset_id}",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to get webset: {response.status} - {error_text}")
                        return None
                    
                    webset_data = await response.json()
                
                # Then get items
                async with session.get(
                    f"{self.base_url}/{webset_id}/items",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to get webset items: {response.status} - {error_text}")
                        return None
                    
                    items_data = await response.json()
                
                # Parse items with logo enhancement
                items = []
                for item_data in items_data.get("data", []):
                    url = item_data.get("url", "")
                    domain = extract_domain(url) if url else None
                    
                    # Get enrichment data
                    enrichments = item_data.get("enrichments", {})
                    
                    item = WebsetItem(
                        url=url,
                        title=item_data.get("title"),
                        description=item_data.get("text", "")[:500] if item_data.get("text") else None,
                        domain=domain,
                        logo_url=logo_service.get_logo_proxy_url(domain) if domain else None,
                        employee_count=enrichments.get("employee_count"),
                        funding_info=enrichments.get("funding"),
                        location=enrichments.get("location"),
                        linkedin_url=enrichments.get("linkedin"),
                        exa_id=item_data.get("id"),
                        relevance_score=item_data.get("score")
                    )
                    items.append(item)
                
                result = WebsetResult(
                    webset_id=webset_id,
                    name=webset_data.get("name", local_record.get("name", "") if local_record else ""),
                    status=webset_data.get("status", "completed"),
                    total_count=len(items),
                    items=items,
                    created_at=webset_data.get("createdAt"),
                    query_description=local_record.get("query_description") if local_record else None
                )
                
                # Cache results locally
                if result.status == "completed" and items:
                    items_json = json.dumps([
                        {
                            "url": i.url,
                            "title": i.title,
                            "description": i.description,
                            "domain": i.domain,
                            "logo_url": i.logo_url,
                            "employee_count": i.employee_count,
                            "funding_info": i.funding_info,
                            "location": i.location,
                            "linkedin_url": i.linkedin_url,
                            "exa_id": i.exa_id,
                            "relevance_score": i.relevance_score
                        }
                        for i in items
                    ])
                    _update_webset_status(webset_id, "completed", len(items), items_json)
                
                return result
                
        except Exception as e:
            logger.error(f"Error fetching webset results: {e}")
            return None
    
    async def delete_webset(self, webset_id: str) -> bool:
        """
        Delete a webset from Exa (does not delete local record).
        
        Args:
            webset_id: The webset ID to delete
        
        Returns:
            True if successful
        """
        if not self.api_key:
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"x-api-key": self.api_key}
                
                async with session.delete(
                    f"{self.base_url}/{webset_id}",
                    headers=headers
                ) as response:
                    if response.status == 200 or response.status == 204:
                        logger.info(f"Deleted webset {webset_id}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to delete webset: {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error deleting webset: {e}")
            return False


# =============================================================================
# Singleton Instance
# =============================================================================

exa_websets_service = ExaWebsetsService()
