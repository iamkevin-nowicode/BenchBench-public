# What Bench-bench measures and how it scores — derived from source only

Written before reading README.md, ENGINEER_BRIEF.md, REVIEW_AND_BUILD_PLAN.md, BENCHMARK_CARD.md,
or reports/. Sources: `bench_bench/*.py` plus two transcripts
(`runs/live-gpt41-seed10-52-opaque/gpt-4.1-seed-10.jsonl`, `runs/step3-live-recalibrated/gpt-5.4-seed-0.jsonl`).

## 1. The task

An agent plays 12 or 52 sequential weeks as "Dave", a 38-year-old returning lifter with an infant,
a full-time job, and a working partner. Each week the agent sees a banded, noisy `WeekObservation`
and returns a `WeekAction`: up to 5 `SessionPlan`s (day/slot/location/focus/sets/reps/load/duration/RPE),
a `LifeAllocation` (meal prep, childcare, chore delegation, partner coverage/giveback, sleep protection,
career choice, capital purchases), and `StandingRules` (conditional responses to low sleep / pain / illness).
Mid-week `InterruptEvent`s (illness, daycare closure, gym closure, partner illness, household shock)
trigger a separate `ReactiveAction` turn.

So the measured capability is: **multi-turn sequential planning under partial observability, with
delayed consequences, irreversible damage, and competing non-training resources.** It is a
long-horizon-planning benchmark wearing a fitness-sim costume.

## 2. The score

`FinalResult.final_1rm_kg` = `BenchEnvironment._standardized_test_capacity()` at week N. Nothing else
enters the headline number. Everything else (pain days, household strain, sleep debt, adherence,
spend) is reported as secondary and never combined into the score.

`_true_capacity()` = 84 kg base
  + adaptation: `fitness_signal * 2.60 - fatigue_signal * 0.25`
  + technique: `(technique - technique_start) * 9.0`   (bounded, ≈ +4 kg max)
  + mass: `(body_mass - 84) * 0.34`, kinked above +8 kg
  + injury: `-1.9` while `injury_recovery_days > 0`
  + stress: `-household_strain * 1.2`

`_standardized_test_capacity()` re-runs the adaptation term with a fixed 3-day taper: it subtracts the
live fitness/fatigue contribution and adds back `fitness*e^{-3/56}` and `fatigue*e^{-3/6}`. Fatigue
decays to 0.61 of value over the taper, fitness to 0.95 — so a genuine taper is rewarded, ~modestly.

Per-session, a completed session adds `effective_stimulus` to `fitness_signal` and `fatigue_cost`
to `fatigue_signal`:
```
volume_units      = sets*reps/20 * clamp(load/max(60,true_capacity), .35, 1.20)
effective_stimulus= volume_units * focus_factor * effort * location * recovery * volume_tolerance
fatigue_cost      = volume_units * (0.72 + rpe*0.038) * sleep_penalty [*0.58 if fallback]
```
`focus_factor`: volume .92, heavy 1.05, technique .56, fallback .60, test .86.

### The decisive structural fact
`fit_tau_days = 56`, `fatigue_tau_days = 6`, and both signals decay **daily**. In steady state a
constant training input yields `fitness ≈ input*56` and `fatigue ≈ input*6`, contributing
`56*2.60 = 145.6` vs `6*0.25 = 1.5` kg per unit of daily input. **Fatigue is a ~1% counterweight to
fitness.** The only real brake on volume is the injury system (tendon irritation → stage 2 → 42-day
recovery, stimulus ×0.28 and −1.9 kg) plus the weekly time budget and the adherence draw.

Second consequence: with a 56-day fitness time constant, the score is essentially a **rolling ~8-week
measurement**, not a year-long compounding one. Week-1 stimulus is discounted by `e^{-357/56} ≈ 0.002`
at the week-52 test. Only technique (≤ ~4 kg) and body mass carry the year. I expect a 12-week episode
to be scoreable at or above a 52-week episode, and I expect a bad week near the end to cost far more
than a bad week early. (The two transcripts are consistent with this: gpt-5.4 scored **97.06 kg over
12 weeks** while gpt-4.1 scored **93.91 kg over 52 weeks**.)

## 3. Determinism and counterfactual safety

Good, and deliberately built. `EventCalendar` pre-rolls the full 52-week arc at construction;
`NoiseBook` pre-rolls per-day sleep/adherence/pain/estimate/illness draws indexed by absolute
`day_index`. Agent choices never advance an RNG stream, so counterfactual comparisons on a seed are
clean. `HiddenVariation` (recovery capacity, volume tolerance, latent injury joint, motivation,
starting technique) is private per-seed. The visible `estimated_1rm_kg` carries ±4.5% multiplicative
noise so the observed estimate is not the score.

