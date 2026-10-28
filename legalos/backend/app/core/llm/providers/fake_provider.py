"""Deterministic fake LLM for tests and offline development of pipelines.

Never selected in production. With nothing registered it fails loudly instead of inventing data.

Ways to drive it (checked in this order, so a test can layer them):

- `script(a, b, c)`: answers consumed one per call. An item is a JSON string, a dict / list / pydantic model
  (serialised for you), an exception instance (raised, e.g. `LLMQuotaError("x")`), or a callable `(FakeCall) -> item`.
  When the script runs out the last item repeats, so `script(LLMUnavailable("down"))` fails every call.
- `route({Schema: item, "substring of the prompt": item})`: first matching key wins; a key is a pydantic class
  (matched on the schema asked for) or a string (matched against prompt + system).
- `set_handler(fn)`: the original hook, `fn(FakeCall) -> str`.

Every call is recorded in `STATE.calls` with the options it was made with (temperature, timeout, max_output_tokens,
thinking_budget, files) so tests can assert on them. `STATE.latency` adds an artificial delay per call.
"""
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence, Type

from pydantic import BaseModel

from app.core.llm.errors import LLMAuthError


@dataclass
class FakeCall:
    prompt: str
    system: str
    json_mode: bool
    schema: Optional[Type[BaseModel]] = None
    files: Optional[Sequence[tuple[bytes, str]]] = None
    temperature: Optional[float] = None
    max_output_tokens: Optional[int] = None
    thinking_budget: Optional[int] = None
    timeout: Optional[float] = None


@dataclass
class _FakeState:
    handler: Optional[Callable[[FakeCall], str]] = None
    calls: list[FakeCall] = field(default_factory=list)
    scripted: list[Any] = field(default_factory=list)
    routes: list[tuple[Any, Any]] = field(default_factory=list)
    latency: float = 0.0
    _cursor: int = 0

    @property
    def last(self) -> Optional[FakeCall]:
        return self.calls[-1] if self.calls else None


STATE = _FakeState()


def reset() -> None:
    STATE.handler = None
    STATE.calls.clear()
    STATE.scripted.clear()
    STATE.routes.clear()
    STATE.latency = 0.0
    STATE._cursor = 0


def set_handler(handler: Optional[Callable[[FakeCall], str]]) -> None:
    """Replaces everything registered so far with a single handler (None clears)."""
    reset()
    STATE.handler = handler


def script(*items: Any) -> _FakeState:
    STATE.scripted[:] = list(items)
    STATE._cursor = 0
    return STATE


def route(table: dict) -> _FakeState:
    STATE.routes[:] = list(table.items())
    return STATE


def _render(item: Any, call: FakeCall) -> str:
    if callable(item) and not isinstance(item, type):
        item = item(call)
    if isinstance(item, BaseException):
        raise item
    if isinstance(item, BaseModel):
        return item.model_dump_json()
    if isinstance(item, (dict, list)):
        return json.dumps(item, ensure_ascii=False)
    return str(item)


def _matches(key: Any, call: FakeCall) -> bool:
    if isinstance(key, type):
        return call.schema is key
    return str(key) in f"{call.system}\n{call.prompt}"


def generate_fake(
    prompt: str,
    system: str = "",
    json_mode: bool = False,
    schema: Optional[Type[BaseModel]] = None,
    files: Optional[Sequence[tuple[bytes, str]]] = None,
    *,
    temperature: Optional[float] = None,
    max_output_tokens: Optional[int] = None,
    thinking_budget: Optional[int] = None,
    timeout: Optional[float] = None,
) -> str:
    call = FakeCall(prompt, system, json_mode, schema, files, temperature, max_output_tokens, thinking_budget, timeout)
    STATE.calls.append(call)
    if STATE.latency:
        time.sleep(STATE.latency)
    if STATE.scripted:
        item = STATE.scripted[min(STATE._cursor, len(STATE.scripted) - 1)]
        STATE._cursor += 1
        return _render(item, call)
    for key, item in STATE.routes:
        if _matches(key, call):
            return _render(item, call)
    if STATE.handler is None:
        raise LLMAuthError("Fake LLM provider has no handler registered.")
    return STATE.handler(call)
