"""Typed event normalization for agent SDK responses."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class AgentEvent:
    type: Literal["token", "usage", "done", "error"]
    content: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    error: str = ""


def normalize_sdk_event(raw: dict) -> AgentEvent:
    """Convert raw SDK stream dict to typed AgentEvent."""
    event_type = raw.get("type", "token")
    return AgentEvent(
        type=event_type,
        content=raw.get("content", ""),
        input_tokens=raw.get("input_tokens", 0),
        output_tokens=raw.get("output_tokens", 0),
        model=raw.get("model", ""),
        error=raw.get("error", ""),
    )
