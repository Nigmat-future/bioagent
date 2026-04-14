"""Genomic analysis tool interfaces — code templates for variant and GWAS analysis."""

from __future__ import annotations

from bioagent.tools.registry import registry


def get_genomic_analysis_template(analysis_type: str) -> str:
    """Get a code template for genomic analysis tasks.

    Parameters
    ----------
    analysis_type : str
        Type: "gwas_simulation", "variant_annotation", "manhattan_plot",
        "allele_frequency", "gene_set_analysis"
    """
    templates = {
        "gwas_simulation": '''# GWAS simulation and analysis
import numpy as np
import pandas as pd

def simulate_gwas(n_samples=1000, n_snps=10000, n_causal=50, heritability=0.3):
    """Simulate a GWAS dataset for method development."""
    np.random.seed(42)

    # Genotype matrix (0, 1, 2 for AA, Aa, aa)
    genotypes = np.random.binomial(2, np.random.uniform(0.05, 0.5, n_snps),
                                    size=(n_samples, n_snps))

    # Causal variants
    causal_idx = np.random.choice(n_snps, n_causal, replace=False)
    effect_sizes = np.zeros(n_snps)
    effect_sizes[causal_idx] = np.random.normal(0, 0.3, n_causal)

    # Phenotype with noise
    genetic_component = genotypes @ effect_sizes
    noise = np.random.normal(0, np.std(genetic_component) * (1 - heritability) / heritability,
                              n_samples)
    phenotype = genetic_component + noise

    # Association testing
    results = []
    for i in range(n_snps):
        from scipy import stats
        corr, pval = stats.pearsonr(genotypes[:, i], phenotype)
        results.append({"snp_id": f"rs{i}", "chromosome": i // (n_snps // 22) + 1,
                        "position": i * 1000, "beta": corr, "pvalue": pval})

    return pd.DataFrame(results)
''',
        "manhattan_plot": '''# Manhattan plot
import matplotlib.pyplot as plt
import numpy as np

def create_manhattan_plot(gwas_results, title="Manhattan Plot",
                          significance_threshold=5e-8):
    """Create a Manhattan plot from GWAS results."""
    fig, ax = plt.subplots(figsize=(12, 4))

    gwas_results["-log10p"] = -np.log10(gwas_results["pvalue"])

    chromosomes = sorted(gwas_results["chromosome"].unique())
    colors = ["#1f77b4", "#ff7f0e"] * 11

    for i, chrom in enumerate(chromosomes):
        subset = gwas_results[gwas_results["chromosome"] == chrom]
        offset = sum(max(gwas_results[gwas_results["chromosome"] == c]["position"].max()
                        for c in chromosomes[:j]) for j in range(i))
        ax.scatter(subset["position"] + offset, subset["-log10p"],
                   c=colors[i % len(colors)], s=3, alpha=0.6)

    ax.axhline(-np.log10(significance_threshold), c="red", ls="--", lw=0.8)
    ax.set_xlabel("Chromosome")
    ax.set_ylabel("-log10(p-value)")
    ax.set_title(title)

    plt.tight_layout()
    plt.savefig("workspace/figures/manhattan_plot.png", dpi=300, bbox_inches="tight")
    print("Manhattan plot saved.")
    return fig
''',
        "gene_set_analysis": '''# Gene set enrichment analysis (overrepresentation)
import numpy as np
import pandas as pd
from scipy import stats

def gene_set_enrichment(gene_list, pathway_genes, all_genes):
    """Simple overrepresentation analysis for a gene set."""
    in_list_and_pathway = len(set(gene_list) & set(pathway_genes))
    in_list_not_pathway = len(set(gene_list) - set(pathway_genes))
    not_in_list_pathway = len(set(pathway_genes) - set(gene_list))
    not_in_list_not_pathway = len(set(all_genes) - set(gene_list) - set(pathway_genes))

    table = [[in_list_and_pathway, in_list_not_pathway],
             [not_in_list_pathway, not_in_list_not_pathway]]

    oddsratio, pvalue = stats.fisher_exact(table)

    return {
        "overlap": in_list_and_pathway,
        "gene_list_size": len(gene_list),
        "pathway_size": len(pathway_genes),
        "odds_ratio": oddsratio,
        "pvalue": pvalue,
        "genes_in_overlap": list(set(gene_list) & set(pathway_genes)),
    }
''',
    }
    return templates.get(analysis_type, f"# Template for '{analysis_type}' not found")


def register_tools() -> None:
    registry.register(
        name="get_genomic_analysis_template",
        description="Get Python code templates for genomic analysis (GWAS simulation, Manhattan plots, variant annotation, gene set analysis).",
        input_schema={
            "type": "object",
            "properties": {
                "analysis_type": {
                    "type": "string",
                    "description": "Analysis type: gwas_simulation, variant_annotation, manhattan_plot, allele_frequency, gene_set_analysis",
                },
            },
            "required": ["analysis_type"],
        },
        function=get_genomic_analysis_template,
    )
