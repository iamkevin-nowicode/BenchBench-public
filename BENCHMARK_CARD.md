# Bench-bench v0.2 Benchmark Card

Engine/config hash for this artifact set: `sha256:438c1d77d284450cd4e3da2eac9fcda83c45bfb81f7a67598c62763d96602a52`

Prompt hash for this artifact set: `sha256:06d96111ac9db67e92f1a26d00f84e986ea95d13fc2acf0825b97be112ef0d27`

This is the v0.2 protocol candidate after prompt freeze, the deterministic
rehearsal, and the four-model seed-400 paid smoke. No public model leaderboard
is claimed by this checkout; the ten-seed public run remains pending.

## Summary

Bench-bench measures long-horizon configuration and programming quality under
recurring disruption. An agent coaches Dave for one simulated year, plans
training and life allocations under a finite time and cash ledger, and tries
to maximize his bench press without voiding the episode through pain or
household overload.

The benchmark is a measurement of this deterministic simulated environment.
It is not evidence that a model gives safe real-world exercise, medical, sleep,
nutrition, or relationship advice. It does not measure episode-specific hidden-
trait inference: that limitation is reported in the Phase 3 certification
artifacts rather than implied away by the prompt.

## Protocol and horizon

- A full episode is 52 simulated weeks, or 364 simulated days. “One year” is
  the benchmark horizon, not a claim about a 365-day calendar year.
- The agent submits one structured weekly plan. Seeded events can create
  short reactive decisions during the week.
- The headline score is the average of three standardized tests at weeks 44,
  48, and 52, each after a fixed three-day taper. The test timing is disclosed
  protocol, not hidden state.
- After four consecutive productive weeks, each subsequent productive week
  adds 0.10 kg to durable base capacity. This is a documented simulator
  mechanic, not a claim about universal physiology.
- The six scripted baselines are calibration diagnostics. The current
  52-week six-policy legacy ordering diagnostic does not serve as the v0.2
  release gate; the held-out ladder and oracle certification artifacts do.
- v0.2 public leaderboard seeds are 400–409. Tuning, certification,
  regression, public, and private seed pools are disjoint. Private seed values
  are held outside this repository.

## Persona and observations

Dave trained casually in his twenties, has not lifted seriously in years, and
returns with no meaningful recent training base. He tests at 84 kg bench and
84 kg body mass at week 0. He has no prior peak to recover; his trajectory is
new-training progression, not recovery of an old max. He has a full-time job,
a full-time working partner, a six-month-old infant at the start, commercial
gym access, no home equipment, and $250/month of discretionary money that
carries over.

Observations are banded and noisy. True capacity, fatigue, recovery capacity,
sleep debt, volume tolerance, injury-prone joint, adherence noise, and future
interrupts are not exposed. Sessions that are planned are not guaranteed to
happen.

## Public action contract

The executable constraint inventory is
[`bench_bench/constraint_inventory.py`](bench_bench/constraint_inventory.py),
and the runner renders its entries into the weekly and reactive system
prompts. The conformance test checks both inventory-to-prompt and
prompt-to-inventory directions.

The action contract includes strict field types and the documented ranges for
SessionPlan, LifeAllocation, StandingRules, WeekAction, ReactiveAction, and
the notebook wrapper. Cross-field rules include fallback sessions capped at
25 minutes/3 sets/6 reps, test sessions requiring one rep, unique purchases,
one session per day, at most five weekly sessions, reactive days 0–6, and
non-overlapping cancel/fallback lists.

The announced week-24 promotion fork is a neutral mechanic: accepting the
stretch project grants 12000¢ and creates an eight-week stretch-project period
with additional work/time pressure; protecting time reduces work strain by
0.04; deferring applies neither branch.

Authored fallback loads above 0.78× the observed estimated 1RM are rejected
and repaired; they are not silently clipped. Weekly ledger, cash, reactive
spend, and scheduled household-shock reserve violations are also rejected.
Every invalid action receives one repair attempt; a still-invalid action is
replaced by a safe fallback.

The engine can transform an otherwise accepted plan during execution.
Transformations are counted and reported in weekly outcomes as
`transformed_sessions`, `transformation_reasons`,
`reactive_action_fallbacks`, and `attempted_sessions`.

## Time, money, and sleep mechanics

The weekly ledger has 900 total minutes. 180 fixed household minutes are
already committed, leaving 720 minutes for authored weekly allocations. The
observation reports `weekly_time_budget_minutes=720` and
`weekly_fixed_household_minutes=180`, so the available amount is not confused
with the total.

Sleep protection costs 0 minutes for `none`, 30 for `standard`, and 60 for
`strong`. Severe sleep degrades execution and recovery. The protocol does not
state or assume a score value for sleep protection.

Delegated chores cost 1200¢ per hour; reactive childcare costs 1400¢ per hour.
A gym session includes 20 commute minutes; a home session includes 10 overhead
minutes. Training, meal prep, childcare, chores, partner coverage, partner
giveback, and sleep protection all draw from the same weekly ledger.

## Scoring and validity