## 4. The Phase 2 separation gate (`evaluation.gate_metrics`)

Six scripted policies, ranked by the author's prior:
`random < reckless-maximalist ≈ rigid-linear < skip-when-busy < recovery-aware < scripted-expert`.

`gate_pass = (separation_ratio >= 3.0) and ordering_pass and stable_ordering_pass and reckless_loses_endogenously`

- `separation_ratio` = `(mean(expert) - mean(random)) / pooled_seed_std`. This is **Cohen's d, not a
  significance statistic** — it does not shrink as seeds are added, and the denominator is the
  *between-seed* spread (seed difficulty), not the paired noise. Since episodes are paired on seed and
  the seed determines the whole hidden environment, most of that SD is common-mode and cancels in the
  pairing. So the ratio simultaneously (a) understates the paired evidence and (b) is not the
  uncertainty measure the name suggests.
- `ordering_pass` compares **means** in a fixed hand-written order.
- `stable_ordering_pass` = every adjacent pairwise win rate ≥ 0.65. On 20 seeds, 0.65 = 13/20, which
  is p ≈ 0.13 against a coin flip. That is a weak stability bar.
- `reckless_loses_endogenously` requires reckless < expert, reckless < recovery-aware, and reckless
  pain > expert pain, and zero invalid episodes.

**What it actually measures:** that six fixed scripts land in the order the author expected, on 20
fixed seeds, with an effect size ≥ 3 pooled SD. That is a sanity check on the simulator, not evidence
that the environment rewards general planning skill. Nothing in it establishes an upper bound —
`scripted-expert` is asserted as the top anchor but is never shown to be near-optimal.

Supporting note from `config.py`: `fitness_to_strength_kg` carries the comment *"Rebalanced slightly
after adding the explicit home-transition term so the expert remains close to the previous 105 kg
calibration."* The constants were tuned toward a target expert score. A gate whose pass condition is
an ordering of the same scripts the constants were tuned against is close to self-fulfilling.

## 5. Invalid-episode path — resolved

- The earlier implementation left `_state.invalid_reason` unassigned and let an unexpected
  execution-time budget charge raise a raw `RuntimeError`. That was a real vacuity and is retained
  here as historical audit context only.
- The current engine assigns `invalid_reason`, emits an `episode_invalidated` record, terminates the
  episode, and returns an invalid final result when an execution-time charge defeats the validated
  cash ledger. The analyzer and leaderboard exclude that result automatically.
- Normal budget overspending remains a visible validation error with one repair attempt and then a
  safe fallback. `tests/test_phase1.py` forces an accounting mismatch through `submit_week` and
  asserts the terminal invalid path, so the invalidation gate is not a vacuous zero-count check.
- `runner_analysis._PRIVATE_PUBLIC_FIELDS = {"sleep_debt"}` — the "public-field audit" is a single
  hardcoded key name check. `FinalResult.as_dict` pops that exact key, so the audit is guaranteed to
  pass on any transcript this code produces. It is a regression test for one past leak, presented as
  a leak audit.

## 6. Gaming vectors identified from source (to be tested)

1. **`focus: "fallback"` at maximum load.** Schema validation for fallback only caps duration ≤30 min
   and sets ≤4 — **not load and not reps**. A planned `fallback` gets `readiness +0.10`,
   `fatigue_cost ×0.58`, `irritation ×0.55`, and a 25-min-class time cost, while still earning
   `focus_factor 0.60 × volume_units` where volume_units uses `load/true_capacity` up to 1.20. The
   engine's *coerced* fallback (`_as_fallback`) cuts load ×0.78 and reps to ≤6, but a directly
   planned one is untouched. `gpt-4.1-seed-10` runs exactly this from week 16 onward: 4×6 "fallback"
   at 95–102 kg for 28 minutes, and holds `pain_band: none` for the whole year.
2. **Partner coverage is a free resource.** `partner_coverage_hours` (≤16/wk) buys session time at
   zero cash cost; the only penalty is `reciprocity_gap = max(0, coverage - giveback)`, which is
   zeroed by setting `partner_giveback_hours` equal. Giveback also costs nothing. So `coverage=8,
   giveback=8` grants 480 free minutes/week with no strain.
3. **Household strain is nearly free.** At the ceiling (1.0) it costs 1.2 kg directly and ~18% of the
   recovery multiplier. gpt-4.1 sat at `critical` for ~35 weeks and still scored 93.91.
