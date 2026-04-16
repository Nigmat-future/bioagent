"""ENCODE project data download tools."""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)

_ENCODE_API = "https://www.encodeproject.org"


def search_encode_datasets(
    assay: str = "",
    biosample: str = "",
    target: str = "",
) -> str:
    """Search ENCODE for experiments/datasets.

    Parameters
    ----------
    assay:
        Assay type, e.g. ``"ChIP-seq"``, ``"ATAC-seq"``, ``"RNA-seq"``.
    biosample:
        Biosample term, e.g. ``"melanoma cell line"``, ``"A375"``.
    target:
        Target protein/gene, e.g. ``"BRAF"``, ``"H3K27ac"``.

    Returns formatted experiment listing with ENCODE accessions.
    """
    params: dict[str, str] = {
        "type": "Experiment",
        "status": "released",
        "format": "json",
        "limit": "20",
    }
    if assay:
        params["assay_title"] = assay
    if biosample:
        params["biosample_ontology.term_name"] = biosample
    if target:
        params["target.label"] = target

    url = f"{_ENCODE_API}/search/?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "BioAgent/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())

        experiments = data.get("@graph", [])
        total = data.get("total", 0)

        if not experiments:
            return (
                f"No ENCODE experiments found for assay={assay}, "
                f"biosample={biosample}, target={target}"
            )

        lines = [f"Found {total} ENCODE experiments (showing {len(experiments)}):\n"]
        for exp in experiments:
            acc = exp.get("accession", "?")
            assay_t = exp.get("assay_title", "?")
            bio = exp.get("biosample_ontology", {})
            bio_name = bio.get("term_name", "?") if isinstance(bio, dict) else "?"
            files = exp.get("files", [])
            lines.append(
                f"- {acc} | {assay_t} | {bio_name} | {len(files)} files"
            )

        lines.append(
            "\nTo download a file: download_encode_file(file_accession)"
            "\nFile accessions start with 'ENCF...'"
            "\nExperiment details: https://www.encodeproject.org/experiments/<ENCSR...>/"
        )
        return "\n".join(lines)

    except urllib.error.URLError as exc:
        return f"ERROR: ENCODE API unreachable — {exc.reason}"
    except Exception as exc:
        return f"ERROR: {exc}"


def download_encode_file(file_accession: str) -> str:
    """Download a specific ENCODE file by its accession.

    Parameters
    ----------
    file_accession:
        ENCODE file accession, e.g. ``"ENCFF123ABC"``.

    Returns a status string.
    """
    from bioagent.config.settings import settings
    from bioagent.tools.execution.sandbox import ensure_workspace

    ensure_workspace()
    data_dir = settings.workspace_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Get file metadata
    meta = _get_encode_file_metadata(file_accession)
    if not meta:
        from bioagent.tools.data.manual_instructions import generate_download_instructions
        return generate_download_instructions(
            dataset_description=f"ENCODE file {file_accession}",
            accession=file_accession,
            source="ENCODE",
            url=f"https://www.encodeproject.org/files/{file_accession}/",
        )

    href = meta.get("href", "")
    file_format = meta.get("file_format", "")
    output_type = meta.get("output_type", "")

    if not href:
        from bioagent.tools.data.manual_instructions import generate_download_instructions
        return generate_download_instructions(
            dataset_description=f"ENCODE file {file_accession} ({output_type})",
            accession=file_accession,
            source="ENCODE",
            url=f"https://www.encodeproject.org/files/{file_accession}/",
        )

    download_url = _ENCODE_API + href
    filename_parts = [file_accession]
    if file_format:
        filename_parts.append(file_format)
    filename = ".".join(filename_parts)

    from bioagent.tools.data.url_download import download_url as dl_url
    result = dl_url(
        url=download_url,
        filename=filename,
        description=f"ENCODE {output_type} file {file_accession}",
    )

    if result.startswith("SUCCESS"):
        return result

    from bioagent.tools.data.manual_instructions import generate_download_instructions
    return generate_download_instructions(
        dataset_description=f"ENCODE file {file_accession} ({output_type})",
        accession=file_accession,
        source="ENCODE",
        url=download_url,
    )


def _get_encode_file_metadata(file_accession: str) -> dict:
    """Fetch metadata for an ENCODE file."""
    try:
        url = f"{_ENCODE_API}/files/{file_accession}/?format=json"
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "BioAgent/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        logger.warning("[encode_tools] Failed to get metadata for %s: %s", file_accession, exc)
        return {}
