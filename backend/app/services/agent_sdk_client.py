"""Thin wrapper around the Anthropic Python SDK for chat, commands, and agent spawning."""

import os
import structlog
from anthropic import Anthropic, AsyncAnthropic
from typing import AsyncIterator

log = structlog.get_logger()

# Model mapping: our friendly names -> Anthropic model IDs
MODEL_MAP = {
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-20250514",
    "haiku": "claude-haiku-4-5-20251001",
}

# Pricing per 1M tokens (input, output) in USD
PRICING = {
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-opus-4-20250514": (15.0, 75.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
}


def _resolve_model(model: str) -> str:
    return MODEL_MAP.get(model, model)


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate approximate cost in USD."""
    resolved = _resolve_model(model) if model in MODEL_MAP else model
    input_rate, output_rate = PRICING.get(resolved, (3.0, 15.0))
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


class AgentSDKClient:
    """Stateless wrapper -- create one instance per app lifetime."""

    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            log.warning("no_anthropic_api_key", msg="ANTHROPIC_API_KEY not set, SDK client will fail")
        self._sync = Anthropic(api_key=api_key) if api_key else None
        self._async = AsyncAnthropic(api_key=api_key) if api_key else None

    def is_available(self) -> bool:
        return self._sync is not None

    def quick_command(
        self,
        prompt: str,
        model: str = "haiku",
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> dict:
        """Synchronous single-turn call.

        Returns {"content": str, "input_tokens": int, "output_tokens": int, "model": str}.
        """
        if not self._sync:
            raise RuntimeError("Anthropic API key not configured")

        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "model": _resolve_model(model),
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = self._sync.messages.create(**kwargs)

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        return {
            "content": content,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model": response.model,
        }

    async def stream_chat(
        self,
        prompt: str,
        model: str = "sonnet",
        system: str | None = None,
        max_tokens: int = 8192,
    ) -> AsyncIterator[dict]:
        """Async streaming chat. Yields {"type": "token"|"usage"|"done", ...} dicts."""
        if not self._async:
            raise RuntimeError("Anthropic API key not configured")

        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "model": _resolve_model(model),
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        async with self._async.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield {"type": "token", "content": text}

            # After stream completes, get final message for usage
            final = await stream.get_final_message()
            yield {
                "type": "usage",
                "input_tokens": final.usage.input_tokens,
                "output_tokens": final.usage.output_tokens,
                "model": final.model,
            }
            yield {
                "type": "done",
                "content": "".join(
                    b.text for b in final.content if b.type == "text"
                ),
            }

    async def spawn_agent(
        self,
        task: str,
        model: str = "sonnet",
        system: str | None = None,
        max_tokens: int = 16384,
    ) -> dict:
        """Non-streaming agent call for background tasks. Returns full result."""
        if not self._async:
            raise RuntimeError("Anthropic API key not configured")

        messages = [{"role": "user", "content": task}]
        kwargs = {
            "model": _resolve_model(model),
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = await self._async.messages.create(**kwargs)

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        return {
            "content": content,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model": response.model,
            "stop_reason": response.stop_reason,
        }


# Singleton
agent_sdk = AgentSDKClient()
