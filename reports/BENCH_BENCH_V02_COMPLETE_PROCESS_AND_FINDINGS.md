# Bench-bench v0.2: Complete Process and Findings Report

## From an idea for a long-horizon benchmark to the current public result

**Report status:** technical retrospective and results record  
**Report date:** 15 August 2026  
**Current branch:** `v0.2`  
**Current preregistration commit:** `d5f17d0`  
**Historical pilot tag:** `v0.1-pilot` at `ad003e6`

> **Purpose of this report:** bring a technically literate reader up to speed on the entire Bench-bench project: why it was created, how the simulator and protocol evolved, which failures were found, how they were repaired, what the calibration and adversarial tests showed, what the current model run measured, and which claims the evidence does—and does not—support.

This is a retrospective of the repository and the project record. It does not claim that every intermediate experiment was part of the final protocol. Intermediate results are included because they explain why the final protocol contains the safeguards it does.

---

## 1. Executive summary

Bench-bench is a model-only benchmark for long-horizon planning under recurring disruption. An AI model acts as the coach for Dave, a fictional 38-year-old parent returning to bench-press training. Each week the model must plan training and allocate a finite pool of time and money across training, commute, meals, childcare, chores, partner coverage, partner giveback, sleep protection, and purchases. Planned sessions can fail to execute. The model receives noisy observations and does not see the hidden state that drives fatigue, recovery, adherence, or injury.

The final v0.2 public run evaluated:

- 4 models;
- 10 public seeds, `400–409`;
- 52 simulated weeks per episode;
- 40 complete episodes;
- hidden standardized tests at weeks 44, 48, and 52, averaged after a fixed three-day taper.

### Final headline results

| Model | Counted mean final 1RM | Sample seed SD | Raw range | Counted seeds | Status |
|---|---:|---:|---:|---:|---|
| Grok 4.6 | **101.19 kg** | 1.66 kg | 98.26–104.19 | 10/10 | Counted and eligible |
| Muse Spark 1.2 | **101.03 kg** | 2.68 kg | 97.17–104.45 | 10/10 | Counted and eligible |
| GPT-5.6 Sol | **96.41 kg** | 1.47 kg | 93.38–97.76 | 10/10 | Counted and eligible |
| Claude Opus 5 | **102.00 kg raw** | 2.42 kg | 98.51–106.28 | 7/10 | Raw diagnostic only; 3 pain-voided seeds |

The correct ranking statement is not “Opus won.” Opus had the highest raw mean but failed the pain constraint on three seeds, so it has no counted aggregate. Among the three all-seed-compliant models, Grok 4.6 and Muse Spark 1.2 are statistically unresolved at the preregistered ten-seed sample; their paired difference is only `+0.17 kg` with a two-sided 95% interval of `−1.37` to `+1.70 kg`. GPT-5.6 Sol is the clearest lower result in this run.

### Main scientific/design conclusion

The benchmark successfully creates meaningful differences in **load calibration** and **executed training volume/session count**. It does **not** yet create meaningful value for **episode-specific hidden-trait inference**. A formal adversarial oracle search, given access to episode-specific hidden information, produced only `0.0115 kg` of headroom over the best fixed policy.

Therefore the defensible v0.2 claim is:

> Bench-bench measures long-horizon configuration and programming quality under recurring disruption: whether an agent chooses appropriate training load and volume, allocates scarce time and money, and sustains a valid plan across a disrupted year.

It should not be cited as evidence that one model has general intelligence, that a model can infer an individual’s hidden recovery traits, or that the simulator is a substitute for real coaching, medical advice, sleep advice, nutrition advice, or relationship advice.

---

## 2. The original idea and the design target

The project began with a question broader than “which model can answer a planning prompt?” The target was a benchmark in the spirit of a long-horizon planning evaluation: an agent should make a sequence of decisions whose consequences appear later, while operating under scarcity and uncertainty.

The initial design target combined four properties:

1. **Long horizon:** one year rather than one turn.
2. **Delayed consequences:** training choices affect future capacity, fatigue, pain, and readiness.
3. **Recurring disruption:** the plan is repeatedly interrupted by childcare, work, sleep, equipment, illness, and household events.
4. **Real tradeoffs:** the model cannot maximize training, household support, recovery, and spending independently because they share finite resources.

The chosen scenario was a working parent trying to improve a bench press. This was intentionally concrete. A strength outcome gives the benchmark a scalar headline score, while the household and scheduling context supplies the planning difficulty.

The user’s initial ambition was stronger than the final measured claim: the benchmark was expected to reward genuinely excellent long-term adaptive planning and distinguish it from merely competent planning. The project eventually showed that the environment did distinguish several programming choices, but did not yet provide enough episode-specific variation for a strong adaptation claim. Narrowing the claim was a result of measurement, not a post-hoc marketing choice.

---

## 3. What the benchmark is, technically

### 3.1 Episode structure

An episode is a deterministic simulated year. The simulator begins from a seed-defined state and advances through 52 weeks / 364 simulated days. The model receives a weekly observation and returns a structured weekly action. Seeded events can create short reactive turns during the week.

The observation is intentionally incomplete. The model sees banded/noisy state such as an estimated 1RM, sleep, work, household, and recovery signals, but does not see:

- true capacity;
- true fatigue;
- true recovery capacity;
- volume tolerance;
- injury-prone joint;
- latent motivation baseline;
- future interrupt schedule;
- the simulator’s exact internal state.

The engine is deterministic conditional on the seed and validated action sequence. That makes paired comparisons possible: two policies can be evaluated against the same simulated life rather than against unrelated random worlds.

### 3.2 Persona

The final persona is explicitly novice-range, not a returning elite lifter recovering an old peak:

| Persona element | Final value/description |
|---|---|
| Age | 38 |
| Starting body mass | 84.0 kg |
| Starting bench / estimated 1RM | 84.0 kg |
| Training history | Trained casually in his twenties; no meaningful recent training base |
| Work | Full-time job |
| Partner | Works full time |
| Child | Six-month-old infant at the start |
| Equipment | Commercial gym membership; no home equipment initially |
| Money | $250/month discretionary budget, carrying over |
| Physiological interpretation | New-training progression, not recovery of a previous peak |

