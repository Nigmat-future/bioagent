"""Benchmark case: Single-cell RNA-seq analysis of PBMCs.

The 10x Genomics PBMC 3k dataset is the canonical scRNA-seq benchmark,
with well-established cell type annotations and marker genes.

Ground truth sourced from:
- Zheng et al. (2017). Nature Comm 8:14049. PMID: 28091601
- Satija et al. (2015). Nature Biotech 33:495-502. PMID: 25867923
- Wolf et al. (2018). Genome Biol 19:15. PMID: 29409532
"""

from __future__ import annotations

from benchmarks.cases.braf_melanoma import BenchmarkCase

SCRNA_PBMC = BenchmarkCase(
    name="scrna_pbmc",
    research_topic="Single-cell RNA-seq analysis of peripheral blood mononuclear cells",
    research_question=(
        "What are the major transcriptionally distinct cell populations in human PBMCs, "
        "and what marker genes define each population?"
    ),
    expected_pmids=[
        "28091601",  # Zheng 2017 — 10x Genomics PBMC
        "25867923",  # Satija 2015 — Seurat
        "29409532",  # Wolf 2018 — Scanpy
        "30283141",  # Luecken & Theis 2019 — scRNA-seq best practices
        "26000488",  # Macosko 2015 — Drop-seq
    ],
    expected_genes=[
        "CD3D",    # T cells
        "CD3E",    # T cells
        "CD4",     # CD4+ T cells
        "CD8A",    # CD8+ T cells
        "CD19",    # B cells
        "MS4A1",   # B cells (CD20)
        "CD14",    # CD14+ Monocytes
        "FCGR3A",  # CD16+ Monocytes (FCGR3A)
        "GNLY",    # NK cells
        "NKG7",    # NK cells
        "PPBP",    # Platelets
        "FCER1A",  # Dendritic cells
    ],
    expected_pathways=[
        "T cell receptor signaling",
        "B cell receptor signaling",
        "NK cell cytotoxicity",
        "Monocyte activation",
        "Interferon signaling",
    ],
    expected_methods=[
        "Quality control (mitochondrial percentage, gene count)",
        "Normalization (total count normalization)",
        "Highly variable gene selection",
        "PCA dimensionality reduction",
        "UMAP visualization",
        "Louvain / Leiden clustering",
        "Marker gene identification (Wilcoxon rank-sum)",
    ],
    ground_truth_statistics={
        "expected_cell_types": 9,       # major PBMC populations
        "expected_min_clusters": 5,
        "cd3d_t_cell_marker": True,
        "cd14_monocyte_marker": True,
        "typical_n_cells_3k": 2638,
        "typical_n_genes_per_cell_min": 200,
        "typical_n_genes_per_cell_max": 2500,
        "expected_pvalue_threshold": 0.05,
    },
    reference_abstract=(
        "Peripheral blood mononuclear cells (PBMCs) comprise a heterogeneous mixture of "
        "immune cell types including T cells (CD4+ and CD8+), B cells, natural killer (NK) "
        "cells, monocytes (CD14+ and CD16+), and dendritic cells. Single-cell RNA-seq of "
        "the canonical 10x Genomics PBMC 3k dataset identifies 9 major cell clusters using "
        "Leiden clustering after PCA and UMAP dimensionality reduction. Cell types are "
        "identified by established marker genes: CD3D/CD3E (T cells), CD19/MS4A1 (B cells), "
        "GNLY/NKG7 (NK cells), CD14 (monocytes), and FCER1A (dendritic cells). "
        "Differential expression analysis confirms known cell-type-specific transcriptional programs."
    ),
    constraints=[
        "Use the PBMC 3k dataset from 10x Genomics or equivalent synthetic data",
        "Follow Scanpy best practices for QC and normalization",
        "Report marker genes for each cluster",
    ],
    tags=["scRNA-seq", "single-cell", "immunology", "PBMC", "Scanpy"],
)
