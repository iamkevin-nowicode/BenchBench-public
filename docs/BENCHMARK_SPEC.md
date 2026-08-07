# Bench-bench Benchmark Specification

## Episode

- One full episode represents 52 weeks.
- Recommended timestep: one day.
- Every seven days, the environment generates a weekly summary.
- Build a 12-week vertical slice before the full year.

## Canonical scenario

A fictional 38-year-old working parent with:

- a full-time job;
- a six-month-old baby;
- household responsibilities;
- limited discretionary time;
- a limited convenience budget;
- a goal of increasing bench-press strength.

The initial release should use one canonical profile. Variants come later.

## Visible state

The agent receives:

- date;
- estimated bench 1RM;
- recent training;
- known obligations;
- flexible time;
- sleep duration and estimated quality;
- perceived energy;
- soreness and pain signals;
- stress;
- nutrition summary;
- body-mass trend;
- budget;
- equipment access;
- upcoming events;
- measurement uncertainty.

## Hidden state

The simulator may track:

- accumulated fatigue;
- adaptation readiness;
- injury susceptibility;
- tissue irritation;
- illness susceptibility;
- burnout risk;
- household strain;
- work strain;
- training responsiveness;
- recovery capacity;
- adherence probability;
- latent motivation;
- sleep debt;
- technique development;
- confidence under heavy load.

Hidden state must influence observable signals. It must not create arbitrary, causally disconnected punishment.

## Agent decisions

### Training

Train, rest, select exercises, choose sets/reps/load, cap effort, shorten sessions, deload, perform technique work, use a fallback session, or schedule a test.

### Recovery

Protect sleep, nap, choose active recovery, take full rest, reduce future load, or seek simulated professional evaluation.

### Nutrition

Meal prep, groceries, convenience meals, protein-supportive meals, hydration, and broad calorie-support choices.

### Time and obligations

Schedule or move training, shorten it, delegate chores, postpone nonessential tasks, use paid help, ask for coverage, or choose home versus gym.

### Financial

Spend on gym access, home equipment, childcare, meal delivery, transportation, or simulated professional care.

### Strategy

Set training blocks, weekly priorities, progression style, minimum viable workouts, fallback plans, and reserves.

## Event families

- infant sleep disruption;
- work deadlines;
- partner illness;
- daycare closure;
- travel;
- gym closure;
- minor illness;
- overtime;
- visitors;
- household repairs;
- budget shocks;
- childcare help;
- missed food preparation;
- pain warnings;
- motivation decline;
- social obligations.

## Strong behavior

Strong agents should preserve consistency, progress when ready, reduce load when warnings accumulate, prepare for predictable disruptions, use shorter sessions instead of unnecessary cancellation, protect reserves, and avoid panic after setbacks.

## Weak behavior

Weak agents may max frequently, sacrifice sleep, skip all training during busy periods, ignore warning signals, constantly redesign the program, choose impossible schedules, or optimize only the current estimated 1RM.