This persona clarification was added as a ceiling guard after earlier discussion overestimated what “returning lifter” might imply. The final scripted expert’s annual gain is about `27.34%`, which remains within the chosen `10–30%` novice-range guard. The exact guard is a benchmark design choice, not a universal physiological law.

### 3.3 Weekly and reactive actions

The model has two turn types:

- a **weekly action** containing session plans, life allocations, rules, purchases, a coach note, and a notebook update;
- a **reactive action** for an interrupt such as a shock, cancellation, or sudden childcare need.

The weekly and reactive schemas are intentionally different. This became important after the first live experiments showed that the model was often asked to produce a smaller interrupt schema while seeing only the larger weekly schema.

The final prompt is rendered from an executable constraint inventory in `bench_bench/constraint_inventory.py`. The inventory includes field types/ranges, cross-field validation, engine rejection rules, ledger/cash rules, scoring rules, and transformation reporting. A conformance test checks both directions:

1. Every inventory entry appears in the rendered prompt.
2. Every constraint stated in the prompt exists in the inventory.

This makes a new validation rule difficult to add silently—the failure mode that produced several early live-run repair artifacts.

### 3.4 Representative action constraints

| Area | Final rule |
|---|---|
| Session day | Integer 0–6 |
| Session slot | `morning`, `lunch`, or `evening` |
| Location | `gym`, `home`, or `hotel` |
| Focus | `volume`, `heavy`, `technique`, `fallback`, or `test` |
| Sets / reps | Sets 1–8; reps 1–15 |
| Load | 0–250 kg, with engine-level authored fallback ceiling |
| Duration | 10–120 minutes |
| RPE | 5–10 |
| Weekly sessions | At most 5; one session per day |
| Fallback | At most 25 minutes, 3 sets, 6 reps |
| Test session | Reps must equal 1 |
| Purchases | At most 3 and unique |
| Notebook update | At most 2,000 characters |
| Coach note | At most 600 characters |
| Reactive action | Cancel/fallback lists at most 5; days 0–6; no overlap |
| Reactive childcare | 0–8 hours; charged against remaining ledger and cash |
| Authored fallback load | Above `0.78 ×` permitted estimated-1RM ceiling is rejected, not clipped |

The full inventory in the source is authoritative; this table is a reader’s summary, not a replacement for the schema.

### 3.5 Repair and fallback semantics

The runner follows one repair attempt:

1. Send the model’s output to validation.
2. If invalid, return the validation error plus the correct schema context.
3. Ask the model for one corrected action.
4. If the correction is still unavailable or invalid, substitute the safe fallback.

The final protocol separates these metrics:

- rejected model-output objects;
- rejected output decisions;
- repair attempts;
- successful repairs;
- transport failures;
- automatic fallbacks;
- transformed sessions.

This vocabulary was introduced after Kimi’s transport retries had been incorrectly mixed into the repair rate. A transport failure is not evidence that the model emitted an invalid action.

### 3.6 Engine transformations

An accepted action can still encounter a simulator transformation during execution. Examples include missed sessions, equipment cancellation, adherence loss, time failure, or a scheduled event. These are not supposed to disappear silently.

Weekly outcomes report transformation information through fields including:

- `transformed_sessions`;
- `transformation_reasons`;
- `reactive_action_fallbacks`;
- `attempted_sessions`.

Session accounting was separated into planned, transformed, attempted, completed, and missed. `fallback_sessions` was moved into the completed execution branch so unperformed sessions are not counted as completed fallbacks.

---

## 4. The protocol evolution: chronology from idea to v0.2

The project did not move directly from concept to paid leaderboard. It went through a sequence of diagnostic, adversarial, calibration, and artifact phases. The chronology matters because each major protocol rule exists in response to a measured failure.

### 4.1 Phase 0: initial simulator and protocol skeleton

The first implementation established:

- a 52-week native engine;
- Dave’s persona and starting state;
- weekly planning as the canonical cadence;
- short interrupt turns for seeded events;
- structured Pydantic actions;
- noisy public observations;
- hidden capacity/fatigue/recovery variables;
- deterministic standardized test scoring;
- JSONL transcripts;
- one repair then safe fallback.

At this stage, the headline task looked like a strength-planning problem with life logistics around it. The first questions were calibration questions: how much could the expert gain in a year, how much should random play lose, what did a bodyweight or nutrition pathway do, and whether reckless training lost for the intended reason.

### 4.2 Early calibration findings

Initial calibration surfaced several structural questions:

- The difference between expert and random was large enough to produce an apparently impressive sigma separation, but the denominator depended heavily on seed variance and scoring semantics.
- A returning-lifter interpretation risked allowing a large “recovery” gain. The persona was later redefined as novice-range and the annual gain was guarded rather than retuned to an arbitrary target.
- Bodyweight was initially fixed at 84.0 kg for the episode. The mass/nutrition pathway was audited and later made explicit/bounded, rather than leaving an apparently meaningful input disconnected from the score.
- Technique learning and productive-week qualification were not allowed to depend merely on completion count; they were tied to executed stimulus.
- The `technique_tau_sessions` parameter was found to be unused and was connected to the relevant learning pathway.

The important design lesson was that a high-level story (“nutrition matters,” “technique adapts,” “recovery matters”) is not enough. Every declared mechanic needs a live code path and a regression check.

### 4.3 Prompt and interrupt failure discovery

The first large live diagnostic found that the interrupt mechanic—the benchmark’s core disruption mechanism—was not actually being exercised by the model. Across 720 interrupt decisions, **715 were resolved by automatic fallback**. The model was often asked for a `ReactiveAction` while the prompt context still emphasized the weekly schema.

The repair work included:

- a turn-appropriate system message for weekly and interrupt turns;
- an explicit `ReactiveAction` schema and valid example on interrupt turns;
- a repair prompt containing the correct schema, not merely the validation error;
- an audit of valid ReactiveAction fields;
- a full repair exchange showing error plus corrected example.

This turned the interrupt from a mostly automatic mechanism into an actual model-facing decision point.

### 4.4 Live model diagnostics and notebook behavior

Short live runs with GPT-4.1 and GPT-5.4 showed that the notebook channel was being used to restate the plan rather than accumulate observations about Dave. One GPT-5.4 notebook entry called a plan a “proven template” and then used it to justify frozen loads for eleven weeks.

