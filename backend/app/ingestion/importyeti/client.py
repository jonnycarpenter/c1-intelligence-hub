"""
ImportYeti API Client
=====================
Wraps all ImportYeti endpoints used by the C1 Intelligence Hub.

Key design decisions:
- Every API call returns a standardized (data, metadata) tuple
- Automatic retry with exponential backoff on failures
- Courtesy delay between calls to avoid hammering the API
- Credit tracking so you always know your consumption
- Full response logging at DEBUG level for troubleshooting

Usage:
    client = ImportYetiClient(api_key="your-key")
    data, meta = client.search_company("basf")
    data, meta = client.get_company("basf-corporation")
    data, meta = client.get_supplier("basf")
"""

import time
import logging
import requests
from typing import Optional, Tuple, Any

from .config.settings import (
    IMPORTYETI_BASE_URL,
    API_TIMEOUT_SECONDS,
    API_RETRY_ATTEMPTS,
    API_RETRY_DELAY_SECONDS,
    API_DELAY_BETWEEN_CALLS,
)

logger = logging.getLogger("importyeti_client")


class ImportYetiClient:
    """
    Thin wrapper around the ImportYeti REST API.

    Handles authentication, retry logic, courtesy delays, and credit tracking.
    Business logic (which companies to fetch, how to parse supplier tables)
    lives in ingestion.py.
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError(
                "ImportYeti API key is required. "
                "Set IMPORTYETI_API_KEY environment variable."
            )
        self.base_url = IMPORTYETI_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "IYApiKey": api_key,
            "accept": "application/json",
        })

        # Credit tracking
        self.total_credits_used = 0
        self.credits_remaining = None
        self._last_call_time = 0

    # ─────────────────────────────────────────
    # Public API Methods
    # ─────────────────────────────────────────

    def search_company(self, name: str) -> Tuple[Optional[list], dict]:
        """
        Search for a US company by name. 0 credits.

        Returns:
            (data, meta) where data is a list of matching companies.
        """
        return self._get(
            "/company/search",
            params={"name": name},
            entity_label=f"company_search:{name}",
        )

    def get_company(self, company_slug: str) -> Tuple[Optional[dict], dict]:
        """
        Get full company profile by ImportYeti slug. 1 credit.

        The slug is the part after "company/" in the key field.
        E.g., key = "company/sherwin-williams" -> slug = "sherwin-williams".
        """
        return self._get(
            f"/company/{company_slug}",
            entity_label=f"company:{company_slug}",
        )

    def search_supplier(self, name: str) -> Tuple[Optional[list], dict]:
        """
        Search for an overseas supplier by name. 0 credits.

        Returns:
            (data, meta) where data is a list of matching suppliers.
        """
        return self._get(
            "/supplier/search",
            params={"name": name},
            entity_label=f"supplier_search:{name}",
        )

    def get_supplier(self, supplier_slug: str) -> Tuple[Optional[dict], dict]:
        """
        Get full supplier profile by ImportYeti slug. 1 credit.

        The slug is the part after "supplier/" in the key field.
        """
        return self._get(
            f"/supplier/{supplier_slug}",
            entity_label=f"supplier:{supplier_slug}",
        )

    def get_database_updated(self) -> Tuple[Optional[str], dict]:
        """Check when ImportYeti's database was last updated."""
        return self._get("/database-updated", entity_label="db_updated")

    # ─────────────────────────────────────────
    # Internal Request Handler
    # ─────────────────────────────────────────

    def _get(
        self,
        path: str,
        params: Optional[dict] = None,
        entity_label: str = "",
    ) -> Tuple[Optional[Any], dict]:
        """
        Execute a GET request with retry logic and credit tracking.

        Returns:
            (data, metadata) tuple.
        """
        url = f"{self.base_url}{path}"
        meta = {
            "credits_used": 0,
            "credits_remaining": self.credits_remaining,
            "execution_time": None,
            "status": "pending",
            "error": None,
            "url": url,
        }

        # Courtesy delay between API calls
        self._apply_rate_limit()

        for attempt in range(1, API_RETRY_ATTEMPTS + 1):
            try:
                logger.debug(
                    f"[IMPORTYETI] API call [{entity_label}] attempt {attempt}/{API_RETRY_ATTEMPTS}: "
                    f"GET {url} params={params}"
                )

                response = self.session.get(
                    url,
                    params=params,
                    timeout=API_TIMEOUT_SECONDS,
                )

                self._last_call_time = time.time()

                # Handle HTTP errors
                if response.status_code == 404:
                    logger.warning(f"[IMPORTYETI] [{entity_label}] Not found (404): {url}")
                    meta["status"] = "not_found"
                    meta["error"] = "Entity not found in ImportYeti"
                    return None, meta

                if response.status_code == 429:
                    wait_time = API_RETRY_DELAY_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"[IMPORTYETI] [{entity_label}] Rate limited (429). "
                        f"Waiting {wait_time}s before retry..."
                    )
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()

                # Parse response
                body = response.json()

                # Track credits
                credits_used = body.get("requestCost", 1)
                self.total_credits_used += credits_used
                self.credits_remaining = body.get("creditsRemaining")

                meta["credits_used"] = credits_used
                meta["credits_remaining"] = self.credits_remaining
                meta["execution_time"] = body.get("executionTime")
                meta["status"] = "success"

                data = body.get("data")

                logger.info(
                    f"[IMPORTYETI] [{entity_label}] Success | "
                    f"Credits: {credits_used} used, {self.credits_remaining} remaining | "
                    f"API time: {meta['execution_time']}"
                )

                return data, meta

            except requests.exceptions.Timeout:
                logger.warning(f"[IMPORTYETI] [{entity_label}] Timeout on attempt {attempt}")
                meta["error"] = "Request timeout"

            except requests.exceptions.ConnectionError as e:
                logger.warning(f"[IMPORTYETI] [{entity_label}] Connection error on attempt {attempt}: {e}")
                meta["error"] = f"Connection error: {e}"

            except requests.exceptions.HTTPError as e:
                logger.error(f"[IMPORTYETI] [{entity_label}] HTTP error: {e}")
                meta["error"] = f"HTTP error: {e}"
                meta["status"] = "error"
                if response.status_code < 500:
                    return None, meta

            except Exception as e:
                logger.error(f"[IMPORTYETI] [{entity_label}] Unexpected error: {e}")
                meta["error"] = str(e)
                meta["status"] = "error"
                return None, meta

            # Exponential backoff before retry
            if attempt < API_RETRY_ATTEMPTS:
                wait = API_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                logger.info(f"[IMPORTYETI] [{entity_label}] Retrying in {wait}s...")
                time.sleep(wait)

        # All retries exhausted
        meta["status"] = "error"
        logger.error(f"[IMPORTYETI] [{entity_label}] All {API_RETRY_ATTEMPTS} attempts failed")
        return None, meta

    def _apply_rate_limit(self):
        """Apply courtesy delay between API calls."""
        if self._last_call_time > 0:
            elapsed = time.time() - self._last_call_time
            if elapsed < API_DELAY_BETWEEN_CALLS:
                sleep_time = API_DELAY_BETWEEN_CALLS - elapsed
                time.sleep(sleep_time)

    def get_credit_summary(self) -> dict:
        """Return current credit usage stats."""
        return {
            "total_credits_used": self.total_credits_used,
            "credits_remaining": self.credits_remaining,
        }
