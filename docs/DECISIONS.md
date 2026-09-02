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
- Development seeds 0–19 and the earlier v0.1 public values 100–109 are burned
  by calibration and pilot publication. The v0.2 public leaderboard will use
  seeds 400–409. Ten private evaluator seeds are supplied out of band; their
  concrete values are deliberately absent from this repository, tests,
  reports, configs, and Git history, and must be disjoint from 300–349 and
  400–409.
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

## v0.2 Phase 1 and Phase 2 redesign — 2026-08-14

This section supersedes the v0.1 release-gate and scoring-constraint claims
above for the v0.2 branch. The v0.1 pilot remains frozen at its tagged
artifact commit.

- The v0.2 seed pools are disjoint: tuning 300–319, certification 320–339,
  fixed regression policies 340–349, and public leaderboard 400–409. Private
  evaluator values remain out of band and are not stored in this repository.
- `docs/GROUNDING.md` is the required pre-calibration record. It separates
  evidence-supported ranges, Dave-specific assumptions, deliberate simulator
  deviations, and calibration choices. No coefficient retuning is permitted
  against certification, regression, or public seeds.
- Hidden recovery capacity and volume tolerance shift the location of the
  episode's weekly over-reaching optimum; they do not multiply every reward.
  Weekly raw stimulus is converted through a smooth over-reaching penalty with
  no hard output cap. Delivered stimulus controls fitness, technique learning,
  and productive-week qualification.
- Sleep protection is priced in the shared weekly ledger: `standard` reserves
  30 minutes and `strong` reserves 60 minutes; `none` reserves zero. Protection
  adds 10.8 and 21.6 minutes/night respectively; those values remain unchanged
  by the sleep recalibration. Sleep now affects adherence only below a
  6-hour breakpoint and applies a modest conditional quality modifier to
  completed work. The breakpoint and slopes are calibration choices informed
  by Borba, Knowles, Saner, and Kekkonen as summarized in `GROUNDING.md`.
- The synthetic sleep center is 6.72 hours/night. Its direction is informed by
  parent actigraphy (Kalogeropoulos fathers 6.68 hours; Tikotzky mothers about
  6.24 hours), while the exact center is a calibration choice. The target is
  ordinary weeks around 6.5–6.8 hours and event troughs around 5.5–6.0 hours.
- Frequency has no independent efficacy multiplier. A fourth session helps
  only by delivering additional executed volume through the same smooth
  over-reaching penalty. This follows the supplied Grgic/Ralston synthesis:
  frequency is an opportunity to deliver volume, not a free bonus.
- A shared 900-minute weekly ledger includes training, commute, meal prep,
  childcare, chores, partner coverage, giveback, reactive childcare, and a
  fixed 180-minute household reserve. Delegation and reactive childcare remain
  cash charges. The reserve is a logistics assumption for the parent persona,
  not a free resource.
- Injury exposure has a conservative 0.90 load-onset boundary plus cumulative
  volume/tolerance exposure. A normal sub-onset session is not automatically
  painful; repeated excess work, sleep loss, and high effort can still create
  injury burden.
- Sustained household strain is a hard score constraint chosen from the
  persona before observing baseline results: four weeks at or above 0.75, or a
  final-third 13-week mean above 0.75, voids the counted score. A one-week peak
  is reported but does not void an episode. Sleep debt remains a reported
  diagnostic because it already reduces readiness and recovery. The standing
  rule is that no unscored resource may be free.
- The six scripted policies are diagnostic fixtures. The v0.2 release gate is
  the held-out policy ladder: all load and frequency rungs must be feasible,
  adjacent paired effect sizes must reach 0.64 at the intended seed count, and
  every life-allocation field must have an explicit ledger, cash, household,
  or event consequence. Partner-giveback's seed-wise optimum is reported as a
  diagnostic rather than collapsed into a magnitude dominance ratio. The
  adversarial search must also cover the known hand-written regression genome
  before any headroom claim is reported. Oracle headroom is a secondary
  diagnostic; the historical six-policy ordering is not a substitute gate. The
  within-seed load-ratio response surface remains a standing diagnostic.

