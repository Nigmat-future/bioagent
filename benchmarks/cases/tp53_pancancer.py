"""Benchmark case: TP53 loss-of-function across cancer types.

TP53 is the most frequently mutated gene in human cancer (~50% of all cancers).
This case evaluates BioAgent's ability to synthesize pan-cancer genomic data.

Ground truth sourced from:
- TCGA pan-cancer analysis (Hoadley et al., 2018). Cell 173:291-304. PMID: 29625048
- Hollstein et al. (1991). Science 253:49-53. PMID: 1905840
- Freed-Pastor & Prives (2012). Genes Dev 26:1268-1286. PMID: 22713868
"""

from __future__ import annotations

from benchmarks.cases.braf_melanoma import BenchmarkCase

TP53_PANCANCER = BenchmarkCase(
    name="tp53_pancancer",
    research_topic="TP53 tumor suppressor in pan-cancer genomics",
    research_question=(
        "What are the frequency, spectrum, and functional consequences of TP53 "
        "mutations across major cancer types, and how do they influence prognosis?"
    ),
    expected_pmids=[
        "29625048",  # TCGA pan-cancer 2018
        "1905840",   # Hollstein 1991 — TP53 discovery
        "22713868",  # Freed-Pastor & Prives 2012 — GOF mutants
        "27959929",  # TP53 database (IARC)
        "31500070",  # COSMIC mutation signatures
        "26343385",  # MDM2 inhibitors review
    ],
    expected_genes=[
        "TP53",
        "MDM2",
        "MDM4",
        "CDKN2A",
        "BCL2",
        "BAX",
        "PUMA",  # BBC3
        "NOXA",  # PMAIP1
        "p21",   # CDKN1A
        "ATM",
    ],
    expected_pathways=[
        "p53 signaling pathway",
        "DNA damage response",
        "Apoptosis",
        "Cell cycle checkpoint",
        "MDM2-p53 feedback loop",
    ],
    expected_methods=[
        "Somatic mutation analysis",
        "Copy number variation",
        "Pan-cancer comparison",
        "Kaplan-Meier survival analysis",
        "Mutational signature analysis",
        "Logistic regression",
    ],
    ground_truth_statistics={
        "tp53_mutation_frequency_all_cancers": 0.42,   # ~42% pan-cancer
        "tp53_freq_serous_ovarian": 0.96,              # ovarian high-grade serous
        "tp53_freq_triple_neg_breast": 0.80,
        "tp53_freq_colorectal": 0.52,
        "tp53_freq_hepatocellular": 0.28,
        "missense_fraction": 0.74,                     # 74% of mutations are missense
        "hotspot_r175h_frequency": 0.06,               # R175H is most common hotspot
        "expected_pvalue_threshold": 0.05,
    },
    reference_abstract=(
        "TP53 is mutated in approximately 42% of human cancers, with frequency ranging from "
        "96% in high-grade serous ovarian carcinoma to less than 10% in thyroid cancer. "
        "The mutation spectrum is dominated by missense mutations (74%) at hotspots R175, "
        "G245, R248, R249, R273, and R282. Gain-of-function (GOF) mutants not only lose "
        "tumor suppressive activity but actively promote invasion and chemoresistance. "
        "MDM2 amplification provides an alternative mechanism of p53 inactivation in "
        "tumors retaining wild-type TP53. Pan-cancer analyses reveal distinct mutational "
        "signatures associated with specific carcinogenic exposures."
    ),
    constraints=[
        "Use pan-cancer TCGA data or equivalent",
        "Distinguish loss-of-function from gain-of-function mutations",
        "Include MDM2 amplification as alternative inactivation mechanism",
    ],
    tags=["pan-cancer", "tumor-suppressor", "genomics", "TCGA"],
)
