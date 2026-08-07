# Bench-bench v0.1 Benchmark Card

Engine/config hash for this artifact set: `sha256:5bd2bc4dbdcf35846c87adf5102851b42692f1dcab9b35144a3b7bca0405dd27`

## Summary

Bench-bench evaluates long-horizon operational decision-making. An agent
manages one simulated year for Dave, a 38-year-old returning lifter with a
full-time job, full-time working partner, six-month-old baby, limited
discretionary money, and commercial-gym access. The headline question is:

> How much can the agent bench after a year without letting the rest of the
> routine collapse?

Version 0.1 ships the model-only track. There is no web corpus, search tool, or
open-web track in this release.

## Protocol and horizon

- A full episode is 52 simulated weeks, or 364 simulated days. It is a
  benchmark year, not a claim about a 365-day calendar year.
- The agent submits one structured weekly plan: sessions, life allocations,
  capital purchases, a career fork choice when offered, and standing rules for
  sleep, pain, and illness.
- The simulator executes days internally. Seeded illness, closure, travel,
  work, or household events can create short reactive decisions.
- The headline score is the arithmetic mean of three hidden standardized-test
  projections taken after weeks 44, 48, and 52. Each projection uses the fixed
  three-day test protocol and is read-only: it does not alter the episode.
- Test timing is hidden from the acting model. A 12-week configuration is a
  development diagnostic and does not constitute the release horizon.
- After four consecutive productive weeks, each subsequent productive week
  adds 0.10 kg to durable base capacity. This is the current consistency drift
  mechanic.
- The release horizon is 52 weeks only. The 12-week configuration is a
  development diagnostic and has no release-gate status.
- Calibration uses development seeds 0–19. Those values are burned and never
  serve as public leaderboard seeds. The public leaderboard will use seeds
  100–109; ten private evaluator seeds are supplied out of band and are not
  recorded in this repository.
- The release gate requires the original 65% minimum adjacent paired-order
  rate, at least 3σ expert-versus-random separation, the intended aggregate
  ordering, and endogenous loss by reckless-maximalist. Report means, seed
  spread, and per-seed results—not a best-seed score.

## Persona and visible state

Dave starts at 84 kg body mass and an 84 kg estimated 1RM. He has a commercial
gym membership and no home equipment; the household has a $250/month
discretionary budget. Observations show noisy estimated 1RM, coarse sleep,
energy, soreness, pain, illness, nutrition, time, budget, equipment, known
obligations, and recent outcomes.

The simulator hides true capacity, fitness, fatigue, sleep debt, recovery
capacity, volume tolerance, injury-prone joint, adherence noise, and the
future random interrupt calendar. Hidden values affect visible feedback but
are never placed in model prompts or public episode logs. Sleep debt remains
available to evaluator-side baseline summaries but is omitted from public
episode and model-runner result records.

## Simulator assumptions

Strength uses a deliberately coarse Banister-style fitness-fatigue impulse
response with delayed adaptation, recovery gating, technique proficiency,
tendon irritation, endogenous adherence, and consistency-based base-capacity
drift. The event calendar includes the baby sleep arc, daycare illness
exposure, work crunches, travel, gym crowding, household shocks, and capital
decisions. These are benchmark-designed mechanics, not a physiological model.

## Scoring and validity

Headline score is the averaged hidden-test 1RM. Secondary reporting includes
improvement, productive weeks, completed and missed sessions, fallback use,
pain burden, sleep debt, household strain, spending, and repair counts.

Budget and schema errors are handled through validation, one repair attempt,
and a safe fallback. If an execution-time charge nevertheless exceeds the
available cash ledger, the episode terminates immediately, records an
`episode_invalidated` event, and sets a non-null `invalid_reason` in its final
result. The analyzer and leaderboard exclude such episodes automatically.
The current 52-week calibration suite contains zero invalid episodes.

## Current validation

The six scripted baselines were evaluated on development seeds 0–19 under the
current 52-week configuration. These are burned calibration values, not the
public leaderboard seed set:

| Policy | Mean final 1RM (kg) | Seed SD (kg) |
|---|---:|---:|
| scripted-expert | 105.03 | 0.77 |
| recovery-aware | 101.02 | 0.85 |
| skip-when-busy | 97.89 | 1.17 |
| rigid-linear | 92.71 | 1.47 |
| reckless-maximalist | 90.10 | 0.97 |
| random | 88.43 | 1.06 |

Ordering is `expert > recovery-aware > skip-when-busy > rigid-linear >
reckless > random`. The expert–random gap is 16.604 kg, or 17.901 pooled
seed SDs. The 65% adjacent-order criterion passes; reckless loses
endogenously; all 20 baseline episodes are valid.

The 12-week diagnostic has 6.216σ expert–random separation but fails the
stable-ordering diagnostic, so it is not a release gate. In the fresh
52-week adversarial search, the best valid candidate scored 104.44 kg against
the 105.03 kg expert; no candidate beat expert, required human review, or
blocked release. The volume-stacking and 8×4 regression families scored about
82.12 kg; the over-ceiling authored fallback family was invalid in search.

## Public leaderboard status

No public model leaderboard is generated at this commit. The authoritative
leaderboard is intentionally not generated until independent review and a live
run on public seeds 100–109 are complete. The prior model transcripts used seeds 0–9, which are
burned calibration artifacts and have been archived outside the repository;
they are not a leaderboard.

## Intended interpretation

A higher score means better decisions in this deterministic simulated
environment. It does not establish that a model gives safe real-world
exercise, medical, sleep, nutrition, or relationship advice. The benchmark
does not model diagnoses, clinical care, postpartum guidance, biomechanics, or
all household dynamics.

## Reproduction

The current deterministic artifacts are listed in `release_manifest.json` and
all carry the engine/config hash above.

```bash
python3 -m bench_bench baselines --weeks 52 --seed-count 20 \
  --json reports/current_baseline_gate.json \
  --markdown reports/CURRENT_BASELINE_GATE.md

python3 -m bench_bench baselines --weeks 12 --seed-count 20 \
  --json reports/current_12_week_diagnostic.json \
  --markdown reports/CURRENT_12_WEEK_DIAGNOSTIC.md

python3 -m bench_bench redteam --weeks 52 --seed-count 20 \
  --weekly-stimulus-cap 1.0 \
  --json reports/current_adversarial_search.json \
  --markdown reports/CURRENT_ADVERSARIAL_SEARCH.md

python3 scripts/verify_artifacts.py
```

The public leaderboard is not regenerated by the calibration commands above.
Private seed values are evaluator-held outside this repository and are not
present in source, tests, configs, reports, or the release manifest.
