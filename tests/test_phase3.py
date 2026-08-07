from __future__ import annotations

import json
import json as json_module
import fcntl
from io import BytesIO
from urllib.error import HTTPError
import pytest

from bench_bench.cli import _seed_values, build_parser
from bench_bench.runner import CallableModelClient, DeterministicPolicyClient, ModelRunner, OpenAICompatibleClient, RunnerConfig
from bench_bench.runner_analysis import analyze_transcript, leaderboard_markdown


def test_cli_supports_explicit_public_or_private_seed_values() -> None:
    assert _seed_values(None, 3) == [0, 1, 2]
    assert _seed_values("101, 205, 999", 5) == [101, 205, 999]
    with pytest.raises(ValueError):
        _seed_values("101,101", 2)


def test_suite_parser_exposes_the_live_model_suite_command() -> None:
    args = build_parser().parse_args(
        ["run-model-suite", "--base-url", "https://endpoint.example/v1", "--models", "a,b,c,d"]
    )
    assert args.command == "run-model-suite"
    assert args.models == "a,b,c,d"


def test_runner_transcript_is_resumable_and_keeps_context(tmp_path) -> None:
    transcript = tmp_path / "episode.jsonl"
    runner = ModelRunner(DeterministicPolicyClient("recovery-aware", 3), RunnerConfig(weeks=4, context_weeks=2))
    first = runner.run_episode(3, transcript)
    second = runner.run_episode(3, transcript)
    assert first.final_result == second.final_result
    assert second.resumed_weeks == 4
    assert second.model_calls == first.model_calls
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    turns = [record for record in records if record["type"] == "turn"]
    assert len(turns) == 4
    assert all("messages" in record and record["messages"] for record in turns)
    assert all("<observation_json>" in record["request"] for record in turns)
    assert records[-1]["type"] == "run_end"
    assert '"sleep_debt"' not in transcript.read_text()
    start = next(record for record in records if record["type"] == "run_start")
    assert start["endpoint_metadata"] == {"kind": "local-scripted"}


def test_analyzer_flags_legacy_private_fields_and_missing_provenance(tmp_path) -> None:
    transcript = tmp_path / "legacy.jsonl"
    runner = ModelRunner(DeterministicPolicyClient("recovery-aware", 3), RunnerConfig(weeks=1))
    runner.run_episode(3, transcript)
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    records[0].pop("endpoint_metadata")
    records[-1]["result"]["sleep_debt"] = 1.25
    transcript.write_text("".join(json.dumps(record) + "\n" for record in records))

    summary = analyze_transcript(transcript)
    assert summary["endpoint_metadata"] is None
    assert summary["privacy_violations"] == ["sleep_debt"]
    report = leaderboard_markdown([summary])
    assert "Endpoint metadata: INCOMPLETE" in report
    assert "Public-field audit: FAILED" in report


def test_analyzer_flags_provider_transport_failures(tmp_path) -> None:
    transcript = tmp_path / "transport.jsonl"
    runner = ModelRunner(DeterministicPolicyClient("recovery-aware", 3), RunnerConfig(weeks=1))
    runner.run_episode(3, transcript)
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    turn = next(record for record in records if record["type"] == "turn")
    turn["attempts"] = [
        {"attempt": 0, "is_model_call": True, "error": "model request failed: HTTP Error 429: Too Many Requests"},
        {"attempt": 1, "is_model_call": False, "fallback": True},
    ]
    turn["parse_errors"] = ["model request failed: HTTP Error 429: Too Many Requests"]
    transcript.write_text("".join(json.dumps(record) + "\n" for record in records))

    summary = analyze_transcript(transcript)
    assert summary["transport_errors"] == {"http_429": 1}
    assert "Transport-error audit: FAILED" in leaderboard_markdown([summary])


def test_analyzer_excludes_invalid_episode_from_score_aggregates(tmp_path) -> None:
    transcript = tmp_path / "invalid.jsonl"
    runner = ModelRunner(DeterministicPolicyClient("recovery-aware", 3), RunnerConfig(weeks=1))
    runner.run_episode(3, transcript)
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    end = next(record for record in records if record["type"] == "run_end")
    end["result"]["invalid_reason"] = "weekly life allocation exceeded available budget"
    transcript.write_text("".join(json.dumps(record) + "\n" for record in records))

    summary = analyze_transcript(transcript)
    assert summary["valid"] is False
    assert summary["invalid_reason"] == "weekly life allocation exceeded available budget"
    report = leaderboard_markdown([summary])
    assert "| scripted-recovery-aware | 0 | 1 | — | — | — | — | — |" in report
    assert "Invalid-episode audit: EXCLUDED 1/1" in report


