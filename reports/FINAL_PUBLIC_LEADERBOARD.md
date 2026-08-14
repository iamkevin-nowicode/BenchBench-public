# Bench-bench post-run public leaderboard

This standalone post-run report covers five models × ten public seeds × 52 simulated weeks (50 episodes). It is derived from the completed live transcripts; no network calls are made during report generation.

- Engine/config hash: `sha256:fdbd829339622163df8a27d64fe6467e353c1b2bd8ff289b25e36783e8d2e9a1`
- Seeds: 100–109
- Score: mean of standardized tests at weeks 44, 48, and 52 after the fixed three-day taper
- Counted score: only when pain days ≤14 and `invalid_reason` is null; all five models counted on all ten seeds

## Live model leaderboard

| Rank | Model | Mean kg | Seed SD | Range kg | Counted | Pain violations | Repairs / decisions | Transport failures | Cost / ep |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Claude Opus 5 | 100.06 | 2.25 | 94.88–102.15 | 10/10 | 0 | 130/677 (19.20%) | 0 | $5.9503 |
| 2 | Grok 4.5 | 99.19 | 2.09 | 94.91–101.80 | 10/10 | 0 | 57/677 (8.42%) | 0 | $0.9225 |
| 3 | Muse Spark 1.2 | 98.62 | 1.33 | 97.34–101.51 | 10/10 | 0 | 30/677 (4.43%) | 0 | $1.0753 |
| 4 | GPT-5.6 Sol | 93.86 | 1.23 | 91.80–95.44 | 10/10 | 0 | 15/677 (2.22%) | 0 | $2.8056 |
| 5 | Kimi K3 | 90.48 | 6.22 | 84.62–99.79 | 10/10 | 0 | 39/677 (5.76%) | 702 | $2.0095 |

## Scripted reference baselines

| Reference policy | Mean kg | Seed SD | Counted mean | Counted seeds | Violations |
|---|---:|---:|---:|---:|---:|
| scripted-expert | 102.89 | 0.65 | 102.89 | 20/20 | 0 |
| recovery-aware | 99.01 | 0.70 | 99.01 | 20/20 | 0 |
| skip-when-busy | 96.56 | 0.96 | 96.56 | 20/20 | 0 |
| rigid-linear | 92.35 | 1.77 | 92.35 | 20/20 | 0 |
| reckless-maximalist | 87.51 | 1.07 | — | 0/20 | 20 |
| random | 86.94 | 1.00 | 86.94 | 20/20 | 0 |

## Paired differences

A minus B, using the same ten public seeds; intervals are two-sided 95% paired t intervals (df=9), without multiplicity correction.

| A | B | Mean A−B kg | 95% CI kg |
|---|---|---:|---:|
| Claude Opus 5 | Grok 4.5 | 0.87 | [-1.12, 2.87] |
| Claude Opus 5 | Muse Spark 1.2 | 1.45 | [-0.12, 3.01] |
| Claude Opus 5 | GPT-5.6 Sol | 6.20 | [4.62, 7.78] |
| Claude Opus 5 | Kimi K3 | 9.58 | [5.05, 14.12] |
| Grok 4.5 | Muse Spark 1.2 | 0.57 | [-0.99, 2.14] |
| Grok 4.5 | GPT-5.6 Sol | 5.33 | [3.69, 6.97] |
| Grok 4.5 | Kimi K3 | 8.71 | [4.71, 12.71] |
| Muse Spark 1.2 | GPT-5.6 Sol | 4.75 | [3.91, 5.60] |
| Muse Spark 1.2 | Kimi K3 | 8.13 | [3.56, 12.71] |
| GPT-5.6 Sol | Kimi K3 | 3.38 | [-0.82, 7.58] |

## Per-seed scores

| Model | 100 | 101 | 102 | 103 | 104 | 105 | 106 | 107 | 108 | 109 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Opus 5 | 97.61 | 101.13 | 101.88 | 102.15 | 94.88 | 101.52 | 101.09 | 100.31 | 100.65 | 99.42 |
| Grok 4.5 | 101.35 | 101.80 | 100.27 | 99.07 | 97.21 | 98.26 | 100.23 | 100.50 | 94.91 | 98.31 |
| Muse Spark 1.2 | 98.90 | 97.63 | 98.17 | 99.40 | 97.45 | 99.92 | 101.51 | 97.70 | 97.34 | 98.14 |
| GPT-5.6 Sol | 94.75 | 91.80 | 95.44 | 94.68 | 92.58 | 94.91 | 94.37 | 92.85 | 92.82 | 94.44 |
| Kimi K3 | 97.25 | 93.36 | 99.79 | 98.78 | 89.05 | 86.88 | 85.14 | 84.62 | 84.79 | 85.17 |

## Audit

- 50/50 live transcript start records carry the same engine/config hash.
- All 50 episodes completed; all had pain days 0 and no structural invalidation.
- Transport failures are reported separately from rejected-output repairs. Kimi K3 had 702 transport failures; the other four models had none.
- Total live spend: $127.63.
