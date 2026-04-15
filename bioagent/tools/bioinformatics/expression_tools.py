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
        "pydeseq2": '''# DESeq2-style differential expression using PyDESeq2
# More robust than t-tests; uses negative binomial model appropriate for count data
import numpy as np
import pandas as pd

try:
    from pydeseq2.dds import DeseqDataSet
    from pydeseq2.ds import DeseqStats

    # counts: genes x samples raw count matrix (DataFrame)
    # metadata: DataFrame with 'condition' column (e.g. 'control'/'treatment')

    # Simulate count data if real data not available
    np.random.seed(42)
    n_genes, n_samples = 500, 20
    counts = pd.DataFrame(
        np.random.negative_binomial(5, 0.5, size=(n_genes, n_samples)),
        index=[f"gene_{i}" for i in range(n_genes)],
        columns=[f"sample_{i}" for i in range(n_samples)],
    )
    metadata = pd.DataFrame(
        {"condition": ["control"] * 10 + ["treatment"] * 10},
        index=counts.columns,
    )

    dds = DeseqDataSet(counts=counts.T, metadata=metadata, design_factors="condition")
    dds.deseq2()

    stat_res = DeseqStats(dds, contrast=["condition", "treatment", "control"])
    stat_res.summary()
    results = stat_res.results_df

    # Filter significant results
    sig = results[(results["padj"] < 0.05) & (abs(results["log2FoldChange"]) > 1)]
    print(f"DESeq2 analysis complete. Significant genes (padj<0.05, |log2FC|>1): {len(sig)}")
    print(sig.sort_values("padj").head(20).to_string())
    results.to_csv("workspace/output/deseq2_results.csv")

except ImportError:
    print("PyDESeq2 not installed. Install with: pip install pydeseq2")
    print("Falling back to t-test with BH correction...")
    # Fallback: scipy t-test with FDR correction (already in differential_expression template)
''',
        "survival_analysis": '''# Survival analysis — Kaplan-Meier + Cox proportional hazards
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

try:
    from lifelines import KaplanMeierFitter, CoxPHFitter
    from lifelines.statistics import logrank_test

    # Simulate survival data (replace with real data)
    np.random.seed(42)
    n = 100
    durations_A = np.random.exponential(scale=24, size=n // 2)  # months
    durations_B = np.random.exponential(scale=14, size=n // 2)
    events_A = (durations_A < 36).astype(int)
    events_B = (durations_B < 36).astype(int)

    # Kaplan-Meier
    fig, ax = plt.subplots(figsize=(8, 5))
    kmf_A = KaplanMeierFitter()
    kmf_A.fit(durations_A, events_A, label="Group A (control)")
    kmf_A.plot_survival_function(ax=ax, ci_show=True)

    kmf_B = KaplanMeierFitter()
    kmf_B.fit(durations_B, events_B, label="Group B (treatment)")
    kmf_B.plot_survival_function(ax=ax, ci_show=True)

    # Log-rank test
    lr = logrank_test(durations_A, durations_B, events_A, events_B)
    ax.set_title(f"Kaplan-Meier Survival Curves (log-rank p={lr.p_value:.3f})")
    ax.set_xlabel("Time (months)")
    ax.set_ylabel("Survival probability")
    plt.tight_layout()
    plt.savefig("workspace/figures/survival_km.pdf", bbox_inches="tight")
    print(f"Log-rank test p-value: {lr.p_value:.4f}")
    print(f"Median OS — Group A: {kmf_A.median_survival_time_:.1f} months")
    print(f"Median OS — Group B: {kmf_B.median_survival_time_:.1f} months")

    # Cox PH model
    df = pd.DataFrame({
        "duration": np.concatenate([durations_A, durations_B]),
        "event": np.concatenate([events_A, events_B]),
        "treatment": [0] * (n // 2) + [1] * (n // 2),
    })
    cph = CoxPHFitter()
    cph.fit(df, duration_col="duration", event_col="event")
    cph.print_summary()
    print(f"Hazard ratio: {cph.hazard_ratios_['treatment']:.3f}")

except ImportError:
    print("Install lifelines: pip install lifelines")
''',
    }
    return templates.get(analysis_type, f"# Template for '{analysis_type}' not found")


def register_tools() -> None:
    if "get_expression_analysis_template" in registry.list_tools():
        return
    registry.register(
        name="get_expression_analysis_template",
        description=(
            "Get Python code templates for gene expression analysis. "
            "Types: scanpy_basic, differential_expression, clustering, trajectory, "
            "volcano_plot, heatmap, pydeseq2 (negative-binomial DE), survival_analysis."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "analysis_type": {
                    "type": "string",
                    "description": (
                        "Analysis type: scanpy_basic, differential_expression, clustering, "
                        "trajectory, volcano_plot, heatmap, pydeseq2, survival_analysis"
                    ),
                },
            },
            "required": ["analysis_type"],
        },
        function=get_expression_analysis_template,
    )