The notebook instruction was rewritten to ask for:

- what Dave learned about responding to load;
- which sessions were lost and why;
- patterns in disruptions;
- what changed in the environment;
- and explicitly not a restatement of the week’s plan.

A free-text partner-message channel was prototyped as an observation-only field, tested for determinism, then removed. The channel did not affect score, state, or mechanics, but it added protocol surface without contributing enough to the release question.

### 4.5 Mechanical rejection and silent-correction audit

Early runs exposed a broad class of model-facing problems:

- purchases were interpreted inconsistently by validation;
- a sensible two-session week could fail a technical 15-minute floor;
- fallback caps were enforced but not always stated;
- `extra_childcare_hours` drew from the ledger but was not clearly described in the reactive prompt;
- `coach_note` and `notebook_update` length limits were enforced but under-explained;
- the weekly prompt described `life` fields without a complete nested JSON example;
- a shock reserve was reserved only when the shock itself occurred, allowing an earlier reactive spend to invalidate a later shock;
- pydantic coercion accepted numeric strings and sentinels in ways that could silently transform an agent action;
- a reactive action could collapse to `protect_recovery` without enough surface-level accounting;
- gym-closed/no-rack cancellation was initially a pure simulator decision without transformation-counter visibility.

The final rule was:

> Every transformation is either a validation error or is surfaced in the weekly outcome and counted.

That rule was applied to rep-rate clipping, load-ratio clamping, home caps, numeric coercion, reactive collapse, and cancellation paths.

### 4.6 Volume-stacking and zero-load exploits

The earliest engine rewarded executed volume too linearly. That created policies that were legal, plausible-looking, and still contrary to the intended training meaning.

#### Volume stacking

An `8×4`-style policy used roughly five 75-minute sessions per week—375 gym minutes before commute—while exploiting the fact that fatigue was a weak counterweight to fitness. A minimum-duration rule did not solve this because `8×15` at 45 minutes still validated.

The fix was mechanical rather than cosmetic:

- Brzycki-style rep-max ceiling applied in `_execute_session` before volume was computed;
- rep-rate constraints generalized across volume, heavy, technique, and test focuses;
- over-prescription treated as reduced/failed work rather than free stimulus;
- fallback caps added to schemas and validation;
- weekly diminishing returns applied to accumulated stimulus;
- duration coupled to work rather than being an independent field.

The engine-level relationship used as the load/repetition envelope is:

```text
estimated 1RM ≈ load × 36 / (37 − repetitions)
```

This is a practical rep-max approximation, not a claim to measure true physiology.

#### Zero-load credit

One reviewer constructed a legal zero-load policy: three ten-minute sessions at 0 kg. Under the old execution floor it received real stimulus and scored `106.05 kg` versus an expert score of `105.03 kg`, winning 17 of 20 seeds.

The fix removed the stimulus floor for declared loads below a meaningful threshold and made technique learning and productive-week qualification depend on executed stimulus rather than mere completion count. Loads below `0.35 ×` true capacity earn no stimulus or technique credit in the current protocol.

### 4.7 Ledger hardening and fallback-liveness failure

The 8×4 policy revealed that the primary exploit was time-budget evasion, not merely physiology. Training, meals, chores, childcare, coverage, and giveback were moved onto one shared weekly ledger. Delegated chores and reactive childcare gained cash charges. Coverage and giveback could no longer be maximized independently.

The ledger was then tested at tighter pools. The current public configuration is:

| Ledger component | Current value |
|---|---:|
| Nominal weekly pool | 900 minutes |
| Fixed household reserve | 180 minutes |
| Discretionary amount reported to the model | 720 minutes |
| Sleep protection: none / standard / strong | 0 / 30 / 60 minutes |
| Gym commute | 20 minutes per session |
| Home overhead | 10 minutes per session |
| Delegated chores | 1,200¢ per hour |
| Reactive childcare | 1,400¢ per hour |

Before the effective reserve was made explicit, the benchmark reported a 900-minute budget even though only 720 minutes were actually usable. That made the observation misleading and caused reckless policies to be labeled as policies while their weeks were rejected.

One diagnostic found reckless-maximalist replaced by the safe fallback **416/416 weeks** on seeds 300–307. Its raw `84.55 kg` score was below the safe-fallback-only score of `85.28 kg`; the policy was not playing the benchmark it was labeled as. The fix was to make feasibility a gate: any candidate with more than 5% weekly validation fallbacks is infeasible for Phase 3 comparison, while retaining its raw score as a diagnostic.

### 4.8 Home-rack dominance and logistics calibration

The home rack initially dominated the score. Scripted expert scored `105.01 kg` with the rack and `85.58 kg` without it—a `19.43 kg` swing on a `16.67 kg` total baseline range. This was not an interesting decision; it was a required purchase masquerading as strategy.

The development response was to:

- reduce gym commute to 20 minutes;
- give home training a real limitation through the no-spotter/near-max cap;
- retain a meaningful but smaller home-equipment advantage;
- rerun baselines and rack ablations before accepting the calibration.

The final public artifact does not contain a single authoritative final rack-ablation table, so this report does not invent a final kilogram value. The important process result is that the dominance was identified as a design defect and handled as a logistics calibration problem, not left as evidence of superior planning.

### 4.9 Stimulus cap, adversarial search, and the reference-policy gate

The weekly stimulus cap was swept at values including `1.0` and `1.5`. At cap 1.0, the search found a plausible low-intensity, high-repetition policy: five 25-minute home fallbacks, 3×6 at 0.55×1RM, and a rack purchase at week 19. It fit within about 895 minutes and beat a hand-written expert by about 1.71 kg.

That result changed the release philosophy. “No policy may beat expert” is not a defensible rule: a better legal policy is healthy headroom. The release gate was changed to distinguish:

- a legal policy that simply performs better;
- an implausibility/abuse signature;
- and a large margin that requires human review.

The `+5 kg` margin was retained as a **human-review flag**, not labeled an abuse signature. Abuse signatures include pain burden, household strain at the configured ceiling, physically implausible parameters, or evidence that the policy mostly plays the safe fallback.

The adversarial search itself then failed a liveness test: it evaluated 285 compliant candidates but missed a reviewer-written policy. The search was widened to include:

