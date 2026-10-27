"""Typed failures of a live GST registry lookup. The UI shows these as "lookup failed" - never as "active"."""
from typing import Optional

AUTH, QUOTA, UNAVAILABLE, NOT_FOUND, NOT_CONNECTED = "auth", "quota", "unavailable", "not_found", "not_connected"

_DEFAULT_MESSAGES = {
    AUTH: "The GST registry rejected our API key. Check the GST_API_KEY setting.",
    QUOTA: "The GST registry's request limit has been reached. Try again later.",
    UNAVAILABLE: "The GST registry did not respond properly. Try again in a moment.",
    NOT_FOUND: "The GST registry has no record of this GSTIN.",
}


class RegistryError(Exception):
    """kind: auth | quota | unavailable | not_found"""

    def __init__(self, kind: str, message: Optional[str] = None):
        self.kind = kind
        self.message = message or _DEFAULT_MESSAGES.get(kind, _DEFAULT_MESSAGES[UNAVAILABLE])
        super().__init__(self.message)
