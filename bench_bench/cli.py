"""Human CLI for playing and replaying a Bench-bench episode."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from .config import SimConfig
from .engine import BenchEnvironment
from .evaluation import run_episode, run_exploit_suite, run_suite, write_exploit_report, write_report
from .runner import DeterministicPolicyClient, ModelRunner, OpenAICompatibleClient, RunnerConfig
from .runner_analysis import analyze_directory, analyze_paths, write_analysis
from .viewer import render_replay


def _money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _seed_values(raw: str | None, count: int) -> list[int]:
    """Return explicit evaluator seeds, or the reproducible 0..count range."""
    if raw is None:
        return list(range(count))
    values = []
    try:
        values = [int(value.strip()) for value in raw.split(",") if value.strip()]
    except ValueError as exc:
        raise ValueError("--seed-values must be a comma-separated list of integers") from exc
    if not values:
        raise ValueError("--seed-values must contain at least one integer")
    if len(values) != len(set(values)):
        raise ValueError("--seed-values must not contain duplicates")
    return values


def _render_observation(env: BenchEnvironment) -> str:
    obs = env.observation
    upcoming = ", ".join(f"W{event.week}: {event.title}" for event in obs.upcoming_known_events) or "none announced"
    signals = "; ".join(obs.this_week_signals)
    return "\n".join(
        [
            f"\nWEEK {obs.episode_week}/{obs.total_weeks}  |  baby {obs.baby_age_months:.1f} mo  |  estimate {obs.estimated_1rm_kg:.1f} kg ({obs.estimated_1rm_low_kg:.1f}-{obs.estimated_1rm_high_kg:.1f})",
            f"sleep {obs.sleep_band}  energy {obs.energy_band}  soreness {obs.soreness_band}  pain {obs.pain_band}  illness {obs.illness_status}",
            f"nutrition {obs.nutrition_band}  mass {obs.body_mass_kg:.1f} kg ({obs.body_mass_trend})  household {obs.household_strain_band}  work {obs.work_strain_band}",
            f"budget available {_money(obs.budget_available_cents)}  this month {_money(obs.current_month_spend_cents)}  equipment: {', '.join(obs.equipment)}",
            f"time by day: {' '.join(obs.available_time_bands)}",
            f"signals: {signals}",
            f"known ahead: {upcoming}",
        ]
    )


def _print_action_help() -> None:
    print(
        """
Enter a JSON WeekAction with:
  {"sessions":[{"day":1,"slot":"evening","location":"gym","focus":"volume",
    "sets":4,"reps":5,"load_kg":65,"duration_min":50,"target_rpe":7.5}],
   "life":{"meal_prep_hours":3,"sleep_protection":"strong",
    "partner_coverage_hours":2,"partner_giveback_hours":2},
   "rules":{"on_sleep_below_5h":"fallback","on_pain_warning":"reduce",
    "on_illness":"protect_recovery"}}

