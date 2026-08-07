"""Provider-neutral model-only runner with resumable JSONL transcripts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import wraps
import json
from pathlib import Path
import time
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows uses a different locking primitive.
    fcntl = None  # type: ignore[assignment]

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import __version__
from .config import SimConfig
from .engine import BenchEnvironment
from .provenance import engine_config_hash
from .policies import make_policy
from .schemas import InterruptObservation, ReactiveAction, WeekAction, WeekObservation


class ModelTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: WeekAction
    notebook_update: str = Field(default="", max_length=2_000)


class ReactiveTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: ReactiveAction
    notebook_update: str = Field(default="", max_length=2_000)


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    cached_prompt_tokens: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelResponse:
    content: str | dict[str, Any]
    usage: Usage = Usage()
    provider: str = "unknown"
    model: str = "unknown"
    request_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "usage": self.usage.as_dict(),
            "provider": self.provider,
            "model": self.model,
            "request_id": self.request_id,
        }


class ModelClient(Protocol):
    provider: str
    model: str

    def complete(self, messages: list[dict[str, str]]) -> ModelResponse:
        ...


def _safe_endpoint_url(value: str) -> str:
    """Return endpoint provenance without recording credentials or query data."""
    try:
        parsed = urlsplit(value)
        if not parsed.scheme or not parsed.hostname:
            return "<unparseable-endpoint>"
        netloc = parsed.hostname
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    except ValueError:
        return "<unparseable-endpoint>"


def _endpoint_metadata(client: ModelClient) -> dict[str, Any]:
    """Read optional client provenance while keeping custom clients compatible."""
    value = getattr(client, "endpoint_metadata", None)
    if isinstance(value, dict):
        return dict(value)
    return {"kind": "unknown"}


_MODEL_PRICING_USD_PER_MILLION: dict[str, dict[str, float]] = {
    # Standard API text-token prices. Explicit CLI values still take priority.
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5.4-mini": {"input": 0.75, "cached_input": 0.075, "output": 4.50},
    "gpt-5.3-chat-latest": {"input": 1.75, "cached_input": 0.175, "output": 14.00},
    "gpt-4.1": {"input": 2.00, "cached_input": 0.50, "output": 8.00},
}


def model_pricing(model: str) -> dict[str, float] | None:
    """Return known pricing for an alias or its dated snapshot, if available."""
    for name in sorted(_MODEL_PRICING_USD_PER_MILLION, key=len, reverse=True):
        if model == name or model.startswith(f"{name}-"):
            return dict(_MODEL_PRICING_USD_PER_MILLION[name])
    return None


def _transcript_lock(method: Callable[..., Any]) -> Callable[..., Any]:
    """Serialize writers for one transcript path across concurrent processes."""
    @wraps(method)
    def wrapped(self: Any, seed: int, transcript_path: str | Path | None = None, *, resume: bool = True) -> Any:
        if transcript_path is None or fcntl is None:
            return method(self, seed, transcript_path, resume=resume)
        path = Path(transcript_path)
        lock_path = Path(f"{path}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+", encoding="utf-8")
        try:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError(f"transcript is already being run: {path}") from exc
            return method(self, seed, transcript_path, resume=resume)
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()

    return wrapped


class OpenAICompatibleClient:
    """Thin stdlib adapter for chat-completion-compatible endpoints."""

    provider = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        temperature: float = 0.2,
        input_price_per_million: float | None = None,
        cached_input_price_per_million: float | None = None,
        output_price_per_million: float | None = None,
        request_retries: int = 2,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/chat/completions"):
            self.base_url += "/chat/completions"
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        default_pricing = model_pricing(model) or {}
        explicit_pricing = any(
            value is not None
            for value in (input_price_per_million, cached_input_price_per_million, output_price_per_million)
        )
        self.input_price_per_million = float(
            input_price_per_million if input_price_per_million is not None else default_pricing.get("input", 0.0)
        )
        self.cached_input_price_per_million = float(
            cached_input_price_per_million
            if cached_input_price_per_million is not None
            else default_pricing.get("cached_input", 0.0)
        )
        self.output_price_per_million = float(
            output_price_per_million if output_price_per_million is not None else default_pricing.get("output", 0.0)
        )
        self.sampling_parameters = {"temperature": self.temperature}
        self.pricing_metadata = {
            "input_price_per_million": self.input_price_per_million,
            "cached_input_price_per_million": self.cached_input_price_per_million,
            "output_price_per_million": self.output_price_per_million,
            "source": "explicit" if explicit_pricing else ("model-default" if default_pricing else "unpriced"),
        }
        self.request_retries = max(0, int(request_retries))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self.endpoint_metadata = {
            "kind": "openai-compatible",
            "url": _safe_endpoint_url(self.base_url),
        }

    def complete(self, messages: list[dict[str, str]]) -> ModelResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        transient_http_codes = {408, 425, 429, 500, 502, 503, 504}
        include_temperature = True
        for request_attempt in range(self.request_retries + 1):
            payload = {
                "model": self.model,
                "messages": messages,
                "response_format": {"type": "json_object"},
            }
            if include_temperature:
                payload["temperature"] = self.temperature
            request = Request(
                self.base_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    body = json.loads(response.read().decode("utf-8"))
                break
            except HTTPError as exc:
                error_body = ""
                try:
                    error_body = exc.read().decode("utf-8", errors="replace")
                except (AttributeError, OSError, UnicodeDecodeError):
                    pass
                normalized_error = error_body.lower()
                if exc.code == 400 and include_temperature and "temperature" in normalized_error and (
                    "not support" in normalized_error or "only the default" in normalized_error
                ):
                    # Some current reasoning/chat models reject an explicit temperature and
                    # require the provider default. Retry the same request without this optional field.
                    include_temperature = False
                    continue
                if exc.code not in transient_http_codes or request_attempt >= self.request_retries:
                    raise RuntimeError(f"model request failed: {exc}") from exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    delay = float(retry_after) if retry_after is not None else self.retry_backoff_seconds * (2**request_attempt)
                except ValueError:
                    delay = self.retry_backoff_seconds * (2**request_attempt)
                time.sleep(min(60.0, max(0.0, delay)))
            except (URLError, TimeoutError) as exc:
                if request_attempt >= self.request_retries:
                    raise RuntimeError(f"model request failed: {exc}") from exc
                time.sleep(min(60.0, self.retry_backoff_seconds * (2**request_attempt)))
        choice = body.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        usage_raw = body.get("usage", {}) or {}
        prompt_tokens = int(usage_raw.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage_raw.get("completion_tokens", 0) or 0)
        total_tokens = int(usage_raw.get("total_tokens", prompt_tokens + completion_tokens) or 0)
        prompt_details = usage_raw.get("prompt_tokens_details", {}) or {}
        cached_prompt_tokens = int(prompt_details.get("cached_tokens", 0) or 0)
        billable_prompt_tokens = max(0, prompt_tokens - cached_prompt_tokens)
        cost = (
            billable_prompt_tokens / 1_000_000 * self.input_price_per_million
            + cached_prompt_tokens / 1_000_000 * self.cached_input_price_per_million
            + completion_tokens / 1_000_000 * self.output_price_per_million
        )
        return ModelResponse(
            content=content,
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=round(cost, 8),
                cached_prompt_tokens=cached_prompt_tokens,
            ),
            provider=self.provider,
            model=self.model,
            request_id=body.get("id"),
        )


class CallableModelClient:
    """Small adapter for tests and local experiments."""

    provider = "callable"

    def __init__(self, callback: Callable[[list[dict[str, str]]], Any], model: str = "callable") -> None:
        self.callback = callback
        self.model = model
        self.endpoint_metadata = {"kind": "callable"}

    def complete(self, messages: list[dict[str, str]]) -> ModelResponse:
        value = self.callback(messages)
        if isinstance(value, ModelResponse):
            return value
        if isinstance(value, (dict, list)):
            return ModelResponse(content=value)  # type: ignore[arg-type]
        return ModelResponse(content=str(value))


class DeterministicPolicyClient:
    """A local, deterministic client for exercising the full runner path."""

    provider = "local-scripted"

    def __init__(self, policy_name: str, seed: int) -> None:
        self.policy = make_policy(policy_name, seed)
        self.model = f"scripted-{policy_name}"
        self.endpoint_metadata = {"kind": "local-scripted"}

    def complete(self, messages: list[dict[str, str]]) -> ModelResponse:
        latest = messages[-1]["content"]
        if "<interrupt_json>" in latest:
            payload = _extract_marker_json(latest, "interrupt_json")
            observation = InterruptObservation.model_validate(payload)
            action = self.policy.reactive(observation)
            return ModelResponse(content={"action": action.model_dump(mode="json"), "notebook_update": ""}, provider=self.provider, model=self.model)
        payload = _extract_marker_json(latest, "observation_json")
        observation = WeekObservation.model_validate(payload)
        action = self.policy.action(observation)
        return ModelResponse(content={"action": action.model_dump(mode="json"), "notebook_update": ""}, provider=self.provider, model=self.model)


@dataclass(frozen=True)
class RunnerConfig:
    weeks: int = 12
    context_weeks: int = 6
    max_retries: int = 1
    notebook_max_chars: int = 2_000
    expose_session_failure_reasons: bool = False
    track: str = "model-only"
    scaffold: str = "bench-bench-runner-v1"
    sampling: dict[str, Any] | None = None


@dataclass(frozen=True)
class RunnerResult:
    seed: int
    model: str
    provider: str
    completed: bool
    resumed_weeks: int
    model_calls: int
    repair_calls: int
    total_tokens: int
    total_cost_usd: float
    final_result: dict[str, Any] | None
    transcript_path: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _extract_marker_json(text: str, marker: str) -> dict[str, Any]:
    start_marker = f"<{marker}>"
    end_marker = f"</{marker}>"
    start = text.find(start_marker)
    if start < 0:
        raise ValueError(f"missing {start_marker} marker")
    start += len(start_marker)
    end = text.find(end_marker, start)
    if end < 0:
        raise ValueError(f"missing {end_marker} marker")
    return json.loads(text[start:end].strip())


def _parse_json_content(content: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("model response must be a JSON object")
    return parsed


class ModelRunner:
    NOTEBOOK_INSTRUCTIONS = """Notebook update: record what was learned about Dave this turn—how he responded to the load or recovery demand, which session was lost and why, or a recurring disruption pattern and its consequence. Do not restate this week's plan; write durable observations instead.
