# Bench-bench v0.1 Pilot Analyzer Report (Historical)

Historical compatibility analysis of the archived v0.1 pilot transcripts. The transcripts retain their original engine/config hash; this report does not claim current-engine replay. Any provider transport failure excludes that transcript from counted aggregates while retaining its raw score.

- Analysis engine/config hash: `sha256:438c1d77d284450cd4e3da2eac9fcda83c45bfb81f7a67598c62763d96602a52`
| Model | Valid seeds | Excluded | Counted mean final 1RM (kg) | Counted seed SD (kg) | Decisions | Mean calls | Mean cost | Rejected decisions | Repair attempts | Successful repairs | Transport failures | Auto fallbacks | Violations | Raw mean final 1RM (kg) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| claude-opus-5 | 10 | 0 | 100.06 | 2.25 | 677 | 80.7 | $5.9503 | 130 | 130 | 117 | 0 | 13 | — | 100.06 |
| gpt-5.6-sol | 10 | 0 | 93.86 | 1.23 | 677 | 69.2 | $2.8056 | 15 | 15 | 12 | 0 | 3 | — | 93.86 |
| grok-4.5 | 10 | 0 | 99.19 | 2.09 | 677 | 73.4 | $0.9225 | 57 | 57 | 50 | 0 | 7 | — | 99.19 |
| kimi-k3 | 0 | 10 | — | — | 677 | — | — | 40 | 39 | 34 | 702 | 353 | — | 90.48 |
| muse-spark-1.2 | 10 | 0 | 98.62 | 1.33 | 677 | 70.7 | $1.0753 | 30 | 30 | 19 | 0 | 11 | — | 98.62 |

## Aggregation rule

A counted mean and seed standard deviation are reportable only when all expected seeds count (minimum counted-seed fraction 100%). Excluded seeds remain in the denominator and their raw scores remain diagnostic; no survivor mean is ranked.

## Provenance and transcript audit

- Historical transcript engine/config hash: `sha256:fdbd829339622163df8a27d64fe6467e353c1b2bd8ff289b25e36783e8d2e9a1`; current-engine match is intentionally not required.
- Endpoint metadata: present on 50/50 transcripts.
- Endpoint identities: anthropic-messages (https://api.anthropic.com/v1/messages), openai-compatible (https://api.meta.ai/v1/chat/completions), openai-compatible (https://api.moonshot.ai/v1/chat/completions), openai-compatible (https://api.openai.com/v1/chat/completions), openai-compatible (https://api.x.ai/v1/chat/completions).
- Public-field audit: PASS (no evaluator-only fields detected).
- Transport-error audit: FAILED (http_429 in 6/50 transcripts (694 attempts), http_520 in 1/50 transcripts (1 attempts), model_request_failed in 3/50 transcripts (7 attempts)).
- Transcript-structure audit: PASS (configured weeks are unique and complete).
- Invalid-episode audit: PASS (no invalid episodes detected).
- Transport exclusion: EXCLUDED 10/50 transcripts from counted aggregates; raw scores and failure counts remain visible.
- Zero-successful-model-decision transcripts: kimi-k3: 4/10.
- Hard-constraint audit: PASS (pain days ≤14 on all transcripts).
- Exclusion audit: EXCLUDED 10/50 records after validity checks.

## Observed transcript behaviors

- claude-opus-5: format repair required (10 transcripts)
- claude-opus-5: late final-week intensity gamble (10 transcripts)
- gpt-5.6-sol: format repair required (9 transcripts)
- gpt-5.6-sol: late final-week intensity gamble (10 transcripts)
- grok-4.5: format repair required (10 transcripts)
- grok-4.5: late final-week intensity gamble (10 transcripts)
- muse-spark-1.2: capital stacking before the budget recovered (1 transcript)
- muse-spark-1.2: format repair required (10 transcripts)
- muse-spark-1.2: late final-week intensity gamble (5 transcripts)

## Method

The analyzer reads the archived v0.1 runner transcripts in historical compatibility mode. It applies the v0.1 pain-only counted rule, excludes any transcript with provider transport failures from counted aggregates, and retains raw scores and transport metrics for audit. It flags repeated high-intensity sessions, sleep protection choices, reciprocity imbalance, final-week intensity, capital stacking, and format repairs; these are triage signals for human transcript reading, not extra score components.
