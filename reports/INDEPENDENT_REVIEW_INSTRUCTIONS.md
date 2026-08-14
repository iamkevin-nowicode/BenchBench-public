
# Independent review brief for Bench-bench v0.1

Engine/config hash under review: sha256:fdbd829339622163df8a27d64fe6467e353c1b2bd8ff289b25e36783e8d2e9a1

This is the exact brief to give an independent reviewer with access to the repository. Review the original five-model public run only. Do not include later model extensions.

## Assignment

Write an evidence-based review that answers:

1. What does the benchmark actually measure under the current engine and prompt?
2. What do the five-model public results support, and what do they not support?
3. Which differences are model behavior, provider/transport behavior, or prompt/schema artifacts?
4. Is the repository ready for public release, and what exact blockers remain?

Do not tune the simulator, edit prompts, rerun providers, change seeds, or delete transcripts. This is diagnosis and review, not repair.

## Scope

Include only Claude Opus 5, Grok 4.5, Muse Spark 1.2, GPT-5.6 Sol, and Kimi K3.

Use public seeds 100–109, 52 weeks, and the five-model transcripts. Treat scripted baselines on seeds 0–19 as a separate calibration set. Do not make paired claims across those two seed populations.

## Read in this order

1. BENCHMARK_CARD.md
2. release_manifest.json
3. docs/DECISIONS.md
4. ENGINEER_BRIEF.md
5. REVIEW_AND_BUILD_PLAN.md
6. reports/final_public_leaderboard.json
7. reports/FINAL_PUBLIC_LEADERBOARD.md
8. reports/current_baseline_gate.json
9. reports/CURRENT_BASELINE_GATE.md
10. reports/current_adversarial_search.json
11. reports/CURRENT_ADVERSARIAL_SEARCH.md
12. reports/CURRENT_12_WEEK_DIAGNOSTIC.md
13. reports/CURRENT_VERIFICATION.md

Then inspect:

- bench_bench/config.py
- bench_bench/engine.py
- bench_bench/schemas.py
- bench_bench/scoring.py
- bench_bench/runner.py
- bench_bench/runner_analysis.py
- bench_bench/evaluation.py
- bench_bench/adversarial.py
- bench_bench/policies.py
- bench_bench/events.py
- bench_bench/provenance.py

SOURCE_DERIVED_NOTES.md contains useful historical and auxiliary analysis. Distinguish those measurements from artifacts reproducible by a named repository command.

## Transcript inspection

Inspect all 50 JSONL transcripts under:

    runs/live-full-20260808/
    runs/live-grok-4.5-full-20260811/

Start with the first and last records of every transcript. Inspect at least:

- Opus seeds 100, 104, 109 for high repairs and coach_note failures.
- Grok seeds 100 and 104 for early nested-schema failures.
- Muse seeds 100 and 103 for flattened weekly schema failures.
- GPT seeds 101 and 106 for ledger and interrupt cases.
- Kimi seeds 100, 103, 104, 106, and 109 for the transition to transport-dominated episodes.

Verify for every transcript:

- run_start.engine_config_hash matches the current hash;
- endpoint metadata is sanitized and contains no key, bearer token, userinfo, or query credential;
- model string, provider, temperature, effort, and pricing metadata are recorded;
- weeks are complete and ordered 1 through 52;
- run_end.result contains final_1rm_kg, pain_days, and invalid_reason;
- transport failures and rejected model outputs are counted separately;
- weekly and reactive fallbacks are visible;
- planned, transformed, attempted, completed, missed, and fallback counters are distinct;
- evaluator-only fields such as true capacity, fatigue, recovery capacity, volume tolerance, and sleep debt are absent.

Read-only checks:

    rg --files runs/live-full-20260808 runs/live-grok-4.5-full-20260811 | rg '\.jsonl$' | wc -l

    rg -n -i 'api[_-]?key|authorization:|bearer |sk-[A-Za-z0-9]' runs/live-full-20260808 runs/live-grok-4.5-full-20260811 reports/final_public_leaderboard.json

    python3 -m bench_bench analyze-runs --help

