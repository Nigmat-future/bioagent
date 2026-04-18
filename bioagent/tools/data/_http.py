"""Resilient HTTP downloader — httpx + tenacity + Range-resume + gzip integrity.

Shared by all five data tools (url/geo/cbioportal/gdc/ncbi/encode).
Replaces per-tool stdlib urllib calls which had no retry, no resume, no
integrity checking — the root cause of the ``.tmp`` pileup and
``EOFError: Compressed file ended before end-of-stream`` failures
observed on China-side network paths.
"""

from __future__ import annotations

import gzip
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """Structured outcome of a download attempt."""

    status: str  # "success" | "failed"
    path: Optional[Path] = None
    source: str = ""
    bytes_written: int = 0
    attempts: int = 0
    resumed: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "success"


class _RetryableHTTPError(Exception):
    """Marker for 429 / 5xx responses — worth retrying."""


def _build_client(*, verify: bool = True) -> httpx.Client:
    # trust_env=False keeps Clash/system proxies from breaking TLS on Windows,
    # matching the workaround already applied in bioagent/llm/clients.py.
    return httpx.Client(
        trust_env=False,
        verify=verify,
        follow_redirects=True,
        headers={"User-Agent": "BioAgent/1.0 (bioagent@example.com)"},
    )


def _estimate_read_timeout(expected_mb: float, min_mbps: float) -> float:
    mbits = max(expected_mb, 1.0) * 8
    seconds_needed = mbits / max(min_mbps, 0.5)
    return max(60.0, seconds_needed * 2.0)


def cleanup_stale_tmp(data_dir: Path, stale_hours: int = 24) -> int:
    """Delete .tmp files older than ``stale_hours``. Returns count deleted."""
    if not data_dir.exists():
        return 0
    cutoff = time.time() - stale_hours * 3600
    deleted = 0
    for tmp in data_dir.rglob("*.tmp"):
        try:
            if tmp.stat().st_mtime < cutoff:
                tmp.unlink()
                deleted += 1
        except OSError:
            pass
    if deleted:
        logger.info("[_http] Cleaned %d stale .tmp file(s)", deleted)
    return deleted


