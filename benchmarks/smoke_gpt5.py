"""Smoke-test: verify base_generator.call_claude() now hits gpt-5-nano primary path
with a minimal prompt (no evidence harvesting). Confirms wiring end-to-end."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".coco" / "knowledge"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from article_generator import EntityArticleGenerator  # type: ignore  # noqa: E402

gen = EntityArticleGenerator()
prompt = (
    'Return valid JSON exactly matching: '
    '{"title":"Test","summary":"ok","sections":[{"heading":"Overview","content":"short test content"}],'
    '"confidence":0.5}. Respond with ONLY the JSON, nothing else.'
)
system = "You are a concise test bot. Return exactly the JSON requested."

print("Calling gen.call_claude() — watch logs for routing path...")
raw = gen.call_claude(prompt, system_prompt=system)
print("\n=== raw output ===")
print(raw[:500])
print("\n=== parsed ===")
parsed = gen.parse_response(raw)
print(parsed)
