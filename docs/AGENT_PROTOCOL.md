# Bench-bench Agent Protocol

## Daily loop

1. Environment emits a structured observation.
2. Agent returns a structured plan.
3. Environment validates the plan.
4. Environment advances one day.
5. Immediate results are returned.
6. A compressed weekly summary appears every seven days.

## Tracks

### Model-only

The model receives observations and returns plans without external tools.

### Tool-enabled

The model may use approved calculator, calendar, notes, and structured state-query tools. All calls are logged.

### Policy baselines

- random;
- rigid novice program;
- fixed linear progression;
- recovery-aware heuristic;
- reckless maximalist;
- skip-when-busy;
- approximate oracle.

## Invalid actions

Return a clear error, allow one standardized repair attempt, then use a safe fallback action. Formatting difficulty should not dominate.

## Required reporting

Record model, version, provider, scaffold, track, history policy, tools, retries, sampling settings, token use, cost, benchmark version, and seeds.

## Separation

The environment evaluates decisions. The scaffold handles formatting, context, tools, and retries. Reports must distinguish model quality from scaffold quality.