- mixed-focus weeks;
- per-week structures;
- boundary loads including zero;
- purchase ordering;
- realistic durations and rep rates;
- known regression genomes seeded into the initial population;
- more random immigrants and a lower elite fraction to avoid early local-optimum collapse.

A coverage assertion was added: the search’s best all-seed-compliant candidate must meet or exceed a named hand-written regression genome before an oracle headroom number is reportable.

The named regression policy was:

```text
4 sessions/week
alternating volume and technique
4×5 at 0.70× estimated 1RM
40 minutes
home rack purchase at week 8 when cash ≥60,000¢
meal prep 2.0h, coverage 2.0h, giveback 2.0h, chores 1.0h at 1,200¢
rules: fallback / fallback / protect_recovery
```

The widened search reached the known hand-written region. This converted the search from “a plausible number generator” into a coverage-checked measurement tool.

### 4.10 Safety metrics and constrained scoring

The original pain metric required sleep below six hours before pain days could fire. That made it too hard to trigger. The condition was removed. Planned fallback sessions were counted, not only sessions converted into fallbacks. The reported pain and fallback counts were then tied to executed state.

The scoring rule evolved toward explicit validity:

- raw final score is always retained as a diagnostic;
- pain days above 14 void the counted score;
- structural invalidation is separate and automatically excluded;
- counted aggregates require 100% of expected seeds;
- no survivor-only mean is used for ranking.

Household strain’s status changed during development and the repository retains a stale earlier decision entry. The final v0.2 card and Phase 2 protocol treat sustained household strain as a hard constraint with two branches: four weeks at or above 0.75, or a final-third mean above 0.75. Sleep debt remains a diagnostic because it already affects recovery/readiness and is therefore not a free unscored resource. The earlier 2026-08-07 decision text saying both household strain and sleep debt were diagnostics-only should be treated as superseded and reconciled before publication.

### 4.11 Physiological grounding and calibration

The project intentionally separated evidence-supported direction from exact simulator numbers.

| Category | Meaning in the project |
|---|---|
| `[E]` Evidence-supported | Literature or supplied research supports the direction/range. |
| `[P]` Persona assumption | A design input about Dave and his household. |
| `[D]` Deliberate deviation | A simplification chosen for benchmark tractability. |
| `[C]` Calibration choice | A numeric setting tuned on tuning seeds, not a universal physiological truth. |

#### Fitness/fatigue model

The original model used Banister-style fitness/fatigue time constants of approximately 56 days for fitness and 6 days for fatigue. Early calibration showed that fatigue was only a small counterweight to fitness because the coefficients were roughly `0.25` versus `2.60`. A sweep of fatigue scaling confirmed that simply raising fatigue was a dead end: it changed scores but did not create the intended adaptive decision structure. The project therefore did not use fatigue scaling as the primary fix.

#### Annual gain

The final scripted expert’s certification gain is `27.3411%`, from 84.0 kg to 106.9665 kg. This is retained as a guard within the chosen 10–30% novice-range design band. It is not presented as the scientifically correct gain for every novice.

#### Detraining fixtures

The repository reports the following detraining values:

| Layoff | Engine result | Literature range recorded in docs |
|---:|---:|---:|
| 3 weeks | 1.0377% | 2.0–3.3% |
| 10 weeks | 3.6022% | 3–6% |
| 12 weeks | 4.6774% | 5–15% |

The 10-week value lies inside the recorded range. The 3-week and 12-week values are below the stated lower bounds as printed. Some repository text says the fixtures “remain within bounds,” which does not match the table literally. That documentation inconsistency should be resolved before a formal release; the report does not silently relabel the values as passing.

#### Hidden traits and volume

Hidden recovery capacity and volume tolerance were changed to shift the location of the episode’s weekly over-reaching optimum rather than multiplying every reward. Delivered stimulus, not planned completion count, drives fitness, technique learning, and productive-week qualification.

Weekly stimulus uses diminishing returns: the current documented curve is approximately linear through 0.75 raw units and approaches a 1.00-unit cap. The start point was changed because an earlier `diminishing_start=1.25` would have clamped directly to the 1.0 cap and functioned as a hard clip rather than the curve described in the documentation.

Consistency drift was adopted: after a four-week productive streak, each subsequent productive week adds 0.10 kg to durable base capacity. This was intended to make early consistency matter without changing the physiology into a purely front-loaded gain.

#### Sleep calibration

An evidence review challenged the earlier model, where ordinary sleep protection could be worth about 20 kg. The supplied literature argued against a large continuous annual strength penalty from a modest marginal sleep difference, while still supporting meaningful consequences under severe restriction.

The final sleep decisions were:

- lower the synthetic sleep center to 6.72 hours/night;
- target ordinary weeks around 6.5–6.8 hours and event troughs around 5.5–6.0 hours;
- retain protection gains of about +10.8 and +21.6 minutes/night for standard and strong;
- charge 0 / 30 / 60 ledger minutes for none / standard / strong;
- use a threshold-shaped adherence effect below six hours rather than a continuous per-hour penalty;
- apply a modest conditional session-quality modifier to executed work rather than a large completion bonus;
- remove an independent frequency multiplier and let frequency matter only through additional executed volume.

On certification seeds 320–339, below-six-hour nights were:

| Protection | Fraction of nights below 6h | Mean sleep |
|---|---:|---:|
| None | 8.30% | 6.45 h |
| Standard | 1.15% | 6.63 h |
| Strong | 0.47% | 6.81 h |

The sleep change reduced the earlier dominance effect and made sleep protection score-neutral/tied in the ledger-matched checkbox test. It did not create meaningful hidden-state adaptation headroom. That result was recorded as a scope limitation rather than used to justify another round of physiology tuning.

### 4.12 Prompt freeze and protocol freeze

The final prompt was rewritten to state the objective at the beginning and end:

- maximize Dave’s bench press 1RM;
- score the average of hidden tests at weeks 44, 48, and 52;
- use a 52-week horizon;
- observe pain, household, sleep, money, time, and interruptions;
- plan as Dave’s coach rather than speak in first person;
- obey the ledger and cash constraints;
- understand that planned sessions may not happen.

