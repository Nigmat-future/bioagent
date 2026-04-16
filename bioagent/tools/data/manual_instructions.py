"""Last-resort fallback: generate a human-readable download instruction guide."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_INSTRUCTIONS_FILE = "data/DOWNLOAD_INSTRUCTIONS.md"


def generate_download_instructions(
    dataset_description: str,
    accession: str = "",
    source: str = "",
    url: str = "",
) -> str:
    """Write manual download instructions to workspace/data/DOWNLOAD_INSTRUCTIONS.md.

    Called when all automated download attempts have failed.

    Parameters
    ----------
    dataset_description:
        Plain-English description of what data is needed.
    accession:
        Dataset accession number (e.g. GSE12345, TCGA-SKCM).
    source:
        Source database name (e.g. GEO, cBioPortal, GDC).
    url:
        Direct URL for the data, if known.

    Returns a status string explaining what was written.
    """
    from bioagent.config.settings import settings
    from bioagent.tools.execution.sandbox import ensure_workspace

    ensure_workspace()
    data_dir = settings.workspace_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    instructions_path = settings.workspace_path / _INSTRUCTIONS_FILE

    section = _build_section(dataset_description, accession, source, url)

    # Append to any existing instructions file
    existing = ""
    if instructions_path.exists():
        existing = instructions_path.read_text(encoding="utf-8")
        if section.strip() in existing:
            return f"NOTE: Instructions for '{dataset_description}' already written to {instructions_path}"

    header = "# Manual Data Download Instructions\n\n" if not existing else ""
    instructions_path.write_text(
        existing + header + section,
        encoding="utf-8",
    )

    logger.info("[manual_instructions] Written to %s", instructions_path)
    return (
        f"MANUAL_REQUIRED: Automated download failed for '{dataset_description}'. "
        f"Detailed download instructions written to {instructions_path}. "
        f"Please follow those instructions to obtain the data, then place the files "
        f"in workspace/data/ and re-run the analysis."
    )


def _build_section(
    dataset_description: str,
    accession: str,
    source: str,
    url: str,
) -> str:
    lines = [f"## {dataset_description}\n"]

    if accession:
        lines.append(f"**Accession:** `{accession}`  ")
    if source:
        lines.append(f"**Source:** {source}  ")
    if url:
        lines.append(f"**URL:** <{url}>  ")
    lines.append("")

    # Source-specific shell commands
    src_lower = source.lower() if source else ""
    acc_lower = accession.lower() if accession else ""

    if "geo" in src_lower or acc_lower.startswith("gse") or acc_lower.startswith("gpl"):
        lines += _geo_instructions(accession)
    elif "cbioportal" in src_lower or "tcga" in acc_lower:
        lines += _cbioportal_instructions(accession)
    elif "gdc" in src_lower or "tcga" in src_lower:
        lines += _gdc_instructions(accession)
    elif "ncbi" in src_lower or "genbank" in src_lower:
        lines += _ncbi_instructions(accession)
    elif "encode" in src_lower or acc_lower.startswith("encf") or acc_lower.startswith("encs"):
        lines += _encode_instructions(accession)
    elif url:
        lines += _generic_url_instructions(url, accession)
    else:
        lines.append(
            "No automated download available. Please locate the dataset manually "
            f"using the accession `{accession}` at the source database."
        )

    lines.append("\n**After downloading:** place the file(s) in `workspace/data/`\n\n---\n\n")
    return "\n".join(lines)


def _geo_instructions(accession: str) -> list[str]:
    acc = accession.upper()
    ftp_base = f"https://ftp.ncbi.nlm.nih.gov/geo/series/{acc[:-3]}nnn/{acc}"
    return [
        "### Download via GEOparse (Python):",
        "```python",
        "import GEOparse",
        f'gse = GEOparse.get_GEO(geo="{acc}", destdir="workspace/data/")',
        "```",
        "",
        "### Or direct FTP download:",
        "```bash",
        f"wget {ftp_base}/matrix/{acc}_series_matrix.txt.gz -P workspace/data/",
        f"gunzip workspace/data/{acc}_series_matrix.txt.gz",
        "```",
        "",
        f"### Or visit: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={acc}",
    ]


def _cbioportal_instructions(study_id: str) -> list[str]:
    return [
        "### Download via cBioPortal API:",
        "```bash",
        f'curl "https://www.cbioportal.org/api/studies/{study_id}/clinical-data?clinicalDataType=PATIENT" \\',
        '  -H "Accept: application/json" > workspace/data/clinical_data.json',
        "",
        f'curl "https://www.cbioportal.org/api/molecular-profiles/{study_id}_mutations/mutations" \\',
        '  -H "Accept: application/json" > workspace/data/mutations.json',
        "```",
        "",
        f"### Or visit: https://www.cbioportal.org/study/summary?id={study_id}",
        "Click 'Download' → select data types → extract to workspace/data/",
    ]


def _gdc_instructions(project: str) -> list[str]:
    return [
        "### Download via GDC API:",
        "```bash",
        "# 1. Find file IDs:",
        f'curl "https://api.gdc.cancer.gov/files?filters=%7B%22op%22%3A%22and%22%2C%22content%22%3A%5B%7B%22op%22%3A%22in%22%2C%22content%22%3A%7B%22field%22%3A%22cases.project.project_id%22%2C%22value%22%3A%5B%22{project}%22%5D%7D%7D%5D%7D&fields=file_id,file_name&size=10" | python -m json.tool',
        "",
        "# 2. Download a specific file:",
        "curl https://api.gdc.cancer.gov/data/<FILE_UUID> -o workspace/data/<filename>",
        "```",
        "",
        f"### Or use GDC Portal: https://portal.gdc.cancer.gov/projects/{project}",
        "Note: Some GDC data requires dbGaP access approval.",
    ]


def _ncbi_instructions(accession: str) -> list[str]:
    return [
        "### Download via NCBI E-utilities:",
        "```bash",
        f'curl "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nucleotide&id={accession}&rettype=fasta&retmode=text" \\',
        f"  -o workspace/data/{accession}.fasta",
        "```",
        "",
        "### Or via BioPython:",
        "```python",
        "from Bio import Entrez, SeqIO",
        'Entrez.email = "your@email.com"',
        f'handle = Entrez.efetch(db="nucleotide", id="{accession}", rettype="fasta")',
        f'SeqIO.write(SeqIO.read(handle, "fasta"), "workspace/data/{accession}.fasta", "fasta")',
        "```",
    ]


def _encode_instructions(accession: str) -> list[str]:
    return [
        "### Download via ENCODE REST API:",
        "```bash",
        f'curl "https://www.encodeproject.org/files/{accession}/@@download/{accession}.fastq.gz" \\',
        f"  -L -o workspace/data/{accession}.fastq.gz",
        "```",
        "",
        f"### Or visit: https://www.encodeproject.org/files/{accession}/",
    ]


def _generic_url_instructions(url: str, accession: str) -> list[str]:
    filename = url.split("/")[-1].split("?")[0] or (accession or "dataset")
    return [
        "### Direct download:",
        "```bash",
        f"wget '{url}' -O workspace/data/{filename}",
        "# or:",
        f"curl -L '{url}' -o workspace/data/{filename}",
        "```",
    ]
