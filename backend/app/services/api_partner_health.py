"""API partner health checks."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import httpx

from app.config.settings import settings

DEFAULT_PARTNERS = [
    "exa",
    "tavily",
    "sec_api",
    "fmp",
    "stocknewsapi",
    "api_ninjas",
]

_KNOWN_PARTNERS = set(DEFAULT_PARTNERS)


def _normalize_partners(partners: Optional[List[str]]) -> List[str]:
    if not partners:
        return list(DEFAULT_PARTNERS)
    normalized = []
    for partner in partners:
        if partner is None:
            continue
        normalized.append(str(partner).strip().lower())
    return normalized or list(DEFAULT_PARTNERS)


def _skipped(reason: str) -> Dict[str, object]:
    return {"ok": False, "skipped": True, "reason": reason}


def _error_result(status_code: Optional[int], latency_ms: int, error: str) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "ok": False,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "error": error,
    }
    return payload


def _success_result(status_code: int, latency_ms: int, info: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "ok": True,
        "status_code": status_code,
        "latency_ms": latency_ms,
    }
    if info:
        payload.update(info)
    return payload


def _extract_error_text(response: httpx.Response) -> str:
    try:
        text = response.text
    except Exception:
        return "unreadable_response"
    return text[:200] if text else "empty_response"


def _exa_headers() -> Dict[str, str]:
    return {
        "x-api-key": settings.exa_api_key,
        "Content-Type": "application/json",
    }


async def _ping_exa(client: httpx.AsyncClient) -> Tuple[Optional[int], Optional[Dict[str, object]], Optional[str]]:
    if not settings.exa_api_key:
        return None, None, "missing_api_key"
    payload = {
        "query": "carbon fiber",
        "numResults": 1,
        "useAutoprompt": False,
        "type": "neural",
    }
    response = await client.post("https://api.exa.ai/search", json=payload, headers=_exa_headers())
    if response.status_code >= 400:
        return response.status_code, None, _extract_error_text(response)
    data = response.json()
    return response.status_code, {"result_count": len(data.get("results", []))}, None


async def _ping_tavily(client: httpx.AsyncClient) -> Tuple[Optional[int], Optional[Dict[str, object]], Optional[str]]:
    if not settings.tavily_api_key:
        return None, None, "missing_api_key"
    payload = {
        "api_key": settings.tavily_api_key,
        "query": "carbon fiber",
        "max_results": 1,
        "search_depth": "basic",
    }
    response = await client.post("https://api.tavily.com/search", json=payload)
    if response.status_code >= 400:
        return response.status_code, None, _extract_error_text(response)
    data = response.json()
    return response.status_code, {"result_count": len(data.get("results", []))}, None


async def _ping_sec_api(client: httpx.AsyncClient) -> Tuple[Optional[int], Optional[Dict[str, object]], Optional[str]]:
    if not settings.sec_api_key:
        return None, None, "missing_api_key"
    payload = {
        "query": "formType:\"10-K\"",
        "from": "0",
        "size": "1",
        "sort": [{"filedAt": {"order": "desc"}}],
    }
    headers = {"Authorization": settings.sec_api_key}
    response = await client.post("https://api.sec-api.io", json=payload, headers=headers)
    if response.status_code >= 400:
        return response.status_code, None, _extract_error_text(response)
    data = response.json()
    return response.status_code, {"result_count": len(data.get("filings", []))}, None


async def _ping_fmp(client: httpx.AsyncClient) -> Tuple[Optional[int], Optional[Dict[str, object]], Optional[str]]:
    if not settings.fmp_api_key:
        return None, None, "missing_api_key"
    params = {"apikey": settings.fmp_api_key, "limit": 1}
    response = await client.get("https://financialmodelingprep.com/stable/news/stock", params=params)
    if response.status_code >= 400:
        return response.status_code, None, _extract_error_text(response)
    data = response.json()
    result_count = len(data) if isinstance(data, list) else 0
    return response.status_code, {"result_count": result_count}, None


async def _ping_stocknews(client: httpx.AsyncClient) -> Tuple[Optional[int], Optional[Dict[str, object]], Optional[str]]:
    if not settings.stocknews_api_key:
        return None, None, "missing_api_key"
    params = {
        "tickers": "HXL",
        "items": 1,
        "token": settings.stocknews_api_key,
    }
    response = await client.get("https://stocknewsapi.com/api/v1", params=params)
    if response.status_code >= 400:
        return response.status_code, None, _extract_error_text(response)
    data = response.json()
    result_count = len(data.get("data", [])) if isinstance(data, dict) else 0
    return response.status_code, {"result_count": result_count}, None


async def _ping_api_ninjas(client: httpx.AsyncClient) -> Tuple[Optional[int], Optional[Dict[str, object]], Optional[str]]:
    if not settings.api_ninja_key:
        return None, None, "missing_api_key"
    headers = {"X-Api-Key": settings.api_ninja_key}
    params = {"ticker": "HXL"}
    response = await client.get("https://api.api-ninjas.com/v1/earningscalendar", params=params, headers=headers)
    if response.status_code >= 400:
        return response.status_code, None, _extract_error_text(response)
    data = response.json()
    result_count = len(data) if isinstance(data, list) else 0
    return response.status_code, {"result_count": result_count}, None


async def check_api_partners(partners: Optional[List[str]] = None) -> Dict[str, object]:
    selected = _normalize_partners(partners)
    results: Dict[str, object] = {}

    async with httpx.AsyncClient(timeout=20.0) as client:
        for partner in selected:
            if partner not in _KNOWN_PARTNERS:
                results[partner] = _skipped("unknown_partner")
                continue

            start_time = time.monotonic()
            if partner == "exa":
                status_code, info, error = await _ping_exa(client)
            elif partner == "tavily":
                status_code, info, error = await _ping_tavily(client)
            elif partner == "sec_api":
                status_code, info, error = await _ping_sec_api(client)
            elif partner == "fmp":
                status_code, info, error = await _ping_fmp(client)
            elif partner == "stocknewsapi":
                status_code, info, error = await _ping_stocknews(client)
            elif partner == "api_ninjas":
                status_code, info, error = await _ping_api_ninjas(client)
            else:
                results[partner] = _skipped("unknown_partner")
                continue

            latency_ms = int((time.monotonic() - start_time) * 1000)

            if error == "missing_api_key":
                results[partner] = _skipped("missing_api_key")
                continue

            if error:
                results[partner] = _error_result(status_code, latency_ms, error)
                continue

            if status_code is None:
                results[partner] = _error_result(None, latency_ms, "no_response")
                continue

            if status_code >= 400:
                results[partner] = _error_result(status_code, latency_ms, "http_error")
                continue

            results[partner] = _success_result(status_code, latency_ms, info)

    return {
        "checked_at": datetime.utcnow().isoformat(),
        "partners": results,
    }