Tactical leakage was removed. The prompt no longer tells the model “do not maximize coverage and giveback” or “use zero/defaults.” It states mechanics and schema, not what strategy the evaluator wants.

The final prompt hash is:

```text
sha256:06d96111ac9db67e92f1a26d00f84e986ea95d13fc2acf0825b97be112ef0d27
```

The current engine/config hash is:

```text
sha256:438c1d77d284450cd4e3da2eac9fcda83c45bfb81f7a67598c62763d96602a52
```

Both hashes are stamped in transcripts and archive manifests.

---

## 5. Phase 3 certification: what the free tests showed

Phase 3 was intentionally supposed to be a no-model-call gate. The key question was whether the environment could distinguish good from excellent policies before spending money on live model episodes.

### 5.1 Six scripted baseline diagnostic

The current six-policy diagnostic was regenerated on development seeds 0–19. It is not the public model leaderboard and is not the final release gate.

| Policy | Raw mean | Counted mean | Raw SD | Counted SD | Violation status |
|---|---:|---:|---:|---:|---|
| scripted-expert | 106.90 kg | 106.90 kg | 0.97 | 0.97 | None |
| rigid-linear | 101.88 kg | — | 0.88 | — | Household strain |
| recovery-aware | 101.13 kg | 101.13 kg | 0.87 | 0.87 | None |
| skip-when-busy | 96.46 kg | 96.46 kg | 1.07 | 1.07 | None |
| reckless-maximalist | 95.04 kg | — | 0.61 | — | Pain + household strain |
| random | 90.72 kg | — | 1.26 | — | Household strain |

Raw ordering is:

```text
scripted-expert > rigid-linear > recovery-aware > skip-when-busy > reckless-maximalist > random
```

The expert–random raw gap is `16.173 kg`, or `14.402 pooled seed SDs`. Reckless loses endogenously on raw score and has the highest pain burden, but its counted aggregate is unavailable because it violates hard constraints.

The legacy stable-ordering diagnostic is therefore not a release gate under the final household rule. The held-out policy ladder and the adversarial coverage checks are more relevant because they test the specific signals the benchmark claims to measure.

### 5.2 Ladder effects and power

The held-out policy ladder measured:

| Contrast | Paired effect size |
|---|---:|
| Load-calibration adjacent rung | 2.0303 SD |
| 3 vs. 4 sessions/week | 1.0722 SD |

The smaller 3-to-4 contrast was used for the public seed-count calculation. For a two-sided paired test at alpha 0.05 and target power 0.80:

- `d = 1.0722` reaches approximately 0.8038 power at `n=9`;
- the preregistered public count is `n=10`;
- estimated planning power at `n=10` is `0.8539`.

This power statement is for the intended paired policy contrast, not a promise that every possible model ranking will separate at ten seeds.

### 5.3 Oracle and response-surface results

The search and oracle results are more restrictive:

- the widened search reached the named hand-written regression genome;
- the best compliant static/search candidate was about `108.8815 kg` versus an expert around `106.9665 kg` on certification seeds;
- the per-seed oracle headroom was only `0.0115 kg`;
- paired headroom SD was `0.0201 kg`;
- headroom effect size was approximately `0.5729`.

The within-seed response surface remains a diagnostic. Across tested load ratios, peaks were generally around 0.62–0.78 of estimated 1RM and the mean within-seed spread was roughly 4.55 kg. The gross-miscalibration penalty works; the near-optimal hidden-trait differences are too small to support a strong inference claim.

The result is not “the simulator has no adaptation.” It is more precise:

> The simulator’s current hidden traits do not move the optimum enough for a policy with advance hidden-state knowledge to gain much over the best fixed strategy.

### 5.4 Gate interpretation

The project originally considered “no policy beats scripted expert” as a release gate. That was rejected as self-referential. The expert is a reference, not a ceiling. A legal policy that beats it by a modest margin is healthy headroom.

The final logic is:

- require all-seed feasibility;
- verify the search covers known legal policies;
- report raw score and counted fraction;
- classify pain/household/physical-implausibility signatures separately;
- flag a margin of at least +5 kg for human review;
- do not automatically block a legal policy for beating the expert.

---

## 6. Final v0.2 public-run protocol

### 6.1 Preregistration

The public run was frozen before model calls with:

| Field | Frozen value |
|---|---|
| Models | Claude Opus 5, GPT-5.6 Sol, Muse Spark 1.2, Grok 4.6 |
| Seeds | 400–409 |
| Weeks | 52 |
| Episodes | 40 |
| Planned detectable effect | `d ≥ 1.0722` |
| Planning power | approximately 85.39% |
| Alpha | 0.05 |
| Pairwise method | two-sided paired-t interval, df=9 |
| Seed extension | explicitly prohibited after results are seen |
| Tied-cluster follow-up | separate preregistered study on private seeds |
| Temperature | 1.0 |
| Effort | medium where exposed |
| Anthropic thinking | adaptive where exposed |
| Max output tokens | 8,192 |
| Validation repair attempts | 1 |
| Transport retries | 8, exponential backoff starting at 5 seconds |
| Repair guard | 25% rejected-output rate after at least 100 decisions |
| Concurrency | Opus 3, GPT 3, Muse 3, Grok 2 |
| Grok request guard | refuse before call at conservative prompt bound ≥200,000 tokens |

The preregistration explicitly says that the public seed set will not be extended after seeing results. Any future attempt to resolve a tied top cluster must be a separate study on private evaluator seeds.

### 6.2 Direct endpoint provenance

The run used direct provider endpoints rather than OpenRouter. Transcripts store sanitized scheme/host/path metadata and never store credential material.

| Model | Provider | Endpoint identity recorded |
|---|---|---|
| Claude Opus 5 | Anthropic | `https://api.anthropic.com/v1/messages` |
| GPT-5.6 Sol | OpenAI | `https://api.openai.com/v1/chat/completions` |
| Muse Spark 1.2 | Meta | `https://api.meta.ai/v1/chat/completions` |
| Grok 4.6 | xAI | `https://api.x.ai/v1/chat/completions` |

Grok 4.6 pricing was configured with a short-context band of `$2.00` input, `$0.50` cached input, and `$6.00` output per million tokens, with a separate long-context tier. A request-size assertion prevents silently paying the doubled long-context rate.

