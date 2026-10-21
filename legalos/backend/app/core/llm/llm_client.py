import asyncio
import functools
import time
from app.config import settings
from app.core.llm.providers.gemini_provider import generate_gemini
from app.core.llm.providers.local_provider import generate_local


def generate(prompt: str, system: str = "", json_mode: bool = False, workspace: str = "") -> str:
    """
    Single entrypoint for all synchronous LLM calls in the system.
    Reads LLM_PROVIDER from settings ("gemini" | "local").
    Routes to the matching provider in core/llm/providers/.
    `workspace` is passed for logging/telemetry purposes.
    """
    provider = settings.llm_provider.lower().strip()
    
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [LLM CALL] workspace='{workspace}' provider='{provider}' json_mode={json_mode}")
    
    start_time = time.time()
    try:
        if provider == "gemini":
            response = generate_gemini(prompt, system=system, json_mode=json_mode)
        elif provider == "local":
            response = generate_local(prompt, system=system, json_mode=json_mode)
        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")
            
        elapsed = time.time() - start_time
        print(f"[LLM CALL SUCCESS] provider='{provider}' elapsed={elapsed:.2f}s")
        return response
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[LLM CALL ERROR] provider='{provider}' elapsed={elapsed:.2f}s error='{str(e)}'")
        raise e


async def generate_async(prompt: str, system: str = "", json_mode: bool = False, workspace: str = "") -> str:
    """
    Async-safe wrapper around `generate()`.
    
    Runs the synchronous LLM call in a thread-pool executor so it never blocks
    the asyncio event loop.  Use this in any `async def` route or service.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        functools.partial(generate, prompt=prompt, system=system, json_mode=json_mode, workspace=workspace)
    )
