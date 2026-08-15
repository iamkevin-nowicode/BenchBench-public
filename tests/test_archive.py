from __future__ import annotations

import json
from pathlib import Path
import tarfile

import pytest

from scripts.build_archive import ArchiveBuildError, build_archive


def _write_transcript(path: Path, response: str = "{}") -> None:
    weekly_prompt = "weekly system prompt"
    reactive_prompt = "reactive system prompt"
    records = [
        {
            "type": "run_start",
            "runner_version": "test",
            "engine_config_hash": "sha256:engine",
            "seed": 100,
            "model": "test-model",
            "config": {"weeks": 1},
        },
        {
            "type": "turn",
            "week": 1,
            "messages": [{"role": "system", "content": weekly_prompt}],
            "reactive_turns": [
                {"messages": [{"role": "system", "content": reactive_prompt}]}
            ],
            "model_response": response,
        },
        {"type": "run_end", "engine_config_hash": "sha256:engine"},
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def test_archive_bytes_are_deterministic_across_output_paths(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _write_transcript(source / "model" / "seed-100.jsonl")
    first = build_archive(source, tmp_path / "first.tar.gz", tmp_path / "first.json", expected_file_count=1)
    second = build_archive(source, tmp_path / "second.tar.gz", tmp_path / "second.json", expected_file_count=1)

    assert (tmp_path / "first.tar.gz").read_bytes() == (tmp_path / "second.tar.gz").read_bytes()
    assert first["archive_sha256"] == second["archive_sha256"]
    with tarfile.open(tmp_path / "first.tar.gz", "r:gz") as archive:
        member = archive.getmembers()[0]
        assert member.name == "v0.1-pilot-transcripts/model/seed-100.jsonl"
        assert member.mtime == 0
        assert member.uid == 0
        assert member.gid == 0


def test_archive_refuses_detected_credentials(tmp_path: Path) -> None:
    source = tmp_path / "source"
    synthetic_token = "sk-" + "test-credential-value-1234567890"
    _write_transcript(source / "model" / "seed-100.jsonl", f"Bearer {synthetic_token}")

    with pytest.raises(ArchiveBuildError, match="credential scan failed"):
        build_archive(source, tmp_path / "pilot.tar.gz", tmp_path / "pilot.json", expected_file_count=1)
    assert not (tmp_path / "pilot.tar.gz").exists()
    assert not (tmp_path / "pilot.json").exists()


def test_archive_supports_named_append_only_run_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "source"
    archive_path = tmp_path / "artifacts" / "v0.2-public-transcripts.tar.gz"
    manifest_path = tmp_path / "artifacts" / "v0.2-public-manifest.json"
    _write_transcript(source / "model" / "seed-400.jsonl")
    manifest = build_archive(
        source,
        archive_path,
        manifest_path,
        expected_file_count=1,
        label="v0.2 public live run",
        archive_prefix="v0.2-public-transcripts",
        archive_path_label="artifacts/v0.2-public-transcripts.tar.gz",
    )
    assert manifest["label"] == "v0.2 public live run"
    assert manifest["archive_path"] == "artifacts/v0.2-public-transcripts.tar.gz"
    assert manifest["archive_member_prefix"] == "v0.2-public-transcripts"
