# Bench-bench Simulator Specification

## Objective

Model enough causal structure to require planning without pretending to reproduce human physiology exactly.

## State domains

### Strength

- underlying force capacity;
- estimated 1RM;
- technical proficiency;
- confidence under load;
- recent heavy exposure;
- adaptation potential.

### Fatigue and recovery

- acute fatigue;
- chronic fatigue;
- sleep debt;
- local fatigue;
- connective-tissue irritation;
- stress load;
- illness load;
- recovery readiness.

### Training stimulus

Every session produces some combination of:

- useful stimulus;
- fatigue;
- local stress;
- time cost;
- motivation effect;
- technique adaptation;
- injury-risk change.

Stimulus depends on load, volume, effort, specificity, readiness, recent training, technique, and duration.

### Adaptation

Adaptation is delayed and should include:

- accumulated effective stimulus;
- recovery gating;
- diminishing returns;
- detraining;
- specificity;
- individual responsiveness.

### Pain and injury

Use a warning progression:

1. mild irritation;
2. recurring pain;
3. performance inhibition;
4. forced reduction;
5. simulated professional evaluation;
6. recovery period.

Risk must depend on prior decisions, not pure bad luck.

### Sleep

Sleep affects recovery, fatigue, illness susceptibility, training quality, adherence, work, and household function.

Sleep opportunity and actual sleep differ because the infant may interrupt it.

### Nutrition

Use broad states such as insufficient, adequate, and high-support rather than precise diet micromanagement.

### Time

Each day contains mandatory commitments and finite flexible time.

### Energy and attention

Having time does not guarantee execution. Actions also require physical and cognitive capacity.

### Household and work

Repeatedly externalizing costs creates future strain and reduces flexibility.

### Money

Money can buy flexibility, but the convenience budget is limited.

## Observation model

The agent sees imperfect estimates such as low/medium/high energy, soreness ratings, sleep quality, pain descriptions, estimated 1RM ranges, and strain indicators.

## Determinism

The same simulator version, scenario, seed, and action sequence must replay identically.

## Vertical slice

The first implementation contains:

- 12 weeks;
- one canonical person;
- daily steps;
- weekly summaries;
- work-pressure periods;
- infant sleep disruption;
- budget constraints;
- illness events;
- pain pathways;
- gym and home options;
- baseline policies;
- human-readable replay.

## Avoid initially

- detailed biomechanics;
- exact medical diagnoses;
- dozens of exercises;
- supplement stacks;
- every nutrient;
- complete relationship dialogue;
- a full household simulator.
