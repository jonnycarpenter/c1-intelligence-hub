"""
ImportYeti API Client
=====================

Client for interacting with the ImportYeti API to fetch US Customs trade data.

API Endpoints:
- GET /v1.0/database-updated - Check last update date (0 credits)
- GET /v1.0/company/search - Search companies (1 credit)
- GET /v1.0/company/{company} - Get company profile (1 credit)
- GET /v1.0/supplier/search - Search suppliers (1 credit)
- GET /v1.0/supplier/{supplier} - Get supplier profile (1 credit)
- GET /v1.0/product/{product}/suppliers - Product suppliers (1 credit)
- GET /v1.0/product/{product}/companies - Product companies (1 credit)
- GET /v1.0/bol/{number} - Single BOL (1 credit)
- GET /v1.0/company/{company}/bols - Company BOLs (1 credit)
- GET /v1.0/supplier/{supplier}/bols - Supplier BOLs (1 credit)
"""

import os
import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
import httpx

logger = logging.getLogger(__name__)

# API Configuration
BASE_URL = "https://data.importyeti.com/v1.0"
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
RETRY_DELAY = 2.0


@dataclass
class APIResponse:
    """Wrapper for API responses with metadata."""
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    credits_used: int
    credits_remaining: Optional[int]
    execution_time_ms: int
    raw_response: Optional[Dict[str, Any]]