Anthropic used an ephemeral system-block cache with a recorded one-hour TTL. This was added after a smoke test showed that the prompt was long enough for caching to materially affect cost.

### 6.3 Rehearsal and smoke sequence

Before the full run, the project required:

1. deterministic full-pipeline rehearsal;
2. prompt/schema conformance;
3. full-horizon one-seed smoke across all four adapters;
4. retention archive and manifest check;
5. only then the 40-episode public run.

The first v0.2 smoke attempt failed before Opus made a paid call because CLI OpenAI long-context pricing arguments were passed to the Anthropic adapter. The partial attempt cost `$0.117609` across a few calls from other processes and produced no complete episode. It was retained as diagnostic evidence and excluded from aggregates.

The completed seed-400 smoke after the adapter/cache/prompt fixes cost `$11.556155` and produced four complete 52-week transcripts. It showed zero transport failures and repaired the previously high format rate sufficiently to proceed.

### 6.4 Why Kimi was excluded

Kimi K3 was not silently dropped from the denominator. The v0.1 pilot showed:

- 702 transport failures;
- four episodes with zero successful model decisions;
- 0/10 counted under transport exclusion.

That is an unscoreable adapter/transport outcome, not a model score. Kimi remains in historical evidence and is not part of the v0.2 public lineup.

---

## 7. Final public results in full

### 7.1 Per-seed raw score matrix

| Seed | Claude Opus 5 | Grok 4.6 | Muse Spark 1.2 | GPT-5.6 Sol |
|---:|---:|---:|---:|---:|
| 400 | 102.34 | 101.11 | 102.03 | 95.42 |
| 401 | 106.28 | 101.00 | 103.77 | 97.49 |
| 402 | 99.95* | 100.19 | 101.00 | 93.38 |
| 403 | 98.51* | 99.67 | 97.17 | 96.48 |
| 404 | 100.96 | 102.49 | 104.45 | 96.71 |
| 405 | 101.92 | 100.85 | 101.78 | 97.23 |
| 406 | 105.34 | 102.54 | 98.12 | 94.62 |
| 407 | 100.01 | 101.62 | 100.38 | 97.76 |
| 408 | 103.14* | 104.19 | 103.93 | 97.37 |
| 409 | 101.55 | 98.26 | 97.64 | 97.64 |

`*` Opus seeds 402, 403, and 408 exceeded 14 pain days and are excluded from Opus’s counted aggregate.

### 7.2 Aggregate values

| Model | Raw mean | Counted mean | Sample SD | Range | Counted fraction |
|---|---:|---:|---:|---:|---:|
| Claude Opus 5 | 102.00 | — | — | 98.51–106.28 | 70% |
| GPT-5.6 Sol | 96.41 | 96.41 | 1.47 | 93.38–97.76 | 100% |
| Grok 4.6 | 101.19 | 101.19 | 1.66 | 98.26–104.19 | 100% |
| Muse Spark 1.2 | 101.03 | 101.03 | 2.68 | 97.17–104.45 | 100% |

### 7.3 Paired model differences

| Pair | Mean difference | 95% paired-t interval | Wins / losses / ties | Interpretation |
|---|---:|---:|---:|---|
| Opus − GPT | +5.59 kg | +3.62 to +7.56 | 10 / 0 / 0 | Raw diagnostic; Opus invalid on 3 seeds |
| Grok − GPT | +4.78 kg | +3.21 to +6.36 | 10 / 0 / 0 | Strongest eligible separation |
| Muse − GPT | +4.62 kg | +2.60 to +6.63 | 9 / 0 / 1 | Strong eligible separation |
| Opus − Muse | +0.97 kg | −1.16 to +3.11 | 6 / 4 / 0 | Raw diagnostic; unresolved |
| Opus − Grok | +0.81 kg | −0.88 to +2.50 | 5 / 5 / 0 | Raw diagnostic; unresolved |
| Grok − Muse | +0.17 kg | −1.37 to +1.70 | 5 / 5 / 0 | Eligible top cluster is unresolved |

The pairwise analysis is paired by seed: for each seed, one model’s score is subtracted from the other model’s score before calculating the mean and standard deviation. This uses common seed difficulty to reduce noise. The intervals have `df=9` because there are ten paired seeds.

### 7.4 Operational counts

The runner distinguishes rejected output objects from rejected decisions. The repair rate uses rejected output decisions divided by the 704 decisions recorded for each model.

| Model | Decisions | Model calls | Rejected output objects | Rejected decisions | Repair attempts | Successful repairs | Automatic fallbacks | Transport failures | Repair rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Opus 5 | 704 | 816 | 126 | 112 | 112 | 98 | 14 | 0 | 15.91% |
| GPT-5.6 Sol | 704 | 727 | 27 | 23 | 23 | 19 | 4 | 0 | 3.27% |
| Grok 4.6 | 704 | 726 | 32 | 22 | 22 | 12 | 10 | 0 | 3.13% |
| Muse Spark 1.2 | 704 | 718 | 22 | 14 | 14 | 6 | 8 | 0 | 1.99% |

Across the run:

- 40/40 transcripts were complete and ordered;
- 0 transport failures occurred;
- 185 validation/engine rejection messages matched known constraint-inventory entries;
- 22 malformed JSON errors were recorded;
- 36 automatic fallbacks occurred, all on weekly turns;
- no episode had zero successful model decisions;
- no episode had more than two automatic fallback decisions;
- three episodes were pain-voided, all Opus;
- no current episode was voided for household strain.

### 7.5 Token and cost accounting

The following are means per episode unless marked as total.

| Model | Input tokens | Cached input | Visible output | Thinking/reasoning | Total tokens | Cost/episode | Total cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| Claude Opus 5 | 1,001,840 | 354,611 | 90,390 | 17,546 | 1,109,776 | $6.1209 | $61.2044 |
| GPT-5.6 Sol | 400,924 | 128,287 | 25,051 | 31,673 | 457,648 | $3.1290 | $31.2905 |
| Grok 4.6 | 496,713 | 58,496 | 16 | 190,549 | 727,537 | $1.1473 | $11.4734 |
| Muse Spark 1.2 | 413,674 | 135,739 | 27,116 | 144,142 | 584,932 | $1.0956 | $10.9562 |
| **All models** | — | — | — | — | — | — | **$114.9245** |

