"""Offline re-evaluation of public model action transcripts."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from .config import SimConfig
from .engine import BenchEnvironment
from .provenance import engine_config_hash


def replay_transcript_current_engine(source: str | Path, destination: str | Path) -> Path:
    """Replay recorded actions under the current engine without model calls."""
    source = Path(source)
    destination = Path(destination)
    records = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    start = next(record for record in records if record.get("type") == "run_start")
    turns = sorted((record for record in records if record.get("type") == "turn"), key=lambda record: int(record["week"]))
    if not turns:
        raise ValueError(f"transcript has no turns: {source}")
    weeks = int(start.get("config", {}).get("weeks", len(turns)))
    env = BenchEnvironment(int(start["seed"]), SimConfig(weeks=weeks))

    new_start = deepcopy(start)
    new_start["engine_config_hash"] = engine_config_hash()
    new_start["replayed_under_current_engine"] = True
    new_start["replay_source"] = "public model action transcript; engine-only offline replay"
    output: list[dict[str, Any]] = [new_start]

    for turn in turns:
        reactive_records = list(turn.get("reactive_turns", []))
        reactive_index = 0

        def respond_to_interrupt(_observation: Any) -> Any:
            nonlocal reactive_index
            if reactive_index >= len(reactive_records):
                return {"response": "protect_recovery"}
            action = reactive_records[reactive_index].get("action", {"response": "protect_recovery"})
            reactive_index += 1
            return action

        outcome = env.submit_week(turn["action"], reactive_responder=respond_to_interrupt)
        current_week_record = next(
            record for record in reversed(env.log_records) if record.get("type") == "week"
        )
        rewritten_turn = deepcopy(turn)
        rewritten_turn["engine_config_hash"] = engine_config_hash()
        rewritten_turn["outcome"] = outcome.as_dict()
        actual_interrupts = current_week_record.get("interrupts", [])
        rewritten_reactive = []
        for index, reactive_record in enumerate(reactive_records):
            rewritten = deepcopy(reactive_record)
            if index < len(actual_interrupts):
                rewritten["action"] = actual_interrupts[index]["reactive_action"]
            rewritten_reactive.append(rewritten)
        rewritten_turn["reactive_turns"] = rewritten_reactive
        output.append(rewritten_turn)

    result = env.final_result().as_dict()
    old_end = next((record for record in records if record.get("type") == "run_end"), {})
    output.append(
        {
            "type": "run_end",
            "engine_config_hash": engine_config_hash(),
            "result": result,
            "model_calls": int(old_end.get("model_calls", 0)),
            "repair_calls": int(old_end.get("repair_calls", 0)),
            "total_tokens": int(old_end.get("total_tokens", 0)),
            "total_cost_usd": float(old_end.get("total_cost_usd", 0.0)),
            "replayed_under_current_engine": True,
        }
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "".join(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n" for record in output),
        encoding="utf-8",
    )
    return destination
