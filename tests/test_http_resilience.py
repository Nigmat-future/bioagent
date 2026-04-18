"""Tests for the resilient HTTP backbone used by all data tools.

Covers: retry-on-transient-error, Range-resume, gzip integrity, stale .tmp
cleanup, and mirror-list ordering. All network calls are mocked.
"""

from __future__ import annotations

import gzip
import io
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────


def _fake_response(
    status_code: int = 200,
    content: bytes = b"",
    headers: dict | None = None,
):
    """Build a MagicMock that quacks like an httpx.Response for stream/head."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.reason_phrase = "OK" if status_code < 400 else "Error"
    resp.headers = headers or {}
    resp.text = content.decode("utf-8", errors="replace") if content else ""

    def _iter(chunk_size=65536):
        yield content

    resp.iter_bytes = _iter
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _make_client(
    head_resp,
    get_sequence: list,
):
    """Build a fake httpx.Client whose head() returns head_resp and whose
    stream() walks get_sequence in order (one entry per attempt)."""
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.head.return_value = head_resp

    calls = {"i": 0}

    def _stream(method, url, headers=None, timeout=None):
        idx = calls["i"]
        calls["i"] = min(idx + 1, len(get_sequence) - 1)
        item = get_sequence[idx]
        if isinstance(item, Exception):
            raise item
        return item

    client.stream = _stream
    client._calls = calls
    return client


# ── Retry on transient 5xx ────────────────────────────────────────────────────


class TestRetry:
    def test_503_then_200(self, tmp_path, monkeypatch):
        """503 twice → 200 → success on attempt 3, no resume."""
        from bioagent.tools.data import _http

        # Shrink wait to keep tests fast.
        monkeypatch.setattr(
            "bioagent.tools.data._http.wait_exponential",
            lambda *a, **k: lambda *_: 0,
        )

        head = _fake_response(
            200, headers={"Content-Length": "100", "Accept-Ranges": "bytes"}
        )
        get_sequence = [
            _fake_response(503, b""),
            _fake_response(503, b""),
            _fake_response(200, b"A" * 100, headers={"Content-Length": "100"}),
        ]
        fake_client = _make_client(head, get_sequence)

        with patch.object(_http, "_build_client", return_value=fake_client):
            dest = tmp_path / "file.bin"
            result = _http.stream_download(
                "https://example.com/file.bin",
                dest,
                source_label="test",
                validate_gzip=False,
            )

        assert result.ok, f"expected success, got {result.error}"
        assert result.attempts == 3
        assert result.resumed is False
        assert dest.exists()
        assert dest.stat().st_size == 100

    def test_404_fails_fast_no_retry(self, tmp_path):
        """4xx (non-429) fails immediately without retry."""
        from bioagent.tools.data import _http

        head = _fake_response(404)
        get_sequence = [_fake_response(404)]
        fake_client = _make_client(head, get_sequence)

        with patch.object(_http, "_build_client", return_value=fake_client):
            dest = tmp_path / "nope.bin"
            result = _http.stream_download(
                "https://example.com/nope.bin",
                dest,
                validate_gzip=False,
            )

        assert not result.ok
        assert result.attempts == 1
        assert "404" in result.error


# ── Resume via Range header ───────────────────────────────────────────────────


class TestResume:
    def test_resume_from_partial_tmp(self, tmp_path, monkeypatch):
        """Existing .tmp + Accept-Ranges → Range request + 206 + ab-mode append."""
        from bioagent.tools.data import _http

        monkeypatch.setattr(
            "bioagent.tools.data._http.wait_exponential",
            lambda *a, **k: lambda *_: 0,
        )

        dest = tmp_path / "big.bin"
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_bytes(b"X" * 40)  # "already downloaded" prefix

        full_size = 100
        head = _fake_response(
            200,
            headers={
                "Content-Length": str(full_size),
                "Accept-Ranges": "bytes",
            },
        )
        remaining = b"Y" * 60  # bytes 40-99
        get_sequence = [
            _fake_response(
                206,
                remaining,
                headers={"Content-Range": f"bytes 40-99/{full_size}"},
            ),
        ]
        fake_client = _make_client(head, get_sequence)

        captured_headers: dict = {}

        def _stream(method, url, headers=None, timeout=None):
            captured_headers.update(headers or {})
            return get_sequence[0]

        fake_client.stream = _stream

        with patch.object(_http, "_build_client", return_value=fake_client):
            result = _http.stream_download(
                "https://example.com/big.bin",
                dest,
                validate_gzip=False,
            )

        assert result.ok, result.error
        assert result.resumed is True
        assert captured_headers.get("Range") == "bytes=40-"
        assert dest.stat().st_size == full_size
        assert dest.read_bytes() == b"X" * 40 + b"Y" * 60


# ── Gzip integrity ────────────────────────────────────────────────────────────


class TestGzipIntegrity:
    def test_valid_gzip_passes(self, tmp_path):
        """A valid .gz stream completes cleanly."""
        from bioagent.tools.data import _http

        payload = b"hello world" * 100
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
            gz.write(payload)
        gz_bytes = buf.getvalue()

        head = _fake_response(
            200, headers={"Content-Length": str(len(gz_bytes))}
        )
        get_sequence = [_fake_response(200, gz_bytes)]
        fake_client = _make_client(head, get_sequence)

        with patch.object(_http, "_build_client", return_value=fake_client):
            dest = tmp_path / "data.gz"
            result = _http.stream_download(
                "https://example.com/data.gz",
                dest,
                validate_gzip=True,
            )

        assert result.ok
        with gzip.open(dest, "rb") as gz:
            assert gz.read() == payload

    def test_truncated_gzip_triggers_retry_and_fails(
        self, tmp_path, monkeypatch
    ):
        """Truncated .gz fails integrity check on every attempt → failure."""
        from bioagent.tools.data import _http

        monkeypatch.setattr(
            "bioagent.tools.data._http.wait_exponential",
            lambda *a, **k: lambda *_: 0,
        )

        # Truncate a real gzip stream to break its trailer.
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
            gz.write(b"payload" * 500)
        bad = buf.getvalue()[:-8]  # lop off CRC + size

        head = _fake_response(
            200, headers={"Content-Length": str(len(bad))}
        )
        # Return the same truncated bytes on every retry attempt.
        get_sequence = [_fake_response(200, bad) for _ in range(10)]
        fake_client = _make_client(head, get_sequence)

        with patch.object(_http, "_build_client", return_value=fake_client):
            dest = tmp_path / "bad.gz"
            result = _http.stream_download(
                "https://example.com/bad.gz",
                dest,
                validate_gzip=True,
                max_attempts=3,
            )

        assert not result.ok
        assert result.attempts == 3
        assert not dest.exists()


# ── Stale .tmp cleanup ────────────────────────────────────────────────────────


class TestStaleTmpCleanup:
    def test_stale_tmp_is_deleted(self, tmp_path):
        from bioagent.tools.data._http import cleanup_stale_tmp

        old_tmp = tmp_path / "old.gz.tmp"
        old_tmp.write_bytes(b"stale bytes")
        old_time = time.time() - 48 * 3600
        import os

        os.utime(old_tmp, (old_time, old_time))

        fresh_tmp = tmp_path / "fresh.gz.tmp"
        fresh_tmp.write_bytes(b"fresh bytes")

        deleted = cleanup_stale_tmp(tmp_path, stale_hours=24)

        assert deleted == 1
        assert not old_tmp.exists()
        assert fresh_tmp.exists()

    def test_missing_dir_noop(self, tmp_path):
        from bioagent.tools.data._http import cleanup_stale_tmp

        assert cleanup_stale_tmp(tmp_path / "nonexistent") == 0


# ── Mirror resolution ─────────────────────────────────────────────────────────


class TestMirrors:
    def test_geo_series_matrix_returns_ebi_first(self):
        from bioagent.tools.data.mirrors import resolve_geo_series_matrix

        candidates = resolve_geo_series_matrix("GSE65904")
        assert len(candidates) == 2
        assert candidates[0][1] == "EBI-ArrayExpress"
        assert candidates[1][1] == "NCBI-GEO-FTP"
        assert "GSE65904_series_matrix.txt.gz" in candidates[0][0]
        assert "ftp.ncbi.nlm.nih.gov" in candidates[1][0]

    def test_sra_fastq_ena_url_format(self):
        from bioagent.tools.data.mirrors import resolve_sra_fastq

        cands = resolve_sra_fastq("SRR8281117")
        assert len(cands) == 1
        assert cands[0][1] == "ENA-SRA"
        assert cands[0][0].endswith("/SRR8281117.fastq.gz")
        assert "ftp.sra.ebi.ac.uk" in cands[0][0]

    def test_sra_fastq_paired_returns_r1_r2(self):
        from bioagent.tools.data.mirrors import resolve_sra_fastq

        cands = resolve_sra_fastq("SRR8281117", paired=True)
        assert len(cands) == 2
        assert cands[0][0].endswith("_1.fastq.gz")
        assert cands[1][0].endswith("_2.fastq.gz")

    def test_10x_pbmc3k_cdn(self):
        from bioagent.tools.data.mirrors import resolve_10x_pbmc3k

        cands = resolve_10x_pbmc3k("filtered")
        assert len(cands) == 1
        assert cands[0][1] == "10x-CDN"
        assert "cf.10xgenomics.com" in cands[0][0]
        assert "filtered" in cands[0][0]

    def test_invalid_accession_returns_empty(self):
        from bioagent.tools.data.mirrors import (
            resolve_geo_series_matrix,
            resolve_sra_fastq,
        )

        assert resolve_geo_series_matrix("bogus") == []
        assert resolve_sra_fastq("XYZ123") == []


# ── try_mirrors walker ────────────────────────────────────────────────────────


class TestTryMirrors:
    def test_falls_through_on_failure(self, tmp_path):
        from bioagent.tools.data import _http

        calls: list[str] = []

        def fake_stream_download(url, dest, *, source_label="", **kwargs):
            calls.append(source_label)
            if source_label == "good":
                dest.write_bytes(b"x" * 10)
                return _http.DownloadResult(
                    status="success",
                    path=dest,
                    source=source_label,
                    bytes_written=10,
                    attempts=1,
                )
            return _http.DownloadResult(
                status="failed",
                source=source_label,
                attempts=1,
                error="404 not found",
            )

        with patch.object(_http, "stream_download", side_effect=fake_stream_download):
            result = _http.try_mirrors(
                [
                    ("https://bad1/", "bad1"),
                    ("https://bad2/", "bad2"),
                    ("https://good/", "good"),
                ],
                tmp_path / "out.bin",
            )

        assert result.ok
        assert result.source == "good"
        assert calls == ["bad1", "bad2", "good"]

    def test_returns_last_failure_when_all_fail(self, tmp_path):
        from bioagent.tools.data import _http

        with patch.object(
            _http,
            "stream_download",
            return_value=_http.DownloadResult(
                status="failed", error="boom", attempts=4
            ),
        ):
            result = _http.try_mirrors(
                [("u1", "a"), ("u2", "b")], tmp_path / "x"
            )

        assert not result.ok
        assert "boom" in result.error
