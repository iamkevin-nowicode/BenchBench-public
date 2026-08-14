# Independent review — Bench-bench v0.1

Engine/config hash reviewed: `sha256:fdbd829339622163df8a27d64fe6467e353c1b2bd8ff289b25e36783e8d2e9a1`
(matches `provenance.engine_config_hash()` at review time — **Reproduced**)

Scope: Claude Opus 5, Grok 4.5, Muse Spark 1.2, GPT-5.6 Sol, Kimi K3 on public seeds 100–109,
52 weeks, 50 transcripts under `runs/live-full-20260808/` and `runs/live-grok-4.5-full-20260811/`.
`runs/live-grok-4.6-full-20260812/` and all seed-0–12 smoke directories are excluded per brief.
Scripted baselines on seeds 0–19 are treated as a separate calibration population.

Every claim is labelled **Observed** (read directly from an artifact), **Reproduced** (re-derived by
running code), or **Inferred**.

**Verdict: not ready for public release.** The simulator and scoring core are sound and reproduce
exactly. The release-artifact layer does not: the repository fails its own verification script, three
governance documents state that no live run has occurred while 50 live transcripts and $127.63 of
spend sit in the tree, and the published leaderboard contradicts the project's own analyzer on
whether one of the five models has a scoreable result. Nine blockers, all listed in §8.

---

## 1. Scope and protocol

**Observed.** One episode is 52 weeks. The agent returns a `WeekAction` (≤5 `SessionPlan`, one
`LifeAllocation`, `StandingRules`, `coach_note`) plus a `ReactiveAction` per mid-week interrupt.

**Reproduced.** The headline score is the arithmetic mean of three standardized-test projections at
weeks 44/48/52 (`engine.HIDDEN_STANDARDIZED_TEST_WEEKS == [44, 48, 52]`). On seed 0 with
scripted-expert the three projections are `[101.748, 102.685, 103.806]`, mean `102.7463`, and
`FinalResult.final_1rm_kg == 102.75`. The weekly observation estimate at the same point is 105.53 —
distinct from the score, as documented.

**Reproduced.** Test timing is stated in `WEEK_SYSTEM_PROMPT` and the card now describes it as
"disclosed by protocol". The previous card/prompt contradiction on this point is resolved.

**What the benchmark measures.** Long-horizon planning under partial observability against a hard
weekly resource ledger, scored on terminal capacity with a behavioural veto (pain days). Because
`fit_tau_days = 56` and the score averages three tests 4 weeks apart, the effective measurement
window is roughly the last 8–14 weeks; earlier weeks contribute mainly through technique, body mass,
and consistency drift. This is a design property, not a defect, but it should not be described as a
year-long compounding measurement without that qualifier.

---

## 2. Reproducibility audit

### Passes

**Reproduced.** All three calibration commands in `BENCHMARK_CARD.md` regenerate **byte-identical**
markdown to the shipped `reports/CURRENT_BASELINE_GATE.md`, `reports/CURRENT_12_WEEK_DIAGNOSTIC.md`,
and `reports/CURRENT_ADVERSARIAL_SEARCH.md` (`diff` clean on all three).

**Reproduced.** Every numeric validation value printed in `BENCHMARK_CARD.md` §Current validation
re-derives from source: baseline means/SDs, the 15.953 kg expert−random gap, 18.920 pooled SD,
the 5.766σ 12-week diagnostic, and the 100.72 kg best adversarial candidate.

**Reproduced.** Transcript hygiene across all 50 files:

