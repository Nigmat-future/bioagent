"""Workspace (sandbox) directory management."""

from __future__ import annotations

import logging
from pathlib import Path

from bioagent.config.settings import settings

logger = logging.getLogger(__name__)


def ensure_workspace() -> Path:
    """Create workspace subdirectories if they don't exist, return root path."""
    root = settings.workspace_path
    for sub in ("scripts", "data", "figures", "output"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def get_scripts_dir() -> Path:
    return ensure_workspace() / "scripts"


def get_data_dir() -> Path:
    return ensure_workspace() / "data"


def get_figures_dir() -> Path:
    return ensure_workspace() / "figures"


def get_output_dir() -> Path:
    return ensure_workspace() / "output"
