"""File read/write/list tools for the workspace."""

from __future__ import annotations

import logging
from pathlib import Path

from bioagent.config.settings import settings
from bioagent.tools.execution.sandbox import ensure_workspace

logger = logging.getLogger(__name__)


def read_file(path: str) -> str:
    """Read a file from the workspace and return its contents.

    Parameters
    ----------
    path : str
        Relative path within the workspace (e.g. ``"data/gene_counts.csv"``).
    """
    full_path = settings.workspace_path / path
    if not full_path.exists():
        return f"Error: file not found: {path}"
    try:
        return full_path.read_text(encoding="utf-8")
    except Exception as exc:
        return f"Error reading file: {exc}"


def write_file(path: str, content: str) -> str:
    """Write content to a file in the workspace.

    Parameters
    ----------
    path : str
        Relative path within the workspace.
    content : str
        Content to write.
    """
    full_path = settings.workspace_path / path
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} chars to {path}"
    except Exception as exc:
        return f"Error writing file: {exc}"


def list_files(directory: str = "") -> str:
    """List files in a workspace directory.

    Parameters
    ----------
    directory : str
        Relative path within the workspace. Defaults to workspace root.
    """
    target = settings.workspace_path / directory if directory else settings.workspace_path
    if not target.exists():
        return f"Error: directory not found: {directory}"

    entries = []
    for p in sorted(target.rglob("*")):
        rel = p.relative_to(target)
        kind = "DIR " if p.is_dir() else "FILE"
        size = f"{p.stat().st_size:>10,} bytes" if p.is_file() else ""
        entries.append(f"{kind}  {rel}  {size}")

    if not entries:
        return "Directory is empty."

    # Limit output
    if len(entries) > 100:
        return "\n".join(entries[:100]) + f"\n... and {len(entries) - 100} more"

    return "\n".join(entries)
