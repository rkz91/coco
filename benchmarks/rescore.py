"""Re-score an existing benchmark run from its raw_*.txt files without re-calling models."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gemma_vs_gpt5nano import quality_metrics, gpt5nano_cost, SECTION_FLOORS, MLX_MODEL, QB_MODEL  # type: ignore


def main(run_dir: str) -> None:
    d = Path(run_dir)
    gem_text = (d / "raw_gemma.txt").read_text()
    gpt_text = (d / "raw_gpt5nano.txt").read_text()
    gem_resp = json.loads((d / "raw_gemma_response.json").read_text())
    gpt_resp = json.loads((d / "raw_gpt5nano_response.json").read_text())
    metrics_in = json.loads((d / "metrics.json").read_text())

    qm_gem = quality_metrics(gem_text)
    qm_gpt = quality_metrics(gpt_text)
    cost_gpt = gpt5nano_cost(gpt_resp.get("usage", {}))

    gem_elapsed = metrics_in["gemma_26b_a4b"]["elapsed_s"]
    gpt_elapsed = metrics_in["gpt5_nano"]["elapsed_s"]
    ev_stats = metrics_in["evidence"]

    metrics_out = dict(metrics_in)
    metrics_out["gemma_26b_a4b"]["quality"] = qm_gem
    metrics_out["gpt5_nano"]["quality"] = qm_gpt
    metrics_out["gpt5_nano"]["cost_usd"] = cost_gpt
    (d / "metrics.json").write_text(json.dumps(metrics_out, indent=2))

    lines: list[str] = []
    lines.append(f"# Gemma 26B-A4B vs gpt-5-nano — {metrics_in['entity']['name']} in {metrics_in['entity']['project']}")
    lines.append(f"Run: `{metrics_in['timestamp']}`")
    lines.append("")
    lines.append("## Input")
    lines.append(f"- Evidence chunks: **{ev_stats['chunks_total']}**")
    lines.append(f"- Evidence block: **{ev_stats['evidence_block_chars']:,} chars**")
    lines.append(f"- User prompt (with evidence): **{ev_stats['user_prompt_chars']:,} chars**")
    lines.append(f"- System prompt: **{ev_stats['system_prompt_chars']:,} chars**")
    lines.append("")
    lines.append("## Headline numbers")
    lines.append("| Metric | Gemma 26B-A4B (local MLX) | gpt-5-nano (QB Gateway) |")
    lines.append("|---|---|---|")
    lines.append(f"| Wall time | **{gem_elapsed:.1f}s** | **{gpt_elapsed:.1f}s** |")
    lines.append(f"| Output words | **{qm_gem['word_count']:,}** | **{qm_gpt['word_count']:,}** |")
    lines.append(f"| Output chars | {qm_gem['char_count']:,} | {qm_gpt['char_count']:,} |")
    lines.append(f"| ms/word | {1000*gem_elapsed/max(qm_gem['word_count'],1):.0f} "
                 f"| {1000*gpt_elapsed/max(qm_gpt['word_count'],1):.0f} |")
    lines.append(f"| Sections detected | {qm_gem['sections_detected']}/6 | {qm_gpt['sections_detected']}/6 |")
    lines.append(f"| Section floors met | **{sum(qm_gem['section_floor_compliance'].values())}/6** | "
                 f"**{sum(qm_gpt['section_floor_compliance'].values())}/6** |")
    lines.append(f"| Unique dates cited | {qm_gem['unique_dates']} | {qm_gpt['unique_dates']} |")
    lines.append(f"| Unique named people | {qm_gem['unique_named_people']} | {qm_gpt['unique_named_people']} |")
    lines.append(f"| Unique tech artifacts | {qm_gem['unique_tech_artifacts']} | {qm_gpt['unique_tech_artifacts']} |")
    lines.append(f"| Cost | **$0.000** (local) | **${cost_gpt['total_cost_usd']:.6f}** |")
    lines.append("")
    lines.append("## gpt-5-nano token usage")
    lines.append(f"- Prompt tokens: {cost_gpt['prompt_tokens']:,} (cached: {cost_gpt['cached_tokens']:,})")
    lines.append(f"- Completion tokens: {cost_gpt['completion_tokens']:,} "
                 f"(reasoning: {cost_gpt['reasoning_tokens']:,} / visible: {cost_gpt['visible_output_tokens']:,})")
    lines.append("- Cost breakdown:")
    for k, v in cost_gpt["breakdown"].items():
        lines.append(f"  - {k}: ${v:.6f}")
    lines.append("")
    lines.append("## Section-floor compliance")
    lines.append("| Section | Floor | Gemma words | Gemma | gpt-5-nano words | gpt-5-nano |")
    lines.append("|---|---|---|---|---|---|")
    for sec, floor in SECTION_FLOORS.items():
        gw = qm_gem["section_word_counts"].get(sec, 0)
        nw = qm_gpt["section_word_counts"].get(sec, 0)
        gp = "PASS" if qm_gem["section_floor_compliance"].get(sec) else "FAIL"
        np_ = "PASS" if qm_gpt["section_floor_compliance"].get(sec) else "FAIL"
        lines.append(f"| {sec} | {floor} | {gw} | {gp} | {nw} | {np_} |")
    lines.append("")
    lines.append("## Specificity — top named people")
    lines.append("| # | Gemma | gpt-5-nano |")
    lines.append("|---|---|---|")
    g_ppl = sorted(qm_gem["top_named_people"].items(), key=lambda x: -x[1])[:10]
    n_ppl = sorted(qm_gpt["top_named_people"].items(), key=lambda x: -x[1])[:10]
    for i in range(max(len(g_ppl), len(n_ppl))):
        g = f"{g_ppl[i][0]} (×{g_ppl[i][1]})" if i < len(g_ppl) else ""
        n = f"{n_ppl[i][0]} (×{n_ppl[i][1]})" if i < len(n_ppl) else ""
        lines.append(f"| {i+1} | {g} | {n} |")
    lines.append("")
    lines.append("## Specificity — sample dates")
    lines.append(f"- Gemma: {', '.join(qm_gem['dates_sample']) or '(none)'}")
    lines.append(f"- gpt-5-nano: {', '.join(qm_gpt['dates_sample']) or '(none)'}")
    lines.append("")
    lines.append("## Specificity — top tech artifacts")
    g_tech = list(qm_gem["top_tech_artifacts"].items())[:10]
    n_tech = list(qm_gpt["top_tech_artifacts"].items())[:10]
    lines.append("| # | Gemma | gpt-5-nano |")
    lines.append("|---|---|---|")
    for i in range(max(len(g_tech), len(n_tech))):
        g = f"`{g_tech[i][0]}` (×{g_tech[i][1]})" if i < len(g_tech) else ""
        n = f"`{n_tech[i][0]}` (×{n_tech[i][1]})" if i < len(n_tech) else ""
        lines.append(f"| {i+1} | {g} | {n} |")
    lines.append("")
    lines.append("## Files")
    lines.append("- `raw_gemma.txt` / `raw_gpt5nano.txt` — raw model outputs")
    lines.append("- `metrics.json` — full structured metrics")
    lines.append("- `raw_*_response.json` — full API responses")
    lines.append("- `system_prompt.txt`, `user_prompt.txt` — exact inputs")

    (d / "REPORT.md").write_text("\n".join(lines))
    print(f"Rewrote {d / 'REPORT.md'}")
    print(f"Gemma floors: {sum(qm_gem['section_floor_compliance'].values())}/6")
    print(f"gpt-5-nano floors: {sum(qm_gpt['section_floor_compliance'].values())}/6")


if __name__ == "__main__":
    main(sys.argv[1])