## v0.2 persona and Phase 3 measurement guards — 2026-08-14

- Dave is novice-range for this protocol: he trained casually in his twenties,
  has not lifted seriously in years, has no meaningful recent training base,
  and has no prior peak to recover. His week-0 bench and body mass are both
  84 kg. The trajectory is new-training progression, not old-max recovery.
- The current scripted-expert annual gain (approximately +26.8% on
  certification seeds) is retained as a ceiling guard, not a retuning target.
  The best static-template result remains a diagnostic headroom check.
- Detraining fixtures and the 10–30% annual-gain guard must pass before any
  fitness/fatigue coefficient changes. Pain-days and household-strain limits
  are persona-based benchmark design choices; detraining literature does not
  determine them.
- A Phase 3 candidate with more than 5% weekly validation fallbacks is
  infeasible and cannot contribute a counted or gate score. Its raw score is
  retained as a diagnostic. Normalized comparison is the paired per-seed
  candidate-minus-expert delta, with strict all-seed eligibility.

## Evidence-driven sleep and volume calibration — predictions recorded before implementation

The supplied sleep-calibration report is treated as evidence for model
direction, not as an identified annual strength coefficient. Before changing
the engine or running the diagnostics below, we record these predictions for
the certification seeds (320–339):

1. The sleep-protection ladder effect will fall from the current 19.98 kg to
   below 7 kg.
2. The minimum adjacent load-ladder effect will remain at least 1.5σ.
3. Replacing the frequency multiplier with a volume-response term will leave
   the 3→4-session comparison at least 1.0σ.
4. In the first 12 certification seeds, strong sleep protection will no longer
   be the best of none/standard/strong on every seed (the checkbox diagnostic
   will be non-unanimous, fewer than 12 of 12).
5. The largest life-field effect will be smaller than the combined load and
   session-count effects (dominance ratio below 1.0).
6. Secondary oracle headroom will rise above the current 0.53 kg diagnostic.

These are falsifiable calibration predictions, not release criteria by
themselves. A miss is reported rather than corrected by retuning against the
certification seeds.

## Sleep-baseline recalibration result and scope limitation — 2026-08-14

The sleep center was lowered to 6.72 hours/night. This produces a materially
different sleep distribution across certification seeds: below-6-hour nights
are 8.30% with no protection, 1.15% with standard protection, and 0.47% with
strong protection. The corresponding means are 6.45, 6.63, and 6.81 hours.

The held-out ladder passes its current mechanical gate: all training rungs are
feasible, the smallest adjacent load effect is 2.0303 paired SDs, the 3-to-4
session effect is 1.0722 paired SDs, and every life-allocation field is priced.
Partner-giveback is priced, but its best tested level is 2.0 hours on all 20
certification seeds; its optimum therefore does not yet vary across episodes.
The sleep checkbox is non-unanimous only because all three choices tie on the
first 12 seeds; strong protection has zero unique wins.

The formal 20-seed adversarial search reached the named hand-written template
and found a compliant candidate at 108.8815 kg versus the expert's 106.9665
kg. However, the per-seed oracle headroom is only 0.0115 kg, with paired SD
0.0201 kg and effect size 0.5729, below the approximately 0.5 kg stop
threshold. The evidence-based sleep change therefore did not establish
meaningful hidden-state adaptation value. This is a scope limitation of the
current benchmark, not a reason to iterate physiology again: the benchmark
shows that load and executed session count matter, but it does not yet support
the stronger claim that a model can discover episode-specific recovery
optima.

The annual expert gain remains 27.3411% (106.9665 kg from an 84.0 kg start),
inside the 10–30% novice-range guard. Detraining fixtures remain within their
documented bounds: 1.0377% after 3 weeks, 3.6022% after 10 weeks, and 4.6774%
after 12 weeks. No further engine, prompt, model, or paid-run work should
proceed under this calibration decision without an explicit redesign review.

## v0.2 final protocol sequence — 2026-08-14

The remaining release work is procedural and does not reopen the engine:

