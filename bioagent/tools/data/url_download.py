"""Generic URL downloader with gzip/zip extraction and validation.

Delegates to the resilient ``_http.stream_download`` backbone which
handles retries, Range-resume, adaptive timeouts, and gzip integrity.
"""

from __future__ import annotations

import gzip
import logging
import shutil
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)


def download_url(url: str, filename: str = "", description: str = "") -> str:
    """Download a file from any HTTP/HTTPS URL into ``workspace/data/``.

    Parameters
    ----------
    url:
        Full URL to download.
    filename:
        Output filename (auto-detected from URL if empty).
    description:
        Human-readable description logged alongside the download.

    Returns a status string describing the outcome.
    """
    import urllib.parse

    from bioagent.config.settings import settings
    from bioagent.tools.data._http import cleanup_stale_tmp, stream_download
    from bioagent.tools.execution.sandbox import ensure_workspace

    ensure_workspace()
    data_dir = settings.workspace_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # One-time opportunistic cleanup of stale .tmp files from old runs.
    cleanup_stale_tmp(data_dir, stale_hours=settings.tmp_stale_hours)

    if not filename:
        filename = url.split("/")[-1].split("?")[0] or "downloaded_file"

    out_path = data_dir / filename
    host = urllib.parse.urlparse(url).hostname or "direct"
    label = description or url

    logger.info("[url_download] %s → %s", label, out_path)

    result = stream_download(
        url,
        out_path,
        source_label=host,
        validate_gzip=True,
    )

    if not result.ok:
        return f"ERROR: {result.error} (after {result.attempts} attempt(s))"

    extracted_path = _try_extract(out_path)
    if extracted_path and extracted_path != out_path:
        size_mb = extracted_path.stat().st_size / 1_048_576
        return (
            f"SUCCESS: Downloaded and extracted to {extracted_path} "
            f"({size_mb:.1f} MB, source={result.source}, "
            f"attempts={result.attempts})"
        )

    size_mb = out_path.stat().st_size / 1_048_576
    return (
        f"SUCCESS: Downloaded to {out_path} ({size_mb:.1f} MB, "
        f"source={result.source}, attempts={result.attempts}"
        f"{', resumed' if result.resumed else ''})"
    )


def _try_extract(path: Path) -> Path:
    """Extract .gz or .zip archives. Returns the extracted path or original."""
    suffix = path.suffix.lower()
    if suffix == ".gz" and path.stem.endswith(".tar"):
        return path  # leave tar.gz archives alone
    if suffix == ".gz":
        out = path.with_suffix("")
        with gzip.open(path, "rb") as f_in, open(out, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        path.unlink()
        return out
    if suffix == ".zip":
        extract_dir = path.parent / path.stem
        with zipfile.ZipFile(path) as zf:
            zf.extractall(extract_dir)
        path.unlink()
        return extract_dir
    return path