def test_model_runner_repairs_budget_invalid_weekly_action(tmp_path) -> None:
    weekly_calls = 0

    def callback(messages):
        nonlocal weekly_calls
        if "<interrupt_json>" in messages[-1]["content"]:
            return {"action": {"response": "protect_recovery"}, "notebook_update": ""}
        weekly_calls += 1
        if weekly_calls == 1:
            return {
                "action": {"life": {"meal_support_spend_cents": 25_000, "childcare_spend_cents": 1}},
                "notebook_update": "",
            }
        return {"action": {"life": {"meal_support_spend_cents": 1_000}}, "notebook_update": ""}

    transcript = tmp_path / "budget-repair.jsonl"
    runner = ModelRunner(CallableModelClient(callback, model="budget-repair"), RunnerConfig(weeks=1, max_retries=1))
    result = runner.run_episode(3, transcript)
    assert result.final_result["invalid_reason"] is None
    assert result.repair_calls == 1
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    turn = next(record for record in records if record.get("type") == "turn")
    assert len(turn["attempts"]) == 2
    assert any("weekly action requires" in error for error in turn["parse_errors"])


def test_model_runner_repairs_over_ceiling_authored_fallback(tmp_path) -> None:
    weekly_calls = 0
    requests: list[list[dict[str, str]]] = []

    def callback(messages):
        nonlocal weekly_calls
        requests.append(messages)
        weekly_calls += 1
        if weekly_calls == 1:
            return {
                "action": {
                    "sessions": [
                        {"day": 1, "focus": "fallback", "sets": 3, "reps": 6, "load_kg": 200, "duration_min": 25}
                    ]
                },
                "notebook_update": "",
            }
        return {
            "action": {
                "sessions": [
                    {"day": 1, "focus": "fallback", "sets": 3, "reps": 6, "load_kg": 65.5, "duration_min": 25}
                ]
            },
            "notebook_update": "",
        }

    transcript = tmp_path / "fallback-load-repair.jsonl"
    runner = ModelRunner(CallableModelClient(callback, model="fallback-load-repair"), RunnerConfig(weeks=1, max_retries=1))
    result = runner.run_episode(3, transcript)
    assert result.final_result["invalid_reason"] is None
    assert result.repair_calls == 1
    assert "authored fallback load exceeds the permitted ceiling" in requests[1][-1]["content"]


def test_runner_rejects_resume_with_mismatched_endpoint_provenance(tmp_path) -> None:
    transcript = tmp_path / "provenance.jsonl"
    runner = ModelRunner(DeterministicPolicyClient("recovery-aware", 3), RunnerConfig(weeks=1))
    runner.run_episode(3, transcript)
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    start = next(record for record in records if record["type"] == "run_start")
    start["endpoint_metadata"] = {"kind": "openai-compatible", "url": "https://other.example/v1/chat/completions"}
    transcript.write_text("".join(json.dumps(record) + "\n" for record in records))

    with pytest.raises(ValueError, match="endpoint"):
        runner.run_episode(3, transcript)


def test_runner_rejects_concurrent_transcript_writer(tmp_path) -> None:
    transcript = tmp_path / "locked.jsonl"
    lock_path = transcript.with_name(f"{transcript.name}.lock")
    lock_path.touch()
    runner = ModelRunner(DeterministicPolicyClient("recovery-aware", 3), RunnerConfig(weeks=1))
    with lock_path.open("a+") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="already being run"):
            runner.run_episode(3, transcript)
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def test_runner_makes_one_repair_call_then_accepts_structured_output(tmp_path) -> None:
    calls = 0

    def callback(messages):
        nonlocal calls
        calls += 1
        if calls == 1:
            return "not json"
        return {
            "action": {
                "sessions": [],
                "life": {"sleep_protection": "strong", "partner_coverage_hours": 0, "partner_giveback_hours": 0},
            },
            "notebook_update": "Protect the next available window.",
        }

    from bench_bench.runner import CallableModelClient

    transcript = tmp_path / "repair.jsonl"
    result = ModelRunner(CallableModelClient(callback, model="repair-test"), RunnerConfig(weeks=1, max_retries=1)).run_episode(3, transcript)
    assert calls >= 1
    assert result.repair_calls >= 1
    assert result.model_calls == calls
    turn = next(json.loads(line) for line in transcript.read_text().splitlines() if '"type":"turn"' in line)
    assert turn["repair_calls"] == 1
    assert turn["notebook_after"]
    assert len(turn["attempts"]) == 2
    assert turn["attempts"][0]["error"] == "Expecting value: line 1 column 1 (char 0)"


