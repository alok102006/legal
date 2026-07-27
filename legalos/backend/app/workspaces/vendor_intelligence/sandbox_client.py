import time
from typing import Optional, Dict, Any
import httpx
from app.config import settings
from app.shared.exceptions import BadRequestException

# Global in-memory cache for Sandbox.co.in JWT token
_token_cache: Optional[str] = None
_token_expiry: float = 0.0


async def get_sandbox_token() -> str:
    """
    Authenticates with Sandbox.co.in to get a JWT access token.
    Uses in-memory cache to reuse token if it is valid.
    """
    global _token_cache, _token_expiry
    
    # Reuse cached token if it exists and has more than 1 minute remaining
    if _token_cache and time.time() < _token_expiry - 60:
        return _token_cache

    api_key = settings.sandbox_co_api_key
    api_secret = settings.sandbox_co_api_secret
    base_url = settings.sandbox_co_base_url

    if not api_key or not api_secret:
        raise BadRequestException(
            "Sandbox.co.in API Key or API Secret is not configured. "
            "Please check the SANDBOX_CO_API_KEY and SANDBOX_CO_API_SECRET variables in your .env file."
        )

    url = f"{base_url.rstrip('/')}/authenticate"
    headers = {
        "x-api-key": api_key,
        "x-api-secret": api_secret,
        "x-api-version": "1.0",
        "Content-Type": "application/json"
    }

    print(f"[SANDBOX CLIENT] Requesting authentication token from {url}...")
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(url, headers=headers)
        except Exception as e:
            raise BadRequestException(f"Connection to Sandbox.co.in failed: {str(e)}")

        if response.status_code != 200:
            print(f"[SANDBOX CLIENT] Authentication failed: {response.status_code} - {response.text}")
            raise BadRequestException(
                f"Failed to authenticate with Sandbox.co.in. HTTP Status {response.status_code}."
            )

        res_data = response.json()
        data_block = res_data.get("data") or {}
        access_token = data_block.get("access_token")

        if not access_token:
            raise BadRequestException("Invalid response payload from Sandbox.co.in authentication API.")

        _token_cache = access_token
        # Token is typically valid for 24 hours, expire in 23 hours in our local cache to be safe
        _token_expiry = time.time() + 23 * 3600
        print("[SANDBOX CLIENT] Cached new Sandbox.co.in access token successfully.")
        return _token_cache


async def search_gstin_live(gstin: str) -> Dict[str, Any]:
    """
    Submits a GSTIN search to Sandbox.co.in's public compliance search API.
    Handles token expiration gracefully by resetting the cached token and retrying once.
    """
    api_key = settings.sandbox_co_api_key
    base_url = settings.sandbox_co_base_url

    if not api_key:
        raise BadRequestException("Sandbox.co.in API Key is not configured in settings.")

    token = await get_sandbox_token()
    url = f"{base_url.rstrip('/')}/gst/compliance/public/gstin/search"
    headers = {
        "x-api-key": api_key,
        "authorization": token,
        "x-api-version": "1.0",
        "Content-Type": "application/json"
    }
    payload = {
        "gstin": gstin.upper().strip()
    }

    print(f"[SANDBOX CLIENT] Initiating GSTIN search for: {gstin}...")
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
        except Exception as e:
            raise BadRequestException(f"Network error during GSTIN search query: {str(e)}")

        # Handle expired token gracefully (refresh token once and retry)
        if response.status_code == 401:
            print("[SANDBOX CLIENT] Access token expired (401). Retrying with a refreshed token...")
            global _token_cache
            _token_cache = None
            token = await get_sandbox_token()
            headers["authorization"] = token
            try:
                response = await client.post(url, headers=headers, json=payload)
            except Exception as e:
                raise BadRequestException(f"Network error during retry search query: {str(e)}")

        if response.status_code != 200:
            print(f"[SANDBOX CLIENT] Search query failed: {response.status_code} - {response.text}")
            try:
                err_json = response.json()
                msg = err_json.get("message") or err_json.get("data", {}).get("message") or "Unknown API error"
            except Exception:
                msg = response.text
            raise BadRequestException(f"Sandbox.co.in search API error: {msg}")

        res_data = response.json()
        
        # Check standard Sandbox.co.in nested data structure: code, data: { data: { taxpayer details } }
        data_outer = res_data.get("data") or {}
        if isinstance(data_outer, dict):
            taxpayer_data = data_outer.get("data") or data_outer
        else:
            taxpayer_data = data_outer

        if not taxpayer_data or not isinstance(taxpayer_data, dict):
            raise BadRequestException("Sandbox.co.in search returned an empty or invalid taxpayer data block.")

        return taxpayer_data
