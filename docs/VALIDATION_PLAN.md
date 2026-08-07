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
