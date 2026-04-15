"""Benchmark case: BRAF V600E in Melanoma.

A well-established case with known papers, pathways, and statistical results.
Used to evaluate whether BioAgent can correctly identify and analyse a canonical
oncology research question.

Ground truth sourced from:
- Davies et al. (2002). Nature 417:949-954. PMID: 12068308
- Flaherty et al. (2010). NEJM 363:809-819. PMID: 20818844
- Chapman et al. (2011). NEJM 364:2507-2516. PMID: 21639808
- Sosman et al. (2012). NEJM 366:707-714. PMID: 22356324
- Larkin et al. (2015). NEJM 373:23-34. PMID: 26027431
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BenchmarkCase:
    """A benchmark case with ground-truth annotations for evaluation."""

    name: str
    research_question: str
    research_topic: str
    expected_pmids: list[str]
    expected_genes: list[str]
    expected_pathways: list[str]
    expected_methods: list[str]
    ground_truth_statistics: dict
    reference_abstract: str
    constraints: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


BRAF_MELANOMA = BenchmarkCase(
    name="braf_melanoma",
    research_topic="BRAF V600E mutation in melanoma",
    research_question=(
        "What is the mechanistic role of BRAF V600E mutation in melanoma pathogenesis, "
        "and what are the most effective targeted therapeutic strategies?"
    ),
    expected_pmids=[
        "12068308",  # Davies 2002 — BRAF discovery
        "20818844",  # Flaherty 2010 — vemurafenib phase I
        "21639808",  # Chapman 2011 — vemurafenib phase III
        "22356324",  # Sosman 2012 — dabrafenib
        "26027431",  # Larkin 2015 — nivolumab + ipilimumab
        "24025706",  # Hauschild 2012 — dabrafenib vs DTIC
        "22663011",  # Falchook 2012 — trametinib
    ],
    expected_genes=[
        "BRAF",
        "MEK1",  # MAP2K1
        "MEK2",  # MAP2K2
        "ERK1",  # MAPK3
        "ERK2",  # MAPK1
        "NRAS",
        "PTEN",
        "CDKN2A",
        "TP53",
        "RAS",
    ],
    expected_pathways=[
        "MAPK/ERK signaling",
        "RAS-RAF-MEK-ERK cascade",
        "PI3K-AKT pathway",
        "Apoptosis regulation",
        "Cell cycle regulation",
    ],
    expected_methods=[
        "Kaplan-Meier survival analysis",
        "Progression-free survival",
        "Overall survival",
        "RECIST criteria",
        "Immunohistochemistry",
        "Next-generation sequencing",
    ],
    ground_truth_statistics={
        "braf_mutation_frequency_in_melanoma": 0.50,  # ~50% of cutaneous melanomas
        "vemurafenib_response_rate": 0.48,            # 48% objective response rate
        "vemurafenib_pfs_months": 5.3,                # median PFS
        "dabrafenib_response_rate": 0.53,
        "combination_pfs_hazard_ratio": 0.58,         # dabrafenib + trametinib vs mono
        "expected_pvalue_threshold": 0.05,
    },
    reference_abstract=(
        "BRAF V600E is present in approximately 50% of cutaneous melanomas and leads to "
        "constitutive activation of the MAPK/ERK signaling pathway. Vemurafenib and "
        "dabrafenib, selective BRAF inhibitors, achieve objective response rates of 48-53% "
        "with significant improvements in progression-free survival compared to chemotherapy. "
        "However, acquired resistance emerges in most patients within 6-8 months, mediated "
        "through NRAS mutations, MEK amplification, and alternative pathway activation. "
        "Combination strategies targeting both BRAF and MEK1/2 improve durable responses "
        "and delay resistance onset."
    ),
    constraints=[
        "Focus on BRAF V600E specifically, not other BRAF mutations",
        "Include both targeted therapy and immunotherapy perspectives",
        "Address resistance mechanisms",
    ],
    tags=["oncology", "targeted-therapy", "melanoma", "MAPK-signaling"],
)
