# Bench-bench Decision Log

## Approved initial decisions

- Project name: Bench-bench.
- Headline outcome: final simulated bench-press 1RM after one year.
- Core capability: long-horizon personal operations under chronic scarcity and delayed consequences.
- Initial scenario: busy working parent with a six-month-old baby.
- Reckless strategies must not win solely through a high final test.
- Build Bench-bench before considering a broader LifeBench platform.

## Decisions still required

- None blocking v0.1. Persona variants, alternative cadences, and tool-use
  tracks remain explicitly deferred until the model-only release earns it.

## Tool-use decisions

- v1 is model-only. Frozen-corpus and live-web tracks are deferred until a
  reproducible model-only leaderboard earns attention.
- Weekly planning is the canonical cadence; daily execution is internal to the
  simulator, with short event interrupts only when a seeded event fires.
- Retrieved content is outside v1. If added later, it remains untrusted and
  cannot override benchmark instructions or alter simulator truth.

## Phase 0 decisions adopted for implementation — 2026-08-02

- Canonical persona is Dave: 38, returning lifter, 84 kg body mass, estimated
  1RM 84 kg, full-time job, full-time working partner, six-month-old baby,
  $250/month discretionary budget, commercial gym, no home equipment.
- The engine is 52-week native; Phase 1 runs the same model for 12 weeks.
- A weekly action contains session plans, meal/sleep/childcare/chore/money
  allocations, capital purchases, and standing contingencies for sleep, pain,
  and illness. Interrupts use a separate pre-rolled event stream.
- Final score is the deterministic standardized-test capacity after a fixed
  three-day taper. Injury and pain reduce future output endogenously. Budget
  overspending is rejected during action validation and repaired or safely
  fallen back; any non-null invalidation remains excluded from leaderboard
  aggregates.
- The public observation exposes noisy estimated 1RM and coarse recovery
  bands. Recovery capacity, volume tolerance, injury-prone joint, true
  capacity, fatigue, and the future interrupt calendar stay hidden.
- Phase 1 uses pydantic 2 schemas and JSONL logs with no simulator dependency
  beyond pydantic. The CLI's one-repair-then-safe-fallback behavior is part of
  the reproducibility contract.

## Phase 2 diagnostics and 52-week gate — 2026-08-02

- Six fixed policies are evaluated on the same 20 seeds: random,
  rigid-linear, reckless-maximalist, skip-when-busy, recovery-aware, and
  scripted-expert.
- The 12-week run remains a diagnostic vertical slice, not a release gate.
  Its close adjacent pairs (0.276σ and 0.361σ under the cap-1.0 calibration)
  are not expected to discriminate reliably at that horizon.
- The enforced gate is the 52-week configuration, retaining the minimum
  adjacent paired order rate of 65%, alongside the separation, aggregate
  ordering, endogenous-recklessness, and validity checks.
- Sleep, delayed adaptation, and event ablations all change scores and
  decisions, so none was cut as a no-op. Their release relevance is assessed
  against the 52-week gate rather than the short-horizon diagnostic.

## Phase 3 and Phase 4 release decisions — 2026-08-02

- The model runner uses a thin OpenAI-compatible HTTP adapter plus a callable
  test adapter. The v1 runner rejects non-model-only tracks, requests JSON
  output, gives one repair call, then lets the simulator's safe fallback take
  over. Every turn records messages, response, usage, cost, parse errors,
  repairs, action, notebook update, interrupt turns, and outcome.
- Resume means replaying already logged validated actions and reactive choices
  into a fresh deterministic environment before requesting the next model
  turn. This avoids persisting hidden state as an authority.
- With no endpoint credentials available in the development environment, the
  prior Phase 3 model transcript set was treated as a deterministic calibration
  artifact, not a claim about frontier models. It is not an authoritative
  leaderboard. Real endpoints use `run-model` and write the same transcript
  format.
- The 52-week gate passes on the same 20 development seeds at separation
  9.618. Weekly maxing, endgame sleep sacrifice, 1RM-estimate gaming, and
  final-test gambling all remain below the scripted expert; their reports are
  retained as regression fixtures.
- The historical pre-calibration release seed policy used ten public values
  (0–9). Those values and the reproducible 0–19 development values are burned
  calibration fixtures, not the current release seed set.
- The replay viewer is a single HTML file with the public JSONL embedded. It
  has no network dependency and does not embed hidden snapshots.
- Full-year audit found the promotion fork was visible but initially had no
  actionable consequence. The weekly life allocation now has a
  `career_choice` field: protecting time, accepting an eight-week stretch
  project with a deterministic cash bonus and time strain, or deferring. The
  12- and 52-week gates are rerun after this schema change.
- Completion audit found the hidden `injury_joint` trait was present in the
  variation snapshot but did not affect outcomes. It now changes endogenous
  tendon irritation by session focus (shoulder-prone: heavy/test sensitivity;
  elbow-prone: volume/technique sensitivity), multiplied by pre-rolled pain
  noise. The Phase 2 and 52-week gates are regenerated after this validity
  fix.
- The same audit found the latent motivation baseline was not part of the
  adherence probability. Adherence now multiplies readiness by motivation,
  recovery capacity, fatigue, and household/work stress; the headline score
  definition and action schema are unchanged. All gate and release fixtures
  are regenerated after this simulator-model correction.
