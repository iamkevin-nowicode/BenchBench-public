#!/usr/bin/env python3
"""Unattended, resumable supervisor for the selectable live Bench-bench suite.

The existing model runner owns provider calls, validation/repair, transcript
appends, and per-request retries. This supervisor owns cross-episode
concurrency, resumability, progress logging, and suite-level guardrails.
"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from typing import Any

from bench_bench.runner import retry_metrics_from_records


SEEDS = tuple(range(400, 410))
WEEKS = 52
TEMPERATURE = 1.0
MAX_OUTPUT_TOKENS = 8192
MAX_REPAIR_ATTEMPTS = 1
REQUEST_RETRIES = 8
REQUEST_BACKOFF_SECONDS = 5.0
MAX_EPISODE_ATTEMPTS = 5
SUPERVISOR_RETRY_SECONDS = 15.0
REPAIR_RATE_LIMIT = 0.25
MIN_DECISIONS_FOR_REPAIR_GUARD = 100


@dataclass(frozen=True)
class ModelSpec:
    label: str
    provider: str
    model: str
    base_url: str
    key_file_name: str
    key_env: str
    effort: str
    max_workers: int
    cost_ceiling: float
    request_backoff_seconds: float = REQUEST_BACKOFF_SECONDS
    input_price_per_million: float | None = None
    cached_input_price_per_million: float | None = None
    output_price_per_million: float | None = None
    long_context_threshold_tokens: int | None = None
    long_context_input_price_per_million: float | None = None
    long_context_cached_input_price_per_million: float | None = None
    long_context_output_price_per_million: float | None = None
    max_prompt_tokens: int | None = None


# v0.2 public lineup.  The ordering is also the smoke-start order.
MODEL_SPECS = (
    ModelSpec(
        "claude-opus-5",
        "anthropic",
        "claude-opus-5",
        "https://api.anthropic.com/v1/messages",
        ".bench-bench-anthropic-key",
        "BENCH_BENCH_ANTHROPIC_API_KEY",
        "medium",
        3,
        70.0,
        input_price_per_million=5.00,
        cached_input_price_per_million=0.50,
        output_price_per_million=25.00,
    ),
    ModelSpec(
        "gpt-5.6-sol",
        "openai-compatible",
        "gpt-5.6-sol",
        "https://api.openai.com/v1",
        ".bench-bench-openai-key",
        "BENCH_BENCH_OPENAI_API_KEY",
        "medium",
        3,
        40.0,
        input_price_per_million=5.00,
        cached_input_price_per_million=0.50,
        output_price_per_million=30.00,
    ),
    ModelSpec(
        "muse-spark-1.2",
        "openai-compatible",
        "muse-spark-1.2",
        "https://api.meta.ai/v1",
        ".bench-bench-meta-key",
        "BENCH_BENCH_META_API_KEY",
        "medium",
        3,
        15.0,
        input_price_per_million=1.25,
        cached_input_price_per_million=0.15,
        output_price_per_million=4.25,
    ),
    ModelSpec(
        "grok-4.6",
        "openai-compatible",
        "grok-4.6",
        "https://api.x.ai/v1",
        ".bench-bench-xai-key",
        "BENCH_BENCH_XAI_API_KEY",
        "medium",
        2,
        30.0,
        5.0,
        2.0,
        0.50,
        6.0,
        200_000,
        4.0,
        1.0,
        12.0,
        max_prompt_tokens=200_000,
    ),
)


@dataclass
class Job:
    spec: ModelSpec
    seed: int
    process: subprocess.Popen[str]
    log_handle: Any
    attempt: int
    transcript: Path
    child_log: Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def model_stem(model: str) -> str:
    return model.replace("/", "_")


def transcript_path(output_root: Path, spec: ModelSpec, seed: int) -> Path:
    seed_dir = output_root / spec.label / f"seed-{seed}"
    return seed_dir / f"{model_stem(spec.model)}-seed-{seed}.jsonl"


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                # A writer may be between append and flush. The next poll will
                # see the complete record, so ignore only this partial line.
                continue
            if isinstance(record, dict):
                records.append(record)
    except OSError:
        return records
    return records


def attempt_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for record in records:
        if record.get("type") != "turn":
            continue
        attempts.extend(record.get("attempts", []) or [])
        for reactive in record.get("reactive_turns", []) or []:
            attempts.extend(reactive.get("attempts", []) or [])
    return [item for item in attempts if isinstance(item, dict)]


def transcript_metrics(path: Path) -> dict[str, Any]:
    records = read_records(path)
    turns = [record for record in records if record.get("type") == "turn"]
    interrupts = sum(len(record.get("reactive_turns", []) or []) for record in turns)
    decisions = len(turns) + interrupts
    end = next((record for record in reversed(records) if record.get("type") == "run_end"), None)
    attempts = attempt_records(records)
    retry_metrics = retry_metrics_from_records(records)
    if end is not None:
        cost = float(end.get("total_cost_usd", 0.0) or 0.0)
        model_calls = int(end.get("model_calls", 0) or 0)
        input_tokens = int(end.get("input_tokens", 0) or 0)
        cached_input_tokens = int(end.get("cached_input_tokens", 0) or 0)
        cache_creation_input_tokens = int(end.get("cache_creation_input_tokens", 0) or 0)
        visible_output_tokens = int(end.get("visible_output_tokens", 0) or 0)
        thinking_tokens = int(end.get("thinking_tokens", 0) or 0)
        total_tokens = int(end.get("total_tokens", 0) or 0)
    else:
        cost = sum(float((item.get("usage") or {}).get("cost_usd", 0.0) or 0.0) for item in attempts)
        model_calls = sum(1 for item in attempts if item.get("is_model_call", True))
        input_tokens = sum(int((item.get("usage") or {}).get("input_tokens", 0) or 0) for item in attempts)
        cached_input_tokens = sum(int((item.get("usage") or {}).get("cached_prompt_tokens", 0) or 0) for item in attempts)
        cache_creation_input_tokens = sum(int((item.get("usage") or {}).get("cache_creation_input_tokens", 0) or 0) for item in attempts)
        visible_output_tokens = sum(int((item.get("usage") or {}).get("visible_output_tokens", 0) or 0) for item in attempts)
        thinking_tokens = sum(int((item.get("usage") or {}).get("thinking_tokens", 0) or 0) for item in attempts)
        total_tokens = sum(int((item.get("usage") or {}).get("total_tokens", 0) or 0) for item in attempts)
    errors = []
    for record in turns:
        errors.extend(str(error) for error in record.get("parse_errors", []) or [])
        errors.extend(str(item["error"]) for item in record.get("attempts", []) or [] if item.get("error"))
        for reactive in record.get("reactive_turns", []) or []:
            errors.extend(str(error) for error in reactive.get("parse_errors", []) or [])
            errors.extend(str(item["error"]) for item in reactive.get("attempts", []) or [] if item.get("error"))
    result = (end or {}).get("result", {}) or {}
    return {
        "complete": end is not None,
        "cost": cost,
        "repairs": retry_metrics["rejected_output_decisions"],
        "rejected_model_outputs": retry_metrics["rejected_model_outputs"],
        "repair_attempts": retry_metrics["repair_attempts"],
        "successful_repairs": retry_metrics["successful_repairs"],
        "model_calls": model_calls,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "cache_creation_input_tokens": cache_creation_input_tokens,
        "visible_output_tokens": visible_output_tokens,
        "thinking_tokens": thinking_tokens,
        "output_tokens": visible_output_tokens + thinking_tokens,
        "total_tokens": total_tokens,
        "decisions": decisions,
        "repair_rate": retry_metrics["rejected_output_decisions"] / decisions if decisions else 0.0,
        "transport_failures": retry_metrics["transport_failures"],
        "interrupts": interrupts,
        "reactive_fallbacks": int(result.get("reactive_action_fallbacks", 0) or 0),
        "pain_days": result.get("pain_days"),
        "score": result.get("final_1rm_kg"),
        "errors": errors,
    }


def redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<redacted>")
    return text


def classify_auth_failure(text: str) -> bool:
    lowered = text.lower()
    return bool(
        re.search(r"\b(401|403)\b", lowered)
        or "unauthorized" in lowered
        or "authentication" in lowered
        or "invalid api key" in lowered
        or "invalid_api_key" in lowered
    )


class Supervisor:
    def __init__(self, output_root: Path, seeds: tuple[int, ...], specs: tuple[ModelSpec, ...]) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.output_root = output_root
        self.seeds = seeds
        self.specs = specs
        self.progress_path = output_root / "progress.log"
        self.state_path = output_root / "state.json"
        self.lock_path = output_root / ".supervisor.lock"
        self.lock_handle: Any = None
        self.secrets: list[str] = []
        self.active: dict[int, Job] = {}
        self.pending: dict[str, deque[tuple[int, float]]] = {}
        self.attempts: dict[tuple[str, int], int] = {}
        self.auth_failures: dict[str, int] = {spec.label: 0 for spec in self.specs}
        self.runtime_errors: dict[str, int] = {spec.label: 0 for spec in self.specs}
        self.stop_reason: str | None = None
        self.last_status = 0.0
        self.state: dict[str, Any] = {
            "status": "starting",
            "started_at": now_iso(),
            "updated_at": now_iso(),
            "seeds": list(seeds),
            "models": {spec.label: {"attempts": {}, "auth_failures": 0, "runtime_errors": 0} for spec in self.specs},
        }

    def log(self, event: str, message: str, **fields: Any) -> None:
        entry = {"time": now_iso(), "event": event, "message": message, **fields}
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)
        with self.progress_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        print(line, flush=True)

    def save_state(self) -> None:
        self.state["updated_at"] = now_iso()
        for spec in self.specs:
            model_state = self.state["models"][spec.label]
            model_state["attempts"] = {
                str(seed): self.attempts.get((spec.label, seed), 0)
                for seed in self.seeds
            }
            model_state["auth_failures"] = self.auth_failures[spec.label]
            model_state["runtime_errors"] = self.runtime_errors[spec.label]
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.state_path)

    def acquire_lock(self) -> bool:
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.lock_handle = self.lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self.lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    def prepare(self) -> bool:
        if not self.acquire_lock():
            self.log("already_running", "another live-suite supervisor owns this output directory")
            return False
        for spec in self.specs:
            key_path = Path.home() / spec.key_file_name
            try:
                key = key_path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                self.stop_reason = f"missing key file for {spec.label}: {exc}"
                self.log("fatal", "required provider key file could not be read", model=spec.label)
                return False
            if not key:
                self.stop_reason = f"empty key file for {spec.label}"
                self.log("fatal", "required provider key file is empty", model=spec.label)
                return False
            self.secrets.append(key)
            self.pending[spec.label] = deque()
            for seed in self.seeds:
                path = transcript_path(self.output_root, spec, seed)
                metrics = transcript_metrics(path)
                if not metrics["complete"]:
                    self.pending[spec.label].append((seed, 0.0))
        self.state["status"] = "running"
        self.state["config"] = {
            "weeks": WEEKS,
            "seeds": list(self.seeds),
            "temperature": TEMPERATURE,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "max_repair_attempts": MAX_REPAIR_ATTEMPTS,
            "request_retries": REQUEST_RETRIES,
            "request_backoff_seconds": {spec.label: spec.request_backoff_seconds for spec in self.specs},
            "model_concurrency": {spec.label: spec.max_workers for spec in self.specs},
            "cost_ceilings_usd": {spec.label: spec.cost_ceiling for spec in self.specs},
            "pricing": {
                spec.label: {
                    "input_price_per_million": spec.input_price_per_million,
                    "cached_input_price_per_million": spec.cached_input_price_per_million,
                    "output_price_per_million": spec.output_price_per_million,
                    "long_context_threshold_tokens": spec.long_context_threshold_tokens,
                    "long_context_input_price_per_million": spec.long_context_input_price_per_million,
                    "long_context_cached_input_price_per_million": spec.long_context_cached_input_price_per_million,
                    "long_context_output_price_per_million": spec.long_context_output_price_per_million,
                    "max_prompt_tokens": spec.max_prompt_tokens,
                }
                for spec in self.specs
            },
        }
        self.save_state()
        self.log(
            "started",
            "full live suite supervisor started",
            output_dir=str(self.output_root),
            episodes=len(self.specs) * len(self.seeds),
            start_order=[spec.label for spec in self.specs],
        )
        for spec in self.specs:
            self.log(
                "model_config",
                "provider configured",
                model=spec.label,
                exact_model=spec.model,
                endpoint=spec.base_url,
                effort=spec.effort if spec.effort != "not-exposed" else "not exposed",
                temperature=TEMPERATURE,
                max_workers=spec.max_workers,
                request_backoff_seconds=spec.request_backoff_seconds,
                cost_ceiling_usd=spec.cost_ceiling,
                pricing={
                    "input_price_per_million": spec.input_price_per_million,
                    "cached_input_price_per_million": spec.cached_input_price_per_million,
                    "output_price_per_million": spec.output_price_per_million,
                    "long_context_threshold_tokens": spec.long_context_threshold_tokens,
                    "long_context_input_price_per_million": spec.long_context_input_price_per_million,
                    "long_context_cached_input_price_per_million": spec.long_context_cached_input_price_per_million,
                    "long_context_output_price_per_million": spec.long_context_output_price_per_million,
                    "max_prompt_tokens": spec.max_prompt_tokens,
                },
                pending=len(self.pending[spec.label]),
            )
        return True

    def model_paths(self, spec: ModelSpec) -> list[Path]:
        return [transcript_path(self.output_root, spec, seed) for seed in self.seeds]

    def model_summary(self, spec: ModelSpec) -> dict[str, Any]:
        metrics = [transcript_metrics(path) for path in self.model_paths(spec)]
        completed = sum(item["complete"] for item in metrics)
        cost = sum(float(item["cost"]) for item in metrics)
        repairs = sum(int(item["repairs"]) for item in metrics)
        decisions = sum(int(item["decisions"]) for item in metrics)
        transport_failures = sum(int(item["transport_failures"]) for item in metrics)
        return {
            "completed": completed,
            "total": len(metrics),
            "cost": cost,
            "repairs": repairs,
            "decisions": decisions,
            "repair_rate": repairs / decisions if decisions else 0.0,
            "transport_failures": transport_failures,
            "input_tokens": sum(int(item["input_tokens"]) for item in metrics),
            "cached_input_tokens": sum(int(item["cached_input_tokens"]) for item in metrics),
            "cache_creation_input_tokens": sum(int(item["cache_creation_input_tokens"]) for item in metrics),
            "visible_output_tokens": sum(int(item["visible_output_tokens"]) for item in metrics),
            "thinking_tokens": sum(int(item["thinking_tokens"]) for item in metrics),
            "output_tokens": sum(int(item["output_tokens"]) for item in metrics),
            "total_tokens": sum(int(item["total_tokens"]) for item in metrics),
            "episodes": [
                {
                    "seed": seed,
                    "complete": item["complete"],
                    "input_tokens": item["input_tokens"],
                    "cached_input_tokens": item["cached_input_tokens"],
                    "cache_creation_input_tokens": item["cache_creation_input_tokens"],
                    "visible_output_tokens": item["visible_output_tokens"],
                    "thinking_tokens": item["thinking_tokens"],
                    "output_tokens": item["output_tokens"],
                    "total_tokens": item["total_tokens"],
                    "cost_usd": round(float(item["cost"]), 8),
                    "repair_rate": item["repair_rate"],
                    "transport_failures": item["transport_failures"],
                    "automatic_fallbacks": item["reactive_fallbacks"],
                    "pain_days": item["pain_days"],
                    "score_kg": item["score"],
                }
                for seed, item in zip(self.seeds, metrics)
            ],
            "errors": sum(len(item["errors"]) for item in metrics) + self.runtime_errors[spec.label],
            "auth_failures": self.auth_failures[spec.label],
        }

    def status(self, force: bool = False) -> None:
        current = time.monotonic()
        if not force and current - self.last_status < 30:
            return
        self.last_status = current
        values = {}
        for spec in self.specs:
            summary = self.model_summary(spec)
            values[spec.label] = {
                "completed": f"{summary['completed']}/{summary['total']}",
                "running_cost_usd": round(summary["cost"], 6),
                "repair_rate": round(summary["repair_rate"], 6),
                "transport_failures": summary["transport_failures"],
                "errors": summary["errors"],
                "auth_failures": summary["auth_failures"],
            }
        self.log("progress", "suite progress", models=values)
        self.save_state()

    def guard_failure(self) -> str | None:
        for spec in self.specs:
            summary = self.model_summary(spec)
            if summary["cost"] > spec.cost_ceiling:
                return f"cost ceiling breached for {spec.label}: ${summary['cost']:.6f} > ${spec.cost_ceiling:.2f}"
            if (
                summary["decisions"] >= MIN_DECISIONS_FOR_REPAIR_GUARD
                and summary["repair_rate"] > REPAIR_RATE_LIMIT
            ):
                return (
                    f"repair rate exceeded 25% for {spec.label}: "
                    f"{summary['repairs']}/{summary['decisions']} = {summary['repair_rate']:.4f}"
                )
            if self.auth_failures[spec.label] >= 2:
                return f"repeated authentication failures for {spec.label}"
        return None

    def command(self, spec: ModelSpec, seed: int, seed_dir: Path) -> list[str]:
        command = [
            sys.executable,
            "-m",
            "bench_bench",
            "run-model",
            "--provider",
            spec.provider,
            "--base-url",
            spec.base_url,
            "--model",
            spec.model,
            "--weeks",
            str(WEEKS),
            "--seed-values",
            str(seed),
            "--temperature",
            str(TEMPERATURE),
            "--effort",
            spec.effort,
            "--max-output-tokens",
            str(MAX_OUTPUT_TOKENS),
            "--max-retries",
            str(MAX_REPAIR_ATTEMPTS),
            "--api-key-env",
            spec.key_env,
            "--output-dir",
            str(seed_dir),
            "--request-retries",
            str(REQUEST_RETRIES),
            "--retry-backoff-seconds",
            str(spec.request_backoff_seconds),
        ]
        for flag, value in (
            ("--input-price-per-million", spec.input_price_per_million),
            ("--cached-input-price-per-million", spec.cached_input_price_per_million),
            ("--output-price-per-million", spec.output_price_per_million),
            ("--long-context-threshold-tokens", spec.long_context_threshold_tokens),
            ("--long-context-input-price-per-million", spec.long_context_input_price_per_million),
            ("--long-context-cached-input-price-per-million", spec.long_context_cached_input_price_per_million),
            ("--long-context-output-price-per-million", spec.long_context_output_price_per_million),
            ("--max-prompt-tokens", spec.max_prompt_tokens),
        ):
            if value is not None:
                command.extend([flag, str(value)])
        return command

    def launch_for(self, spec: ModelSpec) -> None:
        while len([job for job in self.active.values() if job.spec.label == spec.label]) < spec.max_workers:
            if not self.pending[spec.label]:
                return
            seed, ready_at = self.pending[spec.label][0]
            if ready_at > time.monotonic():
                return
            self.pending[spec.label].popleft()
            path = transcript_path(self.output_root, spec, seed)
            if transcript_metrics(path)["complete"]:
                continue
            attempt = self.attempts.get((spec.label, seed), 0) + 1
            self.attempts[(spec.label, seed)] = attempt
            seed_dir = path.parent
            seed_dir.mkdir(parents=True, exist_ok=True)
            child_log = seed_dir / f"attempt-{attempt}.log"
            key_path = Path.home() / spec.key_file_name
            key = key_path.read_text(encoding="utf-8").strip()
            environment = os.environ.copy()
            environment[spec.key_env] = key
            environment["PYTHONUNBUFFERED"] = "1"
            handle = child_log.open("a", encoding="utf-8")
            process = subprocess.Popen(
                self.command(spec, seed, seed_dir),
                cwd=self.root,
                env=environment,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.active[process.pid] = Job(spec, seed, process, handle, attempt, path, child_log)
            self.log(
                "episode_started",
                "episode process started",
                model=spec.label,
                seed=seed,
                attempt=attempt,
                pid=process.pid,
                transcript=str(path),
            )

    def terminate_all(self, reason: str) -> None:
        self.stop_reason = reason
        self.log("halt", "halting all model processes", reason=reason)
        jobs = list(self.active.values())
        for job in jobs:
            if job.process.poll() is None:
                job.process.terminate()
        deadline = time.monotonic() + 10
        for job in jobs:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                job.process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                job.process.kill()
        for job in jobs:
            job.log_handle.close()
        self.active.clear()

    def reap_finished(self) -> None:
        for pid, job in list(self.active.items()):
            return_code = job.process.poll()
            if return_code is None:
                continue
            self.active.pop(pid, None)
            job.log_handle.close()
            metrics = transcript_metrics(job.transcript)
            if metrics["complete"]:
                self.log(
                    "episode_completed",
                    "episode reached run_end",
                    model=job.spec.label,
                    seed=job.seed,
                    return_code=return_code,
                    cost_usd=round(metrics["cost"], 6),
                    repairs=metrics["repairs"],
                    decisions=metrics["decisions"],
                    repair_rate=round(metrics["repair_rate"], 6),
                    transport_failures=metrics["transport_failures"],
                    pain_days=metrics["pain_days"],
                    score_kg=metrics["score"],
                )
                continue
            tail = ""
            try:
                tail = job.child_log.read_text(encoding="utf-8")[-4000:]
            except OSError:
                pass
            tail = redact(tail, self.secrets)
            self.runtime_errors[job.spec.label] += 1
            auth_failure = classify_auth_failure(tail)
            if auth_failure:
                self.auth_failures[job.spec.label] += 1
            self.log(
                "episode_error",
                "episode process ended without run_end; it will be retried",
                model=job.spec.label,
                seed=job.seed,
                return_code=return_code,
                auth_failure=auth_failure,
                error_tail=tail[-1000:],
            )
            if self.attempts[(job.spec.label, job.seed)] < MAX_EPISODE_ATTEMPTS:
                self.pending[job.spec.label].append((job.seed, time.monotonic() + SUPERVISOR_RETRY_SECONDS))

    def run(self) -> int:
        if not self.prepare():
            if self.stop_reason:
                self.state["status"] = "failed"
                self.state["stop_reason"] = self.stop_reason
                self.save_state()
            return 2
        try:
            # Start the first selected provider, then fill all model pools.
            self.launch_for(self.specs[0])
            for spec in self.specs[1:]:
                self.launch_for(spec)
            while self.active or any(self.pending[spec.label] for spec in self.specs):
                self.reap_finished()
                failure = self.guard_failure()
                if failure:
                    self.terminate_all(failure)
                    self.state["status"] = "halted"
                    self.state["stop_reason"] = failure
                    self.save_state()
                    self.status(force=True)
                    return 2
                for spec in self.specs:
                    self.launch_for(spec)
                self.status()
                time.sleep(5)
            self.status(force=True)
            incomplete = []
            for spec in self.specs:
                summary = self.model_summary(spec)
                if summary["completed"] != summary["total"]:
                    incomplete.append(spec.label)
            if incomplete:
                self.state["status"] = "incomplete"
                self.state["stop_reason"] = f"episodes exhausted retry budget: {', '.join(incomplete)}"
                self.log("incomplete", "suite ended with incomplete episodes", models=incomplete)
                self.save_state()
                return 1
            self.state["status"] = "complete"
            self.log("complete", f"all {len(self.specs) * len(self.seeds)} episodes reached run_end")
            self.save_state()
            return 0
        except KeyboardInterrupt:
            self.terminate_all("supervisor interrupted")
            self.state["status"] = "interrupted"
            self.state["stop_reason"] = self.stop_reason
            self.save_state()
            return 130
        finally:
            if self.lock_handle is not None:
                try:
                    fcntl.flock(self.lock_handle.fileno(), fcntl.LOCK_UN)
                finally:
                    self.lock_handle.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runs/v0.2-public-leaderboard"),
        help="directory containing per-seed transcripts, state, and progress.log",
    )
    parser.add_argument(
        "--seed-values",
        default=",".join(str(seed) for seed in SEEDS),
        help="comma-separated public leaderboard seed values",
    )
    parser.add_argument(
        "--models",
        default=",".join(spec.label for spec in MODEL_SPECS),
        help="comma-separated model labels to run",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        seeds = tuple(dict.fromkeys(int(value.strip()) for value in args.seed_values.split(",") if value.strip()))
    except ValueError as exc:
        print(f"invalid seed selection: {exc}", file=sys.stderr)
        return 2
    if not seeds:
        print("at least one seed is required", file=sys.stderr)
        return 2
    requested_models = tuple(dict.fromkeys(value.strip() for value in args.models.split(",") if value.strip()))
    specs_by_label = {spec.label: spec for spec in MODEL_SPECS}
    unknown_models = [label for label in requested_models if label not in specs_by_label]
    if unknown_models:
        print(f"unknown model label(s): {', '.join(unknown_models)}", file=sys.stderr)
        return 2
    if not requested_models:
        print("at least one model is required", file=sys.stderr)
        return 2
    specs = tuple(specs_by_label[label] for label in requested_models)
    return Supervisor(args.output_dir, seeds, specs).run()


if __name__ == "__main__":
    raise SystemExit(main())