1. **Prompt freeze.** Update the card and prompt to the measured scope: load
   calibration and executed session volume are discriminating signals; the
   benchmark does not support claims about episode-specific inference. Add the
   complete constraint inventory and a prompt/engine conformance test, including
   the 0/30/60-minute sleep-protection ledger costs. The prompt must not claim
   that sleep protection has a fixed score bonus or is universally score-neutral.
2. **Retention before any paid transcript.** The `artifacts/` convention,
   append-only policy, credential-scanned deterministic archive builder, and
   per-file manifest with engine and prompt hashes are prerequisites to the
   live smoke. The smoke and later public run write incrementally to their
   named `runs/` roots, then archive through the retention command in
   `release_manifest.json` before those roots are treated as disposable.
3. **Rehearsal loop.** Run the $0 deterministic full pipeline. Then run the
   one-seed, four-model, 52-week smoke. The smoke validates transcript writing,
   four direct-provider adapters, endpoint provenance, pricing, retries,
   repairs, and the weeks 44/48/52 scoring path; it supplies no power estimate.
   Any prompt or adapter defect sends the protocol back to the deterministic
   rehearsal before a paid full run. No patch-forward is permitted.
4. **Power decision.** Derive the public seed count from the held-out ladder,
   not from the one-seed smoke: load calibration is 2.030σ and session volume
   is 1.072σ at 20 certification seeds. Translate the intended model-relevant
   effects (approximately 6.1 percentage points of load ratio and two sessions
   per week) through the paired design and observed model spread before fixing
   the seed count. Freeze sampling, effort, token, endpoint, and pricing
   metadata at the same step.
5. **Publish.** Use public seeds 400–409, keep the ten private evaluator values
   disjoint from 300–349 and 400–409, regenerate the retained archive manifest,
   leaderboard, card, and verification reports from named commands, and include
   the v0.1 pilot as history. The historical pilot analyzer reports Kimi K3 as
   0/10 counted under transport exclusion; the old 90.48 kg counted result is
   retracted and is not an authoritative leaderboard.

## v0.2 provider-lineup decision — 2026-08-14

- The v0.2 public lineup is Claude Opus 5, GPT-5.6 Sol, Muse Spark 1.2, and
  Grok 4.6. The release manifest and live supervisor are frozen to this
  four-model lineup before any paid smoke or public run.
- Kimi K3 is excluded rather than silently removed from the denominator. The
  v0.1 pilot recorded 702 transport failures and four episodes containing zero
  successful model decisions. Those episodes are unscoreable and cannot
  represent Kimi model behavior; the historical pilot artifact retains them
  as evidence and reports them as transport-excluded.
- Grok 4.6 uses explicit per-million pricing metadata in the live supervisor:
  $2.00 input, $0.50 cached input, and $6.00 output below the 200k prompt-token
  threshold, with the configured long-context tier recorded separately.

## v0.2 paid smoke result — 2026-08-14

- The four-model smoke ran on public seed 400 for the full 52-week horizon
  after the prompt hash and current engine hash were frozen. It completed four
  complete, sanitized transcripts through all three scored test weeks.
- Final scores were: Claude Opus 5 97.10 kg, GPT-5.6 Sol 96.22 kg, Grok 4.6
  101.08 kg, and Muse Spark 1.2 100.75 kg. These are smoke observations, not
  leaderboard aggregates.
- Transport failures were 0 for all four episodes. Rejected model outputs /
  repair attempts / successful repairs / automatic fallbacks were respectively
  Opus 18/16/14/2, GPT 5/4/3/1, Grok 3/2/1/1, and Muse 2/1/0/1. Every rejection
  matched the constraint inventory; the observed causes were ledger, cash, and
  coach_note length. All pain counts were 0, and no episode was invalid.
- The archive builder scanned the source for credentials, wrote the deterministic
  four-file smoke archive and per-file manifest, and the raw run tree was moved
  under `runs/archive/`. The full public ten-seed run remains pending.

## v0.2 failed smoke attempt — 2026-08-15

