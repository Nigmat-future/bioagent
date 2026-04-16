# Benchmark Data Provenance

This document describes the datasets referenced by each benchmark case in `benchmarks/cases/`. All downloads are attempted through the `DataAcquisitionAgent` (`bioagent/agents/data_acquisition.py`) using public APIs; every source has a documented fallback to a human-readable manual-instructions file if the automated path fails.

All listed resources are **public** and **open-access**. No controlled-access data (dbGaP, protected TCGA) is used.

---

## Case 1 — BRAF V600E in Melanoma (`braf_melanoma`)

**Research question:** Investigate the role of BRAF V600E mutation in melanoma drug resistance.

| Source | Accession | Description | Fallback |
|---|---|---|---|
| **cBioPortal** | `skcm_tcga` | TCGA SKCM mutations + clinical | REST API `/studies/skcm_tcga/data/` |
| **GEO** | `GSE65904` | Bulk RNA-seq of melanoma tumours (Cirenajwis 2015) | Direct FTP from NCBI |
| **GEO** | `GSE50509` | BRAF-inhibitor resistant vs sensitive melanoma lines | Direct FTP |
| **OncoKB / PubMed** | via BioMCP | BRAF V600E therapeutic annotations | Cached PMIDs in `references.bib` |

**Download script:** the agent autonomously issues these calls during the `data_acquisition` phase; `benchmarks/run_benchmark.py --case braf_melanoma` reproduces the workflow.

**Expected disk usage:** ~25 MB (compressed), ~120 MB (uncompressed expression matrices).

**Data availability statement (for manuscript):** "All datasets used in this study are publicly available. TCGA Skin Cutaneous Melanoma (SKCM) data were obtained via cBioPortal study `skcm_tcga`. GEO series GSE65904 and GSE50509 are accessible at <https://www.ncbi.nlm.nih.gov/geo/>. No controlled-access data were used."

---

## Case 2 — TP53 Pan-Cancer (`tp53_pancancer`)

**Research question:** Compare TP53 mutation hotspots and their functional consequences across cancer types.

| Source | Accession | Description | Fallback |
|---|---|---|---|
| **GDC** | `TCGA-PANCAN` | Somatic mutations across 33 cancer types | REST API `/cases` + file UUIDs |
| **cBioPortal** | `msk_impact_2017` | MSK-IMPACT clinical sequencing cohort | REST API |
| **ClinVar** | via BioMCP | TP53 germline variants | BioMCP `search variant TP53` |
| **UniProt** | `P04637` | TP53 structure / domains | E-utilities |

**Expected disk usage:** ~80 MB.

---

## Case 3 — scRNA-seq PBMC (`scrna_pbmc`)

**Research question:** Identify rare immune cell populations in healthy donor PBMCs.

| Source | Accession | Description | Fallback |
|---|---|---|---|
| **GEO** | `GSE149689` | 10x Chromium PBMCs, 8 healthy donors | Direct FTP |
| **ENCODE** | `ENCSR000EYZ` (optional) | Chromatin accessibility reference | REST API |

**Expected disk usage:** ~500 MB (raw 10x output).

---

## Reproducibility Notes

1. **Seeding** — `BIOAGENT_RANDOM_SEED=42` is set by `scripts/reproduce_benchmark.sh`. Python `random`, `numpy.random`, and `scanpy` seeds are all injected by `bioagent/utils/seeding.py`.
2. **Network variability** — download timestamps, temporary redirect URLs, and server-side metadata fields are excluded from the hash manifest (`benchmarks/expected_hashes.json`) because they legitimately vary between runs.
3. **Graceful fallback** — when an automated download fails, the agent writes `workspace/data/DOWNLOAD_INSTRUCTIONS.md` with exact URLs and shell commands, rather than synthesising fake data. If a reproduction fails on the download step, this file tells the user precisely what to fetch manually.
4. **Ethics / licensing** — all datasets listed here are re-distributable under their respective public licences (TCGA open tier, GEO public release, ENCODE CC0). No patient-identifiable data is touched.
