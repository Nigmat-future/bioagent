"""cBioPortal data download tools — uses BioMCP CLI and direct API."""

from __future__ import annotations

import json
import logging
import urllib.parse

logger = logging.getLogger(__name__)

_API_BASE = "https://www.cbioportal.org/api"


def search_cbioportal_studies(query: str) -> str:
    """Search cBioPortal for studies matching the query.

    Tries BioMCP first (richer output), falls back to REST API.

    Parameters
    ----------
    query:
        Free-text search term, e.g. ``"melanoma BRAF"`` or ``"TCGA-SKCM"``.

    Returns formatted study listing with study IDs.
    """
    # Try BioMCP first
    result = _biomcp_study_list(query)
    if result and "error" not in result.lower()[:50]:
        return result

    # Fallback: REST API search
    return _api_search_studies(query)


def download_cbioportal_study(
    study_id: str,
    data_types: str = "mutations,clinical",
) -> str:
    """Download data files from a cBioPortal study into workspace/data/.

    Tries BioMCP study download, then direct API, then generates instructions.

    Parameters
    ----------
    study_id:
        cBioPortal study ID, e.g. ``"skcm_tcga"`` or ``"brca_tcga_pub"``.
    data_types:
        Comma-separated data types: ``mutations``, ``clinical``, ``cna``,
        ``expression``, ``methylation``.

    Returns a status string describing what was downloaded.
    """
    from bioagent.config.settings import settings
    from bioagent.tools.execution.sandbox import ensure_workspace

    ensure_workspace()
    data_dir = settings.workspace_path / "data" / study_id
    data_dir.mkdir(parents=True, exist_ok=True)

    requested = [t.strip() for t in data_types.split(",")]
    downloaded = []
    failed = []

    for dtype in requested:
        result = _download_data_type(study_id, dtype, data_dir)
        if result.startswith("SUCCESS"):
            downloaded.append(dtype)
            logger.info("[cbioportal] Downloaded %s/%s", study_id, dtype)
        else:
            failed.append(f"{dtype}: {result}")
            logger.warning("[cbioportal] Failed %s/%s — %s", study_id, dtype, result)

    if downloaded:
        status = (
            f"SUCCESS: Downloaded {', '.join(downloaded)} data for {study_id} "
            f"to {data_dir}."
        )
        if failed:
            status += f" Failed: {'; '.join(failed)}"
        return status

    # All downloads failed — generate manual instructions
    logger.warning("[cbioportal] All downloads failed for %s, generating instructions", study_id)
    from bioagent.tools.data.manual_instructions import generate_download_instructions
    return generate_download_instructions(
        dataset_description=f"cBioPortal study {study_id} ({data_types})",
        accession=study_id,
        source="cBioPortal",
        url=f"https://www.cbioportal.org/study/summary?id={study_id}",
    )


# ── Internal helpers ───────────────────────────────────────────────────────────


def _biomcp_study_list(query: str) -> str:
    """Run biomcp study list via subprocess."""
    from bioagent.tools.literature.biomcp_tools import _run_biomcp
    return _run_biomcp("study", "list", "--query", query, timeout=45)


def _api_search_studies(query: str) -> str:
    """Search cBioPortal REST API for studies (with retry)."""
    from bioagent.tools.data._http import get_json

    url = f"{_API_BASE}/studies?keyword={urllib.parse.quote(query)}&pageSize=20"
    studies, source = get_json(url, timeout=30.0, source_label="cBioPortal")
    if studies is None:
        return f"ERROR (cBioPortal API search): {source}"
    if not isinstance(studies, list) or not studies:
        return f"No studies found for query: {query}"

    lines = [f"Found {len(studies)} cBioPortal studies:\n"]
    for s in studies[:10]:
        lines.append(
            f"- {s.get('studyId', '?')} | {s.get('name', 'Unknown')} "
            f"({s.get('allSampleCount', '?')} samples)"
        )
    return "\n".join(lines)


def _download_data_type(study_id: str, dtype: str, data_dir) -> str:
    """Download one data type for a study."""
    endpoints = {
        "mutations": f"/molecular-profiles/{study_id}_mutations/mutations?pageSize=50000",
        "clinical": f"/studies/{study_id}/clinical-data?clinicalDataType=PATIENT&pageSize=50000",
        "cna": f"/molecular-profiles/{study_id}_gistic/discrete-copy-number?pageSize=50000",
        "expression": f"/molecular-profiles/{study_id}_rna_seq_v2_mrna/molecular-data?pageSize=50000",
        "methylation": f"/molecular-profiles/{study_id}_methylation_hm450/molecular-data?pageSize=50000",
    }

    endpoint = endpoints.get(dtype)
    if not endpoint:
        return f"ERROR: Unknown data type '{dtype}'. Valid: {', '.join(endpoints)}"

    url = _API_BASE + endpoint
    out_file = data_dir / f"{dtype}.json"

    from bioagent.tools.data._http import get_json

    data, source = get_json(url, timeout=60.0, source_label="cBioPortal")
    if data is None:
        if "404" in source:
            return (
                f"ERROR: Profile '{study_id}_{dtype}' not found (404). "
                "Study may use a different profile ID."
            )
        return f"ERROR: {source}"
    if not data:
        return f"ERROR: Empty response from {url}"

    try:
        out_file.write_text(json.dumps(data), encoding="utf-8")
        _json_to_csv(out_file, dtype)
        size_kb = out_file.stat().st_size / 1024
        return f"SUCCESS: {out_file.name} ({size_kb:.0f} KB, source={source})"
    except Exception as exc:
        return f"ERROR: write failed: {exc}"


def _json_to_csv(json_path, dtype: str) -> None:
    """Convert JSON API response to a flat CSV for easy loading."""
    try:
        import csv
        import json as _json

        data = _json.loads(json_path.read_bytes())
        if not isinstance(data, list) or not data:
            return

        csv_path = json_path.with_suffix(".csv")
        keys = list(data[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data)

    except Exception:
        pass  # CSV export is best-effort
