# Bench-bench

A long-horizon decision-making benchmark for AI agents: manage one simulated year in the life of a 38-year-old father of an infant and maximize his bench-press 1RM across hidden standardized tests at weeks 44, 48, and 52 — without wrecking his sleep, budget, family, or joints.

> Naming: the project is **Bench-bench** (hyphenated, exactly this capitalization). Repo `bench-bench`, Python package `bench_bench`. The separate parallel benchmark uses a different unhyphenated name; never mix the two projects.

## Reading order (engineer)

1. **`ENGINEER_BRIEF.md`** — the build directive. Scope, invariants, phases, exit gates. Start here; this is the contract.
2. **`REVIEW_AND_BUILD_PLAN.md`** — the reasoning behind the brief: analysis of the original spec, the year's event arc (Part 2), design decisions (Part 3), and the phased plan (Part 4).
3. **`docs/`** — the original `bench_bench_handoff_v3` spec pack. Design intent and useful detail (especially `SCORING_SPEC.md`, `SIMULATOR_SPEC.md`, `SAFETY_AND_ETHICS.md`), but **superseded by the two files above wherever they conflict** — notably: v1 is model-only (no frozen-web corpus, no open-web track) and uses a weekly decision cadence, not daily turns.

## Status

The v0.1 pilot is preserved as a reproducible archive. v0.2 has completed its
prompt freeze, deterministic rehearsal, and four-model seed-400 paid smoke;
the six scripted policies remain diagnostics and no public model leaderboard is
claimed by this checkout. v0.2's public leaderboard pool is seeds 400–409; its
tuning, certification, and regression pools are disjoint. The provider-neutral
model-only runner, resumable transcripts, exploit checks, and self-contained
replay viewer are included.

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

Use `--seed-values 400,401,402,403,404` when the evaluator needs an exact
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
  --markdown reports/PILOT_V0.1_LEADERBOARD.md \
  --historical-pilot
```

The archive manifest is `artifacts/v0.1-pilot-manifest.json`. It records the
per-transcript hashes and provenance, plus the deterministic tarball hash,
runner version, and content-addressed pricing-table version.

The historical pilot analyzer applies the v0.1 pain-only score rule and
excludes any transcript with provider transport failures from counted
aggregates. Kimi K3 therefore remains visible with its raw scores and 702
transport failures, but is counted 0/10 rather than being ranked on a
transport-contaminated mean.

To create a new live full-year model suite (separate from the current
authoritative offline replay), use:

```bash
python3 scripts/run_live_suite.py \
  --models claude-opus-5,gpt-5.6-sol,muse-spark-1.2,grok-4.6 \
  --seed-values 400,401,402,403,404,405,406,407,408,409 \
  --output-dir runs/v0.2-public-leaderboard
```

The public leaderboard directory is intentionally empty until the ten-seed
public run. The seed-400 paid smoke is retained separately under the paths in
`release_manifest.json`. Before the public run, archive the completed run with `scripts/build_archive.py` using
the v0.2 paths in `release_manifest.json`; do not delete or overwrite an
existing artifact.

For a local runner smoke test and transcript analyzer:

```bash
python3 -m bench_bench demo-runner --weeks 12 --seed-count 5
python3 -m bench_bench build-leaderboard \
  --input-dir runs/v0.2-public-leaderboard \
  --json reports/PUBLIC_LEADERBOARD.json \
  --markdown reports/PUBLIC_LEADERBOARD.md
python3 -m bench_bench verify-transcript runs/v0.2-public-leaderboard/gpt-5.6-sol/seed-400/gpt-5.6-sol-seed-400.jsonl \
  --output /tmp/gpt-5.6-sol-seed-400.current-engine.jsonl
python3 -m bench_bench render-replay runs/v0.2-public-leaderboard/gpt-5.6-sol/seed-400/gpt-5.6-sol-seed-400.jsonl --output /tmp/bench-bench-replay.html
```
