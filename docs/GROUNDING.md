# Bench-bench v0.2 grounding

This document freezes the physiological and persona assumptions used for the
v0.2 redesign before calibration. It is deliberately a range-and-rationale
document, not a claim that a small simulator reproduces human physiology.
The implementation uses evidence for direction, delays, and plausible bounds;
the exact coefficients remain benchmark calibration choices.

## 1. Evidence-supported anchors

### Fitness and fatigue

The simulator uses a Banister-style impulse-response model: training creates a
longer-lived fitness signal and a shorter-lived fatigue signal. Across training
and detraining literature, neither time constant is universal; plausible
engineering ranges for a recreational-to-trained strength task are:

| Quantity | Grounded range | v0.2 starting choice | Confidence | Use |
|---|---:|---:|---|---|
| fitness time constant | 42–84 days | 56 days | moderate for direction, low for exact value | delayed adaptation and detraining |
| fatigue time constant | 7–21 days | 10 days | moderate for direction, low for exact value | recovery and over-reaching |
| useful weekly exposures | 2–4 sessions | 3–4 open days | moderate | frequency opportunity, not a prescription |
| novice-range one-year improvement | roughly 10–30% from a novice-range baseline | calibration guard only | low-to-moderate and population-dependent | plausibility ceiling, not a target score |

The v0.2 engine therefore keeps delayed adaptation, but does not treat the
Banister constants as universal truths. The smooth over-reaching term is an
explicit model extension: it represents the empirical fact that additional
work does not remain equally productive once recovery and connective-tissue
capacity are exceeded.

The current scripted-expert result is approximately +26.8% over the 84 kg
starting bench on certification seeds. That magnitude is not being retuned in
this phase: it is a ceiling guard. It is conservative relative to the supplied
Ogasawara anchors (+21.0% at six weeks and +51.3% at 24 weeks in previously
untrained subjects), while the best current static template is approximately
+29.6%, near the upper end of the 10–30% plausibility range used here. These
comparisons justify a guard against implausibly large annual gains; they do not
claim that the cited studies determine Dave's exact response.

### Detraining regression guard

The CI fixture runs the scripted expert through week 24, removes bench-training
sessions for a specified mid-episode layoff while preserving that week's life
allocation, then resumes the expert. The current observations on seeds 320–327
are retained as diagnostics and checked against the literature upper bounds:

| Layoff | Current engine loss | Literature reference | CI rule |
|---|---:|---:|---|
| 3 weeks | approximately 1.0% | 2.0–3.3% (Ogasawara) | no greater than 3.3% |
| 10 weeks | approximately 3.5–3.9% | 3–6% (Halonen) | no greater than 6% |
| 12 weeks | approximately 4.5–5.0% | 5–15% (Blocquiaux) | no greater than 15% |

The lower ends are descriptive literature ranges, not minimum requirements for
this deliberately conservative simulator. Detraining/retraining literature
does not define the pain-days or household-strain thresholds; those remain
persona-based benchmark design choices above.

### Load and repetitions

The Brzycki relationship is used as a conservative rep-max envelope:

`estimated 1RM ≈ load × 36 / (37 − repetitions)`

It is a practical load/repetition approximation, not a measurement of Dave's
true capacity. The engine uses it to prevent a high-repetition prescription
from receiving the same credit as a physically compatible set. Duration also
limits delivered repetitions; neither rule is intended to select the model's
training strategy.

### Frequency, volume, and adaptation

Strength and hypertrophy literature generally supports a positive response to
more weekly resistance-training work within a useful range, with diminishing
returns and substantial individual variation. Ralston et al. report a graded
volume–strength relationship, while Grgic et al. find that much of the apparent
frequency advantage disappears when weekly volume is equated [E; supplied
report, refs. 4 and 10]. The engine therefore treats frequency as an
opportunity to deliver volume, not as an independent reward: three versus four
sessions matters only when the fourth session changes executed work that
survives the volume and over-reaching curves.

The active response is accumulated executed volume followed by the hidden
episode-specific smooth over-reaching penalty [D]. This is the benchmark's
graded volume term; there is no independent frequency multiplier. The exact
over-reaching curvature remains a calibration choice [C], not a fitted human
dose-response coefficient. Missed and transformed sessions contribute only
their executed stimulus.

### Sleep restriction, adherence, and session quality — 2026-08-14