def stream_download(
    url: str,
    dest: Path,
    *,
    source_label: str = "",
    validate_gzip: bool = True,
    max_bytes: Optional[int] = None,
    min_mbps: Optional[float] = None,
    max_attempts: Optional[int] = None,
) -> DownloadResult:
    """Download ``url`` to ``dest`` with retries, Range-resume, and gzip validation.

    Writes to ``dest.tmp``; atomically renames on success.
    Resumes via ``Range: bytes=<offset>-`` when the server advertises
    ``Accept-Ranges: bytes`` and a partial ``.tmp`` is present.
    """
    from bioagent.config.settings import settings

    if max_bytes is None:
        max_bytes = settings.max_download_size_mb * 1024 * 1024
    if min_mbps is None:
        min_mbps = getattr(settings, "min_download_mbps", 2.0)
    if max_attempts is None:
        max_attempts = getattr(settings, "download_max_retries", 4)

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")

    state = {"attempts": 0, "resumed": False}

    @retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(
            (
                httpx.TransportError,
                httpx.ReadTimeout,
                httpx.ConnectTimeout,
                httpx.RemoteProtocolError,
                _RetryableHTTPError,
                gzip.BadGzipFile,
                EOFError,
            )
        ),
        reraise=True,
    )
    def _attempt() -> None:
        state["attempts"] += 1
        attempt = state["attempts"]
        label = source_label or url
        logger.info("[_http] attempt=%d url=%s", attempt, label)

        resume_offset = tmp.stat().st_size if tmp.exists() else 0

        with _build_client(verify=settings.tls_verify) as client:
            content_length = 0
            accept_ranges = False
            try:
                head = client.head(url, timeout=20.0)
                if head.status_code < 400:
                    content_length = int(head.headers.get("Content-Length", 0) or 0)
                    accept_ranges = (
                        head.headers.get("Accept-Ranges", "").lower() == "bytes"
                    )
            except httpx.HTTPError:
                pass

            if content_length and content_length > max_bytes:
                raise RuntimeError(
                    f"File size {content_length / 1_048_576:.0f} MB exceeds limit "
                    f"{max_bytes / 1_048_576:.0f} MB"
                )

            expected_mb = (content_length or 10_000_000) / 1_048_576
            read_timeout = _estimate_read_timeout(expected_mb, min_mbps)
            timeout = httpx.Timeout(
                connect=15.0, read=read_timeout, write=read_timeout, pool=15.0
            )

            headers: dict[str, str] = {}
            mode = "wb"
            if (
                accept_ranges
                and resume_offset > 0
                and (not content_length or resume_offset < content_length)
            ):
                headers["Range"] = f"bytes={resume_offset}-"
                mode = "ab"
                state["resumed"] = True
                logger.info("[_http] Resuming from offset %d bytes", resume_offset)
            elif tmp.exists():
                tmp.unlink()
                resume_offset = 0

            with client.stream("GET", url, headers=headers, timeout=timeout) as resp:
                if resp.status_code in (408, 429, 500, 502, 503, 504):
                    raise _RetryableHTTPError(f"HTTP {resp.status_code}")
                if resp.status_code >= 400:
                    raise RuntimeError(
                        f"HTTP {resp.status_code}: {resp.reason_phrase}"
                    )

                # Server ignored our Range request — start fresh.
                if mode == "ab" and resp.status_code != 206:
                    tmp.unlink(missing_ok=True)
                    mode = "wb"
                    state["resumed"] = False
                    resume_offset = 0

                ctype = resp.headers.get("Content-Type", "")
                if "text/html" in ctype and ".html" not in dest.name:
                    raise RuntimeError(
                        f"Server returned HTML (Content-Type: {ctype}); "
                        "likely an error page or auth required"
                    )

                written = resume_offset if mode == "ab" else 0
                with open(tmp, mode) as fh:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        if not chunk:
                            continue
                        written += len(chunk)
                        if written > max_bytes:
                            tmp.unlink(missing_ok=True)
                            raise RuntimeError(
                                f"Exceeded max size "
                                f"{max_bytes / 1_048_576:.0f} MB"
                            )
                        fh.write(chunk)

        if not tmp.exists() or tmp.stat().st_size == 0:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("Downloaded file is empty")

        if validate_gzip and dest.suffix == ".gz":
            try:
                with gzip.open(tmp, "rb") as gz:
                    while gz.read(1 << 20):
                        pass
            except (gzip.BadGzipFile, EOFError, OSError) as exc:
                tmp.unlink(missing_ok=True)
                raise gzip.BadGzipFile(
                    f"Gzip integrity check failed: {exc}"
                ) from exc

        if dest.exists():
            dest.unlink()
        tmp.rename(dest)

    try:
        _attempt()
    except Exception as exc:
        logger.warning(
            "[_http] Failed after %d attempt(s) (resumed=%s): %s",
            state["attempts"],
            state["resumed"],
            exc,
        )
        return DownloadResult(
            status="failed",
            source=source_label,
            attempts=state["attempts"],
            resumed=state["resumed"],
            error=str(exc),
        )

    size = dest.stat().st_size
    logger.info(
        "[_http] Success: %s (%.1f MB, attempts=%d, resumed=%s, source=%s)",
        dest.name,
        size / 1_048_576,
        state["attempts"],
        state["resumed"],
        source_label or "direct",
    )
    return DownloadResult(
        status="success",
        path=dest,
        source=source_label or "direct",
        bytes_written=size,
        attempts=state["attempts"],
        resumed=state["resumed"],
    )


def try_mirrors(
    candidates: list[tuple[str, str]],
    dest: Path,
    **kwargs,
) -> DownloadResult:
    """Walk ``(url, source_label)`` candidates in order; return first success."""
    last: Optional[DownloadResult] = None
    for url, label in candidates:
        result = stream_download(url, dest, source_label=label, **kwargs)
        if result.ok:
            return result
        last = result
        logger.info(
            "[_http] Mirror '%s' failed (%s); trying next",
            label,
            result.error[:120],
        )
    return last or DownloadResult(status="failed", error="no candidates provided")


def get_json(
    url: str,
    *,
    timeout: float = 30.0,
    source_label: str = "",
    max_attempts: Optional[int] = None,
) -> tuple[Optional[dict], str]:
    """Resilient JSON GET. Returns (data, source_label_on_success) or (None, error_msg).

    Used by cBioPortal / GDC / ENCODE API calls that don't hit our streaming path.
    """
    from bioagent.config.settings import settings

    if max_attempts is None:
        max_attempts = getattr(settings, "download_max_retries", 4)

    import json

    state = {"attempts": 0}

    @retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(
            (httpx.TransportError, httpx.ReadTimeout, _RetryableHTTPError)
        ),
        reraise=True,
    )
    def _attempt() -> dict:
        state["attempts"] += 1
        with _build_client(verify=settings.tls_verify) as client:
            resp = client.get(
                url,
                timeout=timeout,
                headers={"Accept": "application/json"},
            )
            if resp.status_code in (408, 429, 500, 502, 503, 504):
                raise _RetryableHTTPError(f"HTTP {resp.status_code}")
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"HTTP {resp.status_code}: {resp.reason_phrase}"
                )
            return json.loads(resp.text)

    try:
        data = _attempt()
        return data, source_label or "api"
    except Exception as exc:
        logger.warning(
            "[_http] JSON GET failed after %d attempt(s): %s",
            state["attempts"],
            exc,
        )
        return None, f"ERROR: {exc}"
