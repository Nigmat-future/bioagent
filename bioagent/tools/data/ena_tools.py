"""ENA (European Nucleotide Archive) and 10x Genomics CDN download tools.

These bypass NCBI's slow Asia-Pacific paths. ENA mirrors SRA and
ArrayExpress mirrors GEO, and both are typically faster from China.
10x Genomics hosts the canonical PBMC 3k scRNA-seq benchmark on their
Cloudflare CDN — ideal for reproducible benchmarks.
"""

from __future__ import annotations

import logging
import re
import tarfile

logger = logging.getLogger(__name__)


def download_sra_fastq(accession: str, paired: bool = False) -> str:
    """Download a FASTQ file from ENA by SRA accession.

    Parameters
    ----------
    accession:
        SRR / ERR / DRR run accession, e.g. ``"SRR8281117"``.
    paired:
        If ``True``, fetch both ``_1.fastq.gz`` and ``_2.fastq.gz`` (paired-end).

    Returns a status string.
    """
    from bioagent.config.settings import settings
    from bioagent.tools.data._http import stream_download
    from bioagent.tools.data.mirrors import resolve_sra_fastq
    from bioagent.tools.execution.sandbox import ensure_workspace

    ensure_workspace()
    acc = accession.strip().upper()
    if not re.match(r"^(SRR|ERR|DRR)\d+$", acc):
        return f"ERROR: Invalid SRA accession: {accession}"

    data_dir = settings.workspace_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    candidates = resolve_sra_fastq(acc, paired=paired)
    if not candidates:
        return f"ERROR: Could not resolve ENA URL for {acc}"

    results: list[str] = []
    for url, label in candidates:
        fname = url.rsplit("/", 1)[-1]
        dest = data_dir / fname
        result = stream_download(url, dest, source_label=label)
        if result.ok:
            mb = result.bytes_written / 1_048_576
            results.append(
                f"{fname} ({mb:.1f} MB, source={result.source}, "
                f"attempts={result.attempts})"
            )
        else:
            return (
                f"ERROR: ENA download failed for {acc} via {label} "
                f"after {result.attempts} attempt(s): {result.error}"
            )

    return "SUCCESS: Downloaded " + "; ".join(results)


def download_geo_from_ena(accession: str) -> str:
    """Download a GEO series matrix via the EBI ArrayExpress mirror.

    Falls back to NCBI FTP if EBI doesn't mirror the series. Parses the
    series matrix into an expression CSV on success.

    Parameters
    ----------
    accession:
        GEO series accession, e.g. ``"GSE65904"``.

    Returns a status string.
    """
    from bioagent.config.settings import settings
    from bioagent.tools.data._http import try_mirrors
    from bioagent.tools.data.mirrors import resolve_geo_series_matrix
    from bioagent.tools.execution.sandbox import ensure_workspace

    ensure_workspace()
    acc = accession.strip().upper()
    if not re.match(r"^GSE\d+$", acc):
        return f"ERROR: Invalid GEO series accession: {accession}"

    data_dir = settings.workspace_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    dest = data_dir / f"{acc}_series_matrix.txt.gz"
    candidates = resolve_geo_series_matrix(acc)
    result = try_mirrors(candidates, dest, validate_gzip=True)

    if not result.ok:
        return (
            f"ERROR: GEO series matrix download failed for {acc}: {result.error}"
        )

    # Decompress + parse to CSV (same behaviour as the legacy FTP fallback).
    import gzip
    import shutil

    txt_path = data_dir / f"{acc}_series_matrix.txt"
    try:
        with gzip.open(dest, "rb") as f_in, open(txt_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        dest.unlink()
    except Exception as exc:
        return (
            f"SUCCESS (downloaded): {dest} via {result.source} "
            f"(gunzip failed: {exc})"
        )

    from bioagent.tools.data.geo_tools import _parse_series_matrix

    csv_path = _parse_series_matrix(txt_path, acc, data_dir)
    if csv_path:
        mb = csv_path.stat().st_size / 1_048_576
        return (
            f"SUCCESS: Downloaded {acc} via {result.source} "
            f"(attempts={result.attempts}, resumed={result.resumed}). "
            f"Expression CSV: {csv_path} ({mb:.1f} MB)"
        )
    return (
        f"SUCCESS: Downloaded {acc} via {result.source} "
        f"(attempts={result.attempts}). Series matrix: {txt_path}"
    )


def download_10x_pbmc3k(variant: str = "filtered") -> str:
    """Download the canonical 10x Genomics PBMC 3k scRNA-seq dataset.

    Parameters
    ----------
    variant:
        ``"filtered"`` (cell-called, ~2700 cells, recommended) or ``"raw"``
        (pre-cell-calling, ~737k barcodes).

    Returns a status string. Auto-extracts the ``.tar.gz`` into
    ``workspace/data/pbmc3k/`` containing ``matrix.mtx``, ``barcodes.tsv``,
    and ``genes.tsv`` ready for Scanpy's ``sc.read_10x_mtx``.
    """
    from bioagent.config.settings import settings
    from bioagent.tools.data._http import stream_download
    from bioagent.tools.data.mirrors import resolve_10x_pbmc3k
    from bioagent.tools.execution.sandbox import ensure_workspace

    ensure_workspace()
    variant = variant.lower().strip()
    if variant not in ("filtered", "raw"):
        variant = "filtered"

    data_dir = settings.workspace_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    candidates = resolve_10x_pbmc3k(variant)
    url, label = candidates[0]
    tar_path = data_dir / f"pbmc3k_{variant}.tar.gz"

    result = stream_download(
        url, tar_path, source_label=label, validate_gzip=False
    )
    if not result.ok:
        return (
            f"ERROR: 10x PBMC 3k download failed after "
            f"{result.attempts} attempt(s): {result.error}"
        )

    extract_dir = data_dir / "pbmc3k"
    try:
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(extract_dir)
    except Exception as exc:
        return (
            f"SUCCESS (downloaded, extract failed): {tar_path} "
            f"via {result.source}. Extract error: {exc}"
        )

    mtx_files = list(extract_dir.rglob("matrix.mtx*"))
    mb = tar_path.stat().st_size / 1_048_576

    return (
        f"SUCCESS: Downloaded and extracted PBMC 3k ({variant}) via "
        f"{result.source} (attempts={result.attempts}). "
        f"Archive: {tar_path} ({mb:.1f} MB). "
        f"Extracted {len(mtx_files)} matrix file(s) to {extract_dir}. "
        f"Load with: scanpy.read_10x_mtx('{extract_dir}', var_names='gene_symbols')"
    )
