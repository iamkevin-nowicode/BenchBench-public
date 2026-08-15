
> **SUPERSEDED HISTORICAL REPORT — NOT AN AUTHORITATIVE LEADERBOARD**
>
> This report preserves the original write-up, but its Kimi K3 aggregate is
> transport-contaminated. Use `PILOT_V0.1_LEADERBOARD.md` for the analyzer's
> corrected historical presentation: Kimi K3 is 0/10 counted, with raw scores
> retained and transport failures reported separately.

# Bench-bench v0.1 — Results and Findings Report (superseded)

Scope: original five-model public run only. Later model extensions are excluded.

Run: 5 models × 10 public seeds (100–109) × 52 weeks = 50 episodes

Engine/config hash: sha256:fdbd829339622163df8a27d64fe6467e353c1b2bd8ff289b25e36783e8d2e9a1

Primary source: reports/final_public_leaderboard.json

## Executive conclusion

Bench-bench produces a meaningful long-horizon operational signal, but this run should be treated as an instrumented first result rather than a universal ranking of model intelligence.

The live ordering is:

Claude Opus 5 > Grok 4.5 > Muse Spark 1.2 > GPT-5.6 Sol > Kimi K3

Key results:

- Claude Opus 5 leads at 100.06 kg.
- Grok 4.5 is 0.87 kg behind; the paired 95% interval is -1.12 to +2.87 kg.
- Muse Spark 1.2 is 1.45 kg behind Opus; the paired interval is -0.12 to +3.01 kg.
- GPT-5.6 Sol is a clearly lower tier in this run at 93.86 kg.
- Kimi K3 reports 90.48 kg, but 702 transport failures dominate the late seeds. This is not a clean capability comparison.
- All 50 live episodes counted: every episode stayed within the pain constraint, had no structural invalidation, and carried the current engine/config hash.

The benchmark measures two things simultaneously: long-horizon decisions in a constrained simulator, and the ability to operate a structured protocol over hundreds of turns. That second signal is useful, but it is not yet cleanly separable from prompt quality. Opus's repair rate is mostly an undocumented coach_note limit; Grok 4.5 and Muse Spark 1.2 show early nested-schema failures; Kimi's score is heavily confounded by provider transport instability.

## Protocol

Dave is a 38-year-old returning lifter with a full-time job, a full-time working partner, and a six-month-old infant at the start. Each week the model submits training and life-allocation decisions. The simulator executes the week under partial observability: sessions can be missed, illness and household events can interrupt the plan, and time and money are conserved across training, commute, childcare, chores, meals, partner coverage, and giveback.

The release horizon is 52 simulated weeks, or 364 simulated days. The score is the average of standardized tests at weeks 44, 48, and 52 after a fixed three-day taper. The weekly estimated 1RM is noisy and is not the score.

The only hard behavioral score constraint is pain_days less than or equal to 14. Household strain and sleep debt are diagnostics. A counted aggregate requires every expected seed.

## Source hierarchy and artifact caveat

This report uses:

1. reports/final_public_leaderboard.json for five-model aggregates, per-seed scores, costs, tokens, repairs, transport, endpoints, and sampling metadata;
2. the 50 live JSONL transcripts under runs/live-full-20260808 and runs/live-grok-4.5-full-20260811;
3. reports/current_baseline_gate.json and reports/CURRENT_BASELINE_GATE.md for scripted references on seeds 0–19;
4. reports/current_adversarial_search.json and reports/CURRENT_ADVERSARIAL_SEARCH.md for the widened search;
5. BENCHMARK_CARD.md, docs/DECISIONS.md, and source code for protocol and mechanics.

The numeric live artifact is present and transcript-backed, but repository release metadata is not reconciled:

- reports/final_public_leaderboard.json and reports/FINAL_PUBLIC_LEADERBOARD.md contain the completed five-model run.
- BENCHMARK_CARD.md, README.md, and release_manifest.json still describe the public leaderboard as pending.
- release_manifest.json points to reports/PUBLIC_LEADERBOARD.json and reports/PUBLIC_LEADERBOARD.md, which do not exist.
- reports/CURRENT_VERIFICATION.md passes the old pending-state contract. That PASS is not a post-live release-integrity check.

