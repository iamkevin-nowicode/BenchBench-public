# Codex Build Sequence

## Initial message

Read all Markdown files in this repository.

Bench-bench is a serious long-horizon agent benchmark. I am the product owner and benchmark designer, and I do not write code.

You own architecture, implementation, tests, scripts, documentation, debugging, reproducibility, and demonstrations.

Do not ask me to manually edit source code.

Challenge assumptions that weaken validity, safety, or interpretability.

Work only on the active milestone.

At each milestone report what changed, commands run, test results, a nontechnical demonstration, assumptions, unresolved risks, and decisions needing approval.

## Milestone 0 — Architecture

Design repository structure, simulator modules, state model, actions, events, replay, scoring, baselines, evaluation harness, and tests.

Do not implement the simulator.

Deliver `ARCHITECTURE.md`, `STATE_MODEL.md`, `ACTION_SCHEMA.md`, `EVENT_MODEL.md`, `TEST_PLAN.md`, and `MILESTONES.md`.

Stop for approval.

## Milestone 1 — Evidence and causal map

Research the evidence plan.

Create `research/EVIDENCE_CATALOG.md`, `research/CAUSAL_MAP.md`, `research/EVIDENCE_GAPS.md`, and `research/MECHANIC_PROPOSALS.md`.

Separate evidence from benchmark design.

Stop for approval.

## Milestone 2 — Twelve-week vertical slice

Implement one canonical person, daily steps, weekly summaries, bench training, sleep, work, childcare, chores, nutrition, budget, fatigue, adaptation, warning signals, missed sessions, and deterministic events.

Add random, rigid progression, recovery-aware, reckless maximalist, and skip-when-busy baselines.

Test determinism, accounting, hidden-state separation, delayed adaptation, fatigue, warning progression, replay fidelity, and invalid actions.

Stop for approval.

## Milestone 3 — Validity audit

Run baselines across seeds, create exploit agents, and perform ablations.

Produce `VALIDITY_REPORT.md`, `EXPLOIT_REPORT.md`, `ABLATION_REPORT.md`, and `DESIGN_REVISIONS.md`.

Stop for approval.

## Milestone 4 — Agent runner

Implement model-only and tool-enabled tracks, provider-neutral adapters, retries, logging, cost tracking, and resumable episodes.

Stop for approval.

## Milestone 5 — Full year

Expand to 52 weeks with seasons, work periods, travel, illness, family events, equipment changes, budget shocks, progression blocks, deloads, and strategic testing.

Re-run validation.

Stop for approval.

## Milestone 6 — Red-team and release

Attack score validity, unsafe incentives, scaffold confounds, hidden-state leakage, fixed-policy exploits, final-test gaming, seed sensitivity, and documentation.

Deliver the benchmark card, reproducibility guide, quickstart, release checklist, paper outline, limitations, and leaderboard rules.
