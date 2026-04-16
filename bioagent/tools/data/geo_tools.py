"""GEO (Gene Expression Omnibus) download tools."""

from __future__ import annotations

import logging
import re

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

    # ── Attempt 1: GEOparse ────────────────────────────────────────────────────
    result = _download_via_geoparse(acc, data_dir)
    if result.startswith("SUCCESS"):
        return result

    logger.warning("[geo_tools] GEOparse failed (%s), trying FTP fallback", result)

    # ── Attempt 2: Direct FTP ─────────────────────────────────────────────────
    result2 = _download_via_ftp(acc, data_dir)
    if result2.startswith("SUCCESS"):
        return result2

    logger.warning("[geo_tools] FTP fallback failed (%s), generating instructions", result2)

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

        from bioagent.config.settings import settings
        gse = GEOparse.get_GEO(
            geo=acc,
            destdir=str(data_dir),
            silent=True,
        )

        # Export expression matrix if available
        output_files = list(data_dir.glob(f"{acc}*"))
        if not output_files:
            return f"ERROR: GEOparse completed but no files written"

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
        import pandas as pd
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


def _download_via_ftp(acc: str, data_dir) -> str:
    """Direct FTP/HTTPS download of series matrix file."""
    import urllib.request
    from bioagent.config.settings import settings
    from pathlib import Path

    # Build NCBI FTP URL
    prefix = acc[:-3] + "nnn" if len(acc) > 3 else acc
    matrix_url = (
        f"https://ftp.ncbi.nlm.nih.gov/geo/series/{prefix}/{acc}/matrix/"
        f"{acc}_series_matrix.txt.gz"
    )
    out_gz = data_dir / f"{acc}_series_matrix.txt.gz"

    from bioagent.tools.data.url_download import download_url
    result = download_url(
        url=matrix_url,
        filename=out_gz.name,
        description=f"GEO series matrix for {acc}",
    )

    if not result.startswith("SUCCESS"):
        return result

    # The url_download tool auto-decompresses .gz → try to parse it
    matrix_txt = data_dir / f"{acc}_series_matrix.txt"
    if matrix_txt.exists():
        csv_path = _parse_series_matrix(matrix_txt, acc, data_dir)
        if csv_path:
            size_mb = csv_path.stat().st_size / 1_048_576
            return (
                f"SUCCESS: Downloaded {acc} via FTP. "
                f"Expression CSV: {csv_path} ({size_mb:.1f} MB)"
            )

    return result


def _parse_series_matrix(txt_path, acc: str, data_dir) -> "Path | None":
    """Parse a GEO series matrix text file into a tidy CSV."""
    try:
        import pandas as pd
        from pathlib import Path

        lines = txt_path.read_text(encoding="utf-8", errors="replace").splitlines()
        data_start = next(
            (i for i, l in enumerate(lines) if not l.startswith("!")),
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