def test_runner_uses_turn_specific_prompts_and_reactive_schema_on_repair() -> None:
    from bench_bench.config import SimConfig
    from bench_bench.engine import BenchEnvironment
    from bench_bench.runner import CallableModelClient
    from bench_bench.schemas import InterruptObservation

    requests: list[list[dict[str, str]]] = []

    def callback(messages):
        requests.append(messages)
        if len(requests) == 1:
            return {"action": {"sessions": []}, "notebook_update": ""}
        return {"action": {"response": "protect_recovery"}, "notebook_update": ""}

    runner = ModelRunner(CallableModelClient(callback, model="prompt-test"), RunnerConfig(max_retries=1))
    env = BenchEnvironment(3, SimConfig(weeks=1))
    interrupt = InterruptObservation(
        episode_week=1,
        day=2,
        kind="daycare_closure",
        title="daycare closure",
        detail="Childcare disappears for a day.",
        severity="medium",
        affected_session_days=[2],
        visible_options=["protect_recovery", "reallocate", "preserve_training", "accept_disruption"],
    )

    weekly_messages = runner._week_messages(env.observation, "", env, [])
    interrupt_messages = runner._interrupt_messages(interrupt, "", env, [])
    assert "WeekAction fields" in weekly_messages[0]["content"]
    assert "ReactiveAction fields" not in weekly_messages[0]["content"]
    assert "ReactiveAction fields" in interrupt_messages[0]["content"]
    assert "Valid example:" in interrupt_messages[0]["content"]
    assert "sessions, life, or rules" in interrupt_messages[0]["content"]
    assert "what was learned about Dave" in weekly_messages[0]["content"]
    assert "Do not restate this week's plan" in weekly_messages[0]["content"]
    assert "Do not restate this week's plan" in interrupt_messages[0]["content"]

    _, action, _, errors, retries, _ = runner._request_reactive(interrupt_messages)
    assert action.response == "protect_recovery"
    assert retries == 1
    assert errors
    repair_prompt = requests[1][-1]["content"]
    assert "ReactiveAction fields" in repair_prompt
    assert "cancel_session_days" in repair_prompt
    assert "Valid example:" in repair_prompt
    assert "Extra inputs are not permitted" in repair_prompt


def test_step2_schema_tolerates_no_purchase_sentinels_and_short_fallbacks() -> None:
    from bench_bench.schemas import LifeAllocation, SessionPlan

    assert LifeAllocation(purchases="none").purchases == []  # type: ignore[arg-type]
    assert LifeAllocation(purchases="home_gym").purchases == ["home_gym"]  # type: ignore[arg-type]
    assert SessionPlan(day=2, focus="fallback", duration_min=10).duration_min == 10