This is an artifact problem, not evidence that the 50 transcripts are invalid. It must be resolved before calling the repository release-ready.

## Scripted calibration

The six reference policies were run on burned development seeds 0–19. Reckless-maximalist remains a raw diagnostic but has no counted mean because it violates the pain constraint on every seed.

| Policy | Raw mean kg | Counted mean kg | Seed SD kg | Counted | Planned | Transformed | Attempted | Completed | Missed | Pain days | Household strain |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scripted-expert | 102.89 | 102.89 | 0.65 | 20/20 | 153.0 | 11.9 | 151.6 | 145.8 | 7.2 | 0.0 | 0.000 |
| recovery-aware | 99.01 | 99.01 | 0.70 | 20/20 | 148.3 | 11.2 | 146.4 | 132.4 | 15.9 | 0.0 | 0.000 |
| skip-when-busy | 96.56 | 96.56 | 0.96 | 20/20 | 121.5 | 0.3 | 111.1 | 106.0 | 15.6 | 0.0 | 0.023 |
| rigid-linear | 92.35 | 92.35 | 1.77 | 20/20 | 156.0 | 11.6 | 155.2 | 88.8 | 67.2 | 0.0 | 0.875 |
| reckless-maximalist | 87.51 | — | 1.07 | 0/20 | 205.0 | 127.5 | 204.3 | 98.0 | 107.0 | 247.3 | 1.000 |
| random | 86.94 | 86.94 | 1.00 | 20/20 | 111.3 | 7.1 | 106.5 | 52.5 | 58.9 | 0.0 | 0.681 |

The intended raw ordering passes: expert > recovery-aware > skip-when-busy > rigid-linear > reckless > random.

The expert–random difference is 15.953 kg, or 18.920 pooled seed SDs. This ratio is a calibration effect-size diagnostic, not a p-value.

| Pair | Paired ordering rate | Mean gap kg | Pooled seed SD | Gap / pooled SD |
|---|---:|---:|---:|---:|
| random < reckless | 70% | 0.567 | 1.034 | 0.548 |
| reckless < rigid-linear | 100% | 4.840 | 1.464 | 3.306 |
| rigid-linear < skip-when-busy | 100% | 4.215 | 1.426 | 2.957 |
| skip-when-busy < recovery-aware | 100% | 2.446 | 0.838 | 2.918 |
| recovery-aware < scripted-expert | 100% | 3.885 | 0.674 | 5.759 |

The 52-week gate passes. The random/reckless boundary is weak; the stronger calibration distinctions are between rigid-linear, skip-when-busy, recovery-aware, and expert.

### Horizon behavior

The 12-week diagnostic is not a release gate. It has 5.766 expert–random separation but fails the intended ordering and stable-ordering checks:

- expert: 94.67 kg
- random: 87.90 kg
- random < reckless: 45%
- rigid/reckless < skip: 40%
- recovery < expert: 100%

An auxiliary current-code analysis in SOURCE_DERIVED_NOTES.md measured the cost of deleting one expert week on seeds 0–7:

| Lost week | Mean score change |
|---:|---:|
| 1 | -0.02 kg |
| 10 | -0.02 kg |
| 20 | -0.06 kg |
| 30 | -0.15 kg |
| 40 | -0.54 kg |
| 48 | -1.33 kg |
| 52 | -2.03 kg |

The supported interpretation is that the terminal score is strongly recency-weighted. This auxiliary measurement should be regenerated into a named artifact before being used as a formal release claim.

### Home-rack ablation

For scripted-expert, rack enabled is 102.89 kg, rack disabled is 99.93 kg, and the paired swing is 2.97 kg. The rack is consequential but not mandatory.

### Adversarial search

The widened search used the 52-week configuration, weekly stimulus cap 1.0, mixed-focus weeks, per-week structure, boundary loads including zero, purchase ordering, and permanent regression genomes.

The best valid generated candidate scored 100.72 kg, 2.17 kg below scripted-expert. No candidate both beat expert and crossed the release review criteria.