The score is void when `pain_days > 14`, or when household strain meets either
branch of the hard rule: at least four weeks at or above 0.75, or a final-third
mean above 0.75. Sleep debt remains a reported diagnostic and is not a second
pass/fail constraint.

Raw scores remain visible beside counted scores. Counted aggregates require
100% of expected seeds to be compliant; violated seeds are not silently
dropped. Structurally invalid episodes are excluded automatically by the
analyzer and leaderboard.

## Current six-policy diagnostic

These figures are regenerated from current source on development seeds 0–19.
They are not public-model results and are not the v0.2 release gate.

| Policy | Raw mean (kg) | Counted mean (kg) | Raw seed SD | Counted seed SD | Violations |
|---|---:|---:|---:|---:|---|
| scripted-expert | 106.90 | 106.90 | 0.97 | 0.97 | — |
| rigid-linear | 101.88 | — | 0.88 | — | household strain |
| recovery-aware | 101.13 | 101.13 | 0.87 | 0.87 | — |
| skip-when-busy | 96.46 | 96.46 | 1.07 | 1.07 | — |
| reckless-maximalist | 95.04 | — | 0.61 | — | pain + household strain |
| random | 90.72 | — | 1.26 | — | household strain |

Raw ordering is `expert > rigid-linear > recovery-aware > skip-when-busy >
reckless > random`; the legacy stable-ordering diagnostic fails under the
current hard household constraint. The expert–random gap is 16.173 kg, or 14.402 pooled seed SDs. Reckless loses endogenously on raw score and has the
highest pain burden, but its counted aggregate is unavailable because its
episodes violate the constraints.

The 12-week diagnostic has 5.212σ expert–random separation and is not a release
gate.

The current widened adversarial search's best valid candidate scored 108.86 kg
against the 106.90 kg expert. This is a healthy legal-policy margin, not an
automatic release block: the candidate has no abuse signature, no human-review
flag, and no release-blocking signature. The search report retains raw score,
counted fraction, and liveness/feasibility diagnostics.

The free full-pipeline rehearsal is persisted in
[`reports/CURRENT_DETERMINISTIC_REHEARSAL.md`](reports/CURRENT_DETERMINISTIC_REHEARSAL.md)
and [`reports/current_deterministic_rehearsal.json`](reports/current_deterministic_rehearsal.json).
It contains the analyzer leaderboard, counted-seed fractions, and per-policy
constraint-violation attribution.

The paid smoke is persisted separately in
[`reports/CURRENT_V02_SMOKE_ANALYSIS.md`](reports/CURRENT_V02_SMOKE_ANALYSIS.md)
and retained as the four-transcript archive
[`artifacts/v0.2-smoke-20260815-transcripts.tar.gz`](artifacts/v0.2-smoke-20260815-transcripts.tar.gz)
with manifest
[`artifacts/v0.2-smoke-20260815-manifest.json`](artifacts/v0.2-smoke-20260815-manifest.json).
It exercises seed 400 for all four lineup models across the full 52-week scoring
horizon; it is a pipeline smoke, not a leaderboard aggregate.

The current smoke scores were Opus 5 **101.40 kg**, GPT-5.6 Sol **96.94 kg**,
Grok 4.6 **100.35 kg**, and Muse Spark 1.2 **99.96 kg**. Episode costs were
$6.397017, $3.034434, $1.090688, and $1.034016 respectively. Opus recorded
351,874 cached-read input tokens and 6,958 cache-creation input tokens under
the Anthropic ephemeral 1-hour cache. These figures are pipeline accounting
results, not public leaderboard scores.

## Public leaderboard status

The authoritative public leaderboard is intentionally not generated before
the final public run. Its named output will be `reports/PUBLIC_LEADERBOARD.json` and
`reports/PUBLIC_LEADERBOARD.md`, generated from
`runs/v0.2-public-leaderboard` with `build-leaderboard`.

The v0.1 pilot remains historical evidence in the tracked archive. Its Kimi
episodes are reported as transport-excluded rather than as counted model
decisions.

The v0.2 public lineup is Claude Opus 5, GPT-5.6 Sol, Muse Spark 1.2, and
Grok 4.6. Kimi K3 is explicitly excluded: the pilot recorded 702 transport
failures and four episodes with zero successful model decisions, so those
episodes are unscoreable rather than a model result.

## Reproduction and rehearsal

```bash
python3 -m pytest
python3 scripts/run_deterministic_rehearsal.py \
  --output-dir /private/tmp/bench-bench-v02-rehearsal \
  --weeks 52 --seed-values 400,401,402,403,404,405,406,407,408,409
python3 -m bench_bench build-leaderboard \
  --input-dir /private/tmp/bench-bench-v02-rehearsal \
  --json /private/tmp/bench-bench-v02-rehearsal/leaderboard.json \
  --markdown /private/tmp/bench-bench-v02-rehearsal/leaderboard.md
python3 scripts/verify_artifacts.py
```

The paid smoke is deliberately separate from the leaderboard and has completed
on seed 400. Every transcript records both the engine/config hash and prompt
hash, plus sanitized endpoint and sampling metadata. The ten-seed public run
has not been started.
