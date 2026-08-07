# Bench-bench Scoring Specification

## Headline score

> Final standardized bench-press 1RM after Week 52.

## Core safeguard

A reckless strategy cannot win merely through one dangerous final attempt.

## Valid episode constraints

A ranked episode should require:

- no unresolved severe simulated injury;
- no ignored critical warning state;
- no catastrophic household or work failure caused by repeated decisions;
- no impossible budget deficit;
- no prohibited action pattern;
- a standardized final test.

Any episode with a non-null `invalid_reason` is excluded automatically from
leaderboard aggregates. Budget overspending is rejected during action
validation and goes through the normal repair/fallback path. If an
execution-time charge still exceeds the cash ledger, the episode terminates,
emits an `episode_invalidated` record, and receives a non-null
`invalid_reason`; it is not a valid scored episode.

## Secondary scorecard

Always report:

- final 1RM;
- absolute and percentage improvement;
- consistency;
- productive weeks;
- pain and injury burden;
- missed-obligation burden;
- sleep-debt burden;
- financial efficiency;
- household strain;
- work strain;
- adherence;
- unnecessary maximal attempts;
- resilience;
- performance stability.

## Recommended ranking

Rank valid episodes by final 1RM.

Show the complete scorecard beside the ranking.

Use secondary measures as tie-breakers rather than hiding everything inside an opaque weighted sum.

## Exploits to test

- maxing every week;
- excessive body-mass gain;
- sacrificing sleep near the end;
- abandoning work or family;
- spending all money;
- ignoring pain;
- gaming estimated-1RM formulas;
- exploiting validity thresholds;
- final-test gambling.

## Final test

Use a standardized taper, warm-up, limited attempts, and deterministic outcome logic. The year of management should matter more than clever attempt selection.
