"""Serialization helpers for state and tool results."""

from __future__ import annotations

import json
from typing import Any


def safe_json_dumps(obj: Any, indent: int = 2) -> str:
    """JSON-serialize with fallback for non-serializable types."""
    return json.dumps(obj, indent=indent, default=str, ensure_ascii=False)


def truncate(text: str, max_len: int = 2000) -> str:
    """Truncate text with ellipsis indicator."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n... [truncated, {len(text) - max_len} chars omitted]"
