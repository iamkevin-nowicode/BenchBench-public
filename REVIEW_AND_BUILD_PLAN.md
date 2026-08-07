# Bench-bench — Review, Analysis, and Build Plan

*Review of `bench_bench_handoff_v3` · 2026-08-02*

---

## Part 1 — Verdict on the handoff pack

The conceptual design is genuinely strong. Validity-first thinking, deterministic replay, hidden-state separation, exploit catalogs, secondary scorecards, "reckless can't win" — most benchmark projects never get this rigorous. The idea itself is good: a memorable public hook ("how much can your model bench?") wrapped around a real research question (long-horizon resource allocation under delayed consequences). It sits in the same family as Vending-Bench but with a richer state space: multiple coupled resources (time, sleep, money, goodwill, tissue tolerance) instead of one cash balance.

Three problems will kill it as specified, though:

### Problem 1 — Scope is a multi-year program, not a benchmark v1

The pack specifies three tracks, a synthetic web corpus with 12 tools, 13 baseline policies, prompt-injection challenge documents, and an open-web browsing harness. The frozen corpus alone is a second full benchmark (synthetic forum posts with hidden accuracy labels, a deterministic search engine, ranking that mixes quality levels...). Every one of these is defensible; together they guarantee the project dies in documentation.

There is a live reference point for this risk: BenchBench (Kevin's separate, parallel benchmark project — the city public-bench simulator) has run this same doc-driven, milestone-gated, agent-built process, and after 7 milestones it carries 70+ governance markdown files, preregistrations, and remediation reports while a public release and model leaderboard are still outstanding. The v3 handoff's 9-step Codex sequence reproduces that process almost exactly; Bench-bench should deliberately run leaner.

**Fix:** v1 = model-only track, one canonical persona, ~6 baselines, weekly cadence. Frozen-web is v2, only if v1 gets traction. Open-web is v3 or never. Collapse 9 milestones into 4 phases (Part 4).

### Problem 2 — The simulator's dynamics ARE the benchmark, and that cuts both ways

The score is a deterministic function of decisions in a hand-designed causal model. This creates a dilemma the spec pack never names:

- **If the dynamics faithfully track public strength-training knowledge**, every frontier LLM already knows the optimal policy. Linear progression → 531-style periodization → deload when fatigued is memorized text. Headroom collapses; all competent models bench within noise of each other and the benchmark measures formatting discipline.
- **If the dynamics deviate from real physiology**, real-world knowledge actively misleads, and the benchmark measures "system identification of an arbitrary hidden model" — which is a valid task but not the one being advertised.

**Fix — three moves:**

1. **Shift difficulty from physiology to logistics.** Make the training-response model coarse and forgiving (any sane progression works). Make the *hard* part executing consistently through a hostile year: the model that correctly pre-positions for the daycare-germ wave, buys the home bench before the December gym closure, and uses 25-minute fallback sessions instead of cancelling — that model wins. Life management is not memorized text; this is where long-horizon decision quality actually differentiates.
2. **Per-seed latent responsiveness.** Randomize (per seed, hidden) the persona's recovery capacity, volume tolerance, and injury-prone joint. The agent must infer its athlete from noisy feedback across weeks — no single memorizable optimum, and "interpreting noisy feedback" becomes load-bearing instead of decorative.
3. **Noisy estimated-1RM observation.** The agent's visible 1RM estimate should carry ±3–5% noise and update slowly, so gradient-climbing the observable is a losing strategy and only the hidden capacity matters at the final test.

### Problem 3 — Nobody has checked whether the score can discriminate

A realistic year for a 38-year-old returning lifter is maybe +10–20% on bench. If the reckless baseline lands at 102 kg and the oracle at 110 kg, seed noise swamps the signal and the leaderboard is a random-number generator. This is the single most likely quiet failure, and the validation plan treats it as one experiment among many instead of the gate everything hangs on.

**Fix:** define a hard **separation gate** before any model touches the benchmark:

> separation ratio = (scripted-expert mean − random mean) / pooled per-seed std ≥ 3.0

Tune simulator parameters until this holds across 20 seeds and the baseline ordering (random < reckless ≈ rigid < skip-when-busy < recovery-aware < scripted expert) is stable. Same seeds for every model (paired design), report mean over ≥5 seeds per model. Widening the dynamic range is legitimate design freedom: a simulated year can compress "what consistency vs. chaos does over 3 real years" as long as the direction and delays stay realistic.

### Smaller but important issues

- **Binary validity gates invite threshold-surfing.** "Episode invalid if severe injury unresolved" teaches agents to ride the line just under critical. Prefer *endogenous* punishment: an injury costs 6 weeks of reduced training inside the sim, so the final 1RM is naturally lower. Keep hard invalidation only for egregious patterns (sustained obligation abandonment, budget insolvency).
- **Daily steps × 365 is a cost and context bomb.** ~365 turns × several k tokens = well over a million tokens per episode before history management, times seeds, times models. See the weekly-cadence design in Part 3 — it is cheaper *and* a better test.
- **The "approximate oracle" baseline is a research project by itself.** Replace with a hand-scripted expert policy (you know the sim; write the near-optimal script). Add a search-based oracle later if ever.
- **Formatting must not dominate.** The one-repair-then-fallback rule is good; also report invalid-action counts per model so scaffolding noise is visible, and keep the action schema small enough that mid-tier models emit it reliably.
- **Naming:** this project is **Bench-bench** — always hyphenated, capital B lowercase b. "BenchBench" (no hyphen) is a separate parallel project of Kevin's and also the name of an existing academic meta-benchmark, so never use that spelling here. Repo: `bench-bench`; Python package: `bench_bench`.

---

## Part 2 — What must be factored in across the simulated year

The year should have a *shape*. A flat random-event generator wastes the premise; a 6-month-old turning 18 months old gives you a natural, realistic difficulty curve that rewards agents who anticipate rather than react. Suggested arc (start ≈ March, month numbers relative):

### The baby arc (the backbone)
| Months | What happens | Pressure on the agent |
|---|---|---|
| 1–2 (6–8 mo old) | Baseline chaos: 1–2 night wakings, naps unpredictable | Learn the terrain, establish routine |
| 2–3 (8–9 mo) | **Sleep regression + crawling** | Sleep debt spike; home workouts interrupted |
| 3–4 (9–10 mo) | **Daycare starts → illness waves.** Daycare kids catch 6–10 colds/yr and parents catch half of them | Repeated 3–7 day training washouts; the agent who deloads *into* illness recovers faster |
| 5–6 (11–12 mo) | Walking → constant supervision; first birthday event | Flexible time shrinks; a social obligation spike |
| 7–8 (13–14 mo) | 12-month sleep regression, molars | Second sleep-debt trough |
| 9–12 (15–18 mo) | Consolidation: one nap, sleeping through more nights | *Improving* conditions — rewards agents who preserved capacity to exploit the easy final quarter |

### Seasonality
- **Winter:** cold/flu season peak (stacks with daycare germs), holiday travel (1–2 weeks, no barbell access — test of "maintain vs. abandon"), gym closures, food environment shifts.
- **New Year:** gym crowding (sessions take longer or get compromised for ~4 weeks — nudges the home-equipment decision).
- **Summer:** family vacation (predictable, announced in advance — tests pre-positioning), longer daylight = slightly better mood/energy.

### Work annual cycle
Fiscal quarter crunches (announced 2–3 weeks ahead), one performance-review period, 1–2 business trips (hotel-gym constraints), and one mid-year fork: a promotion/stretch-project offer trading money for time. There is no "right" answer — it tests whether the agent reasons about the trade instead of pattern-matching "more money good."

### Partner and household
The partner is an agent-shaped constraint, not scenery: their own work crunches and illnesses (which transfer childcare load), a **reciprocity meter** (repeatedly taking morning gym slots without giving back raises household strain, which degrades sleep quality, adherence, and flexibility), date nights and social obligations that compete with training but *reduce* strain, and occasional windfalls (grandparents visit for a week = free childcare — does the agent exploit it?).

### Physiology of a 38-year-old returning lifter
- **Starting point (recommendation):** trained in his 20s, detrained since the baby; 84 kg body mass, 1RM ≈ 84 kg (185 lb). Plausible year-end range 95–110 kg. "Returning lifter" gives muscle-memory-flavored early gains (satisfying curve) plus realistic headroom, and makes detraining during illness a live mechanic.
- Slower recovery than a 25-year-old; heavy sessions need ≥48 h local recovery; warm-up matters.
- **One pre-existing niggle** (shoulder or elbow, per-seed) that flares under high volume + poor sleep — the pain-warning ladder from the spec attaches here.
- **Body mass:** eating in a surplus genuinely helps bench but costs money, spousal dinner logistics, and (past a threshold) energy/health. Cap the exploit with escalating soft costs, not a hard rule.
- Detraining: capacity decays on a ~2–3 week onset during full layoffs; maintenance doses (even one short session/week) mostly prevent it. This makes "minimum viable workout" strategically central, which is exactly the behavior the benchmark wants to reward.

### Strategic capital decisions (the chess moves)
At least three genuine multi-week investments should exist: **home equipment** (bench + rack + bar, ~$600 — eliminates commute and closure risk forever after), **recurring childcare hours** (money → guaranteed training windows), and **meal-prep subscription** (money → nutrition adequacy with zero time). Great agents recognize these as convex; weak agents nickel-and-dime.

### One-off shocks (seeded, 4–6 per year)
Car repair (budget hit + a week of transit friction), household repair, a non-training injury (tweaked ankle chasing the toddler — can he still bench? yes: tests exercise-substitution reasoning), a friend's bachelor weekend, jury-duty-style time confiscation.

### The endgame
Weeks 47–52: the agent must *schedule* its taper and final test. Peaking on accumulated fitness minus fatigue (fitness-fatigue model makes this emergent, not scripted) — an agent that trains hard through week 51 tests tired; one that coasts from week 44 detrains. Deterministic final-test protocol per the scoring spec.

---

## Part 3 — Key design decisions (recommended answers to DECISIONS.md open items)

1. **Cadence: weekly planning + standing rules + event interrupts** — not daily turns.
   - Each Sunday the agent receives a structured weekly report and emits: (a) a session plan for the week (day, location, exercise slots, target intensity/volume, duration cap), (b) life allocations (meal-prep hours, spending, chore delegation, sleep-protection choices), and (c) **standing contingency rules** ("if night-sleep < 5 h, convert session to 25-min fallback"; "if elbow pain ≥ 2, drop board work").
   - The simulator executes the week day-by-day internally, applying the standing rules. Mid-week **interrupts** (daycare closure, illness onset, gym closed) pause execution for a short reactive decision.
   - Why this is better, not just cheaper: it tests *planning and delegation* — writing robust policies rather than micro-reacting — which is the actual long-horizon skill. ~52 planning turns + ~15–30 interrupts ≈ 70–80 model calls per episode. At ~4–6 k tokens/turn round-trip that is ~$2–8 per episode on mid-tier models: affordable at 5 seeds × N models.
2. **Hidden strength model: Banister-style fitness–fatigue impulse response.** `capacity(t) = base + Σ stimulus·e^(−Δt/τ_fit) − Σ stimulus·e^(−Δt/τ_fat)`, with stimulus scaled by load/volume/specificity and **gated by a recovery multiplier** (sleep adequacy × nutrition adequacy × stress). Two decay constants give you delayed adaptation, overtraining, tapering, and detraining *for free* from ~10 parameters — tractable to tune against the separation gate. Layer on: technique proficiency (grows with frequency, caps stimulus→1RM conversion), tendon-irritation accumulator (drives the pain ladder), adherence probability (motivation × fatigue × household strain — planned sessions can silently fail).
3. **Determinism:** one master seed → pre-rolled event calendar + noise streams. Same version + seed + action sequence replays identically. Interrupt decisions consume from a dedicated stream so alternate choices don't reshuffle the future (counterfactual replay stays clean).
4. **Body mass:** track it, let surplus help, escalate soft costs past +8 kg. No hard cap.
5. **Seeds:** 10 public (development) + 10 private (leaderboard). Same seed set for every model.
6. **Scoring:** headline = mean final tested 1RM (kg) across seeds. Secondary scorecard exactly per SCORING_SPEC. Endogenous consequences instead of most validity gates (see Part 1). Report invalid-action/repair counts.
7. **Stack:** Python 3.11+, pydantic for observation/action schemas, zero heavy dependencies for the sim; episode log = JSONL; provider-neutral runner (litellm or thin HTTP adapters); a single self-contained HTML replay viewer that renders an episode as a scrollable year (this is your marketing asset — "watch Claude's year, week by week").

---

## Part 4 — The practical build plan

Four phases, buildable by one person + AI agents. The sim engine is 52-week-native from day 1; only the *validated config* starts at 12 weeks.

### Phase 0 — Lock decisions (1 day)
Adopt Part 3's answers (or amend), write them into `DECISIONS.md`, freeze the persona ("Dave, 38, returning lifter, 84 kg, est. 1RM 84 kg, partner works full-time, baby 6 mo, $250/mo discretionary, commercial gym membership, no home equipment").

### Phase 1 — Playable simulator (Week 1)
- Core engine: calendar/time budget, fitness–fatigue strength model, sleep system (opportunity vs. actual, infant interruptions), nutrition tiers, budget, event system reading a seeded 52-week calendar, pain ladder, adherence.
- Observation renderer (weekly report JSON + human-readable text) and action schema with validation + one-repair + fallback.
- **A CLI so a human can play it** (`python -m bench_bench play --seed 3`). If it isn't fun-adjacent and legible to you, no transcript will be either. Determinism + accounting tests.
- *Exit:* you can play a 12-week game, feel the trade-offs, and replay a log identically.

### Phase 2 — Baselines and the separation gate (Week 2) ← the real design work
- Six scripted policies: random, rigid-linear, reckless-maximalist, skip-when-busy, recovery-aware-heuristic, scripted-expert.
- Run all × 20 seeds × 12-week config; iterate simulator parameters until: correct ordering, **separation ratio ≥ 3**, reckless loses on final 1RM (endogenously — injuries cost him weeks), no baseline exploits win.
- Quick ablations (remove sleep system / delayed adaptation / events → does the ordering collapse? A mechanic that changes nothing gets cut).
- *Exit:* a tuning report with the numbers. Do not proceed until the gate passes — everything downstream is worthless without it.

### Phase 3 — LLM runner + first real results (Week 3)
- Provider-neutral runner: structured output, retries, full transcript + cost logging, resumable episodes, context policy (rolling window of recent weeks + agent-maintained "coach's notebook" the agent can write to each turn — this is the memory mechanism and it's cheap).
- Run 4 models (e.g., Haiku 4.5, Sonnet, a GPT-class model, an open-weights model) × 5 public seeds × 12 weeks. **Read the transcripts.** This is where you discover what the benchmark actually measures.
- *Exit:* first mini-leaderboard + a list of observed exploits and degenerate behaviors.

### Phase 4 — Full year, red-team, ship (Weeks 4–5)
- Extend the validated config to 52 weeks with the Part 2 arc; re-run Phase 2 gate at 52 weeks; run the exploit agents from SCORING_SPEC ("max weekly", "sleep-sacrifice endgame", "1RM-formula gaming", "final-test gambling") and patch.
- Package: repo (`bench-bench`), README with the hook, quickstart (`pip install`, one command to evaluate any OpenAI-compatible endpoint), benchmark card with the honest limitations (simulated physiology, evidence labels per DATA_AND_RESEARCH_PLAN, "does not validate real coaching advice"), HTML replay viewer, leaderboard JSON, private-seed policy.
- Launch: a post with the leaderboard and 2–3 replay-viewer stories ("GPT-X ignored elbow pain in week 31; here's the six-week hole it dug"). The narrative failures are the viral asset, not the scores.
- *Exit:* v0.1 public, other people can reproduce your numbers.

### Explicitly deferred to v2+
Frozen-web corpus + search tools (build only if v1 earns attention), open-web track, persona variants, prompt-injection challenge suite (v1's model-only track has no retrieval surface, so it isn't needed yet), human-play study, expert review panel (do informally in v1: one strength coach + one working parent reading transcripts beats a formal panel).

### Process guardrails
1. Cap governance docs at ~8 files. Every new .md must replace or delete one.
2. No preregistration/audit/remediation documents before there is a leaderboard with real models on it.
3. Code-first milestones: every phase ends with something runnable, never with documents alone.
4. You (Kevin) play the sim yourself in Phase 1 — designer intuition beats a validity report at this stage.