The supplied calibration report changes the sleep model's direction without
changing the ledger costs. Borba et al. (2024) found no consistent attenuation
of training response across a roughly 89-minute habitual nightly sleep gap in
16 resistance-training sessions, though the study was small and used fixed-
resistance repetition tests rather than bench 1RM [E; supplied report, refs.
1, 6, 7]. That is evidence against a large continuous annual strength penalty
from ordinary marginal sleep differences, not evidence that sleep has no
effect.

Dave's infant, full-time-work, partner-work, and household-support situation is
part of the fictional persona rather than a physiological finding [P]. It
justifies making sleep protection a scarce planning decision, but it does not
identify the sleep-to-strength coefficient.

The sleep calendar center is now 6.72 hours/night. Parent actigraphy gives the
direction for lowering the prior 6.92-hour center: Kalogeropoulos et al.
reported fathers averaging 6.68 hours and Tikotzky et al. reported mothers at
approximately 6.24 hours around six months postpartum [E; supplied report,
refs. 17–19, 26]. The exact 6.72-hour value, and the resulting normal-week
range of roughly 6.5–6.8 hours with event troughs around 5.5–6.0 hours, are
calibration choices rather than a universal parent norm [C].

- Protection remains +11 minutes/night for `standard` and +21 minutes/night
  for `strong` [C]. The former is plausible relative to Stremler et al.'s
  +5.97-minute RCT estimate; the latter is plausible but mildly optimistic
  relative to Hart et al.'s +20-minute estimate [E/C; supplied report, refs.
  21–24].
- Adherence uses a threshold-shaped scenario below 6 hours rather than a
  continuous per-hour penalty [E/D/C]. Kekkonen et al. (FINGER) found nearly
  identical adherence classification at 6–<7 and 7–<8 hours, but materially
  worse adherence below 6 hours [E; supplied report, ref. 15]. The 6-hour
  breakpoint and penalty slope are calibration choices, not identified
  coefficients [C].
- Conditional on a session occurring, sleep applies a modest quality modifier
  to executed stimulus below that same threshold [E/D/C]. Knowles et al.
  observed lower movement velocity without a meaningful volume-load change
  after nine nights at 5 hours, supporting a quality pathway rather than a
  completion-only term [E; supplied report, ref. 3]. The slope and floor are
  calibration choices [C].
- Severe restriction remains consequential through the thresholded adherence
  term, the quality modifier, sleep debt's effect on the sleep trajectory, and
  the existing fatigue/injury pathways. Saner et al.'s 4-hour time-in-bed
  finding supports biological plausibility for severe impairment but does not
  provide a strength-gain coefficient [E; supplied report, ref. 2].

Sleep's architecture is therefore a deliberate moderator of realized training
response, not an additive strength term [D]. The report explicitly finds that
the annual sleep-to-1RM coefficient is not identifiable and that sleep should
not be treated as the dominant determinant [E/C; supplied report, refs. 4, 5,
9, 30].

### Nutrition and body mass

Adequate energy and protein support training and recovery; body mass can affect
absolute strength, but the relationship is not a precise linear conversion
for one fictional lifter. The simulator uses a small bounded mass pathway and
nutrition-dependent recovery. It does not reward unlimited mass gain, and
nutrition is not a hidden score multiplier detached from the life plan.

## 2. Persona assumptions

These are design inputs for Dave, not general physiological findings:

- Dave is 38, 84 kg, and novice-range for this episode: he trained casually
  in his twenties, has not lifted seriously in years, and has no meaningful
  recent training base. His week-0 bench and body mass are both 84 kg. There
  is no prior peak to recover; the intended trajectory is new-training
  progression, not recovery of an old maximum.
- He works full-time; his partner also works full-time; an infant is present at
  the start of the year.
- The household has a commercial-gym membership, no home equipment initially,
  and $250/month of discretionary money that carries over.
- The published v0.2 ledger is 900 minutes per week. It includes training and
  commute, meal preparation, childcare, chores, partner coverage, and
  giveback. A fixed household baseline reserve is charged inside that same
  pool so an agent cannot make ordinary obligations disappear by declaring
  zero allocation.
- Sustained household strain is a hard constraint. The threshold is 0.75;
  four weeks at or above that level is treated as approximately one month of
  persistent overload, and a final-third (13-week) mean above 0.75 captures
  chronic late-year overload. A single peak is reported but does not void the
  episode. These values are set from the persona before observing policy
  results, not chosen to make a particular baseline fail.