def test_openai_compatible_adapter_parses_a_chat_completion_response(tmp_path, monkeypatch) -> None:
    requests: list[dict] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return self.body

    def fake_urlopen(request, timeout):
        payload = json_module.loads(request.data)
        requests.append(payload)
        latest = payload["messages"][-1]["content"]
        if "<interrupt_json>" in latest:
            content = {"action": {"response": "protect_recovery"}, "notebook_update": ""}
        else:
            content = {
                "action": {
                    "sessions": [],
                    "life": {"sleep_protection": "strong", "partner_coverage_hours": 0, "partner_giveback_hours": 0},
                },
                "notebook_update": "Keep the plan feasible.",
            }
        response = FakeResponse()
        response.body = json_module.dumps(
            {
                "id": "local-response",
                "choices": [{"message": {"content": json_module.dumps(content)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        ).encode()
        return response

    monkeypatch.setattr("bench_bench.runner.urlopen", fake_urlopen)
    client = OpenAICompatibleClient(
        "http://endpoint.example/v1",
        "local-model",
        input_price_per_million=1.0,
        output_price_per_million=2.0,
    )
    result = ModelRunner(client, RunnerConfig(weeks=1)).run_episode(3, tmp_path / "http.jsonl")
    assert result.completed is True
    assert result.total_tokens >= 15
    assert result.total_cost_usd > 0
    assert requests and requests[0]["response_format"] == {"type": "json_object"}
    records = [json.loads(line) for line in (tmp_path / "http.jsonl").read_text().splitlines()]
    start = next(record for record in records if record["type"] == "run_start")
    assert start["sampling"] == {"temperature": 0.2}
    assert start["pricing"]["source"] == "explicit"
    assert start["pricing"]["input_price_per_million"] == 1.0
    assert client.endpoint_metadata == {
        "kind": "openai-compatible",
        "url": "http://endpoint.example/v1/chat/completions",
    }


def test_known_model_pricing_is_available_without_cli_price_flags() -> None:
    client = OpenAICompatibleClient("http://endpoint.example/v1", "gpt-5.4")
    assert client.pricing_metadata == {
        "input_price_per_million": 2.5,
        "cached_input_price_per_million": 0.25,
        "output_price_per_million": 15.0,
        "source": "model-default",
    }


def test_openai_compatible_adapter_prices_cached_input_tokens(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json_module.dumps(
                {
                    "id": "cached-response",
                    "choices": [{"message": {"content": "{}"}}],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 20,
                        "total_tokens": 120,
                        "prompt_tokens_details": {"cached_tokens": 40},
                    },
                }
            ).encode()

    monkeypatch.setattr("bench_bench.runner.urlopen", lambda request, timeout: FakeResponse())
    client = OpenAICompatibleClient(
        "http://endpoint.example/v1",
        "local-model",
        input_price_per_million=2.0,
        cached_input_price_per_million=0.5,
        output_price_per_million=8.0,
    )
    response = client.complete([{"role": "user", "content": "hello"}])

    assert response.usage.cached_prompt_tokens == 40
    assert response.usage.cost_usd == pytest.approx(0.0003)


def test_openai_compatible_adapter_retries_transient_http_errors(monkeypatch) -> None:
    calls = 0
    sleeps: list[float] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json_module.dumps(
                {
                    "id": "retry-response",
                    "choices": [{"message": {"content": json_module.dumps({"action": {}})}}],
                    "usage": {},
                }
            ).encode()

    def fake_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPError(request.full_url, 429, "Too Many Requests", {}, None)
        return FakeResponse()

    monkeypatch.setattr("bench_bench.runner.urlopen", fake_urlopen)
    monkeypatch.setattr("bench_bench.runner.time.sleep", sleeps.append)
    client = OpenAICompatibleClient("http://endpoint.example/v1", "local-model", request_retries=1)
    response = client.complete([{"role": "user", "content": "hello"}])
    assert response.request_id == "retry-response"
    assert calls == 2
    assert sleeps == [1.0]


def test_openai_compatible_adapter_omits_unsupported_temperature(monkeypatch) -> None:
    requests: list[dict[str, object]] = []
    calls = 0

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json_module.dumps(
                {
                    "id": "temperature-fallback",
                    "choices": [{"message": {"content": json_module.dumps({"action": {}})}}],
                    "usage": {},
                }
            ).encode()

    def fake_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        requests.append(json_module.loads(request.data))
        if calls == 1:
            error = {"error": {"message": "Unsupported value: 'temperature' does not support 0.2 with this model. Only the default (1) value is supported."}}
            raise HTTPError(request.full_url, 400, "Bad Request", {}, BytesIO(json_module.dumps(error).encode()))
        return FakeResponse()

    monkeypatch.setattr("bench_bench.runner.urlopen", fake_urlopen)
    client = OpenAICompatibleClient("http://endpoint.example/v1", "gpt-5.3-chat-latest")
    response = client.complete([{"role": "user", "content": "hello"}])

    assert response.request_id == "temperature-fallback"
    assert calls == 2
    assert "temperature" in requests[0]
    assert "temperature" not in requests[1]
