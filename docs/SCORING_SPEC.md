# Bench-bench Scoring Specification

## Headline score

> The arithmetic mean of the standardized bench-press 1RM projections at
> hidden tests in Weeks 44, 48, and 52, after each test's fixed three-day
> taper.

## Core safeguard

The behavioral constraints on the headline score are `pain_days ≤ 14` and
sustained household strain. Household strain is a violation when it reaches
or exceeds `0.75` in at least four weeks, or when the mean over the final 13
weeks is above `0.75`. A one-week peak is retained as a diagnostic and does
not void an episode. Sleep debt remains a reported diagnostic because it
already reduces readiness and recovery endogenously. A reckless strategy
therefore cannot win by treating persistent family strain or pain as a free
resource, while raw results remain available for diagnosis.

Structural validity is separate from the behavioral constraint. Any episode
with a non-null `invalid_reason` is excluded automatically from leaderboard
aggregates. Budget overspending is rejected during action validation and goes
through the normal repair/fallback path. If an execution-time charge still
exceeds the cash ledger, the episode terminates, emits an
`episode_invalidated` record, and receives a non-null `invalid_reason`; it is
not a valid scored episode.

For a structurally valid episode, `raw_final_1rm_kg` is always retained. The
counted score is `counted_final_1rm_kg`, which is null when `pain_days > 14`.
The leaderboard reports both fields and a `violations` column.

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
- household strain, including final value, peak, high-strain weeks, and final-third mean;
- work strain;
- adherence;
- unnecessary maximal attempts;
- resilience;
- performance stability.

Session accounting is explicit at both week and episode level:

- `planned_sessions`: sessions authored in the weekly action;
- `transformed_sessions`: planned sessions changed by a standing or reactive rule;
- `attempted_sessions`: sessions that reached execution;
- `completed_sessions`: successful executions;
- `missed_sessions`: cancellations or failed attempts.

`fallback_sessions` is a separate completed-work count: it includes only
fallback-focus sessions that actually completed. A fallback that is cancelled,
equipment-blocked, time-blocked, or lost to adherence remains missed.

Declared work is duration-coupled at one prescribed repetition per minute
across all focuses. Loads below 0.35× true capacity are warm-up-only and earn
no strength or technique stimulus. Productive-week qualification is based on
delivered stimulus, not merely the number of completed session records.

Within a week, raw stimulus is accumulated and passed through a smooth
over-reaching curve. There is no hard weekly cap. Each episode has a hidden
volume/recovery optimum; work above it is penalized by
`delivered = raw × exp(−k × max(0, raw/optimum − 1)²)`. The same delivered
credit controls fitness, technique learning, and productive-week qualification.

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