| Search policy | Mean kg | Difference vs expert | Pain days | Household strain | Status |
|---|---:|---:|---:|---:|---|
| adversarial-001 | 100.72 | -2.17 | 0.0 | 0.003 | valid; physical signature |
| adversarial-002 | 100.70 | -2.20 | 0.0 | 0.003 | valid; physical signature |
| adversarial-003 | 99.78 | -3.12 | 0.0 | 0.003 | valid; physical signature |
| regression-purchase-ordering | 98.22 | -4.67 | 0.0 | 0.008 | valid |
| regression-claude-4x4x8 | 94.69 | -8.20 | 0.0 | 0.085 | valid |
| regression-mixed-focus-week | 82.69 | -20.20 | 0.0 | 0.494 | valid |
| regression-zero-load-boundary | 82.55 | -20.35 | 0.0 | 0.039 | valid |
| regression-volume-stacking | 81.93 | -20.96 | 0.0 | 0.716 | valid; physical signature |
| regression-volume-8x4 | 81.90 | -20.99 | 0.0 | 0.716 | valid |
| regression-Codex-ramp | 81.79 | -21.10 | 0.0 | 0.716 | valid |
| regression-compressed-fallback | — | — | — | — | invalid at validation |

This is evidence that the tested exploit families are closed under the current genome. It is not evidence that the finite search found every plausible policy family.

## Five-model live leaderboard

All rows count on all ten public seeds. The intervals are descriptive t intervals across the ten seed outcomes; they are not repeated-sampling confidence in model weights or provider behavior.

| Rank | Model | Mean kg | Seed SD kg | Descriptive 95% interval | Range kg | Counted | Pain violations | Repairs / decisions | Transport failures | API cost / episode |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Claude Opus 5 | 100.06 | 2.25 | 98.45–101.68 | 94.88–102.15 | 10/10 | 0 | 130/677 (19.20%) | 0 | $5.9503 |
| 2 | Grok 4.5 | 99.19 | 2.09 | 97.70–100.69 | 94.91–101.80 | 10/10 | 0 | 57/677 (8.42%) | 0 | $0.9225 |
| 3 | Muse Spark 1.2 | 98.62 | 1.33 | 97.66–99.57 | 97.34–101.51 | 10/10 | 0 | 30/677 (4.43%) | 0 | $1.0753 |
| 4 | GPT-5.6 Sol | 93.86 | 1.23 | 92.98–94.75 | 91.80–95.44 | 10/10 | 0 | 15/677 (2.22%) | 0 | $2.8056 |
| 5 | Kimi K3 | 90.48 | 6.22 | 86.03–94.93 | 84.62–99.79 | 10/10 | 0 | 39/677 (5.76%) | 702 | $2.0095 |

### Per-seed scores

| Model | 100 | 101 | 102 | 103 | 104 | 105 | 106 | 107 | 108 | 109 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Opus 5 | 97.61 | 101.13 | 101.88 | 102.15 | 94.88 | 101.52 | 101.09 | 100.31 | 100.65 | 99.42 |
| Grok 4.5 | 101.35 | 101.80 | 100.27 | 99.07 | 97.21 | 98.26 | 100.23 | 100.50 | 94.91 | 98.31 |
| Muse Spark 1.2 | 98.90 | 97.63 | 98.17 | 99.40 | 97.45 | 99.92 | 101.51 | 97.70 | 97.34 | 98.14 |
| GPT-5.6 Sol | 94.75 | 91.80 | 95.44 | 94.68 | 92.58 | 94.91 | 94.37 | 92.85 | 92.82 | 94.44 |
| Kimi K3 | 97.25 | 93.36 | 99.79 | 98.78 | 89.05 | 86.88 | 85.14 | 84.62 | 84.79 | 85.17 |

Per-seed winner counts: Claude Opus 5 5/10, Grok 4.5 3/10, Muse Spark 1.2 2/10, GPT-5.6 Sol 0/10, Kimi K3 0/10.

### Paired model differences

A minus B is paired on the same public seed. Intervals are two-sided 95% paired t intervals with df=9.