- The logistics audit found the New Year gym-crowding signal was visible but
  had no execution consequence. Crowding now adds deterministic gym time to a
  session's family-window calculation (home sessions are unaffected), making
  the home-gym capital decision operational. Gate and release fixtures are
  regenerated after this correction.
- Action-semantics audit found two declared standing-rule choices were inert:
  `reduce` under sleep now applies the same bounded reduction as pain, and
  `fallback` under illness converts the session to the 25-minute fallback.
  These are schema-behavior corrections, not new action fields or scoring
  components; all gates are rerun.
- Event-arc audit found the first-birthday obligation was visible but had no
  time consequence. It now adds a deterministic flexible-time penalty in its
  announced week, preserving the weekly-planning trade-off without changing
  the headline score formula or action schema.
- Ablation audit found disabling the event system still left hard-coded
  grandparents, travel, and promotion consequences active. Those consequences
  now honor `enable_event_system=False`, so the no-event report is a clean
  mechanic removal rather than a partial ablation.
- Public-log boundary audit found evaluator-only sleep debt serialized in
  final results and exposed by a sleep-debt signal. Public serialization now
  omits the metric, the signal is derived from the visible recent sleep band,
  and replay normalizes the legacy field for logs written before this fix.

## Current release protocol — 2026-08-07

This section supersedes earlier seed and leaderboard decisions.

- The canonical release horizon is 52 simulated weeks (364 simulated days).
  The headline score is the arithmetic mean of read-only standardized-test
  projections at hidden weeks 44, 48, and 52. The 12-week configuration is a
  diagnostic only and is not a release gate.
- Consistency drift is enabled: after a four-week productive streak, each
  subsequent productive week adds 0.10 kg to durable base capacity. The
  current physiology, logistics, time ledger, safety, and adversarial-search
  configuration is frozen for the live evaluation.
- The six-policy gate uses a 65% minimum adjacent paired-order rate, at least
  3σ expert-versus-random separation, the intended aggregate ordering, and
  endogenous loss by reckless-maximalist. Release-abuse signatures and the
  separate human-review margin remain distinct decisions.
- Development seeds 0–19 are burned by calibration. The public leaderboard
  will use seeds 100–109. Ten private evaluator seeds are supplied out of
  band; their concrete values are deliberately absent from this repository,
  tests, reports, configs, and Git history.
- Budget and schema errors follow one repair attempt and then safe fallback.
  If an execution-time charge still exceeds the cash ledger, the episode
  terminates, records `episode_invalidated`, sets `invalid_reason`, and is
  automatically excluded from aggregates. A non-null invalid result is never
  a passing scored episode.
- No live model run or public leaderboard is generated before independent
  review of this frozen protocol. The authoritative leaderboard is created
  only after the public-seed live run.
- Session accounting is reported separately as planned, transformed,
  attempted, completed, and missed. `fallback_sessions` counts completed
  fallback executions only. Declared work is limited to one prescribed
  repetition per minute; loads below 0.35× true capacity earn no stimulus or
  technique credit, and productive-week qualification uses delivered stimulus.
- Weekly stimulus uses a real diminishing-returns tail: the default curve is
  linear through 0.75 raw units and approaches the 1.00-unit cap thereafter.
  The configured start is deliberately below the cap, so it is not a hard
  clip disguised as a curve.
- Each week reserves the cost of all scheduled household shocks before any
  reactive spend is validated. The terminal invalidation path remains covered
  by an independent execution-time accounting-drift fixture, rather than by a
  validator-approved shock sequence that can fail spuriously.

## Scoring constraint decision — 2026-08-07

- Pain days `≤14` is the only behavioral hard constraint on the headline score.
  A structurally valid episode always retains its raw standardized-test result;
  a pain-violating episode receives no counted leaderboard score and is listed
  in the `violations` column.
- Household strain and sleep debt remain diagnostics only. They are not
  pass/fail thresholds or hidden score penalties. Structural invalidation via
  `invalid_reason` remains separately excluded from aggregates.

## Counted-seed aggregation decision — 2026-08-07

- A counted aggregate is reportable only when every expected seed is counted
  (minimum counted-seed fraction: 100%). Excluded seeds remain in the
  denominator and their raw scores and violations remain visible; survivor
  means are never used for leaderboard ranking.
- This is an ineligibility rule, not a synthetic zero-kilogram score. It avoids
  assigning an arbitrary unit to a voided episode while preventing a policy
  from ranking on only its easiest surviving seeds.
- The same all-seed counted rule applies to scripted-reference means and
  adversarial candidate comparisons.

## v0.2 live-run audit findings — 2026-08-08

- `ModelTurn.notebook_update` is enforced with a 2,000-character maximum, but
  the weekly prompt states neither the limit nor the consequence of exceeding
  it. This is an undocumented validation constraint.
- Authored fallback loads are enforced at no more than 0.78× the permitted
  estimated 1RM ceiling, but the weekly prompt states only the fallback
  duration, set, and repetition caps. This load ceiling is also an
  undocumented validation constraint.
- Live repair metrics count one repair per decision only when a model output is
  rejected. Exhausted provider retries are reported separately as transport
  failures and do not inflate the model-format repair rate.
- The weekly prompt names the `life` object and its fields but does not include
  a complete valid nested weekly-action JSON example. The reactive prompt does
  include a valid example. Grok flattened `life` into `action` on both seed
  100 and seed 101 in week 1; this is recorded as a v0.2 prompt-clarity finding
  and a candidate for a complete weekly example.
