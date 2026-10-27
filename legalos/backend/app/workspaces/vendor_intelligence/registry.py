"""GST registry lookup, with a pluggable live provider.

Providers (GST_API_PROVIDER):
- sandbox: Sandbox.co.in (existing client). Also still activated by the legacy SANDBOX_CO_MODE=live + SANDBOX_CO_API_KEY.
- generic: the common Indian GST public-search shape, GET {GST_API_BASE_URL}/{gstin} with an API key header,
           mapped defensively (lgnm, tradeNam, sts, rgdt, ctb, pradr, dty ...).
- none / empty: not connected. Offline checks only.

sample: a few clearly labelled demo records, only when DEMO_MODE=true (never invented for arbitrary GSTINs).
Anything that goes wrong comes back as source="unavailable" with a typed error_kind. We never fabricate a result
and never report "active" unless the registry said so.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import httpx

from app.config import settings
from app.shared.india import identifiers as ids
from app.workspaces.vendor_intelligence.engine import RegistryResult
from app.workspaces.vendor_intelligence.errors import AUTH, NOT_CONNECTED, NOT_FOUND, QUOTA, UNAVAILABLE, RegistryError

logger = logging.getLogger("legalos.vendors")
GENERIC_TIMEOUT = 8.0


def _gstin(state: str, pan: str) -> str:
    first14 = f"{state}{pan}1Z"
    return first14 + ids.gstin_check_char(first14)


# Demo records so the story can be shown without paid API access. Each one is labelled "sample" in the UI.
SAMPLE_RECORDS: Dict[str, dict] = {
    _gstin("24", "AAFFP7890L"): dict(
        legal_name="Patel Yarn Traders", trade_name="Patel Yarn Traders", status="Active", registration_date="2018-09-04",
        constitution="Partnership Firm", state="Gujarat", msme_category="small", label="Yarn supplier (active, MSME small)"),
    _gstin("27", "AAFFS4321K"): dict(
        legal_name="Shree Steel Traders", trade_name="Shree Steel Traders", status="Active", registration_date="2019-06-12",
        constitution="Partnership Firm", state="Maharashtra", msme_category="small", label="Genuine supplier (active, MSME small)"),
    _gstin("27", "AAACA1111A"): dict(
        legal_name="Apex Shell Logistics Pvt Ltd", trade_name="Apex Shell Logistics", status="Cancelled", registration_date="2023-01-15",
        constitution="Private Limited Company", state="Maharashtra", label="Cancelled registration (do not pay)",
        note="The GST registration was cancelled; the business appears to have stopped operating."),
    _gstin("24", "AAACK9876M"): dict(
        legal_name="Karnavati Steel Trading Pvt Ltd", trade_name="Karnavati Steel", status="Active", registration_date="2020-06-18",
        constitution="Private Limited Company", state="Gujarat", label="Active but not filing returns",
        note="Sample record: GST returns have not been filed for several months, so your input tax credit on its invoices is at risk."),
}


def sample_gstins() -> list:
    return [{"gstin": g, "name": r["legal_name"], "label": r["label"]} for g, r in SAMPLE_RECORDS.items()]


# ------------------------------------------------------------------ provider selection

def _s(v: Optional[str]) -> str:
    return (v or "").strip()


def active_provider() -> Optional[str]:
    """The configured live provider ("sandbox" | "generic"), or None when no live registry is connected."""
    p = _s(settings.gst_api_provider).lower()
    if p == "generic":
        return "generic" if _s(settings.gst_api_key) and _s(settings.gst_api_base_url) else None
    if p == "sandbox":
        return "sandbox" if (_s(settings.sandbox_co_api_key) or _s(settings.gst_api_key)) else None
    if p in ("", "none", "off", "mock") and settings.sandbox_co_mode.lower().strip() == "live" and _s(settings.sandbox_co_api_key):
        return "sandbox"      # legacy configuration
    return None


def registry_mode(result: Optional[RegistryResult] = None) -> Tuple[str, Optional[str]]:
    """(mode, provider) for the UI: live | sample | offline.

    A failed live lookup is still "live" (a registry is connected, it just did not answer); only "no registry
    configured" is "offline"."""
    if result is not None and result.source == "sample":
        return "sample", "sample"
    if result is not None and result.source == "live":
        return "live", result.provider
    if result is not None and result.error_kind in (AUTH, QUOTA, UNAVAILABLE, NOT_FOUND):
        return "live", result.provider or active_provider()
    provider = active_provider()
    return ("live", provider) if provider else ("offline", None)


