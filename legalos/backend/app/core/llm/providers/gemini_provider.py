import os
import time
from google import genai
from google.genai import types
from app.config import settings

# Initialize Client.
# The SDK automatically uses GEMINI_API_KEY from environment if api_key is not passed,
# but we pass settings.gemini_api_key explicitly for reliability.
_client = None

def get_gemini_client():
    global _client
    if _client is None:
        api_key = settings.gemini_api_key
        if not api_key:
            # Fallback to os.environ just in case settings didn't load it
            api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in settings or environment.")
        
        # Instantiate the new google-genai Client
        _client = genai.Client(api_key=api_key)
    return _client


def generate_gemini(prompt: str, system: str = "", json_mode: bool = False) -> str:
    """
    Generate response using Google's Gemini model via the google-genai SDK.
    
    Includes retry logic with exponential backoff to handle transient network
    errors such as 'wsarecv: An existing connection was forcibly closed by the
    remote host' which are common on Windows with long-running SSL connections.
    """
    client = get_gemini_client()
    
    # We use gemini-2.5-flash as the standard fast LLM model
    model_name = "gemini-2.5-flash"
    
    config = types.GenerateContentConfig(
        system_instruction=system if system else None,
        response_mime_type="application/json" if json_mode else "text/plain",
        # Add timeout to prevent indefinite hangs on dropped connections
        timeout=120,
    )
    
    # Retry up to 3 times with exponential backoff for connection errors
    max_retries = 3
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            if not response.text:
                raise RuntimeError("Gemini returned an empty response.")
            return response.text

        except Exception as e:
            last_error = e
            error_str = str(e).lower()

            # Check if it's a transient connection/network error worth retrying
            is_transient = any(kw in error_str for kw in [
                "wsarecv", "connection was forcibly closed", "connection reset",
                "timeout", "503", "429", "500", "remote host",
                "connection aborted", "broken pipe", "econnreset",
                "stream reading error",
            ])

            if is_transient and attempt < max_retries:
                wait_s = 2 ** attempt  # 2s, 4s
                print(
                    f"[GEMINI] Transient error on attempt {attempt}/{max_retries}: {str(e)}"
                    f" — retrying in {wait_s}s..."
                )
                # Force a fresh client on next retry so stale TCP connections
                # are not reused after a forced close by the remote host.
                global _client
                _client = None
                time.sleep(wait_s)
                continue

            # Non-transient error or out of retries — log and re-raise
            print(f"[GEMINI] Error calling Gemini API (attempt {attempt}): {str(e)}")
            raise e

    # Should never reach here, but satisfy the type checker
    raise last_error