| A | B | Mean A−B kg | 95% paired CI kg |
|---|---|---:|---:|
| Claude Opus 5 | Grok 4.5 | 0.87 | -1.12 to 2.87 |
| Claude Opus 5 | Muse Spark 1.2 | 1.45 | -0.12 to 3.01 |
| Claude Opus 5 | GPT-5.6 Sol | 6.20 | 4.62 to 7.78 |
| Claude Opus 5 | Kimi K3 | 9.58 | 5.05 to 14.12 |
| Grok 4.5 | Muse Spark 1.2 | 0.57 | -0.99 to 2.14 |
| Grok 4.5 | GPT-5.6 Sol | 5.33 | 3.69 to 6.97 |
| Grok 4.5 | Kimi K3 | 8.71 | 4.71 to 12.71 |
| Muse Spark 1.2 | GPT-5.6 Sol | 4.75 | 3.91 to 5.60 |
| Muse Spark 1.2 | Kimi K3 | 8.13 | 3.56 to 12.71 |
| GPT-5.6 Sol | Kimi K3 | 3.38 | -0.82 to 7.58 |

The first three models are not decisively separated at n=10. Opus vs Grok is 6–4, Opus vs Muse is 7–3, and Grok vs Muse is 5–5; all three intervals cross zero. Each of the top three beats GPT on all ten seeds. The top two beat Kimi on all ten; Muse beats Kimi on 9/10; GPT beats Kimi on 6/10 with an interval crossing zero.

The scripted-expert mean is 102.89 kg on burned seeds 0–19. Descriptive live-minus-expert reference gaps are Opus -2.83 kg, Grok -3.70 kg, Muse -4.28 kg, GPT -9.03 kg, and Kimi -12.41 kg. These are not paired estimates.

## Operational behavior behind the scores

The following are episode averages. Live result records expose final household strain, not mean household strain; sleep debt is evaluator-only and is not present in public model results.

| Model | Planned | Transformed | Attempted | Completed | Missed | Fallback | Productive weeks | Reactive fallbacks | Final strain | Rack purchases | Simulated spend / episode |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Opus 5 | 204.0 | 17.4 | 197.9 | 154.9 | 49.1 | 33.7 | 46.8 | 0.0 | 0.044 | 7/10 | $3,188.10 |
| Grok 4.5 | 140.0 | 8.3 | 135.1 | 126.3 | 13.7 | 10.0 | 47.5 | 0.0 | 0.008 | 3/10 | $2,349.43 |
| Muse Spark 1.2 | 150.8 | 9.1 | 144.8 | 134.1 | 16.7 | 17.3 | 46.5 | 0.0 | 0.006 | 5/10 | $2,333.20 |
| GPT-5.6 Sol | 149.6 | 7.8 | 145.0 | 130.4 | 19.2 | 9.1 | 44.0 | 0.0 | 0.005 | 3/10 | $3,303.00 |
| Kimi K3 | 100.4 | 7.0 | 98.2 | 87.2 | 13.2 | 28.5 | 21.9 | 7.0 | 0.104 | 2/10 | $1,380.50 |

Strategy signatures from accepted actions:

- Opus planned the most work, used home sessions heavily, bought the rack in 7/10 episodes, and scored highest. It also missed about 49 sessions per episode and used the most fallback sessions.
- Grok planned fewer sessions, completed the highest share among the clean top three, and had the most productive weeks. Its actions were predominantly gym-based and weighted toward technique and volume.
- Muse used a moderate three-session cadence, mostly gym work, balanced volume/heavy/technique sessions, and five rack purchases.
- GPT planned about three sessions per week and was almost entirely gym-based. It was the most protocol-clean model by repair rate but scored below Muse.
- Kimi planned the least work, used fallback focus often, had only 21.9 productive weeks on average, and required reactive fallbacks.

## Repairs, transport, and prompt effects

Repair rate counts the first rejected model output for a decision. Transport failure is separate. The table assigns each repaired decision to one primary cause; a malformed output can contain several field errors.

| Model | Repairs | Primary causes |
|---|---:|---|
| Claude Opus 5 | 130 | 94 coach_note length; 34 weekly ledger; 1 reactive reserve; 1 malformed/format |
| Grok 4.5 | 57 | 46 weekly ledger; 10 flattened/nested-life schema; 1 other validation |
| Muse Spark 1.2 | 30 | 20 purchases at wrong nesting; 8 weekly ledger; 1 flattened life/rules object; 1 other |
| GPT-5.6 Sol | 15 | 11 weekly ledger; 4 reactive reserve |
| Kimi K3 | 39 | 24 notebook_update validation/length; 6 weekly ledger; 3 purchases at wrong nesting; 3 reactive note; 1 reactive reserve; 1 nested-action error; 1 other |

