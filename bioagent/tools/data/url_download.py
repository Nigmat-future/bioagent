"""Generic URL downloader with gzip/zip extraction and validation."""

from __future__ import annotations

import gzip
import logging
import shutil
import urllib.request
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)


def download_url(url: str, filename: str = "", description: str = "") -> str:
    """Download a file from any HTTP/HTTPS URL into workspace/data/.

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
    from bioagent.config.settings import settings
    from bioagent.tools.execution.sandbox import ensure_workspace

    ensure_workspace()
    data_dir = settings.workspace_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    if not filename:
        filename = url.split("/")[-1].split("?")[0] or "downloaded_file"

    out_path = data_dir / filename
    label = description or url

    logger.info("[url_download] Downloading: %s → %s", label, out_path)

    max_bytes = settings.max_download_size_mb * 1024 * 1024
    timeout = settings.download_timeout

    ssl_ctx = None
    if not settings.tls_verify:
        import ssl
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "BioAgent/1.0 (bioagent@example.com)"},
        )
        opener = urllib.request.build_opener()
        if ssl_ctx:
            import urllib.request as ur
            https_handler = ur.HTTPSHandler(context=ssl_ctx)
            opener = ur.build_opener(https_handler)

        with opener.open(req, timeout=timeout) as response:
            # Check content-type — bail on HTML error pages
            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type and ".html" not in filename:
                return (
                    f"ERROR: Server returned HTML instead of data "
                    f"(Content-Type: {content_type}). URL may require authentication."
                )

            # Stream-download with size guard
            downloaded = 0
            tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
            with open(tmp_path, "wb") as fh:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > max_bytes:
                        tmp_path.unlink(missing_ok=True)
                        return (
                            f"ERROR: File exceeds size limit "
                            f"({settings.max_download_size_mb} MB). "
                            f"Set BIOAGENT_MAX_DOWNLOAD_SIZE_MB to increase."
                        )
                    fh.write(chunk)

            tmp_path.rename(out_path)

    except urllib.error.HTTPError as exc:
        return f"ERROR: HTTP {exc.code} — {exc.reason} for {url}"
    except urllib.error.URLError as exc:
        return f"ERROR: URL error — {exc.reason}"
    except TimeoutError:
        return f"ERROR: Download timed out after {timeout}s"
    except Exception as exc:
        return f"ERROR: {exc}"

    if out_path.stat().st_size == 0:
        out_path.unlink(missing_ok=True)
        return "ERROR: Downloaded file is empty."

    # Auto-extract
    extracted_path = _try_extract(out_path)
    if extracted_path and extracted_path != out_path:
        size_mb = extracted_path.stat().st_size / 1_048_576
        return (
            f"SUCCESS: Downloaded and extracted to {extracted_path} "
            f"({size_mb:.1f} MB)"
        )

    size_mb = out_path.stat().st_size / 1_048_576
    return f"SUCCESS: Downloaded to {out_path} ({size_mb:.1f} MB)"


def _try_extract(path: Path) -> Path:
    """Extract .gz or .zip archives. Returns the extracted path or original."""
    suffix = path.suffix.lower()
    if suffix == ".gz" and path.stem.endswith(".tar"):
        # tar.gz — leave as-is for now (too complex to extract arbitrarily)
        return path
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
