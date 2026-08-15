#!/usr/bin/env python3
"""Build a deterministic, credential-scanned archive of published transcripts.

The raw ``runs/`` tree is disposable and ignored by Git.  Published run data
belongs under ``artifacts/`` and is append-only: this command refuses to
overwrite an existing archive or manifest.

The archive is created with :mod:`tarfile` and :mod:`gzip`, rather than a
platform tar command.  Member order, tar metadata, gzip mtime, and compression
level are fixed so the resulting SHA-256 is reproducible.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tarfile
from typing import Any, Iterable

from bench_bench import __version__
from bench_bench.runner import _MODEL_PRICING_USD_PER_MILLION


ARCHIVE_PREFIX = "v0.1-pilot-transcripts"
DEFAULT_EXPECTED_FILE_COUNT = 50
_CREDENTIAL_PATTERNS = (
    ("provider-key-prefix", re.compile(rb"(?i)(?:sk-ant-|sk-proj-|xai-|sk-|key-)[A-Za-z0-9_-]{16,}")),
    ("bearer-token", re.compile(rb"(?i)bearer[ \t]+[A-Za-z0-9._~+/=-]{16,}")),
    (
        "credential-json-field",
        re.compile(
            rb'(?i)"(?:api[_-]?key|access[_-]?token|authorization|secret)"[ \t]*:[ \t]*"[^"\r\n]{16,}"'
        ),
    ),
)


class ArchiveBuildError(RuntimeError):
    """Raised when an archive cannot safely be built."""


@dataclass(frozen=True)
class TranscriptMetadata:
    relative_path: str
    sha256: str
    byte_count: int
    model: str
    seed: int
    weeks: int
    engine_config_hash: str
    prompt_hash: str


def _sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def pricing_table_version() -> str:
    """Return a content-addressed version of the runner's pricing snapshot."""
    payload = _canonical_json(_MODEL_PRICING_USD_PER_MILLION)
    return f"bench_bench.runner._MODEL_PRICING_USD_PER_MILLION@{_sha256_bytes(payload)}"


def _secret_candidates() -> list[tuple[str, bytes]]:
    candidates: list[tuple[str, bytes]] = []
    for path in sorted(Path.home().glob(".bench-bench-*-key")):
        try:
            value = path.read_bytes().strip()
        except OSError:
            continue
        if len(value) >= 12:
            candidates.append((f"key file {path.name}", value))
    for name, value in sorted(os.environ.items()):
        if not value or not any(token in name.upper() for token in ("API_KEY", "TOKEN", "SECRET", "PASSWORD")):
            continue
        encoded = value.encode("utf-8", errors="ignore").strip()
        if len(encoded) >= 12:
            candidates.append((f"environment variable {name}", encoded))
    return candidates


def scan_for_credentials(source_dir: str | Path) -> list[str]:
    """Return safe, non-secret descriptions of credential hits.

    Matched values are never returned or printed.  Both provider-shaped token
    patterns and exact values loaded from local key files/environment variables
    are checked.
    """
    root = Path(source_dir)
    candidates = _secret_candidates()
    hits: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        data = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        for label, pattern in _CREDENTIAL_PATTERNS:
            if pattern.search(data):
                hits.append(f"{relative}: {label}")
        for label, candidate in candidates:
            if candidate in data:
                hits.append(f"{relative}: exact value from {label}")
    return sorted(set(hits))


def _prompt_hash(records: list[dict[str, Any]], relative_path: str) -> str:
    weekly = {
        message.get("content")
        for record in records
        if record.get("type") == "turn"
        for message in record.get("messages", [])
        if message.get("role") == "system"
    }
    reactive = {
        message.get("content")
        for record in records
        if record.get("type") == "turn"
        for reactive_turn in record.get("reactive_turns", [])
        for message in reactive_turn.get("messages", [])
        if message.get("role") == "system"
    }
    if len(weekly) != 1 or len(reactive) != 1:
        raise ArchiveBuildError(
            f"{relative_path}: expected exactly one weekly and one reactive system prompt "
            f"(found {len(weekly)} weekly, {len(reactive)} reactive)"
        )
    calculated = _sha256_bytes(_canonical_json({"reactive": next(iter(reactive)), "weekly": next(iter(weekly))}))
    stamped = {record.get("prompt_hash") for record in records if record.get("prompt_hash")}
    if stamped and (len(stamped) != 1 or calculated not in stamped):
        raise ArchiveBuildError(f"{relative_path}: inconsistent prompt_hash stamp")
    return calculated


def _transcript_metadata(path: Path, source_dir: Path) -> TranscriptMetadata:
    relative_path = path.relative_to(source_dir).as_posix()
    try:
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArchiveBuildError(f"{relative_path}: cannot parse transcript: {exc}") from exc
    starts = [record for record in records if record.get("type") == "run_start"]
    ends = [record for record in records if record.get("type") == "run_end"]
    if len(starts) != 1 or len(ends) != 1:
        raise ArchiveBuildError(f"{relative_path}: expected one run_start and one run_end")
    start = starts[0]
    end = ends[0]
    engine_hashes = {record.get("engine_config_hash") for record in records if record.get("engine_config_hash")}
    if len(engine_hashes) != 1 or start.get("engine_config_hash") not in engine_hashes:
        raise ArchiveBuildError(f"{relative_path}: inconsistent or missing engine_config_hash")
    configured_weeks = int(start.get("config", {}).get("weeks", 0) or 0)
    turns = [record for record in records if record.get("type") == "turn"]
    if configured_weeks <= 0 or len(turns) != configured_weeks:
        raise ArchiveBuildError(
            f"{relative_path}: configured weeks ({configured_weeks}) do not match turn count ({len(turns)})"
        )
    if end.get("engine_config_hash") != start.get("engine_config_hash"):
        raise ArchiveBuildError(f"{relative_path}: run_end engine_config_hash differs from run_start")
    return TranscriptMetadata(
        relative_path=relative_path,
        sha256=_sha256_file(path),
        byte_count=path.stat().st_size,
        model=str(start.get("model", "")),
        seed=int(start.get("seed")),
        weeks=configured_weeks,
        engine_config_hash=str(start.get("engine_config_hash")),
        prompt_hash=_prompt_hash(records, relative_path),
    )


