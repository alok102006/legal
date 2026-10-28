"""Typed LLM errors.

Pipelines must never turn these into "safe" defaults (e.g. risk score 0). They are
surfaced to the user as an explicit failed / retryable state.
"""


class LLMError(Exception):
    """Base class for every LLM failure."""

    retryable: bool = False
    # Short, user-presentable explanation (no secrets).
    user_message: str = "The AI service failed. Please try again."

    def __init__(self, message: str = "", *, user_message: str | None = None):
        super().__init__(message or self.user_message)
        if user_message:
            self.user_message = user_message


class LLMAuthError(LLMError):
    """API key missing / invalid / permission denied. Retrying will not help."""

    user_message = "The AI service is not configured correctly (invalid or missing API key)."


class LLMQuotaError(LLMError):
    """Rate limit or quota exhausted.

    `retry_after`: seconds the server asked us to wait (None when it gave no hint).
    `daily`: the daily free-tier quota is gone; waiting minutes will not help, so job runners must not retry.
    """

    retryable = True
    retry_after: float | None = None
    daily: bool = False
    user_message = "The AI service is busy or its quota is used up. Please retry in a few minutes."


class LLMUnavailable(LLMError):
    """Timeouts, 5xx, connection problems."""

    retryable = True
    retry_after: float | None = None
    user_message = "The AI service is temporarily unavailable. Please retry."


class LLMBadRequest(LLMError):
    """Request rejected (bad schema, unsupported input, blocked content)."""

    user_message = "The AI service could not process this document."


class LLMInvalidOutput(LLMError):
    """The model answered, but not in the required structure, even after a repair attempt."""

    retryable = True
    user_message = "The AI returned an unreadable answer. Please retry."
    # First characters of what the model actually said (for logs and support; never shown to end users).
    raw_excerpt: str = ''
