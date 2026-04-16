"""NCBI E-utilities download tools (sequences, genes, etc.)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def download_ncbi_sequences(
    accession: str,
    database: str = "nucleotide",
    format: str = "fasta",
) -> str:
    """Download sequences or records from NCBI E-utilities.

    Parameters
    ----------
    accession:
        NCBI accession or comma-separated list, e.g. ``"NM_004333"`` or ``"NM_004333,NM_000038"``.
    database:
        NCBI database: ``nucleotide``, ``protein``, ``gene``, ``pubmed``.
    format:
        Return format: ``fasta``, ``genbank``, ``json``, ``xml``.

    Returns a status string describing what was downloaded.
    """
    from bioagent.config.settings import settings
    from bioagent.tools.execution.sandbox import ensure_workspace
    import urllib.request
    import urllib.parse

    ensure_workspace()
    data_dir = settings.workspace_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    email = settings.entrez_email
    api_key = settings.ncbi_api_key

    # Map format to rettype/retmode
    format_map = {
        "fasta": ("fasta", "text"),
        "genbank": ("gb", "text"),
        "json": ("json", "json"),
        "xml": ("xml", "xml"),
    }
    rettype, retmode = format_map.get(format.lower(), ("fasta", "text"))

    # Determine file extension
    ext_map = {"fasta": ".fasta", "genbank": ".gb", "json": ".json", "xml": ".xml"}
    ext = ext_map.get(format.lower(), ".txt")

    # Handle multiple accessions
    acc_list = [a.strip() for a in accession.split(",") if a.strip()]
    ids_str = ",".join(acc_list)
    safe_acc = acc_list[0].replace("/", "_").replace(".", "_")
    out_filename = f"ncbi_{database}_{safe_acc}{ext}"
    out_path = data_dir / out_filename

    params: dict[str, str] = {
        "db": database,
        "id": ids_str,
        "rettype": rettype,
        "retmode": retmode,
        "email": email,
    }
    if api_key:
        params["api_key"] = api_key

    url = f"{_EUTILS_BASE}/efetch.fcgi?" + urllib.parse.urlencode(params)

    # Try BioPython first (cleaner output), then raw HTTP
    result = _biopython_fetch(acc_list, database, rettype, out_path, email)
    if result.startswith("SUCCESS"):
        return result

    logger.warning("[ncbi_tools] BioPython failed (%s), trying direct HTTP", result)

    # Raw HTTP fallback
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": f"BioAgent/1.0 ({email})"},
        )
        with urllib.request.urlopen(req, timeout=settings.download_timeout) as resp:
            content = resp.read()

        if len(content) < 20:
            raise ValueError("Response too short — likely an NCBI error")

        out_path.write_bytes(content)
        size_kb = out_path.stat().st_size / 1024
        return f"SUCCESS: Downloaded {ids_str} from NCBI {database} to {out_path} ({size_kb:.0f} KB)"

    except Exception as exc:
        logger.warning("[ncbi_tools] HTTP fallback failed: %s", exc)

    # Final fallback: manual instructions
    from bioagent.tools.data.manual_instructions import generate_download_instructions
    return generate_download_instructions(
        dataset_description=f"NCBI {database} sequences: {accession}",
        accession=accession,
        source="NCBI",
        url=url,
    )


def _biopython_fetch(acc_list: list, database: str, rettype: str, out_path, email: str) -> str:
    """Download using BioPython's Entrez module."""
    try:
        from Bio import Entrez, SeqIO  # type: ignore

        Entrez.email = email

        ids_str = ",".join(acc_list)
        handle = Entrez.efetch(db=database, id=ids_str, rettype=rettype, retmode="text")
        data = handle.read()
        handle.close()

        if isinstance(data, str):
            out_path.write_text(data, encoding="utf-8")
        else:
            out_path.write_bytes(data)

        if out_path.stat().st_size < 20:
            out_path.unlink(missing_ok=True)
            return "ERROR: BioPython returned empty data"

        size_kb = out_path.stat().st_size / 1024
        return f"SUCCESS: Downloaded {ids_str} from NCBI {database} to {out_path} ({size_kb:.0f} KB)"

    except ImportError:
        return "ERROR: BioPython not installed (pip install biopython)"
    except Exception as exc:
        return f"ERROR (BioPython): {exc}"