`runs/archive/v0.2-smoke-failed-adapter-20260815/` is retained as diagnostic
evidence and is excluded from active-run discovery and all aggregates. The
supervisor launched all four intended providers, but the attempt was stopped
after the Anthropic adapter failed locally three times before making an HTTP
request: the CLI passed OpenAI long-context pricing arguments to
`AnthropicMessagesClient`, which did not accept them. Claude Opus 5 therefore
made 0 model calls and cost $0.00.

The other processes had already started when the supervisor was interrupted:
GPT-5.6 Sol made 3 provider calls ($0.096350), Muse Spark 1.2 made 2 provider
calls ($0.021259), and Grok 4.6 had written only its `run_start` record and made
0 provider calls. The partial attempt cost $0.117609 in total, produced no
complete episode or valid score, and is not part of any leaderboard or smoke
aggregate. The adapter argument bug was fixed before the completed seed-400
smoke; that completed smoke is retained separately under the v0.2 smoke
artifact paths in `release_manifest.json`.

## v0.2 paid smoke after cache and prompt clarification — 2026-08-15

- The four-model smoke was rerun on public seed 400 for the complete 52-week
  horizon after the coach-note purpose clarification and Anthropic adapter cache
  change. Engine/config hash: `sha256:438c1d77d284450cd4e3da2eac9fcda83c45bfb81f7a67598c62763d96602a52`;
  prompt hash: `sha256:06d96111ac9db67e92f1a26d00f84e986ea95d13fc2acf0825b97be112ef0d27`.
- Final smoke scores and costs were: Claude Opus 5 **101.40 kg / $6.397017**,
  GPT-5.6 Sol **96.94 kg / $3.034434**, Grok 4.6 **100.35 kg / $1.090688**,
  and Muse Spark 1.2 **99.96 kg / $1.034016**. Total cost was **$11.556155**.
  These are smoke observations, not leaderboard aggregates.
- Each episode had 69 decisions and zero transport failures. Repair rates,
  using rejected-output decisions divided by decisions, were Opus **12/69
  (17.3913%)**, GPT **2/69 (2.8986%)**, Grok **1/69 (1.4493%)**, and Muse
  **1/69 (1.4493%)**. Rejected model outputs were 13, 3, 2, and 2 respectively;
  successful repairs were 11, 1, 0, and 0. Each episode had one automatic
  safe fallback after two failed attempts at week 14; no fallback was silent.
- Opus used Anthropic ephemeral prompt caching with a recorded `1h` TTL:
  **351,874 cached-read input tokens**, **6,958 cache-creation input tokens**,
  1,038,362 ordinary input tokens, 96,953 visible output tokens, 13,201
  thinking tokens, and **$6.397017** total cost. All four episode costs equal
  the sum of their recorded per-attempt usage charges.
- Endpoint provenance is sanitized to scheme, host, and path only: Anthropic
  `/v1/messages`, OpenAI `/v1/chat/completions`, xAI `/v1/chat/completions`,
  and Meta `/v1/chat/completions`. Credential scanning found zero hits. All
  transcripts replayed under the current engine, and the deterministic archive
  manifest records per-file hashes and the current engine/prompt hashes.
- The prior 2026-08-14 paid-smoke numbers remain historical evidence from the
  pre-clarification prompt and are superseded for current-protocol reporting.

## v0.2 sampling freeze and seed-count derivation — 2026-08-15

- The certification policy ladder on seeds 320–339 measured a minimum adjacent
  load-calibration effect of **2.0303 paired SDs** and a smaller 3-to-4-session
  frequency effect of **1.0722 paired SDs**. The smaller frequency contrast is
  the planning effect, so the seed count is not chosen from the easier load
  contrast.
- For a two-sided paired contrast at alpha 0.05 and target power 0.80, the
  noncentral paired-t calculation reaches the target at **n=9** for d=1.0722
  (estimated power 0.8038). The frozen public pool uses **10 seeds, 400–409**,
  giving estimated power **0.8539** for that planning contrast. This supports
  the ladder's intended policy comparisons; it is not a guarantee that ten
  seeds can resolve every possible model ranking.
