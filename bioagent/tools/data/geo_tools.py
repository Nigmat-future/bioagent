"""GEO (Gene Expression Omnibus) download tools."""

from __future__ import annotations

import logging
import re
from pathlib import Path  # noqa: F401  (used in string type annotations)

logger = logging.getLogger(__name__)


def download_geo_dataset(accession: str, output_dir: str = "data") -> str:
    """Download a GEO dataset (series or platform) into workspace/data/.

    Tries:
      1. GEOparse Python library (auto-installed at runtime)
      2. Direct FTP download of _series_matrix.txt.gz
      3. Generates manual download instructions on total failure

    Parameters
    ----------
    accession:
        GEO accession number, e.g. ``GSE12345`` or ``GPL570``.
    output_dir:
        Subdirectory within workspace to save files (default: ``data``).

    Returns a status string describing what was downloaded.
    """
    from bioagent.config.settings import settings
    from bioagent.tools.execution.sandbox import ensure_workspace

    ensure_workspace()
    acc = accession.strip().upper()
    if not re.match(r"^(GSE|GDS|GPL|GSM)\d+$", acc):
        return f"ERROR: Invalid GEO accession format: {accession}"

    data_dir = settings.workspace_path / output_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    # ── Attempt 1: EBI ArrayExpress mirror → NCBI FTP (resilient) ──────────────
    # Mirror-first because EBI is typically faster from Asia and the
    # resilient backbone handles retries/resume/gzip-integrity that the
    # old single-shot FTP path lacked.
    result = _download_via_mirrors(acc, data_dir)
    if result.startswith("SUCCESS"):
        return result

    logger.warning("[geo_tools] Mirrors failed (%s), trying GEOparse", result)

    # ── Attempt 2: GEOparse (for platform/sample-level metadata) ───────────────
    result2 = _download_via_geoparse(acc, data_dir)
    if result2.startswith("SUCCESS"):
        return result2

    logger.warning("[geo_tools] GEOparse failed (%s), generating instructions", result2)

    # ── Attempt 3: Manual instructions ────────────────────────────────────────
    from bioagent.tools.data.manual_instructions import generate_download_instructions
    return generate_download_instructions(
        dataset_description=f"GEO dataset {acc}",
        accession=acc,
        source="GEO (Gene Expression Omnibus)",
        url=f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={acc}",
    )


def _download_via_geoparse(acc: str, data_dir) -> str:
    """Try to download using the GEOparse library."""
    try:
        try:
            import GEOparse  # type: ignore
        except ImportError:
            import subprocess
            subprocess.run(
                ["pip", "install", "GEOparse", "--quiet"],
                capture_output=True, timeout=120,
            )
            import GEOparse  # type: ignore

        gse = GEOparse.get_GEO(
            geo=acc,
            destdir=str(data_dir),
            silent=True,
        )

        # Export expression matrix if available
        output_files = list(data_dir.glob(f"{acc}*"))
        if not output_files:
            return "ERROR: GEOparse completed but no files written"

        # Try to extract a clean expression matrix CSV
        csv_path = _extract_expression_matrix(gse, acc, data_dir)
        if csv_path:
            size_mb = csv_path.stat().st_size / 1_048_576
            return (
                f"SUCCESS: Downloaded {acc} via GEOparse. "
                f"Expression matrix: {csv_path} ({size_mb:.1f} MB). "
                f"All files in {data_dir}."
            )

        file_names = ", ".join(str(f.name) for f in output_files[:5])
        return f"SUCCESS: Downloaded {acc} via GEOparse. Files: {file_names}"

    except Exception as exc:
        return f"ERROR (GEOparse): {exc}"


