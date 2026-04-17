# Gemma 26B-A4B vs gpt-5-nano — OneTrust in 3pi-v2
Run: `20260417T024045Z`

## Input
- Evidence chunks: **171**
- Evidence block: **19,443 chars**
- User prompt (with evidence): **19,519 chars**
- System prompt: **6,112 chars**

## Headline numbers
| Metric | Gemma 26B-A4B (local MLX) | gpt-5-nano (QB Gateway) |
|---|---|---|
| Wall time | **385.0s** | **34.8s** |
| Output words | **1,559** | **2,658** |
| Output chars | 11,393 | 19,201 |
| ms/word | 247 | 13 |
| Sections detected | 6/6 | 6/6 |
| Section floors met | **1/6** | **6/6** |
| Unique dates cited | 4 | 2 |
| Unique named people | 22 | 27 |
| Unique tech artifacts | 7 | 10 |
| Cost | **$0.000** (local) | **$0.003171** |

## gpt-5-nano token usage
- Prompt tokens: 6,513 (cached: 0)
- Completion tokens: 7,114 (reasoning: 3,264 / visible: 3,850)
- Cost breakdown:
  - uncached_input_usd: $0.000326
  - cached_input_usd: $0.000000
  - output_usd: $0.002846

## Section-floor compliance
| Section | Floor | Gemma words | Gemma | gpt-5-nano words | gpt-5-nano |
|---|---|---|---|---|---|
| Overview | 250 | 252 | PASS | 422 | PASS |
| History & Context | 300 | 280 | FAIL | 428 | PASS |
| Technical Details | 350 | 317 | FAIL | 514 | PASS |
| Key Relationships | 300 | 290 | FAIL | 427 | PASS |
| Current Status | 200 | 164 | FAIL | 313 | PASS |
| Open Questions | 150 | 121 | FAIL | 266 | PASS |

## Specificity — top named people
| # | Gemma | gpt-5-nano |
|---|---|---|
| 1 | Leobardo Mora (×3) | TPI Comments (×7) |
| 2 | Pankaj Arora (×3) | Use Case (×6) |
| 3 | Party Interest (×2) | OneTrust TPRM (×4) |
| 4 | Party Risk (×2) | Rijul Kalra (×4) |
| 5 | Optimize Solutions (×2) | Deepti Zimmerman (×4) |
| 6 | Use Case (×2) | The OneTrust (×4) |
| 7 | Rijul Kalra (×2) | Graham Holton (×4) |
| 8 | Deepti Zimmerman (×2) | Tobias Dietrich (×4) |
| 9 | OneTrust System (×1) | Parth Patel (×3) |
| 10 | Reference Guide (×1) | Optimize Solutions (×3) |

## Specificity — sample dates
- Gemma: February 10, 2026, February 27, 2026, March 19, 2026, March 3, 2026
- gpt-5-nano: February 27, 2026, March 12, 2026

## Specificity — top tech artifacts
| # | Gemma | gpt-5-nano |
|---|---|---|
| 1 | `TPI` (×11) | `API` (×28) |
| 2 | `API` (×10) | `TPI` (×18) |
| 3 | `TPRM` (×3) | `BRD` (×12) |
| 4 | `customField1158` (×3) | `TPRM` (×11) |
| 5 | `BRD` (×1) | `customField1158` (×11) |
| 6 | `OHD` (×1) | `PM` (×2) |
| 7 | `VSA` (×1) | `TL` (×2) |
| 8 |  | `OHD` (×1) |
| 9 |  | `AR` (×1) |
| 10 |  | `IA` (×1) |

## Files
- `raw_gemma.txt` / `raw_gpt5nano.txt` — raw model outputs
- `metrics.json` — full structured metrics
- `raw_*_response.json` — full API responses
- `system_prompt.txt`, `user_prompt.txt` — exact inputs