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
| returning-lifter one-year improvement | roughly 10–30% from a detrained baseline | calibration range only | low-to-moderate and population-dependent | plausibility check, not a target score |

The v0.2 engine therefore keeps delayed adaptation, but does not treat the
Banister constants as universal truths. The smooth over-reaching term is an
explicit model extension: it represents the empirical fact that additional
work does not remain equally productive once recovery and connective-tissue
capacity are exceeded.

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
returns and substantial individual variation. The v0.2 design consequently
lets hidden volume tolerance shift the point at which over-reaching begins. It
does not multiply every session's reward by the trait: two episodes can have
different best weekly volumes while receiving the same stimulus for the same
executed work below their respective optimum.

### Nutrition and body mass

Adequate energy and protein support training and recovery; body mass can affect
absolute strength, but the relationship is not a precise linear conversion
for one fictional lifter. The simulator uses a small bounded mass pathway and
nutrition-dependent recovery. It does not reward unlimited mass gain, and
nutrition is not a hidden score multiplier detached from the life plan.

## 2. Persona assumptions

These are design inputs for Dave, not general physiological findings:

- Dave is 38, 84 kg, and returning to bench training after detraining.
- He works full-time; his partner also works full-time; an infant is present at
  the start of the year.
- The household has a commercial-gym membership, no home equipment initially,
  and $250/month of discretionary money that carries over.
- The published v0.2 ledger is 900 minutes per week. It includes training and
  commute, meal preparation, childcare, chores, partner coverage, and
  giveback. A fixed household baseline reserve is charged inside that same
  pool so an agent cannot make ordinary obligations disappear by declaring
  zero allocation.
- Household strain above 0.75 is a hard constraint violation. This is a
  persona boundary: sustained near-ceiling strain is not an acceptable way for
  a working parent to pursue a one-rep max. The value is set from the persona
  before observing policy results, not chosen to make a particular baseline
  fail.
- Sleep debt remains a diagnostic. It already reduces readiness and recovery,
  so it is not an unpriced resource; burning sleep has endogenous performance
  cost even though it is not a separate pass/fail rule.

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
- Household strain is counted as a constraint, while sleep debt is reported as
  a diagnostic. This asymmetry is a resource-pricing decision, not a claim that
  sleep is unimportant.

## 4. Calibration choices to be tuned only on tuning seeds

The following values are calibration choices, not evidence claims:

- fitness and fatigue strength-to-kg coefficients, constrained to keep the
  returning-lifter outcome within the 10–30% plausibility range;
- the hidden optimum weekly stimulus and the smooth over-reaching curvature;
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

The v0.2 release gate is:

1. oracle adaptation headroom on certification seeds is at least 3× the
   certification-seed standard deviation;
2. adjacent rungs of the policy ladder separate at the intended seed count;
3. known regression policies remain visible and no policy is released as a
   claim without all-seed compliance with the hard constraints.

“Scripted expert beats every static template” is not a gate. It is a reported
diagnostic because a better legal static policy is healthy headroom.

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
