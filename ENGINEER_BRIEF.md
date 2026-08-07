# Bench-bench — Engineering Brief

*From: Kevin (product owner / benchmark designer). You own architecture, code, tests, and reproducibility. Full background: `REVIEW_AND_BUILD_PLAN.md`. Original spec pack: `docs/` (treat as design intent, not contract — this brief supersedes it where they conflict).*

## What we're building

A long-horizon decision-making benchmark. An LLM agent manages one simulated year in the life of a 38-year-old father of an infant, allocating time, sleep, money, and family goodwill to maximize his bench-press 1RM at a standardized week-52 test. Score = final 1RM, mean over fixed seeds.

## v1 scope — build exactly this, nothing more

- **Model-only track.** No web corpus, no search tools, no open-web browsing, no prompt-injection suite. Those are v2 if v1 earns attention.
- **One canonical persona:** "Dave," 38, returning lifter, 84 kg bodyweight, estimated 1RM 84 kg, full-time job, partner works full-time, 6-month-old baby, $250/mo discretionary budget, commercial gym membership, no home equipment.
- **Weekly decision cadence**, not daily turns. Each simulated Sunday the agent submits: (a) the week's session plan (day, location, intensity/volume targets, duration cap), (b) life allocations (meal prep, spending, chore delegation, sleep protection), (c) standing contingency rules ("if night sleep < 5 h, convert session to 25-min fallback"). The sim executes the week internally, applying those rules; mid-week interrupt events (illness onset, daycare closure, gym closed) pause for a short reactive decision. Target ~70–80 model calls per 52-week episode.
- **Python 3.11+, pydantic schemas, no heavy dependencies** in the sim. Episode log = JSONL. Provider-neutral runner (litellm or thin HTTP adapters).
- **Naming:** the project is **Bench-bench** (hyphenated, exactly that capitalization) everywhere — docs, README, output. Repo `bench-bench`, Python package `bench_bench`. Never write "BenchBench": that is a different, unrelated benchmark Kevin runs in parallel.
- Engine is 52-week-native from day 1; validation runs on a 12-week config first.

## Non-negotiable invariants

1. **Determinism.** Same version + seed + action sequence replays byte-identically. Master seed pre-rolls the event calendar and noise streams; interrupts consume a dedicated stream so alternate choices don't reshuffle the future.
2. **Hidden state never leaks.** The agent sees noisy estimates (estimated 1RM ±3–5%, coarse energy/soreness/sleep-quality ratings), never true capacity, fatigue, or the event calendar.
3. **Model output influences decisions only.** Nothing the agent says can directly alter state or score — only validated actions do.
4. **Consequences are endogenous, not gate-based.** An injury costs ~6 simulated weeks of reduced training; reckless play loses on the scoreboard itself. Hard episode invalidation only for egregious patterns (sustained obligation abandonment, budget insolvency).
5. **Formatting must not dominate.** Invalid action → clear error → one repair attempt → safe fallback. Log repair counts per model.

## Core simulator model (keep it this simple)

- **Strength:** Banister fitness–fatigue impulse response — `capacity(t) = base + Σ stim·e^(−Δt/τ_fit) − Σ stim·e^(−Δt/τ_fat)` — stimulus scaled by load/volume/specificity, **gated by recovery multiplier** (sleep × nutrition × stress). This gives delayed adaptation, overtraining, taper, and detraining from ~10 tunable parameters.
- **Plus:** technique proficiency (caps capacity→1RM conversion, grows with frequency), tendon-irritation accumulator driving a 6-stage pain ladder, adherence probability (motivation × fatigue × household strain — planned sessions can silently fail).
- **Per-seed hidden variation:** recovery capacity, volume tolerance, injury-prone joint. There must be no single memorizable optimal program — the agent has to read its athlete from feedback.
- **Difficulty lives in logistics, not physiology.** Any sane progression should work; the differentiator is executing through the year: baby sleep regressions (~months 2–3 and 7–8), daycare start → illness waves (month 3+), holiday travel, New Year gym crowding, work crunches announced 2–3 weeks ahead, a promotion-vs-time fork, partner reciprocity meter, 4–6 one-off shocks, and three capital decisions (home rack ~$600, recurring childcare, meal-prep subscription). Full year arc: REVIEW_AND_BUILD_PLAN.md Part 2.

## Build order and exit gates — do not skip ahead

**Phase 1 (≈1 wk): Playable sim.** Engine + observation renderer + action validation + a CLI so a human can play it (`play --seed 3`). Determinism and accounting tests. *Exit: Kevin plays a 12-week game and can feel the trade-offs; a log replays identically.*

**Phase 2 (≈1 wk): Baselines + separation gate. This is the real work.** Six scripted policies: random, rigid-linear, reckless-maximalist, skip-when-busy, recovery-aware, scripted-expert. Run all × 20 seeds; tune parameters until: ordering is correct and stable, **(expert − random) / pooled seed std ≥ 3.0**, reckless loses endogenously, quick ablations show each mechanic actually moves decisions (cut any that don't). *Exit: tuning report with these numbers. Nothing downstream matters if this gate fails.*

**Phase 3 (≈1 wk): LLM runner.** Structured output, retries, transcript + cost logging, resumable episodes, rolling context window plus an agent-maintained "coach's notebook" as the memory mechanism. Run 4 models × 5 public seeds × 12 weeks. *Exit: mini-leaderboard + a written list of observed exploits and degenerate behaviors from reading transcripts.*

**Phase 4 (≈2 wks): Full year + ship.** 52-week config, re-run the Phase 2 gate, run deterministic automated adversarial search over legal action fields (with volume-stacking and compressed-fallback boundary genomes as regression seeds) and patch. Package: repo, quickstart (one command evaluates any OpenAI-compatible endpoint), benchmark card with honest limitations, single-file HTML replay viewer that renders an episode as a scrollable year, 10 public + 10 private seeds. *Exit: v0.1 public and reproducible by a stranger.*

## Process rules

- Every phase ends with something runnable — never documents alone.
- Governance docs capped at ~8 files total; a new .md must replace one.
- No audit/preregistration/remediation documents before there's a leaderboard with real models on it.
- Stop and flag me at each phase exit and for any decision that changes scoring, the action schema, or the persona. Everything else: decide, log it in `DECISIONS.md`, keep moving.
- Challenge anything here that you think weakens validity — but with data from the sim, not with more specification.
