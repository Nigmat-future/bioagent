"""Custom reducer functions for LangGraph state channels."""

from __future__ import annotations

import hashlib
import json


def _content_hash(item: dict) -> str:
    """Deterministic hash of a dict's JSON representation for dedup."""
    raw = json.dumps(item, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def dedup_add(left: list, right: list | dict) -> list:
    """Append items from *right* to *left*, skipping duplicates by content hash.

    Accepts either a list (standard reducer call) or a single dict
    (convenience for one-item appends).
    """
    if not isinstance(right, list):
        right = [right]

    existing_hashes = {_content_hash(item) for item in left}
    result = list(left)
    for item in right:
        if _content_hash(item) not in existing_hashes:
            result.append(item)
            existing_hashes.add(_content_hash(item))
    return result


def replace_last(left: list, right: list | dict) -> list:
    """Replace the last element of *left* with *right*, or append if empty."""
    if not isinstance(right, list):
        right = [right]

    result = list(left)
    for item in right:
        if result:
            result[-1] = item
        else:
            result.append(item)
    return result
