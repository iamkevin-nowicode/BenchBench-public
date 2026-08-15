"""Reproducibility metadata for engine-backed artifacts."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path


_PACKAGE_DIR = Path(__file__).resolve().parent
_ENGINE_CONFIG_FILES = ("engine.py", "config.py")


def engine_config_hash() -> str:
    """Return a stable hash of the simulator engine and configuration source."""
    digest = sha256()
    for filename in _ENGINE_CONFIG_FILES:
        path = _PACKAGE_DIR / filename
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def current_prompt_hash() -> str:
    """Return the hash of the exact weekly and reactive prompts in the runner."""
    # Imported lazily because runner imports engine/configuration modules that
    # are also used by artifact replay and analysis.
    from .constraint_inventory import prompt_hash
    from .runner import ModelRunner

    return prompt_hash(ModelRunner.WEEK_SYSTEM_PROMPT, ModelRunner.REACTIVE_SYSTEM_PROMPT)