class ImportYetiClient:
    """
    Client for ImportYeti API.
    
    Usage:
        client = ImportYetiClient(api_key="your-key")
        
        # Check database update date
        last_update = await client.get_database_updated()
        
        # Get supplier profile with all customers
        supplier = await client.get_supplier("jushi-group")
        
        # Get company profile with all suppliers
        company = await client.get_company("composites-one")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key or os.getenv("IMPORTYETI_API_KEY", "")
        self.base_url = base_url
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        
        # Track credit usage
        self.credits_used_session = 0
        self.credits_remaining: Optional[int] = None
        
    async def __aenter__(self):
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def _ensure_client(self):
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "IYApiKey": f"{self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        expected_credits: int = 1,
    ) -> APIResponse:
        """
        Make an API request with retries and error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            expected_credits: Expected credit cost for this request
            
        Returns:
            APIResponse with data or error
        """
        await self._ensure_client()
        
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    params=params,
                )
                
                execution_time_ms = int((time.time() - start_time) * 1000)
                
                # Handle response
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract credit info if available
                    credits_remaining = data.get("credits_remaining")
                    if credits_remaining is not None:
                        self.credits_remaining = credits_remaining
                    
                    self.credits_used_session += expected_credits
                    
                    return APIResponse(
                        success=True,
                        data=data.get("data", data),
                        error=None,
                        credits_used=expected_credits,
                        credits_remaining=credits_remaining,
                        execution_time_ms=execution_time_ms,
                        raw_response=data,
                    )
                
                elif response.status_code == 401:
                    logger.error(f"ImportYeti API authentication failed: {response.text}")
                    return APIResponse(
                        success=False,
                        data=None,
                        error=f"Authentication failed (401): {response.text}",
                        credits_used=0,
                        credits_remaining=self.credits_remaining,
                        execution_time_ms=execution_time_ms,
                        raw_response=None,
                    )
                
                elif response.status_code == 429:
                    # Rate limited - wait and retry
                    logger.warning(f"Rate limited, waiting {RETRY_DELAY * (attempt + 1)}s...")
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                
                elif response.status_code == 404:
                    return APIResponse(
                        success=False,
                        data=None,
                        error=f"Not found (404): {endpoint}",
                        credits_used=expected_credits,  # API may still charge
                        credits_remaining=self.credits_remaining,
                        execution_time_ms=execution_time_ms,
                        raw_response=None,
                    )
                
                else:
                    logger.error(f"ImportYeti API error {response.status_code}: {response.text}")
                    return APIResponse(
                        success=False,
                        data=None,
                        error=f"HTTP {response.status_code}: {response.text}",
                        credits_used=0,
                        credits_remaining=self.credits_remaining,
                        execution_time_ms=execution_time_ms,
                        raw_response=None,
                    )
                    
            except httpx.TimeoutException as e:
                logger.warning(f"Request timeout (attempt {attempt + 1}): {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                return APIResponse(
                    success=False,
                    data=None,
                    error=f"Timeout after {MAX_RETRIES} attempts",
                    credits_used=0,
                    credits_remaining=self.credits_remaining,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    raw_response=None,
                )
                
            except Exception as e:
                logger.error(f"Request failed: {e}")
                return APIResponse(
                    success=False,
                    data=None,
                    error=str(e),
                    credits_used=0,
                    credits_remaining=self.credits_remaining,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    raw_response=None,
                )
        
        return APIResponse(
            success=False,
            data=None,
            error="Max retries exceeded",
            credits_used=0,
            credits_remaining=self.credits_remaining,
            execution_time_ms=int((time.time() - start_time) * 1000),
            raw_response=None,
        )

    async def get_credits_remaining(self) -> Optional[int]:
        """
        Get remaining credits.
        If unknown, makes a 0-credit request to fetch status.
        """
        if self.credits_remaining is None:
            await self.get_database_updated()
        return self.credits_remaining
    
    # =========================================================================
    # API Endpoints
    # =========================================================================
    
    async def get_database_updated(self) -> APIResponse:
        """
        Get the last database update date.
        Cost: 0 credits
        
        Returns:
            APIResponse with 'last_updated' date string
        """
        return await self._request("GET", "/database-updated", expected_credits=0)
    
    async def search_companies(
        self,
        query: str,
        page: int = 1,
        per_page: int = 50,
    ) -> APIResponse:
        """
        Search for US companies (importers).
        Cost: 1 credit
        
        Args:
            query: Search term
            page: Page number
            per_page: Results per page
            
        Returns:
            APIResponse with search results
        """
        params = {"q": query, "page": page, "per_page": per_page}
        return await self._request("GET", "/company/search", params=params)
    
    async def get_company(self, company_key: str) -> APIResponse:
        """
        Get detailed company profile with suppliers_table.
        Cost: 1 credit
        
        Args:
            company_key: Company identifier (e.g., 'composites-one')
            
        Returns:
            APIResponse with company profile including:
            - Basic info (name, address, website, etc.)
            - suppliers_table: List of suppliers with shipment details
            - hs_code_charts: Product breakdown
            - country_charts: Source country breakdown
        """
        return await self._request("GET", f"/company/{company_key}")
    
    async def search_suppliers(
        self,
        query: str,
        page: int = 1,
        per_page: int = 50,
    ) -> APIResponse:
        """
        Search for international suppliers.
        Cost: 1 credit
        """
        params = {"q": query, "page": page, "per_page": per_page}
        return await self._request("GET", "/supplier/search", params=params)
    
    async def get_supplier(self, supplier_key: str) -> APIResponse:
        """
        Get detailed supplier profile with companies_table.
        Cost: 1 credit
        
        Args:
            supplier_key: Supplier identifier (e.g., 'jushi-group')
            
        Returns:
            APIResponse with supplier profile including:
            - Basic info (name, country, address, etc.)
            - companies_table: List of US customers with shipment details
            - hs_code_charts: Product breakdown
            - country_charts: Destination breakdown
        """
        return await self._request("GET", f"/supplier/{supplier_key}")
    
    async def get_product_suppliers(
        self,
        product: str,
        page: int = 1,
        per_page: int = 100,
    ) -> APIResponse:
        """
        Get suppliers for a product category.
        Cost: 1 credit
        
        Args:
            product: Product search term (e.g., 'carbon fiber')
            
        Returns:
            APIResponse with list of suppliers for this product
        """
        params = {"page": page, "per_page": per_page}
        return await self._request("GET", f"/product/{product}/suppliers", params=params)
    
    async def get_product_companies(
        self,
        product: str,
        page: int = 1,
        per_page: int = 100,
    ) -> APIResponse:
        """
        Get US companies importing a product category.
        Cost: 1 credit
        
        Args:
            product: Product search term (e.g., 'carbon fiber')
            
        Returns:
            APIResponse with list of US importers for this product
        """
        params = {"page": page, "per_page": per_page}
        return await self._request("GET", f"/product/{product}/companies", params=params)
    
    async def get_bol(self, bol_number: str) -> APIResponse:
        """
        Get a single Bill of Lading.
        Cost: 1 credit
        
        Args:
            bol_number: BOL number
            
        Returns:
            APIResponse with BOL details
        """
        return await self._request("GET", f"/bol/{bol_number}")
    
    async def get_company_bols(
        self,
        company_key: str,
        page: int = 1,
        per_page: int = 100,
    ) -> APIResponse:
        """
        Get BOL numbers for a company.
        Cost: 1 credit
        """
        params = {"page": page, "per_page": per_page}
        return await self._request("GET", f"/company/{company_key}/bols", params=params)
    
    async def get_supplier_bols(
        self,
        supplier_key: str,
        page: int = 1,
        per_page: int = 100,
    ) -> APIResponse:
        """
        Get BOL numbers for a supplier.
        Cost: 1 credit
        """
        params = {"page": page, "per_page": per_page}
        return await self._request("GET", f"/supplier/{supplier_key}/bols", params=params)


# Import asyncio for sleep in retry logic
import asyncio
