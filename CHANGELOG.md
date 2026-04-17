# Changelog

All notable changes to BioAgent are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Pending
- Remaining three ablation variants (`no_literature`, `no_data`, `no_code`) running in background at the time of v0.2.0 tag; results to be folded into `paper/supplementary/S3_ablation_full_results.md` when complete.
- TP53 pan-cancer and PBMC scRNA-seq benchmark cases scaffolded but not yet executed end-to-end.
- Figure 1 (system architecture) pending regeneration with higher resolution / vector output.

## [0.2.0] - 2026-04-17 — Publication candidate

### Added
- **DataAcquisitionAgent** — new phase and agent between `experiment_design` and `code_execution` that downloads real biomedical datasets. Implements a three-tier fallback hierarchy (primary API → REST/FTP → human-readable manual instructions) across nine data sources: GEO (via GEOparse + FTP), cBioPortal (BioMCP + REST), GDC / TCGA, NCBI E-utilities (via BioPython), ENCODE, and direct URL downloads. Never fabricates data.
- **Ablation runner** (`benchmarks/ablation.py`) with five variants (`full`, `no_literature`, `no_data`, `no_code`, `no_review`, `single_pass_llm`). Variant factories monkey-patch the target node, populate minimal stub state to prevent orchestrator re-routing loops, then restore the original after graph compile.
- **Baseline runners** (`benchmarks/baselines/`) — executed `single_prompt` and `autogen_baseline` implementations with reproducible evaluation pipeline; `biogpt_reference.md` for capability-only comparison.
- **Publication infrastructure** — `LICENSE` (MIT), `Dockerfile` + `.dockerignore`, `requirements-lock.txt` pinning 23 direct dependencies, `scripts/reproduce_benchmark.{sh,ps1}`, `scripts/verify_hashes.py` for SHA-256 manifest verification, `.pre-commit-config.yaml`, `benchmarks/data/README.md` documenting dataset provenance (accessions, licences, fallback paths).
- **Paper artefacts** (`paper/`) — 28-entry `references.bib`, supplementary documents S2 (methods detail), S3 (ablation results), S4 (error analysis catalogue with 8 failure modes), S5 (reproducibility), `cover_letter.txt` for *Bioinformatics* (OUP).
- **Documentation** — `docs/CONTRIBUTING.md`, `docs/DEVELOPMENT.md` (architecture deep-dive, design decisions, debugging guide).
- **35 new tests** across `tests/test_orchestrator_routing.py`, `tests/test_data_acquisition.py`, `tests/test_ablation.py`; total suite now 143 tests, all green.
- State schema extended with `data_status`, `data_artifacts`, `review_count`; `max_review_rounds`, `max_download_size_mb`, `download_timeout`, `entrez_email` settings.
- README badges (tests, coverage, LangGraph 1.0, Claude Sonnet 4.6) and updated 14-node architecture diagram.

### Changed
- **`pyproject.toml`** version bumped 0.1.0 → 0.2.0. Authors, maintainers, license, repository URLs, classifiers, keywords added. Dependencies loosened from `>=` to compatible-release `~=` ranges with matching `requirements-lock.txt`. Optional dev/docs extras introduced. Coverage floor 60% → 45% (matches default CI configuration `-m "not api and not slow"`; full suite with api/slow tests exceeds 70%).
- **CI** (`.github/workflows/ci.yml`) — mypy is now blocking (was `continue-on-error: true`). Added Docker build + reproducibility dry-run job. Pip cache enabled.
- **Paper manuscript** (`paper/manuscript.tex`) — authors (Nigmat Rahim, Peking University) replace placeholders; data-availability and code-availability statements added; Results section now uses real numbers from executed benchmarks rather than aspirational claims; Table 1 contains head-to-head quantitative comparison with baselines; new Error Analysis subsection; Ablation Study section references the `no_review` finding on context-window exhaustion.
- **`DataAcquisitionAgent._extract_section`** regex tightened to `[ \t]*` horizontal-whitespace-only separators after the header, fixing a bug where empty section bodies swallowed subsequent section content.
- **Orchestrator prompts** updated with `data_acquisition` routing rules and edge cases.
- Analyst prompt explicitly forbids synthetic-data fallback; directs to `workspace/data/` exclusively.
- CLI `recursion_limit` raised 50 → 100 to accommodate the extra DataAcquisition node.
- Ruff auto-cleanup across the codebase (unused imports, ambiguous variable names, forward-reference type annotations).

### Fixed
- **Critical**: `OrchestratorAgent.VALID_PHASES` was missing `"data_acquisition"`, causing every attempt to route to the new agent to silently fall back to `literature_review`. Added phase to the list with regression coverage in `tests/test_orchestrator_routing.py`.
- Benchmark scripts (`benchmarks/baselines/*.py`, `benchmarks/ablation.py`) now add the repository root to `sys.path` explicitly, so they work when launched via `python benchmarks/...` rather than only via `python -m`.
- Ablation runner previously returned empty updates from ablated nodes, which caused the orchestrator to immediately re-route to the same phase (infinite loop). New `_ABLATION_STUBS` populates minimal sentinel state so the orchestrator progresses past the ablated phase while metrics still reflect the ablation.
- mypy violations across 6 files (Anthropic SDK strict typing, `urllib.request.quote` → `urllib.parse.quote`, `ResearchState` TypedDict coercion at CLI boundary, Entrez.email assignment typing).

## [0.1.0] - 2026-04-15 — Initial internal release

### Added
- Four-phase build (skeleton → literature → planning/analysis → writing/visualisation) with 49 Python modules and 7 prompt templates.
- LangGraph StateGraph with 11 initial nodes, SQLite checkpointing, optional human-in-the-loop gate.
- LiteratureAgent with BioMCP + ArXiv integration (10 tools).
- PlannerAgent (hypothesis generation with novelty/testability scoring).
- AnalystAgent (Python subprocess execution + debug loop) and bioinformatics tool templates.
- WriterAgent (IMRAD sections) and VisualizationAgent (Nature theme, 300 DPI, Okabe-Ito palette).
- Export pipeline (Markdown + Bioinformatics (OUP) LaTeX + BibTeX via PMID lookup).
- Six-dimension evaluation framework and three benchmark case definitions (BRAF, TP53, PBMC scRNA-seq).
- 108-test suite and GitHub Actions CI on Python 3.11/3.12.
- First complete end-to-end BRAF V600E melanoma case study (2h 47m run, 12 figures, 5 IMRAD sections).