- Sampling is frozen at temperature **1.0**, medium effort where exposed,
  Anthropic adaptive thinking where exposed, and an 8192-token output limit.
  The runner allows one validation repair attempt, eight transport retries with
  a 5-second initial exponential backoff, and applies the rejected-output
  repair guard only after 100 decisions at a 25% threshold. Provider/model
  concurrency is Opus 3, GPT 3, Muse 3, and Grok 2. Anthropic prompt caching
  is ephemeral with a recorded one-hour TTL. Exact per-provider sampling and
  pricing metadata remain in each transcript's `run_start` record.

## v0.2 public run preregistration and results framings — 2026-08-15

The following protocol was frozen before any v0.2 public leaderboard model
calls. It is also recorded as `public_run_preregistration` in
`release_manifest.json`.

- The lineup is exactly Claude Opus 5, GPT-5.6 Sol, Muse Spark 1.2, and Grok
  4.6. The public run is 4 models × 10 seeds (400–409) × 52 weeks: 40
  episodes, with no additional public seeds after results are seen.
- The planned detectable paired effect is `d = 1.0722`, the smallest observed
  policy-ladder contrast, with approximately 85% planned power (`0.8539`) at
  the frozen ten-seed count. Pairwise model intervals use a two-sided paired-t
  interval with df=9. This power statement is about the planned paired effect,
  not a guarantee that every model ranking will separate.
- The engine/config hash is
  `sha256:438c1d77d284450cd4e3da2eac9fcda83c45bfb81f7a67598c62763d96602a52`
  and the prompt hash is
  `sha256:06d96111ac9db67e92f1a26d00f84e986ea95d13fc2acf0825b97be112ef0d27`.
  The frozen output root is `runs/v0.2-public-leaderboard`.
- The public seed set will not be extended after results are seen. If the
  leading models form a tied cluster, any future attempt to rank that cluster
  will be a separate pre-registered study on the private evaluator seeds.
- Grok 4.6 requests are refused before the provider call when a conservative
  prompt-size upper bound reaches 200,000 tokens. This run therefore uses the
  short-context pricing band; the guard is fail-fast and cannot become a
  repair or safe fallback.

### Pre-written results framings

**Top models tie.** If the top-model paired 95% intervals include zero or the
win/loss pattern does not support a stable ordering, the report will say that
the tested models are statistically unresolved at the preregistered ten-seed
power. It will show the descriptive per-seed scores, costs, repairs,
transport failures, and counted fractions without crowning a winner. No extra
public seeds will be added to break the tie; ranking a tied cluster requires
the separately pre-registered private-seed study described above.

**Top models separate.** If the preregistered paired contrasts have intervals
excluding zero with a consistent win/loss pattern, the report will state the
observed ordering and quantify each difference and its two-sided 95% paired-t
interval. It will describe that ordering as evidence for this frozen engine,
prompt, provider configuration, and public seed set, not as a universal claim
about the models or a license to extend the seed set after seeing the result.

## v0.2 Claude Fable 5.1 extension preregistration — 2026-09-01

Claude Fable 5.1 is evaluated as a separately identified model extension to the
completed four-model v0.2 public run. The exact API model string is
`claude-fable-5-1`, using Anthropic's native `/v1/messages` endpoint, the
current engine/config hash, and the current prompt hash. It uses temperature
1.0, medium effort, adaptive thinking, an 8192-token output limit, and the
native adapter's one-hour ephemeral system-block cache.

The extension is preregistered for one 52-week episode on each seed 400–409.
Seed 400 is both the first official extension episode and a canary. It is
eligible for the extension aggregate only after the predeclared transcript,
provenance, credential-scan, rejection, transport, cost, and retention checks
pass. A failed canary is excluded and causes the extension to stop and rerun
from seed 400 under the corrected hash; no score-based exclusion is allowed.
The extension is written to `runs/v0.2-fable-5-1-public` and has a $200 funded
budget, with a $180 planning estimate. This does not alter the historical
four-model preregistration or its leaderboard.

Fable 5.1 pricing is recorded explicitly as $10/M base input, $0.25/M cached
input, $20/M one-hour cache creation, and $50/M output, sourced from the
official model documentation. Pricing and token usage are recorded per
attempt and per episode.
