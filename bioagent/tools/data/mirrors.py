"""Mirror / alternative-source URL routing.

Returns ordered ``(url, source_label)`` candidate lists for the download
backbone. Intentionally conservative: only routes known-good mirrors that
have been verified to serve the expected bytes from Asia-Pacific paths.
When no mirror applies, callers should hit the canonical source directly
(with retry+resume handling the rest).
"""

from __future__ import annotations

import re

__all__ = [
    "resolve_geo_series_matrix",
    "resolve_sra_fastq",
    "resolve_10x_pbmc3k",
    "resolve_generic_url",
]


def resolve_geo_series_matrix(acc: str) -> list[tuple[str, str]]:
    """Candidate URLs for a GEO series matrix file.

    EBI mirrors most Affymetrix-era GEO series under ArrayExpress as
    ``E-GEOD-<num>``. It's often faster than NCBI FTP from China. When
    EBI doesn't have the series (newer RNA-seq submissions), the call
    404s quickly and we fall through to NCBI.
    """
    acc = acc.strip().upper()
    if not re.match(r"^GSE\d+$", acc):
        return []

    num = acc[3:]
    prefix = acc[:-3] + "nnn" if len(acc) > 3 else acc
    fname = f"{acc}_series_matrix.txt.gz"

    return [
        (
            f"https://www.ebi.ac.uk/biostudies/files/E-GEOD-{num}/{fname}",
            "EBI-ArrayExpress",
        ),
        (
            f"https://ftp.ncbi.nlm.nih.gov/geo/series/{prefix}/{acc}/matrix/{fname}",
            "NCBI-GEO-FTP",
        ),
    ]


def resolve_sra_fastq(
    accession: str, paired: bool = False
) -> list[tuple[str, str]]:
    """Candidate URLs for a FASTQ file from SRA/ENA/DRA.

    ENA hosts direct ``.fastq.gz`` downloads without requiring
    ``prefetch``/``fasterq-dump`` — faster and protocol-simpler than
    NCBI SRA, and the ENA mirror is notably quicker from Asia.
    """
    accession = accession.strip().upper()
    if not re.match(r"^(SRR|ERR|DRR)\d+$", accession):
        return []

    prefix = accession[:6]
    # ENA layout: last 3 digits of long accessions sit in a subdirectory.
    # Short accessions (7 digits) live directly under <prefix>/<acc>/.
    suffix_dir = ""
    if len(accession) >= 10:
        suffix_dir = f"00{accession[-1]}/" if len(accession) == 10 else f"0{accession[-2:]}/"

    bases = [
        f"https://ftp.sra.ebi.ac.uk/vol1/fastq/{prefix}/{suffix_dir}{accession}",
        f"http://ftp.sra.ebi.ac.uk/vol1/fastq/{prefix}/{suffix_dir}{accession}",
    ]

    if paired:
        return [
            (f"{bases[0]}/{accession}_1.fastq.gz", "ENA-SRA-R1"),
            (f"{bases[0]}/{accession}_2.fastq.gz", "ENA-SRA-R2"),
        ]
    return [
        (f"{bases[0]}/{accession}.fastq.gz", "ENA-SRA"),
    ]


def resolve_10x_pbmc3k(variant: str = "filtered") -> list[tuple[str, str]]:
    """10x Genomics PBMC 3k — the canonical scRNA-seq benchmark dataset.

    ``variant`` is ``"filtered"`` (cell-called matrix, ~2700 cells) or
    ``"raw"`` (pre-cell-calling, ~737k barcodes). Served by 10x's
    Cloudflare CDN, globally fast and reliable.
    """
    base = "https://cf.10xgenomics.com/samples/cell/pbmc3k"
    if variant not in ("filtered", "raw"):
        variant = "filtered"
    fname = f"pbmc3k_{variant}_gene_bc_matrices.tar.gz"
    return [(f"{base}/{fname}", "10x-CDN")]


def resolve_generic_url(url: str) -> list[tuple[str, str]]:
    """Pass-through: a single candidate labelled by host.

    Keeps the ``try_mirrors`` surface uniform for callers that already
    have a concrete URL.
    """
    import urllib.parse

    host = urllib.parse.urlparse(url).hostname or "direct"
    return [(url, host)]