Commands: default (safe fallback), template (print a safe JSON template),
help, or quit. A blank interrupt response protects recovery.
""".strip()
    )


def _read_json(prompt: str) -> Any:
    try:
        line = input(prompt).strip()
    except EOFError:
        return "quit"
    if line in {"", "default"}:
        return None
    if line in {"help", "?"}:
        _print_action_help()
        return _read_json(prompt)
    if line == "template":
        return "template"
    if line == "quit":
        return "quit"
    try:
        return json.loads(line)
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON: {exc}. Try again or type default.")
        return _read_json(prompt)


def play(args: argparse.Namespace) -> int:
    env = BenchEnvironment(args.seed, SimConfig(weeks=args.weeks))
    _print_action_help()
    while not env.done:
        print(_render_observation(env))
        raw = _read_json("week action> ")
        if raw == "quit":
            print("Stopped before the episode completed.")
            return 0
        if raw == "template":
            print(json.dumps(env.safe_action().model_dump(mode="json"), indent=2))
            continue
        if raw is None:
            raw = env.safe_action()
        validation = env.validate_action(raw)
        repair = None
        if validation.errors:
            print("Action error:", " | ".join(validation.errors))
            repair = _read_json("one repair attempt (blank = safe fallback)> ")
            if isinstance(repair, str) and repair in {"quit", "template"}:
                repair = None
        outcome = env.submit_week(raw, repair_action=repair, reactive_responder=_interactive_interrupt)
        print(
            f"W{outcome.week}: {outcome.headline} | planned {outcome.planned_sessions}, transformed {outcome.transformed_sessions}, "
            f"attempted {outcome.attempted_sessions}, completed {outcome.completed_sessions}, missed {outcome.missed_sessions}, "
            f"sleep {outcome.average_sleep_hours:.1f}h, estimate {outcome.estimated_1rm_kg:.1f} kg"
        )

    result = env.final_result()
    print("\nFINAL STANDARDIZED TEST BATTERY (weeks 44/48/52 averaged for 52-week episodes)")
    improvement = f"+{result.improvement_kg:.2f}" if result.improvement_kg >= 0 else f"{result.improvement_kg:.2f}"
    print(
        f"1RM {result.final_1rm_kg:.2f} kg  ({improvement}) | "
        f"planned {result.planned_sessions}, transformed {result.transformed_sessions}, "
        f"attempted {result.attempted_sessions}, completed {result.completed_sessions}, "
        f"missed {result.missed_sessions}, fallbacks {result.fallback_sessions}, "
        f"productive weeks {result.productive_weeks}"
    )
    if result.invalid_reason:
        print(f"INVALID EPISODE: {result.invalid_reason}")
    if args.log:
        env.write_jsonl(args.log)
        print(f"Wrote replay log to {args.log}")
    return 0


def _interactive_interrupt(observation: Any) -> Any:
    print(f"\nINTERRUPT W{observation.episode_week} day {observation.day}: {observation.title}")
    print(observation.detail)
    print("Choose protect_recovery, reallocate, preserve_training, or accept_disruption as JSON.")
    raw = _read_json("reactive action> ")
    if raw is None or (isinstance(raw, str) and raw in {"quit", "template"}):
        return {"response": "protect_recovery"}
    return raw


def replay(args: argparse.Namespace) -> int:
    path = Path(args.log)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    start = next(record for record in records if record.get("type") == "episode_start")
    config = SimConfig(**start["config"])
    env = BenchEnvironment(int(start["seed"]), config)
    # Titles are not unique: a year can contain multiple daycare closures or
    # illness onsets.  Replay the recorded interrupt sequence positionally so
    # alternate reactive choices cannot be substituted by a later same-title
    # event.
    interrupt_actions = [
        {
            "day": int(record["day"]),
            "kind": record["kind"],
            "title": record["title"],
            "reactive_action": record["reactive_action"],
        }
        for week in records
        if week.get("type") == "week"
        for record in week.get("interrupts", [])
    ]
    interrupt_index = 0
    replay_error: str | None = None

    def responder(observation: Any) -> Any:
        nonlocal interrupt_index, replay_error
        if interrupt_index >= len(interrupt_actions):
            replay_error = f"unexpected interrupt: W{observation.episode_week} day {observation.day} {observation.title}"
            return {"response": "protect_recovery"}
        expected = interrupt_actions[interrupt_index]
        interrupt_index += 1
        observed = (observation.day, observation.kind, observation.title)
        logged = (expected["day"], expected["kind"], expected["title"])
        if observed != logged and replay_error is None:
            replay_error = f"interrupt sequence mismatch: observed {observed}, logged {logged}"
        return expected["reactive_action"]

    for record in records:
        if record.get("type") == "week":
            env.submit_week(record["action"], reactive_responder=responder)
    env.final_result()
    rendered = env.jsonl()
    original = "".join(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n" for record in records)
    if replay_error is not None:
        print(f"REPLAY MISMATCH: {replay_error}")
        return 1
    if interrupt_index != len(interrupt_actions):
        print("REPLAY MISMATCH: logged interrupt sequence has unused records")
        return 1
    normalized_records = [_normalize_legacy_public_record(record) for record in records]
    normalized_original = "".join(
        json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
        for record in normalized_records
    )
    if rendered != normalized_original:
        print("REPLAY MISMATCH")
        return 1
    print(f"Replay identical: {args.log}")
    return 0


def _normalize_legacy_public_record(record: dict[str, Any]) -> dict[str, Any]:
    """Drop evaluator-only fields emitted by pre-0.1.0 logs before replay."""
    if record.get("type") != "final_result" or "result" not in record:
        return record
    result = record["result"]
    if not isinstance(result, dict) or "sleep_debt" not in result:
        return record
    normalized = dict(record)
    normalized_result = dict(result)
    normalized_result.pop("sleep_debt", None)
    normalized["result"] = normalized_result
    return normalized


def baselines(args: argparse.Namespace) -> int:
    report = run_suite(range(args.seed_count), weeks=args.weeks, ablations=not args.no_ablations)
    write_report(report, args.json, args.markdown)
    gate = report["gate"]
    enforced = bool(gate.get("gate_enforced", args.weeks == 52))
    label = "Full-year release gate" if enforced else "Short-horizon diagnostic"
    status = ("PASS" if gate["gate_pass"] else "FAIL") if enforced else "NOT ENFORCED"
    stable = ("PASS" if gate["stable_ordering_pass"] else "FAIL") if enforced else ("PASS" if gate["stable_ordering_pass"] else "FAIL") + " (diagnostic)"
    print(
        f"{label}: {status} | "
        f"separation {gate['separation_ratio']:.3f} | "
        f"ordering {'PASS' if gate['ordering_pass'] else 'FAIL'} | "
        f"stable {stable}"
    )
    print(f"Wrote {args.json} and {args.markdown}")
    return 0 if not enforced or gate["gate_pass"] else 2


def run_model(args: argparse.Namespace) -> int:
    try:
        seeds = _seed_values(args.seed_values, args.seed_count)
    except ValueError as exc:
        print(f"Invalid seed selection: {exc}")
        return 2
    api_key = os.environ.get(args.api_key_env)
    client = OpenAICompatibleClient(
        args.base_url,
        args.model,
        api_key=api_key,
        temperature=args.temperature,
        input_price_per_million=args.input_price_per_million,
        cached_input_price_per_million=args.cached_input_price_per_million,
        output_price_per_million=args.output_price_per_million,
        request_retries=args.request_retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
    )
    results = []
    for seed in seeds:
        path = args.output_dir / f"{args.model.replace('/', '_')}-seed-{seed}.jsonl"
        result = ModelRunner(
            client,
            RunnerConfig(
                weeks=args.weeks,
                max_retries=args.max_retries,
                expose_session_failure_reasons=args.expose_session_failure_reasons,
                sampling={"temperature": args.temperature},
            ),
        ).run_episode(seed, path)
        results.append(result.as_dict())
        print(f"seed {seed}: {result.final_result['final_1rm_kg']:.2f} kg | calls {result.model_calls} | cost ${result.total_cost_usd:.4f}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / f"{args.model.replace('/', '_')}-summary.json"
    summary_path.write_text(json.dumps({"model": args.model, "seeds": seeds, "results": results}, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {summary_path}")
    return 0


def run_model_suite(args: argparse.Namespace) -> int:
    models = [model.strip() for model in args.models.split(",") if model.strip()]
    if not models:
        print("At least one model is required")
        return 2
    if len(models) != len(set(models)):
        print("Model list must not contain duplicates")
        return 2
    output_names = [model.replace("/", "_") for model in models]
    if len(output_names) != len(set(output_names)):
        print("Model names collide after transcript filename sanitization")
        return 2
    try:
        seeds = _seed_values(args.seed_values, args.seed_count)
    except ValueError as exc:
        print(f"Invalid seed selection: {exc}")
        return 2
    transcript_paths: list[Path] = []
    for model in models:
        client = OpenAICompatibleClient(
            args.base_url,
            model,
            api_key=os.environ.get(args.api_key_env),
            temperature=args.temperature,
            input_price_per_million=args.input_price_per_million,
            cached_input_price_per_million=args.cached_input_price_per_million,
            output_price_per_million=args.output_price_per_million,
            request_retries=args.request_retries,
            retry_backoff_seconds=args.retry_backoff_seconds,
        )
        for seed in seeds:
            path = args.output_dir / f"{model.replace('/', '_')}-seed-{seed}.jsonl"
            transcript_paths.append(path)
            result = ModelRunner(
                client,
                RunnerConfig(
                    weeks=args.weeks,
                    max_retries=args.max_retries,
                    expose_session_failure_reasons=args.expose_session_failure_reasons,
                    sampling={"temperature": args.temperature},
                ),
            ).run_episode(seed, path)
            print(f"{model} seed {seed}: {result.final_result['final_1rm_kg']:.2f} kg")
    records = analyze_paths(transcript_paths)
    write_analysis(records, args.analysis_json, args.analysis_markdown)
    invalid_count = sum(record.get("invalid_reason") is not None for record in records)
    suffix = f"; excluded {invalid_count} invalid episodes from aggregates" if invalid_count else ""
    print(f"Analyzed {len(records)} transcripts{suffix}; wrote {args.analysis_json} and {args.analysis_markdown}")
    if any(record.get("transport_errors") for record in records):
        print("Transport errors detected; live suite report is invalid until the affected transcripts are rerun.")
        return 2
    return 0


def demo_runner(args: argparse.Namespace) -> int:
    results = []
    for policy in args.policies.split(","):
        policy = policy.strip()
        for seed in range(args.seed_count):
            path = args.output_dir / f"{policy}-seed-{seed}.jsonl"
            client = DeterministicPolicyClient(policy, seed)
            result = ModelRunner(client, RunnerConfig(weeks=args.weeks)).run_episode(seed, path)
            results.append({"policy": policy, **result.as_dict()})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / "demo_runner_results.json"
    summary_path.write_text(json.dumps({"kind": "runner-smoke-test", "results": results}, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote deterministic runner smoke test to {summary_path}")
    return 0


def analyze_runs(args: argparse.Namespace) -> int:
    records = analyze_directory(args.input_dir)
    if not records:
        print(f"No JSONL transcripts found in {args.input_dir}")
        return 2
    write_analysis(records, args.json, args.markdown)
    invalid_count = sum(record.get("invalid_reason") is not None for record in records)
    suffix = f"; excluded {invalid_count} invalid episodes from aggregates" if invalid_count else ""
    print(f"Analyzed {len(records)} transcripts{suffix}; wrote {args.json} and {args.markdown}")
    return 0


def redteam(args: argparse.Namespace) -> int:
    report = run_exploit_suite(
        range(args.seed_count),
        weeks=args.weeks,
        weekly_stimulus_cap=args.weekly_stimulus_cap,
    )
    expert_config = SimConfig(
        weeks=args.weeks,
        **(
            {"weekly_stimulus_cap": args.weekly_stimulus_cap}
            if args.weekly_stimulus_cap is not None
            else {}
        ),
    )
    expert_scores = [run_episode("scripted-expert", seed, expert_config).final_1rm_kg for seed in range(args.seed_count)]
    expert_mean = sum(expert_scores) / len(expert_scores)
    write_exploit_report(report, args.json, args.markdown, expert_mean)
    print(f"Red-team reference expert mean: {expert_mean:.2f} kg")
    print(f"Adversarial candidates beating expert: {report['comparison'].get('candidates_beating_expert') or 'none'}")
    print(f"Candidates requiring human review: {report['comparison'].get('human_review_candidates') or 'none'}")
    print(f"Release-blocking candidates: {report['comparison'].get('release_blocked_candidates') or 'none'}")
    print(f"Wrote {args.json} and {args.markdown}")
    return 0 if not report["comparison"].get("release_blocked_candidates") else 2


def render_replay_command(args: argparse.Namespace) -> int:
    render_replay(args.log, args.output)
    print(f"Wrote self-contained replay viewer to {args.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bench-bench", description="Play or replay a deterministic Bench-bench episode.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    play_parser = subparsers.add_parser("play", help="play the weekly game in a terminal")
    play_parser.add_argument("--seed", type=int, default=3)
    play_parser.add_argument("--weeks", type=int, default=12)
    play_parser.add_argument("--log", type=Path)
    play_parser.set_defaults(func=play)
    replay_parser = subparsers.add_parser("replay", help="verify a JSONL episode log byte-for-byte")
    replay_parser.add_argument("log", type=Path)
    replay_parser.set_defaults(func=replay)
    baseline_parser = subparsers.add_parser("baselines", help="run the six-policy Phase 2 separation gate")
    baseline_parser.add_argument("--weeks", type=int, default=12)
    baseline_parser.add_argument("--seed-count", type=int, default=20)
    baseline_parser.add_argument("--json", type=Path, default=Path("reports/current_baseline_gate.json"))
    baseline_parser.add_argument("--markdown", type=Path, default=Path("reports/CURRENT_BASELINE_GATE.md"))
    baseline_parser.add_argument("--no-ablations", action="store_true")
    baseline_parser.set_defaults(func=baselines)
    model_parser = subparsers.add_parser("run-model", help="evaluate an OpenAI-compatible model-only endpoint")
    model_parser.add_argument("--base-url", required=True, help="chat completions URL or API root")
    model_parser.add_argument("--model", required=True)
    model_parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    model_parser.add_argument("--weeks", type=int, default=12)
    model_parser.add_argument("--seed-count", type=int, default=5)
    model_parser.add_argument("--seed-values", help="comma-separated evaluator seed values; overrides --seed-count")
    model_parser.add_argument("--max-retries", type=int, default=1)
    model_parser.add_argument("--expose-session-failure-reasons", action="store_true")
    model_parser.add_argument("--temperature", type=float, default=0.2)
    model_parser.add_argument("--input-price-per-million", type=float, default=None)
    model_parser.add_argument("--cached-input-price-per-million", type=float, default=None)
    model_parser.add_argument("--output-price-per-million", type=float, default=None)
    model_parser.add_argument("--request-retries", type=int, default=2)
    model_parser.add_argument("--retry-backoff-seconds", type=float, default=1.0)
    model_parser.add_argument("--output-dir", type=Path, default=Path("runs"))
    model_parser.set_defaults(func=run_model)
    suite_parser = subparsers.add_parser("run-model-suite", help="evaluate several models on the same public seeds")
    suite_parser.add_argument("--base-url", required=True)
    suite_parser.add_argument("--models", required=True, help="comma-separated model names")
    suite_parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    suite_parser.add_argument("--weeks", type=int, default=12)
    suite_parser.add_argument("--seed-count", type=int, default=5)
    suite_parser.add_argument("--seed-values", help="comma-separated evaluator seed values; overrides --seed-count")
    suite_parser.add_argument("--max-retries", type=int, default=1)
    suite_parser.add_argument("--expose-session-failure-reasons", action="store_true")
    suite_parser.add_argument("--temperature", type=float, default=0.2)
    suite_parser.add_argument("--input-price-per-million", type=float, default=None)
    suite_parser.add_argument("--cached-input-price-per-million", type=float, default=None)
    suite_parser.add_argument("--output-price-per-million", type=float, default=None)
    suite_parser.add_argument("--request-retries", type=int, default=2)
    suite_parser.add_argument("--retry-backoff-seconds", type=float, default=1.0)
    suite_parser.add_argument("--output-dir", type=Path, default=Path("runs/model-suite"))
    suite_parser.add_argument("--analysis-json", type=Path, default=Path("reports/current_model_suite.json"))
    suite_parser.add_argument("--analysis-markdown", type=Path, default=Path("reports/CURRENT_MODEL_SUITE.md"))
    suite_parser.set_defaults(func=run_model_suite)
    demo_parser = subparsers.add_parser("demo-runner", help="run the local deterministic runner smoke test")
    demo_parser.add_argument("--policies", default="recovery-aware,scripted-expert,reckless-maximalist")
    demo_parser.add_argument("--weeks", type=int, default=12)
    demo_parser.add_argument("--seed-count", type=int, default=2)
    demo_parser.add_argument("--output-dir", type=Path, default=Path("runs/demo"))
    demo_parser.set_defaults(func=demo_runner)
    analysis_parser = subparsers.add_parser("analyze-runs", help="read runner transcripts into a mini-leaderboard and exploit list")
    analysis_parser.add_argument("--input-dir", type=Path, required=True)
    analysis_parser.add_argument("--json", type=Path, default=Path("reports/current_transcript_analysis.json"))
    analysis_parser.add_argument("--markdown", type=Path, default=Path("reports/CURRENT_TRANSCRIPT_ANALYSIS.md"))
    analysis_parser.set_defaults(func=analyze_runs)
    redteam_parser = subparsers.add_parser("redteam", help="run full-year automated legal-action adversarial search")
    redteam_parser.add_argument("--weeks", type=int, default=52)
    redteam_parser.add_argument("--seed-count", type=int, default=20)
    redteam_parser.add_argument("--weekly-stimulus-cap", type=float, default=None)
    redteam_parser.add_argument("--json", type=Path, default=Path("reports/current_adversarial_search.json"))
    redteam_parser.add_argument("--markdown", type=Path, default=Path("reports/CURRENT_ADVERSARIAL_SEARCH.md"))
    redteam_parser.set_defaults(func=redteam)
    viewer_parser = subparsers.add_parser("render-replay", help="render a JSONL episode as a self-contained HTML year viewer")
    viewer_parser.add_argument("log", type=Path)
    viewer_parser.add_argument("--output", type=Path, required=True)
    viewer_parser.set_defaults(func=render_replay_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
