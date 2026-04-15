"""Provenance tracking — records the full audit trail of a research run.

Provenance data is written to ``workspace/output/provenance.json`` and includes:
  - Model name and version
  - API call timestamps (phase-level)
  - Python environment metadata
  - Input / output content hashes
  - Random seed used
  - Total token usage and estimated cost
"""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bioagent.state.schema import ResearchState

logger = logging.getLogger(__name__)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _get_package_versions() -> dict[str, str]:
    """Collect versions of key dependencies."""
    packages = [
        "anthropic",
        "langgraph",
        "numpy",
        "pandas",
        "matplotlib",
        "seaborn",
        "biopython",
        "pydantic",
    ]
    versions: dict[str, str] = {}
    for pkg in packages:
        try:
            import importlib.metadata

            versions[pkg] = importlib.metadata.version(pkg)
        except Exception:
            versions[pkg] = "unknown"
    return versions


def _get_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


@dataclass
class PhaseRecord:
    """Record of a single phase execution."""

    phase: str
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    tokens_used: int = 0

    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at is None:
            return None
        return round(self.completed_at - self.started_at, 2)


class ProvenanceTracker:
    """Tracks provenance information throughout a research run."""

    def __init__(self) -> None:
        self.run_id: str = ""
        self.started_at: float = time.time()
        self.model: str = ""
        self.random_seed: int = 42
        self.phase_records: list[PhaseRecord] = []
        self._current_phase: PhaseRecord | None = None

    def start_run(self, run_id: str, model: str, random_seed: int = 42) -> None:
        self.run_id = run_id
        self.model = model
        self.random_seed = random_seed
        self.started_at = time.time()

    def start_phase(self, phase: str) -> None:
        self._current_phase = PhaseRecord(phase=phase)

    def end_phase(self, tokens: int = 0) -> None:
        if self._current_phase:
            self._current_phase.completed_at = time.time()
            self._current_phase.tokens_used = tokens
            self.phase_records.append(self._current_phase)
            self._current_phase = None

    def to_dict(self, state: ResearchState | None = None) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "run_id": self.run_id,
            "model": self.model,
            "random_seed": self.random_seed,
            "started_at": self.started_at,
            "total_duration_seconds": round(time.time() - self.started_at, 2),
            "python_version": sys.version,
            "platform": platform.platform(),
            "git_commit": _get_git_commit(),
            "package_versions": _get_package_versions(),
            "phases": [
                {
                    "phase": r.phase,
                    "started_at": r.started_at,
                    "duration_seconds": r.duration_seconds,
                    "tokens_used": r.tokens_used,
                }
                for r in self.phase_records
            ],
        }

        if state:
            # Content hashes for reproducibility
            topic = state.get("research_topic", "")
            question = state.get("research_question", "")
            papers_text = json.dumps(
                [p.get("id") for p in state.get("papers", []) if isinstance(p, dict)],
                sort_keys=True,
            )
            doc["input_hash"] = _sha256(topic + question)
            doc["papers_hash"] = _sha256(papers_text)

            paper_sections = state.get("paper_sections", {})
            all_text = " ".join(
                (s.get("content", "") if isinstance(s, dict) else str(s))
                for s in paper_sections.values()
            )
            doc["output_hash"] = _sha256(all_text)

        try:
            from bioagent.llm.token_tracking import global_token_usage

            doc["total_tokens"] = global_token_usage.total
            doc["estimated_cost_usd"] = round(global_token_usage.estimated_cost_usd, 4)
        except Exception:
            pass

        return doc

    def save(self, output_dir: Path, state: ResearchState | None = None) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "provenance.json"
        data = self.to_dict(state)
        out_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        logger.info("Provenance saved to %s", out_path)
        return out_path


# Global provenance tracker — shared across the session
_global_tracker = ProvenanceTracker()


def record_provenance(output_dir: Path, state: ResearchState | None = None) -> Path:
    """Save current provenance data to output_dir/provenance.json."""
    return _global_tracker.save(output_dir, state)


def get_tracker() -> ProvenanceTracker:
    return _global_tracker