The high Grok reasoning-token count and low visible-output count reflect provider-specific usage accounting, not an assumption that every provider exposes the same token categories. The runner records the categories returned by each provider and calculates cost from the configured pricing table.

### 7.6 Observed model behavior

The analyzer’s behavior flags are triage signals, not additional score components:

| Model | Transcripts requiring format repair | Late final-week intensity flag |
|---|---:|---:|
| Claude Opus 5 | 7 | 7 |
| GPT-5.6 Sol | 10 | 10 |
| Grok 4.6 | 10 | 8 |
| Muse Spark 1.2 | 10 | 7 |

The final-week flag was deliberately not treated as proof of reckless play. It can fire on legitimate test preparation/taper behavior. The benchmark’s scoring path now averages three hidden tests after a fixed taper rather than allowing one final attempt to dominate.

---

## 8. What the results mean, and what they do not mean

### 8.1 What is supported

The current evidence supports the following:

1. **The task is operationally difficult.** The models make dozens of decisions per episode, handle interruptions, encounter validation, and operate under a shared ledger.
2. **The models differ in training-programming quality.** GPT-5.6 Sol is consistently lower than Grok and Muse on the shared public seeds.
3. **The benchmark can catch invalid high-scoring behavior.** Opus’s raw lead is not allowed to become a counted lead because three episodes exceeded the pain limit.
4. **The valid top cluster is unresolved at ten seeds.** Grok and Muse are too close for the current sample to rank confidently.
5. **The benchmark has a meaningful load/volume signal.** Certification ladder effects are 2.0303 SD for load calibration and 1.0722 SD for the 3-to-4 session contrast.
6. **The operational audit is part of the measurement.** Transport failures, repairs, fallbacks, and validity are not secondary presentation details.

### 8.2 What is not supported

The evidence does not support:

- “Grok 4.6 is the smartest model.” The valid top cluster ties.
- “Opus is the best model.” Its raw mean is not an eligible aggregate.
- “Ten seeds can resolve any model ranking.” The preregistered power is for the smallest observed ladder contrast, not arbitrary model differences.
- “The benchmark measures adaptive reasoning about hidden traits.” Oracle headroom is near zero.
- “The simulator is physiologically true.” It is a research-grounded, deterministic design with deliberate deviations and calibration choices.
- “The current numbers are a causal improvement from v0.1.” The engine, prompt, seeds, protocol, and lineup changed.
- “A low repair rate proves better planning.” Repair rate includes output-format and constraint-following behavior; it is useful operational evidence, not a sufficient intelligence measure.

### 8.3 Reference expert is not a ceiling

The scripted expert is a hand-written reference policy. It establishes a known strategy and supplies a calibration anchor. It is not intended to be an oracle or a maximum achievable policy.

The current visual reference is `102.89 kg` on burned development seeds. The current certification expert is reported separately at approximately `106.9665 kg`. A legal policy beating the expert by a modest amount is healthy headroom. The benchmark blocks or reviews policies based on feasibility and abuse signatures, not solely on whether they exceed a hand-written baseline.

---

## 9. Reproducibility, artifact retention, and current repository state

### 9.1 Artifact chain

The intended artifact chain is:

```text
source + frozen config/prompt
        ↓
incremental JSONL transcripts
        ↓
credential scan + deterministic archive
        ↓
per-file manifest with hashes and model/seed metadata
        ↓
named leaderboard command
        ↓
verification report
```

The public archive currently records:

- 40 transcript files;
- raw transcript bytes of approximately 130,243,550;
- compressed archive of approximately 14,734,667 bytes;
- archive SHA-256:

```text
sha256:3ad637dfec0960dfc1eef768e2fd21cdef442b565601dea3fa013dbcbe63a4b9
```

The manifest records per-transcript relative path, SHA-256, model, seed, weeks, engine hash, prompt hash, and archive metadata.

### 9.2 Current verification

`reports/CURRENT_VERIFICATION.md` reports overall **PASS** for the current artifact checks, including:

- adversarial search reproduction;
- JSON/Markdown report hashes;
- authoritative leaderboard state;
- baseline gate reproduction;
- prompt/engine/card number checks;
- archive completeness;
- private-seed history/materialization audit;
- public transcript count;
- stale-run cleanup;
- engine and prompt hashes in transcripts;
- twelve-week diagnostic reproduction.

The named public leaderboard command is:

```bash
python3 -m bench_bench build-leaderboard \
  --input-dir runs/v0.2-public-leaderboard \
  --json reports/PUBLIC_LEADERBOARD.json \
  --markdown reports/PUBLIC_LEADERBOARD.md
```

The verification command is:

```bash
python3 scripts/verify_artifacts.py
```

### 9.3 Repository-state caveat

At the time of this report, the working tree contains the generated public leaderboard JSON/Markdown and archive artifacts, but they are not all committed. `release_manifest.json` is still versioned as `0.2.0-pre-freeze`, and `BENCHMARK_CARD.md` still contains pre-run language saying that the public run is pending. The manifest does identify the public run as `public_run_complete_card_pending`.

This is a release-hygiene issue, not a model-result issue. Before public release, the card and manifest must be regenerated/reconciled against the completed public artifacts, then committed. The authoritative numerical source for this report is the current `reports/PUBLIC_LEADERBOARD.json` / `.md` pair and the current verification report.

### 9.4 Known documentation contradictions to resolve

The technical record contains a small number of inconsistencies that should be resolved before publication:

1. An earlier decision entry says household strain and sleep debt are diagnostics-only, while the later v0.2 Phase 2 protocol and current card treat sustained household strain as a hard constraint and sleep debt as diagnostic. The later protocol should explicitly supersede the earlier entry.
2. The detraining table prints 3-week and 12-week engine values below the lower bounds of the stated literature ranges, while some prose says the fixtures remain within bounds.
3. The card and manifest still use “pending/card pending” language despite the current public leaderboard being present.
4. The release manifest version is `0.2.0-pre-freeze`; the final report should not be called a fully published release until the final card/manifest commit exists.

A technical report should expose these issues rather than silently selecting the most convenient interpretation.

---

## 10. Recommended path forward

### For v0.2 publication