Use the project analyzer where possible. A one-off analysis script must not save credentials, transcript contents, or private seed values.

## Statistical requirements

Reproduce and report:

- the 5×10 per-seed score matrix;
- mean, sample seed SD, range, and counted fraction;
- paired differences on the same public seeds;
- two-sided 95% paired t intervals with df=9;
- per-pair seed win/loss/tie counts;
- repairs and transport failures separately;
- API cost per episode and total cost;
- pain violations and structural invalidations.

Do not average only surviving seeds, silently remove Kimi transport-dominated seeds, call the pooled-SD gate ratio a p-value, or treat descriptive ten-seed intervals as repeated-sampling confidence in model weights.

For Kimi, report the complete ten-seed result and a clearly labelled diagnostic split at seeds 100–103 versus 104–109. The split explains transport contamination; it is not a replacement aggregate.

## Prompt/schema audit

Read the exact prompt strings in bench_bench/runner.py and compare every field in bench_bench/schemas.py to the prompt.

Check whether the weekly prompt states:

- the complete nested action, life, rules, coach_note, and notebook_update shape;
- the 600-character coach_note limit;
- the 2,000-character notebook_update limit;
- fallback duration, set, rep, and authored load caps;
- one repair followed by safe fallback;
- purchases nested under life;
- the shared 900-minute ledger and cash constraints.

Check the reactive prompt for:

- every ReactiveAction field;
- the 300-character note limit;
- the extra_childcare_hours ledger rule;
- the cash-reserve rule;
- one valid nested example.

Classify each repair as documented schema, undocumented constraint, prompt-shape/nesting, budget/time ledger, reactive cash reserve, transport, malformed JSON, or other format. Do not collapse all causes into one repair-quality number.

## Engine and scoring audit

Trace BenchEnvironment to FinalResult and confirm:

- the headline score is the average of three standardized tests;
- the fixed taper is used;
- weekly estimated 1RM is not the score;
- pain_days is a non-boolean integer and pain_days greater than 14 voids counted score;
- missing pain_days fails closed;
- invalid episodes terminate with invalid_reason and are excluded automatically;
- raw score remains available when counted score is unavailable;
- counted means require the complete expected seed set;
- public observations and transcripts do not expose evaluator-only state;
- every simulator-side action transformation is either rejected visibly or surfaced and counted.

Explicitly audit rep-rate/duration clipping, load-ratio clamping, home-equipment caps, fallback conversion, gym-closed/no-rack cancellation, numeric-string or sentinel coercion, reactive collapse to protect_recovery, and budget rejection.

Identify every remaining silent correction that is not visible in an outcome or repair record.

## Calibration and adversarial audit

Run:

    python3 -m bench_bench baselines --weeks 52 --seed-count 20 --json /tmp/bench-baseline.json --markdown /tmp/bench-baseline.md

    python3 -m bench_bench baselines --weeks 12 --seed-count 20 --json /tmp/bench-12-week.json --markdown /tmp/bench-12-week.md

    python3 -m bench_bench redteam --weeks 52 --seed-count 20 --weekly-stimulus-cap 1.0 --json /tmp/bench-adversarial.json --markdown /tmp/bench-adversarial.md

Confirm 52-week ordering, adjacent win rates, expert–random separation, reckless pain violations, 12-week ordering failure, rack ablation, best valid adversarial candidate, counted fractions, and the difference between human-review margin and abuse signature.

## Required deliverable

Structure the review as:

1. Scope and protocol.
2. Reproducibility audit.
3. Mechanics audit.
4. Calibration and adversarial audit.
5. Live results.
6. Model behavior versus provider behavior versus prompt artifacts.
7. Limitations.
8. Release verdict with every blocker tied to a file, line, transcript, or command.

Label conclusions as Observed, Reproduced, or Inferred. Do not recommend tuning constants until artifact reconciliation and prompt-documentation issues are resolved.
