"""TCGA / GDC (Genomic Data Commons) download tools."""

from __future__ import annotations

import json
import logging
import urllib.parse

logger = logging.getLogger(__name__)

_GDC_API = "https://api.gdc.cancer.gov"


def search_gdc_datasets(
    project: str = "",
    data_category: str = "",
    data_type: str = "",
) -> str:
    """Search the GDC for available datasets.

    Parameters
    ----------
    project:
        GDC project ID, e.g. ``"TCGA-SKCM"``, ``"TCGA-BRCA"``.
    data_category:
        Category filter, e.g. ``"Transcriptome Profiling"``, ``"Simple Nucleotide Variation"``.
    data_type:
        Type filter, e.g. ``"Gene Expression Quantification"``, ``"Masked Somatic Mutation"``.

    Returns formatted listing of matching files.
    """
    filters: list[dict] = []

    if project:
        filters.append({
            "op": "in",
            "content": {"field": "cases.project.project_id", "value": [project]},
        })
    if data_category:
        filters.append({
            "op": "in",
            "content": {"field": "data_category", "value": [data_category]},
        })
    if data_type:
        filters.append({
            "op": "in",
            "content": {"field": "data_type", "value": [data_type]},
        })

    payload = {
        "filters": json.dumps({"op": "and", "content": filters}) if filters else "{}",
        "fields": "file_id,file_name,data_category,data_type,file_size,access",
        "size": "20",
        "format": "JSON",
    }

    from bioagent.tools.data._http import get_json

    url = f"{_GDC_API}/files?" + urllib.parse.urlencode(payload)
    result, source = get_json(url, timeout=30.0, source_label="GDC")
    if result is None:
        return f"ERROR: GDC API unreachable — {source}"

    hits = result.get("data", {}).get("hits", [])
    total = result.get("data", {}).get("pagination", {}).get("total", 0)

    if not hits:
        return (
            f"No GDC files found for project={project}, "
            f"data_category={data_category}, data_type={data_type}. "
            "Check that the project ID matches (e.g. 'TCGA-SKCM' not 'SKCM')."
        )

    lines = [f"Found {total} GDC files (showing first {len(hits)}):\n"]
    for hit in hits:
        access = hit.get("access", "?")
        size_mb = hit.get("file_size", 0) / 1_048_576
        lines.append(
            f"- {hit.get('file_id', '?')} | {hit.get('file_name', '?')} "
            f"| {hit.get('data_type', '?')} | {size_mb:.1f} MB | access={access}"
        )
    lines.append(
        "\nNote: 'controlled' access files require dbGaP approval. "
        "Use download_gdc_file(file_id) to download 'open' files."
    )
    return "\n".join(lines)


def download_gdc_file(file_id: str, filename: str = "") -> str:
    """Download a single open-access file from the GDC.

    Parameters
    ----------
    file_id:
        GDC UUID (from search_gdc_datasets results).
    filename:
        Output filename. Auto-detected from GDC metadata if empty.

    Returns a status string.
    """
    from bioagent.config.settings import settings
    from bioagent.tools.execution.sandbox import ensure_workspace

    ensure_workspace()
    data_dir = settings.workspace_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Resolve filename from metadata if not provided
    if not filename:
        filename = _resolve_gdc_filename(file_id) or f"{file_id}.dat"

    # Check if it's a controlled-access file first
    access = _check_gdc_access(file_id)
    if access == "controlled":
        from bioagent.tools.data.manual_instructions import generate_download_instructions
        return generate_download_instructions(
            dataset_description=f"GDC controlled-access file {file_id}",
            accession=file_id,
            source="GDC (Genomic Data Commons)",
            url=f"https://portal.gdc.cancer.gov/files/{file_id}",
        )

    download_url = f"{_GDC_API}/data/{file_id}"
    from bioagent.tools.data.url_download import download_url as dl_url
    result = dl_url(
        url=download_url,
        filename=filename,
        description=f"GDC file {file_id}",
    )

    if result.startswith("SUCCESS"):
        return result

    # Download failed — generate instructions
    from bioagent.tools.data.manual_instructions import generate_download_instructions
    return generate_download_instructions(
        dataset_description=f"GDC file {file_id} ({filename})",
        accession=file_id,
        source="GDC (Genomic Data Commons)",
        url=f"https://api.gdc.cancer.gov/data/{file_id}",
    )


def _resolve_gdc_filename(file_id: str) -> str:
    """Fetch the canonical filename for a GDC file UUID (with retry)."""
    from bioagent.tools.data._http import get_json

    url = f"{_GDC_API}/files/{file_id}?fields=file_name"
    data, _ = get_json(url, timeout=15.0, source_label="GDC")
    if data is None:
        return ""
    return data.get("data", {}).get("file_name", "")


def _check_gdc_access(file_id: str) -> str:
    """Return 'open' or 'controlled' for a GDC file (with retry)."""
    from bioagent.tools.data._http import get_json

    url = f"{_GDC_API}/files/{file_id}?fields=access"
    data, _ = get_json(url, timeout=15.0, source_label="GDC")
    if data is None:
        return "open"
    return data.get("data", {}).get("access", "open")