- Sleep debt remains a diagnostic. It is not a separate pass/fail rule, but
  severe sleep loss still affects the sleep trajectory, energy observations,
  fatigue/injury pathways, thresholded adherence, and executed-stimulus quality.
  This is a deliberate architecture choice, not a claim that sleep is
  unimportant [D].
- The pain-days limit and sustained household-strain threshold are
  benchmark-design choices set from this persona, not evidence-derived
  physiological thresholds. Detraining and retraining literature can bound
  strength-loss and regain behavior; it cannot supply a valid pain-days or
  household-strain cutoff for this fictional household.

## 3. Deliberate simulator deviations

The following are intentionally simplified or benchmark-specific:

- A deterministic pre-rolled environment is used so paired policy comparisons
  are reproducible and action choices do not reshuffle future randomness.
- Hidden traits are represented by compact latent variables rather than a
  clinical athlete model. `volume_tolerance` shifts the over-reaching/injury
  boundary; it is not a universal genetic scale factor.
- Injury is a cumulative exposure model with a load-onset boundary. A normal
  0.89×-capacity session does not create an acute load injury solely because it
  is heavy; repeated exposure, excessive volume, sleep loss, and joint-specific
  work can still accumulate irritation.
- The standardized score is the average of hidden tests at weeks 44, 48, and
  52 after a fixed three-day taper. This makes late-year management matter
  while reducing the chance that one final attempt dominates the result.
- Sustained household strain is counted as a constraint, while sleep debt is
  reported as a diagnostic. This asymmetry is a resource-pricing decision, not
  a claim that sleep is unimportant.

## 4. Calibration choices to be tuned only on tuning seeds

The following values are calibration choices, not evidence claims:

- fitness and fatigue strength-to-kg coefficients, constrained to keep the
  novice-range outcome within the 10–30% plausibility range;
- the hidden optimum weekly stimulus and smooth over-reaching curvature;
- the 6-hour sleep-adherence breakpoint, threshold slopes, and quality floor;
- the injury exposure thresholds and recovery duration;
- the fixed household baseline reserve and the relative gym/home time costs;
- the size of consistency drift after four productive weeks.

Calibration must not use certification, regression, or public leaderboard
seeds. A stronger static template beating the scripted expert is reported as
headroom, not treated as a calibration failure.

## 5. Seed pools and release gates

The v0.2 pools are disjoint:

| Pool | Values | Purpose |
|---|---|---|
| tuning | 300–319 | engine calibration and adversarial search |
| certification | 320–339 | oracle headroom and policy-ladder certification |
| regression | 340–349 | fixed exploit and reviewer-policy regressions |
| public leaderboard | 400–409 | paid model comparison |

Private evaluation values remain out-of-band and are not written here, in
source, tests, configs, reports, or Git history.

The v0.2 release gate is the held-out policy ladder:

1. every load and session-frequency rung is all-seed compliant;
2. adjacent load-calibration and session-frequency rungs have paired effect
   size at least 0.64 at the intended certification seed count;
3. every life-allocation field has an explicit ledger, cash, household, or
   event consequence; partner-giveback's seed-wise optimum is reported as a
   diagnostic rather than collapsed into a magnitude dominance ratio;
4. the adversarial search reaches the known hand-written regression genome (or
   a better all-seed-compliant policy) before any headroom claim is reported;
5. known regression policies remain visible and no policy is released as a
   claim without all-seed compliance with the hard constraints.

Oracle adaptation headroom remains a secondary diagnostic. The former 3×
oracle proposal is not a release gate; the 1× paired-headroom-SD value is
reported for context only.

“Scripted expert beats every static template” is not a gate. It is a reported
diagnostic because a better legal static policy is healthy headroom.

The within-seed response surface—score versus load ratio, with peak location
and spread per certification seed—is a standing diagnostic, not a release
gate. It is a liveness check on whether the search is measuring the relevant
region of the action space.

## References and scope

The conceptual anchors are Banister et al., “A systems model of training for
athletic performance” (1975); Mujika and Padilla, the two-part *Detraining*
reviews in *Sports Medicine* (2000); Rhea et al., “A meta-analysis to
determine the dose response for strength development” (2003); later
resistance-training frequency and volume systematic reviews; and Brzycki,
“Strength Testing—Predicting a One-Rep Max from Reps-to-Fatigue” (1993).

These references support the direction of the model, not the numerical
coefficients. Before publication, the bibliography should be checked against
the final cited editions and expanded with the specific frequency, sleep,
nutrition, and returning-lifter evidence used to justify any coefficient that
survives calibration.
