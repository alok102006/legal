"""Deterministic fake LLM for tests and offline development of pipelines.

Never selected in production. With no handler registered it fails loudly instead of
inventing data.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence, Type

from pydantic import BaseModel

from app.core.llm.errors import LLMAuthError


@dataclass
class FakeCall:
    prompt: str
    system: str
    json_mode: bool
    schema: Optional[Type[BaseModel]] = None
    files: Optional[Sequence[tuple[bytes, str]]] = None


@dataclass
class _FakeState:
    handler: Optional[Callable[[FakeCall], str]] = None
    calls: list[FakeCall] = field(default_factory=list)


STATE = _FakeState()


def set_handler(handler: Optional[Callable[[FakeCall], str]]) -> None:
    STATE.handler = handler
    STATE.calls.clear()


def generate_fake(
    prompt: str,
    system: str = "",
    json_mode: bool = False,
    schema: Optional[Type[BaseModel]] = None,
    files: Optional[Sequence[tuple[bytes, str]]] = None,
) -> str:
    call = FakeCall(prompt, system, json_mode, schema, files)
    STATE.calls.append(call)
    if STATE.handler is None:
        raise LLMAuthError("Fake LLM provider has no handler registered.")
    return STATE.handler(call)