def _extract_expression_matrix(gse, acc: str, data_dir) -> "Path | None":
    """Attempt to extract expression matrix as CSV from a GEOparse GSE object."""
    try:
        from pathlib import Path

        # Collect all GPL tables
        frames = []
        for gpl_name, gpl in gse.gpls.items():
            if hasattr(gpl, 'table') and not gpl.table.empty:
                frames.append(gpl.table)

        # Collect all GSM tables
        gsm_frames = {}
        for gsm_name, gsm in gse.gsms.items():
            if hasattr(gsm, 'table') and not gsm.table.empty:
                df = gsm.table.copy()
                if 'VALUE' in df.columns:
                    df = df[['ID_REF', 'VALUE']].rename(columns={'VALUE': gsm_name})
                    gsm_frames[gsm_name] = df

        if gsm_frames:
            # Merge all samples
            merged = None
            for name, df in gsm_frames.items():
                if merged is None:
                    merged = df
                else:
                    merged = merged.merge(df, on='ID_REF', how='outer')

            if merged is not None and not merged.empty:
                csv_path = Path(data_dir) / f"{acc}_expression_matrix.csv"
                merged.to_csv(csv_path, index=False)
                return csv_path

    except Exception as exc:
        logger.debug("[geo_tools] Expression matrix extraction failed: %s", exc)
    return None


def _download_via_mirrors(acc: str, data_dir) -> str:
    """Mirror-first series matrix download (EBI → NCBI), with retry/resume.

    Uses the resilient ``_http.try_mirrors`` backbone: EBI ArrayExpress
    first (faster from Asia, 404-fails fast when series isn't mirrored),
    then NCBI GEO FTP as fallback. Both go through tenacity retry and
    Range-resume; gzip integrity is validated before rename.
    """
    from bioagent.tools.data._http import try_mirrors
    from bioagent.tools.data.mirrors import resolve_geo_series_matrix

    candidates = resolve_geo_series_matrix(acc)
    if not candidates:
        return f"ERROR: No mirror candidates for {acc}"

    out_gz = data_dir / f"{acc}_series_matrix.txt.gz"
    result = try_mirrors(candidates, out_gz, validate_gzip=True)

    if not result.ok:
        return (
            f"ERROR: All mirrors failed for {acc} "
            f"(last attempts={result.attempts}): {result.error}"
        )

    # Decompress the .gz we just saved
    import gzip
    import shutil

    matrix_txt = data_dir / f"{acc}_series_matrix.txt"
    try:
        with gzip.open(out_gz, "rb") as f_in, open(matrix_txt, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        out_gz.unlink()
    except Exception as exc:
        return (
            f"SUCCESS (downloaded): {out_gz} via {result.source} "
            f"(gunzip failed: {exc})"
        )

    csv_path = _parse_series_matrix(matrix_txt, acc, data_dir)
    if csv_path:
        size_mb = csv_path.stat().st_size / 1_048_576
        return (
            f"SUCCESS: Downloaded {acc} via {result.source} "
            f"(attempts={result.attempts}, resumed={result.resumed}). "
            f"Expression CSV: {csv_path} ({size_mb:.1f} MB)"
        )

    return (
        f"SUCCESS: Downloaded {acc} via {result.source} "
        f"(attempts={result.attempts}). Series matrix: {matrix_txt}"
    )


def _parse_series_matrix(txt_path, acc: str, data_dir) -> "Path | None":
    """Parse a GEO series matrix text file into a tidy CSV."""
    try:
        from pathlib import Path

        import pandas as pd

        lines = txt_path.read_text(encoding="utf-8", errors="replace").splitlines()
        data_start = next(
            (i for i, line in enumerate(lines) if not line.startswith("!")),
            None,
        )
        if data_start is None:
            return None

        import io
        data_text = "\n".join(lines[data_start:])
        df = pd.read_csv(io.StringIO(data_text), sep="\t", index_col=0)
        csv_path = Path(data_dir) / f"{acc}_expression_matrix.csv"
        df.to_csv(csv_path)
        return csv_path

    except Exception as exc:
        logger.debug("[geo_tools] Series matrix parse failed: %s", exc)
        return None
