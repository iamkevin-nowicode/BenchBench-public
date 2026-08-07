# Bench-bench Codex Handoff — Version 3

This pack defines Bench-bench and its three evaluation tracks: model-only, frozen-web tool use, and open-web experimental.

## Recommended official track

Frozen-web tool use provides realistic search and forum/article interaction while preserving reproducibility.

## Sequence

1. Read all specification files.
2. Send `01_INITIAL_CODEX_MESSAGE.md`.
3. Send `02_MILESTONE_0_ARCHITECTURE.md`.
4. Continue using `CODEX_SEQUENTIAL_DIRECTIONS.md`.
5. Approve every milestone before Codex proceeds.

Core simulator outcomes must remain deterministic. Retrieved information can influence decisions but never directly determine state or score.