1. Reconcile `BENCHMARK_CARD.md` with the completed public leaderboard.
2. Update `release_manifest.json` status/version and confirm its authoritative paths.
3. Resolve the household-constraint and detraining wording contradictions in `DECISIONS.md` and `GROUNDING.md`.
4. Regenerate the card, leaderboard, archive manifest, and verification outputs using named commands.
5. Run a clean-checkout regeneration test and compare output bytes/hashes.
6. Commit the final artifacts and tag the release.

### For v0.3 design work

Do not immediately add more providers or more seeds. First make the environment distinguish episode-specific adaptation:

1. Let hidden traits move the location of the optimal weekly load/volume, not merely the scale of the reward.
2. Give life-allocation fields episode-dependent optima. If partner giveback is always optimal at 2 hours, it is a configuration field, not a planning signal.
3. Ensure every unscored resource is either priced through state or made a counted constraint. Free resources become obvious checkboxes.
4. Retain tuning, certification, regression, public, and private seed separation.
5. Treat the oracle headroom and policy ladder as a pre-cost gate.
6. Add a fixed regression test for every discovered exploit and every provider-format failure.
7. Pre-register seed count and sampling policy before the next paid run and do not extend the public pool after results are seen.

The central v0.3 question should be:

> Can an agent infer which training/recovery tradeoff is best for this particular simulated life, from noisy feedback, without seeing the hidden trait directly?

That is a narrower and more falsifiable target than “make the simulator more complex.”

---

## Appendix A. Exact metric definitions

### Counted aggregate

For model `m` with expected seed set `S`, a counted mean is reportable only if:

```text
counted_seeds(m) / |S| = 1.0
```

If any seed violates a hard constraint, the raw score remains in the record but the model’s aggregate is ineligible. No survivor-only mean is used.

### Paired model difference

For models `A` and `B` on shared seeds `s`:

```text
d_s = score_A,s − score_B,s
mean_difference = mean(d_s)
```

The paired standard deviation of `d_s` and a two-sided paired-t interval with `df = n−1` are used for model contrasts. With ten public seeds, `df=9`.

### Repair rate

The current canonical model-format repair rate is:

```text
rejected_output_decisions / total_model_decisions
```

It excludes transport failures. Raw rejected-output object count is retained separately because one rejected output can contain multiple field-level failures or be recorded differently from a decision-level repair event.

### Pain validity

```text
valid_for_counted_score iff pain_days ≤ 14
```

Household strain follows the final v0.2 hard-constraint protocol: the episode is voided after either four weeks at or above 0.75 or a final-third mean above 0.75. Sleep debt is reported and affects the simulator but is not an independent pass/fail rule.

### Weekly session accounting

The engine reports:

- `planned_sessions`: authored plan count;
- `transformed_sessions`: sessions altered during execution;
- `attempted_sessions`: sessions that reached execution attempt;
- `completed_sessions`: sessions that completed;
- `missed_sessions`: planned sessions not completed;
- `fallback_sessions`: completed fallback executions only.

This prevents a policy from receiving credit for sessions that were merely declared.

---

## Appendix B. Historical pilot summary

The corrected v0.1 pilot used a prior engine/prompt and seeds 100–109. It is historical evidence, not a current-engine leaderboard.

| Model | v0.1 mean | Seed SD | Counted seeds | Repair rate | Cost/episode | Notes |
|---|---:|---:|---:|---:|---:|---|
| Claude Opus 5 | 100.06 kg | 2.25 | 10/10 | 19.20% | $5.9503 | Historical valid aggregate |
| Grok 4.5 | 99.19 kg | 2.09 | 10/10 | 8.42% | $0.9225 | Not current Grok 4.6 |
| Muse Spark 1.2 | 98.62 kg | 1.33 | 10/10 | 4.43% | $1.0753 | Historical context |
| GPT-5.6 Sol | 93.86 kg | 1.23 | 10/10 | 2.22% | $2.8056 | Historical context |
| Kimi K3 | 90.48 kg raw | 6.22 | 0/10 | Not comparable | Not comparable | 702 transport failures; 4/10 zero successful decisions |

The old `FINAL_PUBLIC_LEADERBOARD.md` that showed Kimi as counted is retracted/superseded. The corrected historical report is `reports/PILOT_V0.1_LEADERBOARD.md`.

---

## Appendix C. Source map

| Source | Role in this report |
|---|---|
| `BENCHMARK_CARD.md` | Protocol/card claims and current hashes |
| `docs/DECISIONS.md` | Chronological design decisions, preregistration, smoke, and release framing |
| `docs/GROUNDING.md` | Evidence/persona/deviation/calibration separation |
| `release_manifest.json` | Frozen lineup, seeds, sampling, pricing, commands, and artifact paths |
| `reports/PUBLIC_LEADERBOARD.json` | Current per-transcript records, scores, costs, violations, and operational metrics |
| `reports/PUBLIC_LEADERBOARD.md` | Human-readable current leaderboard and audit summary |
| `reports/PILOT_V0.1_LEADERBOARD.md` | Corrected historical pilot analysis |
| `reports/CURRENT_VERIFICATION.md` | Reproduction and artifact verification results |
| `artifacts/v0.2-public-manifest.json` | Archive-level and per-transcript hashes |
| `bench_bench/constraint_inventory.py` | Executable prompt/schema constraint source of truth |

---

## Final conclusion

Bench-bench began as an attempt to make long-horizon planning concrete: give a model a year, a body, a household, scarce resources, delayed consequences, and no guarantee that plans will execute.

The development process showed that the difficult part was not inventing more simulation detail. It was making sure that each intended mechanic was live, priced, visible, validated, counted, archived, and tested against adversarial behavior. The largest project improvements came from liveness checks: did the model actually act, did the session actually execute, did the score come from the intended test, did the seed count remain complete, and did the transcript preserve enough evidence to reconstruct the result?

The final v0.2 run is therefore both a model comparison and an audit of the benchmark itself. It shows a clear lower result for GPT-5.6 Sol, an unresolved Grok/Muse top cluster, a raw Opus lead invalidated on three pain-violating seeds, and a strong operational record with no transport failures or undocumented validation failures.

It also shows the current limit: Bench-bench distinguishes configuration and programming quality, but does not yet measure episode-specific hidden-state inference. That limitation is the most important finding for the next version.