def result_from_dict(d: Optional[Dict[str, Any]], source: Optional[str]) -> RegistryResult:
    """Rebuild a RegistryResult from what we stored on a saved supplier."""
    import dataclasses
    known = {f.name for f in dataclasses.fields(RegistryResult)}
    data = {k: v for k, v in (d or {}).items() if k in known and k != "source"}
    return RegistryResult(source=source or "unavailable", **data)


# ------------------------------------------------------------------ defensive field mapping

def _iso(d: Any) -> Optional[str]:
    d = _s(str(d)) if d is not None else ""
    if not d:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%d %b %Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(d[:26] if "T" in d else d, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _first(d: Dict[str, Any], *keys: str) -> Optional[Any]:
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def _text(v: Any) -> Optional[str]:
    if v is None or isinstance(v, (dict, list)):
        return None
    t = _s(str(v))
    return t or None


def normalise_status(raw: Any) -> Optional[str]:
    t = _text(raw)
    if not t:
        return None
    low = t.lower()
    if low.startswith("active"):
        return "Active"
    if low.startswith(("cancel", "cancl")):
        return "Cancelled"
    if low.startswith("suspend"):
        return "Suspended"
    if low.startswith("inactive") or low == "inactive":
        return "Inactive"
    return t


_WRAPPERS = ("data", "result", "results", "response", "payload", "taxpayerInfo", "taxpayer", "taxpayer_info", "gstinDetails")
_MARKERS = ("lgnm", "legalName", "legal_name", "tradeNam", "tradeName", "sts", "gstin_status", "gstinStatus", "registrationStatus")


def unwrap(body: Any) -> Dict[str, Any]:
    """Find the taxpayer block in {data:{...}}, {result:{taxpayerInfo:{...}}}, or a flat object. Raises typed errors."""
    if not isinstance(body, dict):
        raise RegistryError(UNAVAILABLE, "The GST registry returned an answer we could not read.")
    node: Any = body
    for _ in range(4):
        if not isinstance(node, dict):
            break
        # error envelopes: {"flag": false, "message": "..."} / {"success": false} / {"error": "..."}
        failed = node.get("flag") is False or node.get("success") is False or node.get("status") is False
        if failed or (node.get("error") and not any(k in node for k in _MARKERS)):
            msg = " ".join(str(node.get(k) or "") for k in ("message", "error", "errorMessage", "msg")).lower()
            if any(w in msg for w in ("not found", "no record", "invalid gstin", "does not exist", "no data")):
                raise RegistryError(NOT_FOUND)
            if any(w in msg for w in ("api key", "unauthor", "forbidden", "invalid key", "authentication")):
                raise RegistryError(AUTH)
            if any(w in msg for w in ("quota", "limit", "too many", "credit", "balance")):
                raise RegistryError(QUOTA)
            raise RegistryError(UNAVAILABLE)
        if any(k in node for k in _MARKERS):
            return node
        nxt = next((node[w] for w in _WRAPPERS if isinstance(node.get(w), dict)), None)
        if nxt is None:
            break
        node = nxt
    return node if isinstance(node, dict) else {}


def map_taxpayer(t: Dict[str, Any], provider: str) -> RegistryResult:
    """Taxpayer block -> RegistryResult. If neither a name nor a status is present, that is a bad answer, not a record."""
    pradr = t.get("pradr") if isinstance(t.get("pradr"), dict) else {}
    addr = pradr.get("addr") if isinstance(pradr.get("addr"), dict) else {}
    legal = _text(_first(t, "lgnm", "legalName", "legal_name", "legalNameOfBusiness"))
    status = normalise_status(_first(t, "sts", "status", "gstin_status", "gstinStatus", "registrationStatus", "gstinStatusDescription"))
    if not legal and not status:
        raise RegistryError(UNAVAILABLE, "The GST registry returned an empty record.")
    filing = _text(_first(t, "filingStatus", "filing_status", "returnFilingStatus", "returnStatus"))
    return RegistryResult(
        source="live", provider=provider,
        legal_name=legal,
        trade_name=_text(_first(t, "tradeNam", "tradeName", "trade_name")),
        status=status,
        registration_date=_iso(_first(t, "rgdt", "registrationDate", "regStartDate", "registration_date", "dateOfRegistration")),
        cancellation_date=_iso(_first(t, "cxdt", "cancellationDate", "cancellation_date")),
        constitution=_text(_first(t, "ctb", "constitutionOfBusiness", "constitution_of_business", "constitution")),
        taxpayer_type=_text(_first(t, "dty", "taxpayerType", "taxpayer_type")),
        state=_text(_first(addr, "stcd", "state")) or _text(_first(t, "state", "stateName")),
        filing_status=filing,
    )


# ------------------------------------------------------------------ providers

async def _fetch_generic(gstin: str) -> Dict[str, Any]:
    base = _s(settings.gst_api_base_url).rstrip("/")
    key = _s(settings.gst_api_key)
    header = _s(settings.gst_api_key_header) or "x-api-key"
    headers = {"Accept": "application/json", header: (f"Bearer {key}" if header.lower() == "authorization" and not key.lower().startswith("bearer ") else key)}
    if _s(settings.gst_api_secret):
        headers["x-api-secret"] = _s(settings.gst_api_secret)
    try:
        async with httpx.AsyncClient(timeout=GENERIC_TIMEOUT) as client:
            r = await client.get(f"{base}/{gstin}", headers=headers)
    except httpx.HTTPError as e:      # timeout, DNS, connection reset ...
        logger.warning("generic GST lookup network error: %s", type(e).__name__)
        raise RegistryError(UNAVAILABLE) from e
    if r.status_code in (401, 403):
        raise RegistryError(AUTH)
    if r.status_code in (402, 429):
        raise RegistryError(QUOTA)
    if r.status_code == 404:
        raise RegistryError(NOT_FOUND)
    if r.status_code != 200:
        raise RegistryError(UNAVAILABLE, f"The GST registry returned an error (HTTP {r.status_code}). Try again in a moment.")
    try:
        return unwrap(r.json())
    except ValueError as e:
        raise RegistryError(UNAVAILABLE, "The GST registry returned an answer we could not read.") from e


async def _live(provider: str, g: str) -> RegistryResult:
    if provider == "generic":
        return map_taxpayer(await _fetch_generic(g), "generic")
    from app.workspaces.vendor_intelligence.sandbox_client import search_gstin_live
    return map_taxpayer(unwrap(await search_gstin_live(g)), "sandbox")


def _fail(kind: str, message: str) -> RegistryResult:
    return RegistryResult(source="unavailable", error_kind=kind, message=message, provider=active_provider())


async def lookup(gstin: Optional[str]) -> RegistryResult:
    if not (gstin or "").strip():
        return RegistryResult(source="unavailable", error_kind="no_gstin",
                              message="Not checked: the GST registry is searched by GSTIN, and none was given.")
    if not ids.decode_gstin(gstin).valid:
        return RegistryResult(source="unavailable", error_kind="invalid_gstin", message="Not checked: the GSTIN is not valid.")
    g = ids.normalize(gstin)

    provider = active_provider()
    if provider:
        try:
            return await _live(provider, g)
        except RegistryError as e:
            logger.warning("live GST lookup (%s) failed: %s", provider, e.kind)
            return _fail(e.kind, f"Registry lookup failed: {e.message}" if e.kind != NOT_FOUND else e.message)
        except Exception as e:  # parse problems must never look like "all clear"
            logger.warning("live GST lookup (%s) crashed: %s", provider, type(e).__name__)
            return _fail(UNAVAILABLE, "Registry lookup failed: the GST registry could not be reached.")

    if settings.demo_mode and g in SAMPLE_RECORDS:
        r = SAMPLE_RECORDS[g]
        return RegistryResult(source="sample", provider="sample", legal_name=r["legal_name"], trade_name=r.get("trade_name"), status=r["status"],
                              registration_date=r["registration_date"], constitution=r.get("constitution"), state=r.get("state"),
                              note=r.get("note"), msme_category=r.get("msme_category"))

    return RegistryResult(source="unavailable", error_kind=NOT_CONNECTED,
                          message="Not checked: the live GST registry is not connected.")
