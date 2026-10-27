"""Sandbox.co.in GST public-search client. Failures are raised as typed RegistryError (auth/quota/unavailable)."""
import logging
import time
from typing import Any, Dict, Optional, Tuple

import httpx

from app.config import settings
from app.workspaces.vendor_intelligence.errors import AUTH, NOT_FOUND, QUOTA, UNAVAILABLE, RegistryError

logger = logging.getLogger("legalos.vendors")
TIMEOUT = 8.0

# In-memory cache for the Sandbox.co.in JWT
_token_cache: Optional[str] = None
_token_expiry: float = 0.0


def credentials() -> Tuple[Optional[str], Optional[str], str]:
    """(key, secret, base_url). SANDBOX_CO_* wins, GST_API_* is accepted when GST_API_PROVIDER=sandbox."""
    key = (settings.sandbox_co_api_key or settings.gst_api_key or "").strip() or None
    secret = (settings.sandbox_co_api_secret or settings.gst_api_secret or "").strip() or None
    base = (settings.gst_api_base_url or "").strip() if (settings.gst_api_provider or "").strip().lower() == "sandbox" else ""
    if not base:
        base = settings.sandbox_co_base_url
        # Sandbox issues separate test keys (key_test_...) that only work against its test host.
        if key and key.startswith("key_test") and base.rstrip("/") == "https://api.sandbox.co.in":
            base = "https://test-api.sandbox.co.in"
    return key, secret, base.rstrip("/")


def _raise_for_status(status: int, what: str) -> None:
    if status in (401, 403):
        raise RegistryError(AUTH)
    if status in (402, 429):
        raise RegistryError(QUOTA)
    if status == 404:
        raise RegistryError(NOT_FOUND)
    raise RegistryError(UNAVAILABLE, f"The GST registry returned an error ({what}, HTTP {status}). Try again in a moment.")


async def get_sandbox_token() -> str:
    """Authenticate with Sandbox.co.in and cache the JWT (valid ~24h)."""
    global _token_cache, _token_expiry
    if _token_cache and time.time() < _token_expiry - 60:
        return _token_cache

    api_key, api_secret, base_url = credentials()
    if not api_key or not api_secret:
        raise RegistryError(AUTH, "The GST registry API key or secret is not configured (GST_API_KEY / GST_API_SECRET).")

    headers = {"x-api-key": api_key, "x-api-secret": api_secret, "x-api-version": "1.0", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.post(f"{base_url}/authenticate", headers=headers)
        except httpx.HTTPError as e:
            logger.warning("sandbox authenticate network error: %s", type(e).__name__)
            raise RegistryError(UNAVAILABLE) from e
    if response.status_code != 200:
        _raise_for_status(response.status_code, "authentication")

    try:
        access_token = ((response.json() or {}).get("data") or {}).get("access_token")
    except ValueError:
        access_token = None
    if not access_token:
        raise RegistryError(UNAVAILABLE)
    _token_cache = access_token
    _token_expiry = time.time() + 23 * 3600
    return _token_cache


async def search_gstin_live(gstin: str) -> Dict[str, Any]:
    """Public GSTIN search. Refreshes an expired token once. Returns the raw taxpayer block."""
    global _token_cache
    api_key, _secret, base_url = credentials()
    if not api_key:
        raise RegistryError(AUTH, "The GST registry API key is not configured (GST_API_KEY).")

    url = f"{base_url}/gst/compliance/public/gstin/search"
    payload = {"gstin": gstin.upper().strip()}

    async def _post(token: str) -> httpx.Response:
        headers = {"x-api-key": api_key, "authorization": token, "x-api-version": "1.0", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            return await client.post(url, headers=headers, json=payload)

    try:
        response = await _post(await get_sandbox_token())
        if response.status_code == 401:     # token expired: refresh once
            _token_cache = None
            response = await _post(await get_sandbox_token())
    except httpx.HTTPError as e:
        logger.warning("sandbox search network error: %s", type(e).__name__)
        raise RegistryError(UNAVAILABLE) from e

    if response.status_code != 200:
        _raise_for_status(response.status_code, "search")

    try:
        res_data = response.json()
    except ValueError as e:
        raise RegistryError(UNAVAILABLE) from e
    outer = (res_data or {}).get("data") or {}
    taxpayer = (outer.get("data") or outer) if isinstance(outer, dict) else outer
    if not taxpayer or not isinstance(taxpayer, dict):
        raise RegistryError(UNAVAILABLE, "The GST registry returned an empty answer.")
    return taxpayer
