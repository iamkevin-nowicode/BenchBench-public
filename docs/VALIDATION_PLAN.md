# Bench-bench Validation Plan

## Construct-validity question

Does Bench-bench reward sustainable long-horizon planning under fatigue, uncertainty, and competing obligations?

## Expected broad ordering

random
< rigid or reckless policies
< simple adaptive heuristics
< capable planning agents
< approximate oracle

## Required experiments

### Phase 3 measurement contract

Before oracle search or policy-ladder certification, the harness applies the
same accounting to every candidate. A candidate episode with a weekly
validation-fallback rate above 5% is infeasible and is discarded from counted
and gate aggregates. Its raw score and fallback rate remain diagnostics, so a
safe-fallback trajectory cannot masquerade as the authored policy.

Absolute final 1RM in kg remains the headline. The comparison/gate metric is
the paired per-seed normalized delta:

`candidate score(seed) − scripted-expert score(seed)`

The normalized mean and sample SD are reportable as diagnostics for structural
episodes, but a candidate is eligible for a Phase 3 comparison only when every
expected seed is feasible and has a reference value. The paired effect size is
the normalized mean divided by the normalized sample SD. The harness also
reports raw seed SD, reference seed SD, and the candidate/reference volatility
ratio so a mean-only gate cannot hide a stability difference.

The Phase 3 release gate is the held-out policy ladder: all load and
session-frequency rungs must be all-seed compliant; adjacent rungs must reach
paired effect size 0.64 at the intended certification seed count; and every
life-allocation field must have an explicit ledger, cash, household, or event
consequence. Partner-giveback's seed-wise optimum is reported as a diagnostic,
not collapsed into a magnitude dominance ratio. The search must also reach or
exceed the named hand-written regression genome on every certification seed
before any headroom claim is reportable. Oracle headroom remains a secondary
diagnostic; the earlier 3× proposal is not a release gate and the 1×
paired-headroom-SD value is reported for context only. The within-seed
load-ratio response surface, including peak location and spread, remains a
standing diagnostic rather than a release gate.

### Baseline comparison

Measure final 1RM, injury burden, adherence, life stability, variance, and seed sensitivity across many episodes.

### Ablations

Remove or neutralize:

- sleep;
- delayed adaptation;
- injury risk;
- work constraints;
- household constraints;
- money;
- uncertainty;
- known future events;
- long horizon.

A mechanic that does not affect decisions or rankings may not belong.

### Exploit agents

Test agents that max frequently, sacrifice sleep, ignore obligations, overspend, train only when fresh, never train when tired, overdo volume, constantly switch plans, or game the final test.

### Counterfactual replay

For major failures, replay with one changed decision to show whether earlier sleep, reduced load, preserved budget, childcare spending, fallback sessions, or earlier pain response would improve the result.

### Human evaluation

Check whether nonexperts understand the interface, form strategies, notice delayed consequences, outperform random behavior, and explain outcomes.

### Expert review

Seek input from strength coaches, exercise scientists, physical therapists or sports-medicine professionals, working parents, sleep researchers, and benchmark researchers.

## Interpretability requirement

Every episode should reveal major strategic choices, preventable mistakes, causes of missed training, causes of injury or plateau, and why its final score differed from another run.