| check | result |
|---|---|
| `run_start.engine_config_hash` == current | 50/50 |
| weeks complete and ordered 1–52 | 50/50 |
| `run_end.result` has `final_1rm_kg`, `pain_days`, `invalid_reason` | 50/50 |
| evaluator-only fields present (`sleep_debt`, `fitness_signal`, `tendon_irritation`, `base_capacity_kg`, `technique`, `volume_tolerance`, `recovery_capacity`, `injury_joint`, hidden test scores) | 0/50 |
| credential scan (brief's `rg` command) | no matches |
| endpoint metadata sanitized (scheme+host+path only) | 50/50 |
| model, provider, sampling, pricing recorded | 50/50 |

### Failures

**Reproduced.** `python3 scripts/verify_artifacts.py` **exits 1**:

```
authoritative_leaderboard_not_generated_before_live_run: false
stale_run_directories_removed:                           false
```

The release candidate does not pass its own gate.

**Observed.** Three governance documents state the live run has not happened:
- `BENCHMARK_CARD.md` §Public leaderboard status: "No public model leaderboard is generated at this commit."
- `release_manifest.json`: `"public_transcript_count": 0`, `"authoritative_leaderboard_status": "pending_independent_review_and_live_run"`, `"public_leaderboard_note": "…no model calls have been made for this release candidate."`
- `docs/DECISIONS.md:150` — "No live model run or public leaderboard is generated before independent review of this frozen protocol."

Against 50 transcripts on seeds 100–109 and `reports/FINAL_PUBLIC_LEADERBOARD.md` reporting
$127.63 of live spend. `release_manifest.json` also still lists
`"public_models": ["gpt-5.4","gpt-5.4-mini","gpt-5.3-chat-latest","gpt-4.1"]` — none of the five
models under review — and points `public_transcript_directory` at `runs/public-leaderboard`, which
does not exist. `FINAL_PUBLIC_LEADERBOARD.md` is not referenced by the manifest at all.

**Reproduced.** The manifest's documented analysis command cannot read the actual transcript layout.
`runner_analysis.analyze_directory` (`runner_analysis.py:269`) globs `*.jsonl` non-recursively;
transcripts live at `<dir>/<model>/seed-<n>/<file>.jsonl`. `analyze_directory('runs/live-full-20260808')`
returns **0** transcripts.

**Reproduced — the most serious reproducibility failure.** Running the project analyzer over all 50
transcripts (`analyze_paths`) produces a leaderboard that contradicts the published one:

| | project analyzer | `FINAL_PUBLIC_LEADERBOARD.md` |
|---|---|---|
| Kimi K3 counted seeds | **0/10 (excluded)** | **10/10** |
| Kimi K3 counted mean | **—** | **90.48 kg, ranked #5** |
| Transport-error audit | **FAILED** (http_429 ×694 in 6 transcripts, http_520 ×1, model_request_failed ×7) | "Transport failures are reported separately" |
| Exclusion audit | **EXCLUDED 10/50** | not mentioned |
| Opus counted seed SD | 2.14 (population) | 2.25 (sample) |

`analyze_transcript` adds `f"transport: {error}"` to `exclusion_reasons` (`runner_analysis.py:175`),
so any transcript with a transport failure is excluded from counted aggregates. Under the
100%-counted-seed rule the analyzer therefore reports **no counted score for Kimi K3**. The published
leaderboard ranks it anyway. `FINAL_PUBLIC_LEADERBOARD.md` was produced by some other, unnamed path.

**Reproduced.** Seed SD convention is inconsistent in-tree: `runner_analysis.py:304` computes
population SD (`sqrt(fmean((x-mean)^2))`); the published leaderboard and the brief's statistical
requirement use sample SD. This is why the same data yields 2.14 and 2.25.

**Reproduced.** Kimi's repair count is irreconcilable across three sources:

| source | Kimi K3 repairs |
|---|---|
| `FINAL_PUBLIC_LEADERBOARD.md` | **39** |
| Σ `run_end.repair_calls` over 10 transcripts | **47** |
| Σ per-turn + per-reactive `repair_calls` | **95** |

The two engine-side counters disagree only on seeds 104 (6 vs 30) and 105 (2 vs 26) — the two
partially transport-degraded seeds. For the other four models all three sources agree exactly
(130 / 57 / 30 / 15).

---

## 3. Mechanics audit

### Scoring validity — passes

**Reproduced.** `scoring.constraint_violations` now fails closed on every malformed input:

| `pain_days` | result |
|---|---|
| `0`, `14` (int) | counted |
| `15` (int) | `pain_days>14` |
| `None` | `missing_pain_days` |
| `True` / `False` (bool) | `invalid_pain_days` |
| `"0"` / `"15"` (str) | `invalid_pain_days` |
| `3.0` (float), `NaN` | `invalid_pain_days` |
| `-1`, `365` (out of `[0, 364]`) | `invalid_pain_days` |

The string- and bool-coercion holes present in the previous revision are closed.

**Reproduced.** `counted_score` returns `None` for any violation or non-null `invalid_reason`, and
`score_fields` retains `raw_final_1rm_kg` alongside. `MIN_COUNTED_SEED_FRACTION = 1.0` is enforced in
`runner_analysis` aggregation (`runner_analysis.py:300–306`): a counted mean and SD are reportable
only when every expected seed counts. The survivor-mean selection effect identified in the previous
review round is closed, and the analyzer states the rule in its output.

### Simulator-side corrections — all surfaced

**Reproduced.** Every transformation on the brief's list is now visible in `WeekOutcome`:

| correction | surfaced |
|---|---|
| load-ratio execution cap | ✅ `"load-ratio execution cap applied"` |
| Brzycki rep-max ceiling | ✅ `"rep-max ceiling reduced prescribed repetitions"` |
| duration/rep-rate limit | ✅ `"duration/repetition-rate limit reduced prescribed repetitions"` |
| home no-spotter cap | ✅ `"home no-spotter load cap applied"` (verified with rack owned, 200 kg authored) |
| rule/reactive fallback conversion | ✅ named per trigger (sleep / pain / illness / reactive) |
| gym-closed, no rack | ✅ `"gym closure cancelled gym session (no home rack)"`, `transformed=1` |
| invalid reactive → protect_recovery | ✅ `reactive_action_fallbacks=1` + reason with the validation error |
| numeric string / purchase sentinel | ✅ rejected visibly, never coerced |
| budget / ledger excess | ✅ rejected with the numeric requirement in the message |

The gym-closed silent cancellation reported in the previous round is fixed.

**Reproduced.** Independent per-day recount over all six baselines × 3 seeds: of **1,841 completed
sessions**, **zero** executed differently from the authored plan without that day being flagged
transformed. Counters `planned / transformed / attempted / completed / missed / fallback` are
distinct fields and move independently.

### Remaining unsurfaced effects (minor)

**Reproduced.** Two engine effects change outcomes without appearing in any outcome or repair record:
the weekly stimulus diminishing-returns curve discarding work above ~0.75 units, and
`minimum_meaningful_load_ratio` zeroing stimulus below 0.35× capacity. Both are documented in the
card's §Simulator assumptions and neither rewrites the action, so I classify these as modeled
dynamics rather than silent corrections — but an agent cannot distinguish "my work was discarded"
from "my work was ineffective" from the transcript.

---

## 4. Calibration and adversarial audit

**Reproduced**, 52-week gate, seeds 0–19:

| policy | raw mean | counted mean | counted seeds |
|---|---:|---:|---:|
| scripted-expert | 102.89 | 102.89 | 20/20 |
| recovery-aware | 99.01 | 99.01 | 20/20 |
| skip-when-busy | 96.56 | 96.56 | 20/20 |
| rigid-linear | 92.35 | 92.35 | 20/20 |
| reckless-maximalist | 87.51 | **—** | **0/20** (pain_days>14 ×20, mean 247.3) |
| random | 86.94 | 86.94 | 20/20 |

Separation 15.953 kg / 0.843 = 18.920σ. Adjacent paired rates 70/100/100/100/100% — all ≥65%.
Reckless loses endogenously and has no counted score. Gate **PASS**. Rack ablation +2.97 kg.

**Reproduced.** 12-week diagnostic: 5.766σ separation but ordering **FAIL** and stable-ordering
**FAIL**; correctly marked `NOT ENFORCED` and excluded from release status.

**Reproduced.** Adversarial search: best valid candidate `adversarial-001` at 100.72 kg vs expert
102.89. No candidate beats expert, requires human review, or blocks release. All regression genomes
(volume-stacking 81.93, 8×4 81.90, mixed-focus 82.69, zero-load 82.55, purchase-order 98.22) remain
far below expert; `regression-compressed-fallback` is invalid in search. Both prior-reviewer
regression policies are retained and neutralised: `regression-claude-4x4x8-072` scores **94.69**
(it scored ~104.9 before rep-rate clipping) and `regression-codex-4x1x11-ramp` 81.79.

**Reproduced — search coverage caveat.** A 450-point manual grid over session count, duration,
sets×reps, load ratio, and focus mix found a legal, zero-violation policy scoring **104.91 kg on
seeds 0–19** and **104.87 kg on seeds 100–109** — about **+2.0 kg over the expert** and **+4.2 kg
above the search's own best candidate**. The card already states that the search result "is a result
about the current search coverage, not an environment ceiling", which is the correct framing; this
quantifies the gap. Not a release blocker (beating the expert without an abuse signature is
explicitly not a block), but the search should be widened before the number is cited as a ceiling.

---

## 5. Live results

**Reproduced.** Full 5×10 counted matrix (all 50 episodes: `pain_days = 0`, `invalid_reason = null`,
so counted == raw). Sample SD, df = 9.

| model | 100 | 101 | 102 | 103 | 104 | 105 | 106 | 107 | 108 | 109 | mean | SD | range |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--|
| Claude Opus 5 | 97.61 | 101.13 | 101.88 | 102.15 | 94.88 | 101.52 | 101.09 | 100.31 | 100.65 | 99.42 | 100.06 | 2.25 | 94.88–102.15 |
| Grok 4.5 | 101.35 | 101.80 | 100.27 | 99.07 | 97.21 | 98.26 | 100.23 | 100.50 | 94.91 | 98.31 | 99.19 | 2.09 | 94.91–101.80 |
| Muse Spark 1.2 | 98.90 | 97.63 | 98.17 | 99.40 | 97.45 | 99.92 | 101.51 | 97.70 | 97.34 | 98.14 | 98.62 | 1.33 | 97.34–101.51 |
| GPT-5.6 Sol | 94.75 | 91.80 | 95.44 | 94.68 | 92.58 | 94.91 | 94.37 | 92.85 | 92.82 | 94.44 | 93.86 | 1.23 | 91.80–95.44 |
| Kimi K3 | 97.25 | 93.36 | 99.79 | 98.78 | 89.05 | 86.88 | 85.14 | 84.62 | 84.79 | 85.17 | 90.48 | 6.22 | 84.62–99.79 |

All five means, SDs, ranges and per-seed values match `FINAL_PUBLIC_LEADERBOARD.md` exactly.

**Reproduced.** Paired differences, same ten seeds, two-sided 95% paired-t, df = 9, no multiplicity
correction:

| A | B | mean A−B | 95% CI | paired SD | W/L/T |
|---|---|--:|--:|--:|--:|
| Opus 5 | Grok 4.5 | +0.87 | [−1.12, +2.87] | 2.79 | 6/4/0 |
| Opus 5 | Muse 1.2 | +1.45 | [−0.12, +3.01] | 2.19 | 7/3/0 |
| Opus 5 | GPT-5.6 | +6.20 | [+4.62, +7.78] | 2.21 | 10/0/0 |
| Opus 5 | Kimi K3 | +9.58 | [+5.05, +14.12] | 6.34 | 10/0/0 |
| Grok 4.5 | Muse 1.2 | +0.57 | [−0.99, +2.14] | 2.18 | 5/5/0 |
| Grok 4.5 | GPT-5.6 | +5.33 | [+3.69, +6.97] | 2.29 | 10/0/0 |
| Grok 4.5 | Kimi K3 | +8.71 | [+4.71, +12.71] | 5.59 | 10/0/0 |
| Muse 1.2 | GPT-5.6 | +4.75 | [+3.91, +5.60] | 1.18 | 10/0/0 |
| Muse 1.2 | Kimi K3 | +8.13 | [+3.56, +12.71] | 6.39 | 9/1/0 |
| GPT-5.6 | Kimi K3 | +3.38 | [−0.82, +7.58] | 5.87 | 6/4/0 |

**Reproduced.** Repairs, transport, cost — note the shared 677-decision denominator (520 weekly +
157 reactive) is identical across models because interrupts are pre-rolled per seed:

| model | repairs | decisions | rate | rejected-output attempts | transport failures | cost/ep | total |
|---|--:|--:|--:|--:|--:|--:|--:|
| Opus 5 | 130 | 677 | 19.20% | 143 | 0 | $5.9503 | $59.50 |
| Grok 4.5 | 57 | 677 | 8.42% | 64 | 0 | $0.9225 | $9.22 |
| Muse 1.2 | 30 | 677 | 4.43% | 41 | 0 | $1.0753 | $10.75 |
| GPT-5.6 | 15 | 677 | 2.22% | 18 | 0 | $2.8056 | $28.06 |
| Kimi K3 | see §2 | 677 | — | 45 | **702** | $2.0095 | $20.10 |

Total live spend $127.63 — matches the published figure.

**Reproduced — the comparison the artifacts do not make.** The published leaderboard prints
seeds-0–19 baselines beside seeds-100–109 model results, the cross-population comparison the brief
forbids. Re-running the baselines on the public seeds gives the valid version:

| policy (seeds 100–109) | counted mean |
|---|--:|
| scripted-expert | **103.19** |
| recovery-aware | 99.54 |
| skip-when-busy | 97.21 |
| rigid-linear | 92.65 |
| reckless-maximalist | — (0/10 counted) |
| random | 86.39 |

Paired against the expert on identical seeds: **no model wins a single seed.**

| model − expert | mean | 95% CI | wins |
|---|--:|--:|--:|
| Opus 5 | −3.12 | [−4.74, −1.51] | 0/10 |
| Grok 4.5 | −4.00 | [−5.35, −2.65] | 0/10 |
| Muse 1.2 | −4.57 | [−5.39, −3.76] | 0/10 |
| GPT-5.6 | −9.32 | [−9.70, −8.95] | 0/10 |
| Kimi K3 | −12.71 | [−16.88, −8.53] | 0/10 |

Against `recovery-aware`, Opus is +0.52 kg [−1.10, +2.15] — indistinguishable. Muse is −0.93
[−1.66, −0.20] — significantly below.

### What the results support

- The top three (Opus, Grok, Muse) are **not separable** from one another: all three pairwise CIs cross zero.
- GPT-5.6 Sol is separable below the top three (10/0/0 on every comparison, CIs excluding zero).
- All five models sit **below the scripted expert** on every public seed, and the best model is statistically level with `recovery-aware`, the second-best script.

### What the results do not support

- Any ranking within {Opus, Grok, Muse}. The published rank order 1/2/3 is not supported by its own CIs.
- Any scoreable result for Kimi K3 (§6).
- Any claim of separation from the scripted expert, or of an "AI beats expert" framing.
- Ten seeds give descriptive intervals over a fixed seed set, not repeated-sampling confidence over model weights.

---

## 6. Model behavior vs provider behavior vs prompt artifacts

### Kimi K3 is a provider-behaviour measurement, not a model measurement

**Reproduced.** Kimi's transport failures are not uniform — they are a hard regime change at seed 104:

| seed | 100 | 101 | 102 | 103 | 104 | 105 | 106 | 107 | 108 | 109 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| transport failures | 1 | 1 | 2 | 4 | 52 | 94 | 134 | 138 | 140 | 136 |
| weeks played by `safe_action()` | 1 | 0 | 3 | 0 | 23 | 39 | **52** | **52** | **52** | **52** |
| reactive turns defaulted | 0 | 0 | 0 | 0 | 5 | 8 | 15 | 17 | 18 | 16 |
| score | 97.25 | 93.36 | 99.79 | 98.78 | 89.05 | 86.88 | 85.14 | 84.62 | 84.79 | 85.17 |

**274 of 520 Kimi weeks (52.7%) were played by the benchmark's own safe fallback action rather than
the model.** On seeds 106–109 that is 52/52 — the entire episode.

Decisive check: replaying `env.safe_action()` for all 52 weeks on each public seed gives

| seed | safe-fallback-only | Kimi reported | delta |
|---|--:|--:|--:|
| 106 | 85.14 | 85.14 | **0.00** |
| 107 | 84.62 | 84.62 | **0.00** |
| 108 | 84.79 | 84.79 | **0.00** |
| 109 | 85.17 | 85.17 | **0.00** |

Four of the ten "Kimi K3" episodes are **bit-identical to the scripted fallback policy** and contain
zero model decisions. Two more (104, 105) are 44% and 75% fallback-played.

Labelled diagnostic split (**not** a replacement aggregate, per brief): seeds 100–103 mean 97.30
(SD 2.82); seeds 104–109 mean 85.94 (SD 1.72). The complete ten-seed result is 90.48 (SD 6.22) and is
the only figure that should ever be quoted for this run — but it should be quoted as *not a valid
model measurement*, which is exactly what the project analyzer already concludes by excluding it.

### Repair rates are prompt artifacts, not model quality

**Reproduced.** Classifying all 1,013 error-bearing attempts:

| cause | Opus | Grok | Muse | GPT | Kimi | total |
|---|--:|--:|--:|--:|--:|--:|
| transport | 0 | 0 | 0 | 0 | 702 | 702 |
| ledger (documented) | 38 | 52 | 11 | 14 | 10 | 125 |
| **field range not in prompt** | **94** | 0 | 0 | 0 | 28 | **122** |
| prompt-shape / nesting | 0 | 10 | 29 | 0 | 5 | 44 |
| cash (documented) | 10 | 1 | 1 | 4 | 1 | 17 |
| **authored fallback load cap (undocumented)** | 0 | 0 | 0 | 0 | 1 | 1 |
| fallback caps (documented) | 0 | 1 | 0 | 0 | 0 | 1 |
| malformed JSON | 1 | 0 | 0 | 0 | 0 | 1 |

**123 of 311 non-transport rejections (40%) come from constraints the prompt does not state.**

Verbatim, the dominant causes:
- **Opus: 94 × `action.coach_note` "String should have at most 600 characters"**. `coach_note` is a `WeekAction` field (`schemas.py:80`) that the weekly prompt **never mentions** — not the field, not the limit. This single undocumented cap accounts for 66% of Opus's rejected attempts and is the direct reason Opus carries the worst repair rate (19.20%) on the leaderboard while ranking first on score.
- **Kimi: 25 × `notebook_update` over 2,000 characters** (`runner.py:33`) — limit not stated in either prompt.
- **Muse: 16 × `action.purchases` "Extra inputs are not permitted"** — `purchases` emitted at the `action` root instead of nested under `life`. Prompt-shape artifact; matches the brief's Muse seeds 100/103.
- **Grok: 10 × "11 validation errors … `action.meal_prep_hours` Extra inputs"** — whole `life` block flattened to the action root. Matches the brief's Grok seeds 100/104.
- **GPT-5.6: 3 × "reactive action requires 5000 cents plus 4500 cents reserved for scheduled…"** — the 4,500-cent household-shock reserve (`engine.py:36`) is not in the reactive prompt. Matches the brief's GPT seeds 101/106.

**Inferred.** Repair rate as published is a composite of (a) genuine format reliability, (b) verbosity
against an undocumented character cap, and (c) nesting convention. It should not be read as a
model-quality metric until the prompt documents every enforced constraint.

### Sampling heterogeneity

**Observed.** Models did not run under a common sampling configuration:

| model | provider kind | sampling recorded |
|---|---|---|
| Claude Opus 5 | `anthropic-messages` | `temperature 1.0, effort medium, max_output_tokens 8192, thinking adaptive` |
| Grok 4.5 / Muse 1.2 / GPT-5.6 | `openai-compatible` | `temperature 1.0, effort medium` |
| Kimi K3 | `openai-compatible` | `temperature 1.0, effort "not exposed"` |

The top-ranked model is the only one on a different client path with an explicit thinking parameter,
and the bottom-ranked model is the only one whose effort setting is unknown. This is honestly
recorded in every transcript, but it is a real comparability limit and is not stated on the
leaderboard.

**Observed.** Pricing provenance also differs: Grok's is `"source": "explicit"` (CLI-supplied), the
other four are `"model-default"` from the in-repo table. Cost comparisons depend on that table.

---

## 7. Limitations

- Ten seeds and one run per model. No temperature-0 determinism and no repeat runs, so within-model variance is unestimated and cannot be separated from seed variance.
- The two seed populations (0–19 calibration, 100–109 public) are disjoint by design; no paired claim across them is valid, and §5 supplies the correctly-paired baseline figures.
- Grok 4.5 was run three days after the other four (`live-grok-4.5-full-20260811` vs `live-full-20260808`) under the same engine hash. Endpoint-side model drift in that window is not observable from the transcripts.
- Cost figures depend on an in-repo price table for four of five models and on token accounting that the transcripts record but the providers were not audited against.
- I did not review `runs/live-grok-4.6-full-20260812/` or the seed-0–12 smoke directories, per scope.
- The manual policy search in §4 is a 450-point grid, not an optimiser; it establishes a lower bound on achievable score, not the true ceiling.

---

## 8. Release verdict and blockers

**Not ready for public release.** The engine, scoring rules, constraint enforcement, transformation
accounting, and calibration artifacts are in good shape and reproduce exactly. Every blocker below is
in the release-artifact and documentation layer, and all are fixable without touching the simulator.

| # | Blocker | Evidence |
|---|---|---|
| **B1** | Repository fails its own verification | `python3 scripts/verify_artifacts.py` → exit 1; `authoritative_leaderboard_not_generated_before_live_run: false`, `stale_run_directories_removed: false` |
| **B2** | Card, manifest, and DECISIONS all state no live run has occurred | `BENCHMARK_CARD.md` §Public leaderboard status; `release_manifest.json` `public_transcript_count: 0`, `public_leaderboard_note`; `docs/DECISIONS.md:150` — vs 50 transcripts and $127.63 spend |
| **B3** | Manifest describes a different release | `release_manifest.json` `public_models` lists four OpenAI models not under review; `public_transcript_directory: runs/public-leaderboard` does not exist; `FINAL_PUBLIC_LEADERBOARD.md` is unreferenced |
| **B4** | Published leaderboard contradicts the project analyzer | analyzer excludes 10/10 Kimi transcripts (transport audit FAILED) and reports no counted mean; `FINAL_PUBLIC_LEADERBOARD.md` ranks Kimi #5 at 90.48 with "Counted 10/10" |
| **B5** | Four published episodes contain zero model decisions | Kimi seeds 106–109 are bit-identical to `env.safe_action()` replay (85.14 / 84.62 / 84.79 / 85.17); 274/520 Kimi weeks fallback-played |
| **B6** | Leaderboard not reproducible by any documented command | `analyze_directory` is non-recursive (`runner_analysis.py:269`) → 0 transcripts on the real layout; no command in card or manifest emits `FINAL_PUBLIC_LEADERBOARD.md` |
| **B7** | Repair counts irreconcilable | Kimi: 39 published vs 47 (`run_end`) vs 95 (per-turn); the two engine counters disagree on seeds 104–105 |
| **B8** | 40% of non-transport rejections are undocumented constraints | `coach_note` 600-char cap (`schemas.py:80`) absent from the prompt → 94 Opus rejections; `notebook_update` 2,000 cap (`runner.py:33`); authored-fallback load cap; 4,500-cent shock reserve (`engine.py:36`); field ranges for `sets`/`reps`/`load_kg`/`target_rpe`; strict-typing rule; `focus:"test"` ⇒ `reps == 1` |
| **B9** | Cross-population comparison and SD convention | `FINAL_PUBLIC_LEADERBOARD.md` prints seeds-0–19 baselines beside seeds-100–109 models; `runner_analysis.py:304` uses population SD while the published table uses sample SD |

### Recommended resolution order

1. **B1–B3** — decide whether this commit is pre-run or post-run and make card, manifest, DECISIONS, and `verify_artifacts.py` agree. Everything else is downstream.
2. **B4, B5** — either withdraw Kimi K3 from the leaderboard (the analyzer's own verdict) or publish it as an explicitly non-scoreable transport-failed entry showing 0/10 counted. Do not publish 90.48 as a model result.
3. **B6, B7** — make `FINAL_PUBLIC_LEADERBOARD.md` the output of a named command; make `analyze_directory` recursive; reconcile `repair_calls` between the runner counters.
4. **B8** — document every enforced constraint in the prompt, then re-run. Until then the repair column is not a model metric.
5. **B9** — pick sample SD everywhere; compare models to baselines only on seeds 100–109.

Per the brief, I make no recommendation on tuning simulator constants; none of the above requires it.

### What I would keep unchanged

Determinism and counterfactual safety (pre-rolled calendar and noise book); the hash-stamped artifact
chain; the pain constraint and its fail-closed validation; the 100%-counted-seed aggregation rule;
transformation surfacing and the distinct planned/transformed/attempted/completed/missed/fallback
counters; strict schemas; separate transport vs rejected-output accounting; and the card's own
statement that the adversarial result reflects search coverage rather than an environment ceiling.
These are the parts of the release that are working.