The weekly prompt states fallback duration, set, and rep caps, but does not state the 600-character coach_note limit, the 2,000-character notebook_update limit, or the authored fallback-load ceiling. Opus has 94/130 repairs, 72.3%, from coach_note failures. Kimi has 24/39, 61.5%, from notebook validation/length failures. Grok and Muse show the cost of not providing a complete nested weekly example.

Repair timing: Grok and Muse schema-shape failures cluster at the beginning; GPT repairs cluster around the week-14 ledger and reactive-reserve cases; Opus coach_note failures persist across the year; Kimi format repairs occur throughout while transport failures surge late.

### Kimi transport contamination

| Seed | 100 | 101 | 102 | 103 | 104 | 105 | 106 | 107 | 108 | 109 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Transport failures | 1 | 1 | 2 | 4 | 52 | 94 | 134 | 138 | 140 | 136 |
| Score kg | 97.25 | 93.36 | 99.79 | 98.78 | 89.05 | 86.88 | 85.14 | 84.62 | 84.79 | 85.17 |

Seeds 100–103 averaged 97.30 kg; seeds 104–109 averaged 85.94 kg. The 11.35 kg discontinuity coincides with 694 of 702 transport failures. This is a transport-robustness result, not a clean capability estimate. The complete ten-seed aggregate remains official; the split is diagnostic only.

## Provider, token, and cost accounting

| Model | Endpoint identity | Input tokens | Visible output | Thinking tokens | Total tokens | Total API cost | Effort | Temperature |
|---|---|---:|---:|---:|---:|---:|---|---:|
| Claude Opus 5 | api.anthropic.com/v1/messages | 7,856,328 | 705,257 | 103,610 | 8,665,195 | $59.5033 | medium / adaptive thinking | 1.0 |
| GPT-5.6 Sol | api.openai.com/v1/chat/completions | 2,852,147 | 201,823 | 269,356 | 3,323,326 | $28.0557 | medium | 1.0 |
| Grok 4.5 | api.x.ai/v1/chat/completions | 4,120,602 | 3,170 | 847,379 | 5,337,596 | $9.2247 | medium | 1.0 |
| Kimi K3 | api.moonshot.ai/v1/chat/completions | 2,141,746 | 239,406 | 834,168 | 3,215,320 | $20.0951 | not exposed | 1.0 |
| Muse Spark 1.2 | api.meta.ai/v1/chat/completions | 3,294,405 | 302,499 | 1,379,371 | 4,976,275 | $10.7527 | medium | 1.0 |

Total recorded API cost: $127.63. All 50 transcript start records carry the same engine/config hash and sanitized endpoint metadata. No credential material was found in the inspected live transcript or leaderboard artifacts.

## Supported and unsupported claims

Supported:

1. A 52-week environment separates the calibrated reference policies on burned seeds.
2. The full-year hierarchy is materially more stable than the 12-week diagnostic.
3. The live run produces a spread in score, adherence, fallback use, repairs, transport resilience, and cost.
4. Protocol operation is part of the measured task.
5. The top-three live ordering is suggestive, not decisive at n=10.

Not established:

- a universal ranking of the named models;
- a capability ranking independent of provider reliability, prompt/schema fluency, or sampling;
- that scripted-expert is a theoretical optimum or upper bound;
- external validity for real exercise, health, nutrition, sleep, or relationship advice;
- equal contribution from every week to the terminal score;
- that the finite adversarial search found every plausible policy family;
- that repository release metadata is reconciled with the completed run.

## Recommended path forward

1. Reconcile the benchmark card, README, release manifest, verification report, and authoritative leaderboard paths.
2. Document every enforced output limit in the frozen prompt, including coach_note, notebook_update, and authored fallback load.
3. Add complete nested weekly and reactive JSON examples.
4. Rerun the five-model comparison under that frozen, fully documented prompt.
5. Report transport robustness as a first-class metric and do not treat transport-dominated episodes as ordinary capability evidence.
6. Keep paired-seed analysis and all-seed counting.
7. Complete independent review before tuning constants or adding another provider.

See reports/INDEPENDENT_REVIEW_INSTRUCTIONS.md for the exact reviewer brief.
