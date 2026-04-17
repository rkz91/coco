"""
Benchmark: Gemma 4 26B-A4B (warm MLX server) vs gpt-5-nano-2025-08-07 (QB Gateway)
on the improved article-generation prompt, fixed entity = OneTrust in project 3pi-v2.

Produces: benchmarks/runs/gemma-vs-gpt5nano-<TS>/{article_gemma.md, article_gpt5nano.md,
metrics.json, raw_gemma.txt, raw_gpt5nano.txt}
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Allow imports from ~/.coco/knowledge
KNOW = Path.home() / ".coco" / "knowledge"
sys.path.insert(0, str(KNOW))

import httpx  # noqa: E402

import article_generator as ag  # type: ignore  # noqa: E402
from entity_resolver import compute_gid  # type: ignore  # noqa: E402
from engine import KnowledgeEngine, _categorize_evidence  # type: ignore  # noqa: E402


ENTITY_NAME = "OneTrust"
ENTITY_TYPE = "system"
PROJECT_SLUG = "3pi-v2"

MLX_URL = "http://127.0.0.1:8088/v1/chat/completions"
MLX_MODEL = "mlx-community/gemma-4-26b-a4b-it-4bit"

QB_PROJECT = "39867e95-6e22-4c1b-b20d-aba44c739c72"
QB_URL = f"https://openai.prod.ai-gateway.quantumblack.com/{QB_PROJECT}/v1/chat/completions"
QB_MODEL = "gpt-5-nano-2025-08-07"
QB_KEY = (Path.home() / ".coco" / ".qb-gateway-key").read_text().strip()

# Pricing (per user message): gpt-5-nano
PRICE_IN = 0.05 / 1_000_000
PRICE_OUT = 0.40 / 1_000_000
PRICE_CACHED_IN = 0.005 / 1_000_000


def build_input() -> tuple[str, str, dict]:
    """Harvest evidence and build (system_prompt, user_prompt, evidence_stats)."""
    engine = KnowledgeEngine()
    evidence = engine.harvest_evidence(PROJECT_SLUG, ENTITY_NAME)
    categorized = _categorize_evidence(evidence)
    engine.enrich_with_graph_neighbors(categorized, ENTITY_TYPE, ENTITY_NAME)

    entity = {
        "name": ENTITY_NAME,
        "type": ENTITY_TYPE,
        "gid": compute_gid(ENTITY_TYPE, ENTITY_NAME),
        "canonical_name": ENTITY_NAME,
    }

    gen = ag.EntityArticleGenerator()
    evidence_block = gen.build_evidence_block(entity, categorized)
    user_prompt = ag._build_user_prompt(entity, evidence_block, PROJECT_SLUG)
    system_prompt = ag._get_system_prompt(entity)

    stats = {
        "chunks_total": len(evidence.get("chunks", [])),
        "categories": {k: len(v) if isinstance(v, list) else None
                       for k, v in categorized.items()},
        "evidence_block_chars": len(evidence_block),
        "user_prompt_chars": len(user_prompt),
        "system_prompt_chars": len(system_prompt),
    }
    return system_prompt, user_prompt, stats


def call_mlx(system_prompt: str, user_prompt: str) -> dict:
    payload = {
        "model": MLX_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 5000,
    }
    t0 = time.time()
    with httpx.Client(timeout=httpx.Timeout(600.0, connect=10.0)) as client:
        r = client.post(MLX_URL, json=payload)
        r.raise_for_status()
        data = r.json()
    elapsed = time.time() - t0
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {}) or {}
    return {
        "content": content,
        "elapsed_s": elapsed,
        "usage": usage,
        "raw": data,
    }


def call_gpt5nano(system_prompt: str, user_prompt: str) -> dict:
    payload = {
        "model": QB_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        # Must accommodate reasoning tokens + output for a 1800+ word article
        "max_completion_tokens": 16000,
    }
    headers = {
        "Authorization": f"Bearer {QB_KEY}",
        "Content-Type": "application/json",
    }
    t0 = time.time()
    with httpx.Client(timeout=httpx.Timeout(600.0, connect=10.0)) as client:
        r = client.post(QB_URL, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    elapsed = time.time() - t0
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {}) or {}
    return {
        "content": content,
        "elapsed_s": elapsed,
        "usage": usage,
        "raw": data,
    }


# ---------- Quality metrics ----------

DATE_PATTERNS = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),                         # 2024-11-03
    re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b", re.I),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
]
NAMED_ENTITY_PAT = re.compile(r"\b[A-Z][a-zA-Z]+\s+[A-Z][a-zA-Z]+\b")  # "Firstname Lastname" proxy
TECH_ARTIFACT_PAT = re.compile(
    r"\b("
    r"[a-z_]+_id|"
    r"customField\d+|"
    r"[A-Z]{2,}[A-Z0-9_]*|"                      # all-caps acronyms + flags
    r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"  # UUIDs
    r")\b"
)

SECTION_FLOORS_HUMAN = {
    "Overview": 250,
    "History & Context": 300,
    "Work & Involvement": 300,
    "Key Relationships": 300,
    "Current Status": 200,
    "Open Questions": 150,
}
SECTION_FLOORS_SYSTEM = {
    "Overview": 250,
    "History & Context": 300,
    "Technical Details": 350,
    "Key Relationships": 300,
    "Current Status": 200,
    "Open Questions": 150,
}
# Default used by _section_bodies + quality_metrics — switched per entity type
# via get_section_floors(). OneTrust is a system.
SECTION_FLOORS = SECTION_FLOORS_SYSTEM


def get_section_floors(entity_type: str) -> dict:
    if entity_type in {"person", "role", "team", "org_unit"}:
        return SECTION_FLOORS_HUMAN
    return SECTION_FLOORS_SYSTEM


def _extract_json(text: str) -> dict | None:
    """Strip ```json fences and parse."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        # Try to find the outermost {...}
        first = t.find("{")
        last = t.rfind("}")
        if first >= 0 and last > first:
            try:
                return json.loads(t[first:last + 1])
            except json.JSONDecodeError:
                return None
        return None


def _section_bodies(text: str) -> dict[str, str]:
    """Return {section_name: body_text}. Parse JSON article format first; fall back to markdown."""
    out: dict[str, str] = {}
    parsed = _extract_json(text)
    if parsed and isinstance(parsed.get("sections"), list):
        for sec in parsed["sections"]:
            if not isinstance(sec, dict):
                continue
            heading = (sec.get("heading") or sec.get("title") or "").strip()
            # Strip leading "1. " numeric prefixes
            heading = re.sub(r"^\d+\.\s*", "", heading)
            body = sec.get("content") or sec.get("body") or ""
            if isinstance(body, list):
                body = "\n\n".join(str(b) for b in body)
            # Match to canonical section names (case-insensitive, substring tolerant)
            for canonical in SECTION_FLOORS:
                if canonical.lower() in heading.lower() or heading.lower() in canonical.lower():
                    out[canonical] = str(body).strip()
                    break
        return out

    # Markdown fallback
    pattern = re.compile(
        r"^#{1,3}\s+(?:\d+\.\s+)?(" + "|".join(re.escape(k) for k in SECTION_FLOORS) + r")\s*$",
        re.M,
    )
    matches = list(pattern.finditer(text))
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[name] = text[start:end].strip()
    return out


def quality_metrics(text: str) -> dict:
    words = re.findall(r"\b[\w'-]+\b", text)
    word_count = len(words)
    dates = set()
    for pat in DATE_PATTERNS:
        dates.update(pat.findall(text))
    named = Counter(NAMED_ENTITY_PAT.findall(text))
    # Filter out very common false positives (headers etc.)
    FP = {"Open Questions", "Key Relationships", "Current Status", "Work Involvement",
          "History Context", "Of The", "The And", "United States"}
    named_filtered = {k: v for k, v in named.items() if k not in FP}
    tech = Counter(TECH_ARTIFACT_PAT.findall(text))

    sections = _section_bodies(text)
    section_word_counts: dict[str, int] = {}
    floor_compliance: dict[str, bool] = {}
    for sec, floor in SECTION_FLOORS.items():
        body = sections.get(sec, "")
        wc = len(re.findall(r"\b[\w'-]+\b", body))
        section_word_counts[sec] = wc
        floor_compliance[sec] = wc >= floor

    return {
        "word_count": word_count,
        "char_count": len(text),
        "unique_dates": len(dates),
        "dates_sample": sorted(dates)[:12],
        "unique_named_people": len(named_filtered),
        "top_named_people": named_filtered,
        "unique_tech_artifacts": len(tech),
        "top_tech_artifacts": dict(tech.most_common(20)),
        "section_word_counts": section_word_counts,
        "section_floor_compliance": floor_compliance,
        "sections_detected": len(sections),
    }


def gpt5nano_cost(usage: dict) -> dict:
    """Cost = input_tokens * in_price + cached_tokens * cached_price + completion_tokens * out_price."""
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
    uncached_in = max(0, prompt_tokens - cached)
    cost = uncached_in * PRICE_IN + cached * PRICE_CACHED_IN + completion_tokens * PRICE_OUT
    return {
        "prompt_tokens": prompt_tokens,
        "cached_tokens": cached,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning,
        "visible_output_tokens": max(0, completion_tokens - reasoning),
        "total_cost_usd": round(cost, 6),
        "breakdown": {
            "uncached_input_usd": round(uncached_in * PRICE_IN, 6),
            "cached_input_usd": round(cached * PRICE_CACHED_IN, 6),
            "output_usd": round(completion_tokens * PRICE_OUT, 6),
        },
    }


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outdir = Path("/Users/Rijul_Kalra/projects/coco-platform/benchmarks/runs") / f"gemma-vs-gpt5nano-{ts}"
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Building evidence + prompt for {ENTITY_NAME} in {PROJECT_SLUG}...", flush=True)
    system_prompt, user_prompt, ev_stats = build_input()
    print(f"       evidence_chunks={ev_stats['chunks_total']}, "
          f"evidence_block={ev_stats['evidence_block_chars']} chars, "
          f"user_prompt={ev_stats['user_prompt_chars']} chars", flush=True)

    (outdir / "system_prompt.txt").write_text(system_prompt)
    (outdir / "user_prompt.txt").write_text(user_prompt)

    print("[2/4] Calling Gemma 4 26B-A4B via warm MLX server...", flush=True)
    gem = call_mlx(system_prompt, user_prompt)
    (outdir / "raw_gemma.txt").write_text(gem["content"])
    (outdir / "raw_gemma_response.json").write_text(json.dumps(gem["raw"], indent=2))
    print(f"       Gemma done in {gem['elapsed_s']:.1f}s, "
          f"{len(gem['content'])} chars, tps={gem['usage'].get('generation_tps', 0):.1f}",
          flush=True)

    print("[3/4] Calling gpt-5-nano via QB Gateway...", flush=True)
    gpt = call_gpt5nano(system_prompt, user_prompt)
    (outdir / "raw_gpt5nano.txt").write_text(gpt["content"])
    (outdir / "raw_gpt5nano_response.json").write_text(json.dumps(gpt["raw"], indent=2))
    print(f"       gpt-5-nano done in {gpt['elapsed_s']:.1f}s, "
          f"{len(gpt['content'])} chars", flush=True)

    print("[4/4] Computing quality metrics...", flush=True)
    qm_gem = quality_metrics(gem["content"])
    qm_gpt = quality_metrics(gpt["content"])
    cost_gpt = gpt5nano_cost(gpt["usage"])

    metrics = {
        "timestamp": ts,
        "entity": {"name": ENTITY_NAME, "type": ENTITY_TYPE, "project": PROJECT_SLUG},
        "evidence": ev_stats,
        "gemma_26b_a4b": {
            "model_id": MLX_MODEL,
            "transport": "warm MLX server :8088",
            "elapsed_s": round(gem["elapsed_s"], 2),
            "usage": gem["usage"],
            "cost_usd": 0.0,
            "quality": qm_gem,
        },
        "gpt5_nano": {
            "model_id": QB_MODEL,
            "transport": "QB Gateway /v1/chat/completions",
            "elapsed_s": round(gpt["elapsed_s"], 2),
            "usage": gpt["usage"],
            "cost_usd": cost_gpt,
            "quality": qm_gpt,
        },
    }
    (outdir / "metrics.json").write_text(json.dumps(metrics, indent=2))

    # Human-readable report
    lines: list[str] = []
    lines.append(f"# Gemma 26B-A4B vs gpt-5-nano — {ENTITY_NAME} in {PROJECT_SLUG}")
    lines.append(f"Run: `{ts}`")
    lines.append("")
    lines.append("## Input")
    lines.append(f"- Evidence chunks: **{ev_stats['chunks_total']}**")
    lines.append(f"- Evidence block: **{ev_stats['evidence_block_chars']} chars**")
    lines.append(f"- User prompt (with evidence): **{ev_stats['user_prompt_chars']} chars**")
    lines.append(f"- System prompt: **{ev_stats['system_prompt_chars']} chars**")
    lines.append("")
    lines.append("## Headline numbers")
    lines.append("| Metric | Gemma 26B-A4B | gpt-5-nano |")
    lines.append("|---|---|---|")
    lines.append(f"| Wall time | **{gem['elapsed_s']:.1f}s** | **{gpt['elapsed_s']:.1f}s** |")
    lines.append(f"| Output words | **{qm_gem['word_count']}** | **{qm_gpt['word_count']}** |")
    lines.append(f"| Output chars | {qm_gem['char_count']} | {qm_gpt['char_count']} |")
    lines.append(f"| ms/word | {1000*gem['elapsed_s']/max(qm_gem['word_count'],1):.0f} "
                 f"| {1000*gpt['elapsed_s']/max(qm_gpt['word_count'],1):.0f} |")
    lines.append(f"| Section floors met (of 6) | "
                 f"{sum(qm_gem['section_floor_compliance'].values())}/6 | "
                 f"{sum(qm_gpt['section_floor_compliance'].values())}/6 |")
    lines.append(f"| Unique dates cited | {qm_gem['unique_dates']} | {qm_gpt['unique_dates']} |")
    lines.append(f"| Unique named people | {qm_gem['unique_named_people']} | {qm_gpt['unique_named_people']} |")
    lines.append(f"| Unique tech artifacts | {qm_gem['unique_tech_artifacts']} | {qm_gpt['unique_tech_artifacts']} |")
    lines.append(f"| Cost | **$0.000** (local) | **${cost_gpt['total_cost_usd']:.6f}** |")
    lines.append("")
    lines.append("## gpt-5-nano token usage")
    lines.append(f"- Prompt tokens: {cost_gpt['prompt_tokens']:,} "
                 f"(cached: {cost_gpt['cached_tokens']:,})")
    lines.append(f"- Completion tokens: {cost_gpt['completion_tokens']:,} "
                 f"(reasoning: {cost_gpt['reasoning_tokens']:,} / "
                 f"visible: {cost_gpt['visible_output_tokens']:,})")
    lines.append(f"- Cost breakdown:")
    for k, v in cost_gpt["breakdown"].items():
        lines.append(f"  - {k}: ${v:.6f}")
    lines.append("")
    lines.append("## Section-floor compliance")
    lines.append("| Section | Floor | Gemma words | Gemma? | gpt-5-nano words | gpt-5-nano? |")
    lines.append("|---|---|---|---|---|---|")
    for sec, floor in SECTION_FLOORS.items():
        gw = qm_gem["section_word_counts"].get(sec, 0)
        nw = qm_gpt["section_word_counts"].get(sec, 0)
        gp = "✅" if qm_gem["section_floor_compliance"].get(sec) else "❌"
        np_ = "✅" if qm_gpt["section_floor_compliance"].get(sec) else "❌"
        lines.append(f"| {sec} | {floor} | {gw} | {gp} | {nw} | {np_} |")
    lines.append("")
    lines.append("## Files")
    lines.append("- `raw_gemma.txt` — Gemma article body")
    lines.append("- `raw_gpt5nano.txt` — gpt-5-nano article body")
    lines.append("- `metrics.json` — full structured metrics")
    lines.append("- `raw_*_response.json` — full API responses")
    lines.append("- `system_prompt.txt`, `user_prompt.txt` — exact inputs sent to both")

    (outdir / "REPORT.md").write_text("\n".join(lines))

    print("")
    print("=" * 72)
    print(f"Run complete: {outdir}")
    print("=" * 72)
    print(f"Gemma 26B-A4B: {gem['elapsed_s']:.1f}s, {qm_gem['word_count']} words, "
          f"floors {sum(qm_gem['section_floor_compliance'].values())}/6")
    print(f"gpt-5-nano:    {gpt['elapsed_s']:.1f}s, {qm_gpt['word_count']} words, "
          f"floors {sum(qm_gpt['section_floor_compliance'].values())}/6, "
          f"cost=${cost_gpt['total_cost_usd']:.6f}")
    print("")
    print(f"See {outdir}/REPORT.md for the full side-by-side.")


if __name__ == "__main__":
    main()