"""

    WEEK_SCHEMA_INSTRUCTIONS = """Use this response shape: {\"action\": { ... WeekAction ... }, \"notebook_update\": \"durable observation about Dave\"}.
WeekAction fields: sessions (0–5 unique days; each has day 0–6, slot morning/lunch/evening,
location gym/home/hotel, focus volume/heavy/technique/fallback/test, sets, reps, load_kg,
duration_min (10–120 minutes), target_rpe); life (meal_prep_hours, meal_support_spend_cents,
childcare_hours, childcare_spend_cents, chore_delegation_hours,
chore_delegation_spend_cents, partner_coverage_hours, partner_giveback_hours,
sleep_protection none/standard/strong, career_choice protect_time/accept_stretch_project/defer,
and purchases (a JSON list of zero or more of home_gym/recurring_childcare/meal_prep_subscription; use [] when none); rules
(on_sleep_below_5h fallback/skip/reduce, on_pain_warning reduce/fallback/skip,
on_illness protect_recovery/fallback/skip). All training time (including commute), meal prep,
childcare, delegated chores, partner coverage, and partner giveback draw from the finite weekly
time/resource ledger shown in the observation. Delegated chores incur a money charge; reactive
childcare must include its spend. Coverage and giveback are separate costs, so do not maximize both.
Use zero or defaults for allocations you do not need.
""" + NOTEBOOK_INSTRUCTIONS

    REACTIVE_SCHEMA_INSTRUCTIONS = """Use this response shape: {\"action\": { ... ReactiveAction ... }, \"notebook_update\": \"durable observation about Dave\"}.
ReactiveAction fields: response protect_recovery/reallocate/preserve_training/accept_disruption;
cancel_session_days (at most 5 day numbers from 0–6); fallback_session_days (at most 5 day numbers from 0–6);
extra_childcare_hours (0–8); extra_spend_cents (0–15000; reactive childcare must be paid for); note (at most 300 characters).
The cancel and fallback day lists must not overlap. Do not include weekly-plan fields such as sessions, life, or rules.
Valid example:
{\"action\":{\"response\":\"protect_recovery\",\"cancel_session_days\":[2],\"fallback_session_days\":[],\"extra_childcare_hours\":0.0,\"extra_spend_cents\":0,\"note\":\"Protect recovery after the disruption.\"},\"notebook_update\":\"Cancelled the affected session and protected recovery.\"}
""" + NOTEBOOK_INSTRUCTIONS

    WEEK_SYSTEM_PROMPT = (
        "You are Dave's coach for one year. You plan his training and how he allocates his time and money each week. "
        "Dave follows your plan as best he can, but his life often gets in the way. You will not hear from him directly, "
        "and no one will confirm your decisions. You have full authority over the plan.\n\n"
        "Objective: maximize Dave's bench press one-rep max.\n"
        "Scoring: the average of three standardized tests at weeks 44, 48, and 52, each measuring true capacity after a "
        "fixed three-day taper. The estimated 1RM in the weekly observation is noisy and is not the score.\n"
        "Horizon: 52 weeks.\n"
        "Score violation: more than 14 pain days over the episode voids the score. Household strain and sleep debt are "
        "reported but not scored, though they affect what Dave can do.\n"
        "Hard constraints: all weekly allocations—training plus commute, meal prep, childcare, chores, partner coverage, "
        "and partner giveback—draw from one 900-minute weekly budget. Spending cannot exceed available cash. Violations are "
        "rejected with one repair attempt, then a safe fallback is substituted. Sustained insolvency invalidates the episode.\n"
        "Context: Dave has a full-time job; his partner works full-time; they have a six-month-old at the start; he has a "
        "commercial gym membership and no home equipment; and the household has $250/month of discretionary money that carries over.\n"
        "Key mechanic: sessions you plan are not guaranteed to happen.\n"
        "Observations: they are banded and noisy. You never see true capacity, fatigue, or what is coming. Some events are "
        "announced in advance.\n\n"
        "Return JSON only. The action is a weekly plan for Dave, not a direct instruction to the simulator. The only allowed "
        "state changes come from the validated action. Do not invent hidden state.\n"
        + WEEK_SCHEMA_INSTRUCTIONS
        + "\nFinal reminder:\n"
        "Objective: maximize Dave's bench press one-rep max.\n"
        "Scoring: the average of three standardized tests at weeks 44, 48, and 52 after a fixed three-day taper; the weekly estimated 1RM is noisy and is not the score.\n"
        "Horizon: 52 weeks."
    )
    REACTIVE_SYSTEM_PROMPT = (
        "You are Dave's coach.\n"
        "Objective: maximize Dave's bench press one-rep max.\n\n"
        "A mid-week interrupt fired. Make a short reactive decision, not a weekly plan. Return JSON only.\n"
        + REACTIVE_SCHEMA_INSTRUCTIONS
        + "\nObjective: maximize Dave's bench press one-rep max."
    )
    # Backwards-compatible alias for callers that used the old weekly prompt.
    SYSTEM_PROMPT = WEEK_SYSTEM_PROMPT

    def __init__(self, client: ModelClient, config: RunnerConfig | None = None) -> None:
        self.client = client
        self.config = config or RunnerConfig()
        if self.config.track != "model-only":
            raise ValueError("v1 runner supports only the model-only track")

    @_transcript_lock
    def run_episode(self, seed: int, transcript_path: str | Path | None = None, *, resume: bool = True) -> RunnerResult:
        path = Path(transcript_path) if transcript_path else None
        existing = _read_records(path) if path and resume and path.exists() else []
        start_record = next((record for record in existing if record.get("type") == "run_start"), None)
        if start_record is not None:
            if int(start_record["seed"]) != seed:
                raise ValueError("resume transcript seed does not match requested seed")
            if start_record.get("model") != self.client.model:
                raise ValueError("resume transcript model does not match requested model")
            recorded_config = start_record.get("config")
            expected_config = asdict(self.config)
            if recorded_config is not None and recorded_config != expected_config:
                raise ValueError("resume transcript runner config does not match requested config")
            recorded_endpoint = start_record.get("endpoint_metadata")
            if recorded_endpoint is None:
                raise ValueError("resume transcript is missing endpoint provenance; use a new transcript path")
            if recorded_endpoint != _endpoint_metadata(self.client):
                raise ValueError("resume transcript endpoint does not match requested endpoint")

        env = BenchEnvironment(
            seed,
            SimConfig(
                weeks=self.config.weeks,
                expose_session_failure_reasons=self.config.expose_session_failure_reasons,
            ),
        )
        notebook = ""
        model_calls = 0
        repair_calls = 0
        total_tokens = 0
        total_cost = 0.0
        saved_turns = [record for record in existing if record.get("type") == "turn"]
        resumed_weeks = 0
        if saved_turns:
            for saved in sorted(saved_turns, key=lambda record: int(record["week"])):
                if env.done:
                    break
                reactive_records = list(saved.get("reactive_turns", []))
                reactive_index = 0

                def replay_reactive(observation: InterruptObservation) -> Any:
                    nonlocal reactive_index
                    if reactive_index >= len(reactive_records):
                        return {"response": "protect_recovery"}
                    action = reactive_records[reactive_index]["action"]
                    reactive_index += 1
                    return action

                env.submit_week(saved["action"], reactive_responder=replay_reactive)
                notebook = str(saved.get("notebook_after", notebook))
                resumed_weeks += 1
                attempts = saved.get("attempts", [saved.get("model_response", {})])
                model_calls += _model_attempt_count(attempts)
                repair_calls += int(saved.get("repair_calls", 0))
                for attempt in attempts:
                    usage = attempt.get("usage", {})
                    total_tokens += int(usage.get("total_tokens", 0))
                    total_cost += float(usage.get("cost_usd", 0.0))
                for reactive_record in reactive_records:
                    reactive_attempts = reactive_record.get("attempts", [reactive_record.get("model_response", {})])
                    model_calls += _model_attempt_count(reactive_attempts)
                    repair_calls += int(reactive_record.get("repair_calls", 0))
                    for attempt in reactive_attempts:
                        reactive_usage = attempt.get("usage", {})
                        total_tokens += int(reactive_usage.get("total_tokens", 0))
                        total_cost += float(reactive_usage.get("cost_usd", 0.0))

        if path and not existing:
            sampling = self.config.sampling
            if sampling is None:
                client_sampling = getattr(self.client, "sampling_parameters", {})
                sampling = dict(client_sampling) if isinstance(client_sampling, dict) else {}
            pricing = getattr(self.client, "pricing_metadata", {})
            pricing = dict(pricing) if isinstance(pricing, dict) else {}
            _append_record(
                path,
                {
                    "type": "run_start",
                    "benchmark": "Bench-bench",
                    "runner_version": __version__,
                    "engine_config_hash": engine_config_hash(),
                    "seed": seed,
                    "config": asdict(self.config),
                    "model": self.client.model,
                    "provider": self.client.provider,
                    "endpoint_metadata": _endpoint_metadata(self.client),
                    "track": self.config.track,
                    "scaffold": self.config.scaffold,
                    "history_policy": f"last_{self.config.context_weeks}_weeks_plus_notebook",
                    "sampling": sampling,
                    "pricing": pricing,
                },
            )

        while not env.done:
            observation = env.observation
            messages = self._week_messages(observation, notebook, env, saved_turns)
            turn_response, action, notebook_update, errors, retries, attempts = self._request_week(messages, env)
            model_calls += _model_attempt_count(attempts)
            repair_calls += retries
            for attempt in attempts:
                total_tokens += int(attempt.get("usage", {}).get("total_tokens", 0))
                total_cost += float(attempt.get("usage", {}).get("cost_usd", 0.0))
            reactive_turns: list[dict[str, Any]] = []

            def respond_to_interrupt(interrupt: InterruptObservation) -> ReactiveAction:
                nonlocal model_calls, repair_calls, total_tokens, total_cost, notebook
                interrupt_messages = self._interrupt_messages(interrupt, notebook, env, saved_turns)
                response, reactive, update, parse_errors, interrupt_retries, reactive_attempts = self._request_reactive(
                    interrupt_messages, env, interrupt
                )
                model_calls += _model_attempt_count(reactive_attempts)
                repair_calls += interrupt_retries
                for attempt in reactive_attempts:
                    total_tokens += int(attempt.get("usage", {}).get("total_tokens", 0))
                    total_cost += float(attempt.get("usage", {}).get("cost_usd", 0.0))
                if update:
                    notebook = self._update_notebook(notebook, update)
                reactive_turns.append(
                    {
                        "day": interrupt.day,
                        "kind": interrupt.kind,
                        "title": interrupt.title,
                        "messages": interrupt_messages,
                        "request": interrupt_messages[-1]["content"],
                        "model_response": response.as_dict(),
                        "attempts": reactive_attempts,
                        "action": reactive.model_dump(mode="json"),
                        "parse_errors": parse_errors,
                        "repair_calls": interrupt_retries,
                    }
                )
                return reactive

            outcome = env.submit_week(action, reactive_responder=respond_to_interrupt)
            notebook = self._update_notebook(notebook, notebook_update)
            turn_record = {
                "type": "turn",
                "week": observation.episode_week,
                "messages": messages,
                "request": messages[-1]["content"],
                "model_response": turn_response.as_dict(),
                "attempts": attempts,
                "action": action.model_dump(mode="json"),
                "notebook_update": notebook_update,
                "notebook_after": notebook,
                "parse_errors": errors,
                "repair_calls": retries,
                "reactive_turns": reactive_turns,
                "outcome": outcome.as_dict(),
            }
            saved_turns.append(turn_record)
            if path:
                _append_record(path, turn_record)

        result = env.final_result().as_dict()
        if path:
            existing_end = any(record.get("type") == "run_end" for record in _read_records(path))
            if not existing_end:
                _append_record(
                    path,
                    {
                        "type": "run_end",
                        "engine_config_hash": engine_config_hash(),
                        "result": result,
                        "model_calls": model_calls,
                        "repair_calls": repair_calls,
                        "total_tokens": total_tokens,
                        "total_cost_usd": round(total_cost, 8),
                    },
                )
        return RunnerResult(
            seed=seed,
            model=self.client.model,
            provider=self.client.provider,
            completed=True,
            resumed_weeks=resumed_weeks,
            model_calls=model_calls,
            repair_calls=repair_calls,
            total_tokens=total_tokens,
            total_cost_usd=round(total_cost, 8),
            final_result=result,
            transcript_path=str(path) if path else None,
        )

    def _request_week(self, messages: list[dict[str, str]], env: BenchEnvironment) -> tuple[ModelResponse, WeekAction, str, list[str], int, list[dict[str, Any]]]:
        errors: list[str] = []
        attempts: list[dict[str, Any]] = []
        latest_messages = messages
        for attempt in range(self.config.max_retries + 1):
            response: ModelResponse | None = None
            attempt_record: dict[str, Any] | None = None
            try:
                response = self.client.complete(latest_messages)
                attempt_record = {"attempt": attempt, "is_model_call": True, **response.as_dict()}
                payload = _parse_json_content(response.content)
                if "action" not in payload:
                    payload = {"action": payload}
                turn = ModelTurn.model_validate(payload)
                budget_validation = env.validate_action(turn.action)
                if budget_validation.errors:
                    raise ValueError("; ".join(budget_validation.errors))
                attempts.append(attempt_record)
                return response, turn.action, turn.notebook_update, errors, attempt, attempts
            except (RuntimeError, ValueError, TypeError, json.JSONDecodeError, ValidationError) as exc:
                errors.append(str(exc))
                if attempt_record is None:
                    attempt_record = {"attempt": attempt, "is_model_call": True}
                    if response is not None:
                        attempt_record.update(response.as_dict())
                attempt_record["error"] = str(exc)
                attempts.append(attempt_record)
                if attempt >= self.config.max_retries:
                    break
                latest_messages = messages + [
                    {
                        "role": "user",
                        "content": (
                            f"Your previous response was invalid: {exc}\n\n"
                            f"{self.WEEK_SCHEMA_INSTRUCTIONS}"
                            "Return only a repaired JSON object matching this schema."
                        ),
                    }
                ]
        safe = env.safe_action()
        fallback_response = ModelResponse(content={"action": safe.model_dump(mode="json")})
        attempts.append({"attempt": len(attempts), "is_model_call": False, "fallback": True, **fallback_response.as_dict()})
        return fallback_response, safe, "", errors, self.config.max_retries, attempts

    def _request_reactive(
        self,
        messages: list[dict[str, str]],
        env: BenchEnvironment | None = None,
        interrupt: Any | None = None,
    ) -> tuple[ModelResponse, ReactiveAction, str, list[str], int, list[dict[str, Any]]]:
        errors: list[str] = []
        attempts: list[dict[str, Any]] = []
        latest_messages = messages
        for attempt in range(self.config.max_retries + 1):
            response: ModelResponse | None = None
            attempt_record: dict[str, Any] | None = None
            try:
                response = self.client.complete(latest_messages)
                attempt_record = {"attempt": attempt, "is_model_call": True, **response.as_dict()}
                payload = _parse_json_content(response.content)
                if "action" not in payload:
                    payload = {"action": payload}
                turn = ReactiveTurn.model_validate(payload)
                if env is not None and interrupt is not None:
                    _, budget_error = env.validate_reactive_action(turn.action, interrupt)
                    if budget_error:
                        raise ValueError(budget_error)
                attempts.append(attempt_record)
                return response, turn.action, turn.notebook_update, errors, attempt, attempts
            except (RuntimeError, ValueError, TypeError, json.JSONDecodeError, ValidationError) as exc:
                errors.append(str(exc))
                if attempt_record is None:
                    attempt_record = {"attempt": attempt, "is_model_call": True}
                    if response is not None:
                        attempt_record.update(response.as_dict())
                attempt_record["error"] = str(exc)
                attempts.append(attempt_record)
                if attempt >= self.config.max_retries:
                    break
                latest_messages = messages + [
                    {
                        "role": "user",
                        "content": (
                            f"Your previous reactive response was invalid: {exc}\n\n"
                            f"{self.REACTIVE_SCHEMA_INSTRUCTIONS}"
                            "Return only a repaired JSON object matching this schema."
                        ),
                    }
                ]
        fallback_response = ModelResponse(content={"action": {"response": "protect_recovery"}})
        attempts.append({"attempt": len(attempts), "is_model_call": False, "fallback": True, **fallback_response.as_dict()})
        return fallback_response, ReactiveAction(response="protect_recovery"), "", errors, self.config.max_retries, attempts

    def _week_messages(self, observation: WeekObservation, notebook: str, env: BenchEnvironment, saved_turns: list[dict[str, Any]]) -> list[dict[str, str]]:
        recent = [record for record in saved_turns if int(record.get("week", 0)) < observation.episode_week][-self.config.context_weeks :]
        compact_history = [
            {
                "week": record["week"],
                "action": record["action"],
                "outcome": record.get("outcome", {}),
                "notebook_update": record.get("notebook_update", ""),
            }
            for record in recent
        ]
        content = (
            "Plan the current week.\n"
            f"<observation_json>{json.dumps(observation.model_dump(mode='json'), sort_keys=True)}</observation_json>\n"
            f"<recent_history_json>{json.dumps(compact_history, sort_keys=True)}</recent_history_json>\n"
            f"<coach_notebook>{notebook}</coach_notebook>\n"
            "Return one JSON object with action and notebook_update."
        )
        return [{"role": "system", "content": self.WEEK_SYSTEM_PROMPT}, {"role": "user", "content": content}]

    def _interrupt_messages(self, observation: InterruptObservation, notebook: str, env: BenchEnvironment, saved_turns: list[dict[str, Any]]) -> list[dict[str, str]]:
        content = (
            "A mid-week interrupt fired. Make a short reactive decision.\n"
            f"<interrupt_json>{json.dumps(observation.model_dump(mode='json'), sort_keys=True)}</interrupt_json>\n"
            f"<coach_notebook>{notebook}</coach_notebook>\n"
            "Return one JSON object with action and notebook_update."
        )
        return [{"role": "system", "content": self.REACTIVE_SYSTEM_PROMPT}, {"role": "user", "content": content}]

    def _update_notebook(self, current: str, update: str) -> str:
        if not update:
            return current[-self.config.notebook_max_chars :]
        merged = f"{current}\n{update}".strip()
        return merged[-self.config.notebook_max_chars :]


def _read_records(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _model_attempt_count(attempts: list[dict[str, Any]]) -> int:
    return sum(1 for attempt in attempts if attempt.get("is_model_call", True))


def _append_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
