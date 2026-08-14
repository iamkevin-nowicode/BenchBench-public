# Bench-bench

A long-horizon decision-making benchmark for AI agents: manage one simulated year in the life of a 38-year-old father of an infant and maximize his bench-press 1RM across hidden standardized tests at weeks 44, 48, and 52 — without wrecking his sleep, budget, family, or joints.

> Naming: the project is **Bench-bench** (hyphenated, exactly this capitalization). Repo `bench-bench`, Python package `bench_bench`. The separate parallel benchmark uses a different unhyphenated name; never mix the two projects.

## Reading order (engineer)

1. **`ENGINEER_BRIEF.md`** — the build directive. Scope, invariants, phases, exit gates. Start here; this is the contract.
2. **`REVIEW_AND_BUILD_PLAN.md`** — the reasoning behind the brief: analysis of the original spec, the year's event arc (Part 2), design decisions (Part 3), and the phased plan (Part 4).
3. **`docs/`** — the original `bench_bench_handoff_v3` spec pack. Design intent and useful detail (especially `SCORING_SPEC.md`, `SIMULATOR_SPEC.md`, `SAFETY_AND_ETHICS.md`), but **superseded by the two files above wherever they conflict** — notably: v1 is model-only (no frozen-web corpus, no open-web track) and uses a weekly decision cadence, not daily turns.

## Status

The v0.1 release path is implemented. The 12-week run is a diagnostic vertical
slice; the enforced release gate is the 52-week configuration on 20 burned
development seeds, with the original 65% adjacent-order threshold and
expert-vs-random separation requirement. The provider-neutral model-only
runner, resumable transcripts, exploit checks, and self-contained replay viewer
are included. The public leaderboard is intentionally pending independent
review and a live 52-week run on public seeds 100–109; no model leaderboard is
present in this checkout. The runnable Phase 1 slice remains available for
human play.

## Quickstart

```bash
python3 -m pip install -e .
python3 -m bench_bench play --seed 3 --weeks 12 --log /tmp/bench-bench-seed3.jsonl
python3 -m bench_bench replay /tmp/bench-bench-seed3.jsonl
python3 -m bench_bench baselines
python3 -m bench_bench baselines --weeks 52
python3 -m bench_bench redteam
python3 -m pytest
```

The CLI accepts a weekly JSON action, `default` for a safe fallback, or
`template` to print a valid action template. An interrupt receives its own
short reactive action. The log contains public observations, validated
actions, execution results, and the final score; hidden athlete variation and
true capacity are never written to it.

See [`BENCHMARK_CARD.md`](BENCHMARK_CARD.md) for scope, limitations, scoring,
and the public/private seed policy.

## Evaluate a model endpoint

The v1 runner uses the model-only track and accepts an OpenAI-compatible chat
completion endpoint. Set the endpoint's key in an environment variable, then
run five public seeds:

```bash
python3 -m bench_bench run-model \
  --base-url https://your-endpoint.example/v1 \
  --model your-model-name \
  --api-key-env YOUR_API_KEY \
  --weeks 12 --seed-count 5
```

Use `--seed-values 100,101,102,103,104` when the evaluator needs an exact
public seed list;
it overrides `--seed-count` and also supports out-of-band private values.

Each seed writes a resumable transcript under `runs/`. Use
`--base-url .../chat/completions` when the provider does not use the usual API
root convention. The runner retries malformed responses and transient provider
failures, records token usage/cost when the endpoint reports it, and never
grants model text direct access to simulator state. A live suite with
transport failures exits nonzero and marks its report invalid. Some current
reasoning/chat models reject an explicit temperature; the adapter detects that
response and retries without the optional field. If prices are not supplied,
known OpenAI model aliases use the built-in current price table; unknown models
remain explicitly marked unpriced and require the price flags for cost totals.
Transcripts record the requested sampling settings and effective price metadata.

To run a multi-model comparison in one command, use `run-model-suite` with a
comma-separated model list and the same endpoint.
Each new transcript records a sanitized endpoint identity (never the API key,
userinfo, or query string), and the analyzer audits endpoint provenance,
evaluator-only field leaks, and stale transcripts before producing the report.

The v0.1 pilot transcripts are published as the tracked, immutable archive
`artifacts/v0.1-pilot-transcripts.tar.gz`; `runs/` remains disposable. After
extracting that archive into `artifacts/`, the canonical leaderboard is always
generated from this named command over the extracted artifact root. The command
is recursive and deterministic; it does not discover neighboring runs or
hand-built summary files:

```bash
tar -xzf artifacts/v0.1-pilot-transcripts.tar.gz -C artifacts
python3 -m bench_bench build-leaderboard \
  --input-dir artifacts/v0.1-pilot-transcripts \
  --json reports/PILOT_V0.1_LEADERBOARD.json \
  --markdown reports/PILOT_V0.1_LEADERBOARD.md
```

The archive manifest is `artifacts/v0.1-pilot-manifest.json`. It records the
per-transcript hashes and provenance, plus the deterministic tarball hash,
runner version, and content-addressed pricing-table version.

To create a new live full-year model suite (separate from the current
authoritative offline replay), use:

```bash
python3 -m bench_bench run-model-suite \
  --base-url https://api.openai.com/v1 \
  --models gpt-5.4,gpt-5.4-mini,gpt-5.3-chat-latest,gpt-4.1 \
  --weeks 52 --temperature 0.2 --api-key-env BENCH_BENCH_API_KEY \
  --seed-values 100,101,102,103,104,105,106,107,108,109 \
  --request-retries 2 --retry-backoff-seconds 1 \
  --output-dir runs/public-leaderboard \
  --analysis-json reports/PUBLIC_LEADERBOARD.json \
  --analysis-markdown reports/PUBLIC_LEADERBOARD.md
```

The public leaderboard directory is intentionally empty until the independent
review is complete.

For a local runner smoke test and transcript analyzer:

```bash
python3 -m bench_bench demo-runner --weeks 12 --seed-count 5
python3 -m bench_bench build-leaderboard \
  --input-dir runs/public-leaderboard \
  --json reports/PUBLIC_LEADERBOARD.json \
  --markdown reports/PUBLIC_LEADERBOARD.md
python3 -m bench_bench verify-transcript runs/public-leaderboard/gpt-4.1-seed-100.jsonl \
  --output /tmp/gpt-4.1-seed-100.current-engine.jsonl
python3 -m bench_bench render-replay runs/public-leaderboard/gpt-4.1-seed-100.jsonl --output /tmp/bench-bench-replay.html
```
