# Bench-bench v0.2 Paid Smoke Analysis

This artifact is generated from live model transcripts. Endpoint provenance and transport errors are audited below; a failed transport audit must not be presented as a model result.

- Analysis engine/config hash: `sha256:438c1d77d284450cd4e3da2eac9fcda83c45bfb81f7a67598c62763d96602a52`
- Prompt hash: `sha256:06d96111ac9db67e92f1a26d00f84e986ea95d13fc2acf0825b97be112ef0d27`
| Model | Valid seeds | Excluded | Counted mean final 1RM (kg) | Counted seed SD (kg) | Decisions | Mean calls | Mean cost | Rejected decisions | Repair attempts | Successful repairs | Transport failures | Auto fallbacks | Violations | Raw mean final 1RM (kg) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| claude-opus-5 | 1 | 0 | 101.40 | 0.00 | 69 | 81.0 | $6.3970 | 12 | 12 | 11 | 0 | 1 | — | 101.40 |
| gpt-5.6-sol | 1 | 0 | 96.94 | 0.00 | 69 | 71.0 | $3.0344 | 2 | 2 | 1 | 0 | 1 | — | 96.94 |
| grok-4.6 | 1 | 0 | 100.35 | 0.00 | 69 | 70.0 | $1.0907 | 1 | 1 | 0 | 0 | 1 | — | 100.35 |
| muse-spark-1.2 | 1 | 0 | 99.96 | 0.00 | 69 | 70.0 | $1.0340 | 1 | 1 | 0 | 0 | 1 | — | 99.96 |

## Aggregation rule

A counted mean and seed standard deviation are reportable only when all expected seeds count (minimum counted-seed fraction 100%). Excluded seeds remain in the denominator and their raw scores remain diagnostic; no survivor mean is ranked.

## Provenance and transcript audit

- Engine/config hash audit: PASS on 4/4 transcripts.
- Endpoint metadata: present on 4/4 transcripts.
- Endpoint identities: anthropic-messages (https://api.anthropic.com/v1/messages), openai-compatible (https://api.meta.ai/v1/chat/completions), openai-compatible (https://api.openai.com/v1/chat/completions), openai-compatible (https://api.x.ai/v1/chat/completions).
- Public-field audit: PASS (no evaluator-only fields detected).
- Transport-error audit: PASS (no provider/transport failures detected).
- Transcript-structure audit: PASS (configured weeks are unique and complete).
- Invalid-episode audit: PASS (no invalid episodes detected).
- Transport exclusion: PASS (no transcripts excluded for provider transport failures).
- Hard-constraint audit: PASS (pain days ≤14 on all transcripts).

## Observed transcript behaviors

- claude-opus-5: format repair required (1 transcript)
- claude-opus-5: late final-week intensity gamble (1 transcript)
- gpt-5.6-sol: format repair required (1 transcript)
- gpt-5.6-sol: late final-week intensity gamble (1 transcript)
- grok-4.6: format repair required (1 transcript)
- grok-4.6: late final-week intensity gamble (1 transcript)
- muse-spark-1.2: format repair required (1 transcript)

## Method

The analyzer reads only public model transcripts and final results. Structurally invalid or pain-violating episodes remain in audit records, their raw final 1RM is retained, and only counted scores enter aggregates. It flags repeated high-intensity sessions, sleep protection choices, reciprocity imbalance, final-week intensity, capital stacking, and format repairs; these are triage signals for human transcript reading, not extra score components.
