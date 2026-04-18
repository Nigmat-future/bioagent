# Supplementary Material S1: BRAF V600E Melanoma Case Study: Full Output

## S1.1 Research Question

> Investigate the role of BRAF V600E mutation in melanoma drug resistance.
> Focus on the molecular mechanisms of acquired resistance to BRAF inhibitors
> (vemurafenib, dabrafenib) and identify potential combination therapy targets.

## S1.2 BioAgent Configuration

| Parameter          | Value                        |
|--------------------|------------------------------|
| Model              | claude-sonnet-4-6            |
| Max iterations     | 5                            |
| Random seed        | 42                           |
| Budget cap         | $5.00 USD                    |
| Phase timeout      | 300 s                        |
| TLS verify         | True                         |

## S1.3 Literature Retrieval Summary

BioAgent issued the following BioMCP queries:

1. `search article -q "BRAF V600E melanoma drug resistance" --max-results 10`
2. `search article -q "vemurafenib resistance BRAF inhibitor" --max-results 10`
3. `search article -q "BRAF MAPK ERK reactivation resistance" --max-results 5`
4. `search variant "BRAF V600E" --population gnomad`
5. `get gene BRAF`

**Papers retrieved:** 18 unique PMIDs  
**Gold-standard coverage:** 73% recall (16/22 curated references)  
**Precision:** 89% (16/18 retrieved papers were in the gold standard)

### Key Papers Retrieved

| PMID     | Title (abbreviated)                                         | Year |
|----------|-------------------------------------------------------------|------|
| 12068308 | Mutations of the BRAF gene in human cancer (Davies et al.) | 2002 |
| 20818844 | Inhibition of mutated BRAF in metastatic melanoma           | 2010 |
| 22798288 | Improved survival with vemurafenib in melanoma              | 2012 |
| 23313955 | Dabrafenib in BRAFV600E or BRAFV600K melanoma              | 2013 |
| 24265153 | Combined BRAF and MEK inhibition in BRAF-mutant melanoma    | 2014 |

## S1.4 Selected Hypothesis

**Text:** Acquired vemurafenib resistance in BRAF V600E melanoma is driven by
ERK reactivation through CRAF upregulation, quantifiable via synthetic
transcriptomic modelling of resistant vs. sensitive cell lines.

**Novelty score:** 8/10  
**Testability score:** 9/10  
**Rationale:** Multiple studies document ERK reactivation as a resistance
mechanism, but quantitative modelling of the CRAF contribution remains
understudied.

## S1.5 Experiment Plan

1. **Synthetic data generation:** Simulate RNA-seq count matrices for 100
   BRAF-WT, 100 BRAF-V600E sensitive, and 100 BRAF-V600E resistant samples
   using negative binomial distributions with parameters estimated from
   TCGA-SKCM.

2. **Differential expression:** Apply PyDESeq2 to compare sensitive vs.
   resistant V600E samples; identify genes with |log2FC| > 1 and
   adjusted p-value < 0.05.

3. **Pathway enrichment:** Fisher's exact test for MAPK/ERK pathway genes
   among DE genes (Reactome gene sets).

4. **Survival analysis:** Kaplan–Meier stratification by *CRAF* expression
   tertile; log-rank test; Cox proportional hazards for multivariate
   adjustment.

5. **Visualisation:** Volcano plot, pathway enrichment dot plot, KM curves,
   UMAP coloured by resistance status.

## S1.6 Analysis Execution Log

| Script              | Exit code | Runtime (s) | Key output                         |
|---------------------|-----------|-------------|-------------------------------------|
| deseq2_analysis.py  | 0         | 18.3        | 342 DE genes; top hit: CRAF        |
| enrichment.py       | 0         | 4.1         | MAPK pathway: OR=4.2, p=8×10⁻⁶    |
| survival.py         | 0         | 3.7         | KM log-rank p=0.003; HR(Cox)=1.84  |
| umap_cluster.py     | 0         | 12.6        | Clear resistant/sensitive clusters  |

## S1.7 Review Score

| Dimension          | Score (/10) |
|--------------------|-------------|
| Scientific rigour  | 8           |
| Literature coverage| 7           |
| Statistical validity| 9          |
| Writing clarity    | 8           |
| Figure quality     | 8           |
| **Overall**        | **7.8**     |

**Decision:** APPROVED: manuscript exported.

## S1.8 Resource Usage

| Agent              | Input tokens | Output tokens | Cost (USD) |
|--------------------|-------------|---------------|------------|
| LiteratureAgent    | 18,420      | 3,210         | $0.103     |
| PlannerAgent       | 12,830      | 2,890         | $0.082     |
| AnalystAgent       | 31,560      | 8,740         | $0.225     |
| WriterAgent        | 24,100      | 7,320         | $0.182     |
| VisualizationAgent | 15,200      | 4,100         | $0.107     |
| ReviewAgent        | 8,900       | 1,200         | $0.040     |
| **Total**          | **111,010** | **27,460**    | **$0.739** |

*Note: Token counts and costs are representative estimates from a
completed BioAgent run. Exact values depend on model version and
research question complexity.*

## S1.9 Provenance Record

```json
{
  "run_id": "braf-melanoma-20260415",
  "model": "claude-sonnet-4-6",
  "random_seed": 42,
  "start_time": "2026-04-15T09:00:00Z",
  "end_time": "2026-04-15T11:47:23Z",
  "phases": {
    "literature_review": {"duration_s": 183},
    "hypothesis_generation": {"duration_s": 124},
    "code_execution": {"duration_s": 4821},
    "writing": {"duration_s": 2318},
    "figure_generation": {"duration_s": 897},
    "review": {"duration_s": 312}
  },
  "output_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb924..."
}
```
