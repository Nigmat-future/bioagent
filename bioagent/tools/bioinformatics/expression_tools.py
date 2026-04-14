"""Expression analysis tool templates — code helpers for scRNA-seq and bulk RNA-seq."""

from __future__ import annotations

from bioagent.tools.registry import registry


def get_expression_analysis_template(analysis_type: str) -> str:
    """Get a code template for gene expression analysis.

    Parameters
    ----------
    analysis_type : str
        Type: "scanpy_basic", "differential_expression", "clustering",
        "trajectory", "volcano_plot", "heatmap"
    """
    templates = {
        "scanpy_basic": '''# Basic Scanpy scRNA-seq analysis
import scanpy as sc
import numpy as np

def basic_scanpy_analysis(adata):
    """Standard preprocessing pipeline for scRNA-seq data."""
    sc.pp.filter_cells(adata, min_genes=200)
    sc.pp.filter_genes(adata, min_cells=3)
    adata.var["mt"] = adata.var_names.str.startswith("MT-")
    sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], inplace=True)
    adata = adata[adata.obs.n_genes_by_counts < 2500, :]
    adata = adata[adata.obs.pct_counts_mt < 5, :]
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, n_top_genes=2000)
    adata = adata[:, adata.var.highly_variable]
    sc.pp.scale(adata, max_value=10)
    sc.tl.pca(adata, svd_solver="arpack")
    sc.pp.neighbors(adata, n_pcs=30)
    sc.tl.umap(adata)
    return adata
''',
        "differential_expression": '''# Differential expression analysis
import numpy as np
import pandas as pd
from scipy import stats

def differential_expression(group1, group2, gene_names):
    """Perform t-test based differential expression."""
    results = []
    for i, gene in enumerate(gene_names):
        g1 = group1[:, i]
        g2 = group2[:, i]
        stat, pval = stats.ttest_ind(g1, g2)
        log2fc = np.log2(np.mean(g1) / np.mean(g2)) if np.mean(g2) > 0 else 0
        results.append({
            "gene": gene,
            "log2fc": log2fc,
            "pvalue": pval,
            "mean_g1": np.mean(g1),
            "mean_g2": np.mean(g2),
        })
    df = pd.DataFrame(results)
    from statsmodels.stats.multitest import multipletests
    df["padj"] = multipletests(df["pvalue"], method="fdr_bh")[1]
    return df.sort_values("padj")
''',
        "volcano_plot": '''# Volcano plot
import matplotlib.pyplot as plt
import numpy as np

def create_volcano_plot(de_results, title="Volcano Plot",
                        lfc_threshold=1.0, padj_threshold=0.05):
    """Create a volcano plot from differential expression results."""
    fig, ax = plt.subplots(figsize=(8, 6))

    log2fc = de_results["log2fc"].values
    neg_log10_padj = -np.log10(de_results["padj"].values)

    significant = (abs(log2fc) > lfc_threshold) & (de_results["padj"] < padj_threshold)

    ax.scatter(log2fc[~significant], neg_log10_padj[~significant],
               c="gray", alpha=0.5, s=10, label="Not significant")
    ax.scatter(log2fc[significant], neg_log10_padj[significant],
               c="red", alpha=0.7, s=15, label="Significant")

    ax.axhline(-np.log10(padj_threshold), ls="--", c="black", lw=0.5)
    ax.axvline(-lfc_threshold, ls="--", c="black", lw=0.5)
    ax.axvline(lfc_threshold, ls="--", c="black", lw=0.5)

    ax.set_xlabel("log2 Fold Change")
    ax.set_ylabel("-log10(adjusted p-value)")
    ax.set_title(title)
    ax.legend()

    plt.tight_layout()
    plt.savefig("workspace/figures/volcano_plot.png", dpi=300, bbox_inches="tight")
    print(f"Volcano plot saved. {sum(significant)} significant genes found.")
    return fig
''',
    }
    return templates.get(analysis_type, f"# Template for '{analysis_type}' not found")


def register_tools() -> None:
    registry.register(
        name="get_expression_analysis_template",
        description="Get Python code templates for gene expression analysis (scRNA-seq, bulk RNA-seq, differential expression, volcano plots).",
        input_schema={
            "type": "object",
            "properties": {
                "analysis_type": {
                    "type": "string",
                    "description": "Analysis type: scanpy_basic, differential_expression, clustering, trajectory, volcano_plot, heatmap",
                },
            },
            "required": ["analysis_type"],
        },
        function=get_expression_analysis_template,
    )