def _tree_hash(transcripts: Iterable[TranscriptMetadata]) -> str:
    digest = hashlib.sha256()
    for transcript in transcripts:
        digest.update(transcript.relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(transcript.sha256.encode("ascii"))
        digest.update(b"\n")
    return f"sha256:{digest.hexdigest()}"


def _write_deterministic_tar(
    source_dir: Path,
    paths: list[Path],
    archive_path: Path,
    archive_prefix: str,
) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with archive_path.open("wb") as raw_file:
        with gzip.GzipFile(
            filename="",
            fileobj=raw_file,
            mode="wb",
            compresslevel=9,
            mtime=0,
        ) as gzip_file:
            with tarfile.open(fileobj=gzip_file, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                for path in paths:
                    relative = path.relative_to(source_dir).as_posix()
                    data = path.read_bytes()
                    info = tarfile.TarInfo(name=f"{archive_prefix}/{relative}")
                    info.size = len(data)
                    info.mode = 0o644
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    archive.addfile(info, io.BytesIO(data))


def build_archive(
    source_dir: str | Path,
    archive_path: str | Path,
    manifest_path: str | Path,
    *,
    expected_file_count: int = DEFAULT_EXPECTED_FILE_COUNT,
    label: str = "v0.1 pilot",
    archive_prefix: str = ARCHIVE_PREFIX,
    archive_path_label: str | None = None,
) -> dict[str, Any]:
    """Build the archive and manifest, refusing unsafe or ambiguous input."""
    source = Path(source_dir).resolve()
    archive = Path(archive_path).resolve()
    manifest = Path(manifest_path).resolve()
    if not source.is_dir():
        raise ArchiveBuildError(f"source directory does not exist: {source}")
    if archive.exists():
        raise ArchiveBuildError(f"refusing to overwrite existing archive: {archive}")
    if manifest.exists():
        raise ArchiveBuildError(f"refusing to overwrite existing manifest: {manifest}")
    paths = sorted(source.rglob("*.jsonl"), key=lambda item: item.relative_to(source).as_posix())
    if len(paths) != expected_file_count:
        raise ArchiveBuildError(
            f"expected {expected_file_count} transcripts below {source}, found {len(paths)}"
        )
    credential_hits = scan_for_credentials(source)
    if credential_hits:
        details = "; ".join(credential_hits)
        raise ArchiveBuildError(f"credential scan failed; archive not written: {details}")
    transcripts = [_transcript_metadata(path, source) for path in paths]
    runner_versions = {
        str(next(record for record in [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if record.get("type") == "run_start").get("runner_version", ""))
        for path in paths
    }
    if len(runner_versions) != 1:
        raise ArchiveBuildError(f"expected one runner version, found {sorted(runner_versions)}")
    _write_deterministic_tar(source, paths, archive, archive_prefix)
    display_archive_path = archive_path_label or archive.as_posix()
    manifest_data: dict[str, Any] = {
        "benchmark": "Bench-bench",
        "label": label,
        "archive_path": display_archive_path,
        "archive_member_prefix": archive_prefix,
        "archive_sha256": _sha256_file(archive),
        "file_count": len(transcripts),
        "byte_count": sum(transcript.byte_count for transcript in transcripts),
        "runner_version": next(iter(runner_versions)),
        "pricing_table_version": pricing_table_version(),
        "engine_config_hashes": sorted({transcript.engine_config_hash for transcript in transcripts}),
        "prompt_hashes": sorted({transcript.prompt_hash for transcript in transcripts}),
        "transcript_tree_sha256": _tree_hash(transcripts),
        "transcripts": [transcript.__dict__ for transcript in transcripts],
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", default="runs/archive/v0.1-pilot")
    parser.add_argument("--archive", default="artifacts/v0.1-pilot-transcripts.tar.gz")
    parser.add_argument("--manifest", default="artifacts/v0.1-pilot-manifest.json")
    parser.add_argument("--expected-file-count", type=int, default=DEFAULT_EXPECTED_FILE_COUNT)
    parser.add_argument("--label", default="v0.1 pilot")
    parser.add_argument("--archive-prefix", default=ARCHIVE_PREFIX)
    parser.add_argument("--archive-path-label")
    args = parser.parse_args()
    try:
        result = build_archive(
            args.source_dir,
            args.archive,
            args.manifest,
            expected_file_count=args.expected_file_count,
            label=args.label,
            archive_prefix=args.archive_prefix,
            archive_path_label=args.archive_path_label,
        )
    except ArchiveBuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        f"Built {result['file_count']} transcripts; {result['byte_count']} raw bytes; "
        f"archive {result['archive_sha256']}; manifest {args.manifest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
