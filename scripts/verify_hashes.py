"""Verify SHA-256 hashes of benchmark output files against an expected manifest.

Usage:
    python scripts/verify_hashes.py <manifest.json> <results_dir>

The manifest maps relative file paths to SHA-256 hex digests. Files listed in
the manifest but missing from the results directory cause a failure; extra
files in the results directory are allowed (they are logged but not enforced)
because LLM-generated logs contain timestamps that vary run-to-run.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: verify_hashes.py <manifest.json> <results_dir>", file=sys.stderr)
        return 2

    manifest_path = Path(sys.argv[1])
    results_dir = Path(sys.argv[2])

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures: list[tuple[str, str, str]] = []
    missing: list[str] = []

    for rel, expected in manifest.items():
        target = results_dir / rel
        if not target.exists():
            missing.append(rel)
            continue
        actual = sha256_of(target)
        if actual != expected:
            failures.append((rel, expected, actual))

    if missing:
        print(f"[MISSING] {len(missing)} expected files absent:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)

    if failures:
        print(f"[HASH MISMATCH] {len(failures)} files differ:", file=sys.stderr)
        for rel, exp, act in failures:
            print(f"  - {rel}\n      expected: {exp}\n      actual:   {act}", file=sys.stderr)

    if missing or failures:
        return 1

    print(f"All {len(manifest)} file hashes match expected values.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