4. **Malformed output is nearly free.** A failed week falls back to `env.safe_action()`, a valid
   2×5 fallback session. A failed/invalid reactive turn defaults to `protect_recovery`, which
   *reduces* household strain by 0.025 — a garbage reactive responder is rewarded. `repair_calls`
   is logged but not scored.
5. **Excluded runs vanish from the mean.** `leaderboard_markdown` and `summarize` drop non-valid
   records before averaging, so a model whose bad seeds fail transport/structure checks is scored on
   its survivors. Exclusion count is displayed but not penalized.

## 7. Robustness question, stated precisely

Because the fitness signal has a 56-day time constant and the score is a single terminal measurement,
I predict the "one anomalous week" sensitivity is strongly **asymmetric in time**: near-zero cost for
a lost week in the first half, large cost for a lost week in the last ~6, and a large cliff for any
week that triggers `injury_recovery_days = 42` inside the final 6 weeks. To be measured.

---

# Measured results (run against the current code, after the notes above were written)

Scripts: `$CLAUDE_JOB_DIR/tmp/exp1..7.py`.

## A. Gate reproduction — the 12-week gate is seed-set dependent

| seed block | 12-wk separation | ordering | stable | GATE |
|---|---:|---|---|---|
| 0–19 (shipped) | 5.17 | PASS | PASS | **PASS** |
| 20–39 | 3.96 | PASS | **FAIL** (0.60) | **FAIL** |
| 40–59 | 4.84 | PASS | PASS | PASS |
| 100–119 | 6.33 | PASS | PASS | PASS |

Binding constraint is always `random<reckless` (0.60–0.90) and `rigid_or_reckless<skip` (0.65–0.75),
both sitting on the 0.65 threshold. The 52-week gate is solid (separation 10.19 / 6.67, all rates
≥ 0.75 on both blocks).

## B. Effective horizon — measured

Single lost week, scripted-expert, 52 weeks, seeds 0–7, mean Δ final 1RM:
W1 −0.02 · W10 −0.02 · W20 −0.06 · W30 −0.15 · W40 −0.54 · W48 −1.33 · W52 −2.03 kg.
**A lost week at the end costs ~100× a lost week at the start.**

Doing *nothing at all*:
- weeks 1–20 idle → 105.10 kg (97% of the full-year gain retained)
- weeks 1–40 idle → 99.75 kg (72% retained)
- weeks 1–48 idle → 96.44 kg (57% retained)

## C. Undiscovered exploit class — volume stacking (beats the top anchor by 38 kg)

`sets=8, reps=15` (schema maxima) at `load = 1.15 × estimated_1RM`, 5 days/week, 45-minute sessions,
`partner_coverage_hours=8` with `partner_giveback_hours=8` (free — giveback cancels the only penalty).

| policy | 52-wk mean | 12-wk mean |
|---|---:|---:|
| scripted-expert (gate's top anchor) | 105.75 | 99.12 |
| volume stacking, focus `volume` | 142.11 | — |
| volume stacking, focus `heavy` | **143.70** | **131.68** |
| gpt-4.1's max-load `fallback` pattern (2/wk) | 104.15 | — |
| shipped red team: weekly-maxing / estimate-gaming / sleep-sacrifice / final-test-gambling | 84.10 / 86.03 / 98.47 / 103.79 | — |

Root cause: `volume_units = sets*reps/20` is capped only by the schema (max 6.0 per session) and is
**not coupled to `duration_min`** — 120 reps in 45 minutes is legal. With `fit_tau=56d` vs
`fatigue_tau=6d` and `2.60` vs `0.25` kg coefficients, fatigue offsets ~1% of fitness, so nothing
bounds accumulation except tendon irritation, which the `on_pain_warning: skip` standing rule
self-manages.

Every guardrail reports green on it. Single-seed demo transcript (seed 3, 157.18 kg):
```
Public-field audit: PASS · Transport-error audit: PASS
Transcript-structure audit: PASS · Invalid-episode audit: PASS
Observed transcript behaviors: No exploit signature crossed the analyzer thresholds.
```
`pain_days = 0.0`, `household_strain = 0.01`. `pain_days` only increments on days where pain stage ≥ 1
**and** sleep < 6.0 h, so `sleep_protection: strong` zeroes the pain metric regardless of injury state.

## D. Historical regression: invalidation was dead code — resolved

The older packaged copy and pre-recalibration reports documented an invalidation path that the
source did not actually execute. That finding motivated the current terminal `_BudgetInsolvency`
path and its explicit regression test. The old reports and packaged copy are not release artifacts.
