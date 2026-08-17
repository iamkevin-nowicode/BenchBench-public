# Bench-bench Generated Public Leaderboard

This artifact is generated from live model transcripts. Endpoint provenance and transport errors are audited below; a failed transport audit must not be presented as a model result.

- Analysis engine/config hash: `sha256:438c1d77d284450cd4e3da2eac9fcda83c45bfb81f7a67598c62763d96602a52`
- Prompt hash: `sha256:06d96111ac9db67e92f1a26d00f84e986ea95d13fc2acf0825b97be112ef0d27`
| Model | Valid seeds | Excluded | Counted mean final 1RM (kg) | Counted seed SD (kg) | Decisions | Mean calls | Mean cost | Rejected decisions | Repair attempts | Successful repairs | Transport failures | Auto fallbacks | Violations | Raw mean final 1RM (kg) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| claude-opus-5 | 7 | 3 | — | — | 704 | 79.7 | $6.1209 | 112 | 112 | 98 | 0 | 14 | pain_days>14 (3) | 102.00 |
| gpt-5.6-sol | 10 | 0 | 96.41 | 1.47 | 704 | 72.7 | $3.1290 | 23 | 23 | 19 | 0 | 4 | — | 96.41 |
| grok-4.6 | 10 | 0 | 101.19 | 1.66 | 704 | 72.6 | $1.1473 | 22 | 22 | 12 | 0 | 10 | — | 101.19 |
| muse-spark-1.2 | 10 | 0 | 101.03 | 2.68 | 704 | 71.8 | $1.0956 | 14 | 14 | 6 | 0 | 8 | — | 101.03 |

## Aggregation rule

A counted mean and seed standard deviation are reportable only when all expected seeds count (minimum counted-seed fraction 100%). Excluded seeds remain in the denominator and their raw scores remain diagnostic; no survivor mean is ranked.

## Provenance and transcript audit

- Engine/config hash audit: PASS on 40/40 transcripts.
- Endpoint metadata: present on 40/40 transcripts.
- Endpoint identities: anthropic-messages (https://api.anthropic.com/v1/messages), openai-compatible (https://api.meta.ai/v1/chat/completions), openai-compatible (https://api.openai.com/v1/chat/completions), openai-compatible (https://api.x.ai/v1/chat/completions).
- Public-field audit: PASS (no evaluator-only fields detected).
- Transport-error audit: PASS (no provider/transport failures detected).
- Transcript-structure audit: PASS (configured weeks are unique and complete).
- Invalid-episode audit: PASS (no invalid episodes detected).
- Transport exclusion: PASS (no transcripts excluded for provider transport failures).
- Hard-constraint audit: EXCLUDED 3/40 transcripts (pain_days>14: 3); raw scores retained.
- Exclusion audit: EXCLUDED 3/40 records after validity checks.

## Observed transcript behaviors

- claude-opus-5: format repair required (7 transcripts)
- claude-opus-5: late final-week intensity gamble (7 transcripts)
- gpt-5.6-sol: format repair required (10 transcripts)
- gpt-5.6-sol: late final-week intensity gamble (10 transcripts)
- grok-4.6: format repair required (10 transcripts)
- grok-4.6: late final-week intensity gamble (8 transcripts)
- muse-spark-1.2: format repair required (10 transcripts)
- muse-spark-1.2: late final-week intensity gamble (7 transcripts)

## Method

The analyzer reads only public model transcripts and final results. Structurally invalid or pain-violating episodes remain in audit records, their raw final 1RM is retained, and only counted scores enter aggregates. It flags repeated high-intensity sessions, sleep protection choices, reciprocity imbalance, final-week intensity, capital stacking, and format repairs; these are triage signals for human transcript reading, not extra score components.
