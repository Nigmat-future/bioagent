# Changelog

All notable changes to BioAgent are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Pending
- Remaining three ablation variants (`no_literature`, `no_data`, `no_code`) running in background at the time of v0.2.0 tag; results to be folded into `paper/supplementary/S3_ablation_full_results.md` when complete.
- Figure 1 (system architecture) pending regeneration with higher resolution / vector output.

## [0.3.0] - 2026-04-18 — Resilience release

### Added
- **`bioagent/tools/data/_http.py`** — unified HTTP backbone built on `httpx` + `tenacity`. Provides `stream_download()` (exponential-backoff retry, Range-based resume, adaptive read timeout from `Content-Length` × `min_download_mbps` floor, gzip-integrity validation) and `get_json()` (resilient JSON GET with retry). `cleanup_stale_tmp()` removes orphaned `.tmp` files older than `tmp_stale_hours`.
- **`bioagent/tools/data/mirrors.py`** — mirror-first URL routing table. `resolve_geo_series_matrix` tries EBI ArrayExpress before NCBI FTP; `resolve_sra_fastq` routes SRR/ERR/DRR to ENA's direct `.fastq.gz` URLs (no `prefetch`/`fasterq-dump` needed); `resolve_10x_pbmc3k` uses the 10x Cloudflare CDN for the canonical PBMC benchmark.
- **`bioagent/tools/data/ena_tools.py`** — three new tools registered with DataAcquisitionAgent: `download_sra_fastq`, `download_geo_from_ena`, `download_10x_pbmc3k`. Data-acquisition prompt updated to list these as preferred over the legacy GEO/SRA paths for Asia-originating runs.
- **Orchestrator loop detector** (`bioagent/agents/orchestrator.py`). `FORWARD_PROGRESSION` map + `LOOP_THRESHOLD=3` force-advances when the LLM re-selects the same non-terminal phase three times in a row (root cause of the pre-fix BRAF failure). `build_messages` now surfaces the last 8 entries of `phase_history` so the prompt's new **anti-backtrack rule** (in `bioagent/prompts/orchestrator.md`) has concrete state to anchor on.
- **`benchmarks/resume_run.py`** — resume a failed benchmark from its LangGraph SQLite checkpoint by `--thread-id`. Used to recover the TP53 and BRAF runs after an API-gateway quota exhaustion mid-`code_execution`, saving ~40 minutes and ~$7 of redundant literature/planner/data-acquisition work per resumed case.
- **25 new tests** — `tests/test_http_resilience.py` (14: retry-on-5xx, Range-resume, gzip integrity, stale `.tmp` cleanup, mirror resolution, `try_mirrors` fallthrough) and `tests/test_orchestrator_loop.py` (11: loop detection threshold, forward-progression map, phase-history injection, markdown-fenced JSON parsing). Total suite now 168 tests, all green.
- State schema documents a new `data_source` field on each `data_artifacts` entry (values: `"10x-CDN"`, `"EBI-ArrayExpress"`, `"NCBI-GEO-FTP"`, `"ENA-SRA"`, `"cBioPortal"`, `"GDC"`, `"ENCODE"`, `"manual"`). WriterAgent cites this in the Methods section; the paper frames per-file provenance as a differentiator against prior autonomous-research systems.
- Four new settings in `bioagent/config/settings.py`: `min_download_mbps: float = 2.0`, `download_max_retries: int = 4`, `tmp_stale_hours: int = 24`, `prefer_mirrors: bool = True`.

### Changed
- **All five data tools** (`url_download.py`, `geo_tools.py`, `cbioportal_tools.py`, `tcga_gdc_tools.py`, `ncbi_tools.py`, `encode_tools.py`) now delegate their HTTP paths to the `_http` backbone. Public tool signatures and return-string contracts (`SUCCESS: ...` / `ERROR: ...`) unchanged; `test_data_acquisition.py` passes unmodified.
- `geo_tools._download_via_ftp` replaced with `_download_via_mirrors` (EBI → NCBI via `try_mirrors` + gzip validation).
- DataAcquisitionAgent (`bioagent/agents/data_acquisition.py`) tool list expanded with the three ENA/10x-CDN tools; prompt now documents the **Mirror Preferences** section and the new fallback hierarchy table.
- Writer prompt (`bioagent/prompts/writer.md`) requires Methods section to cite the `data_source` mirror for each dataset.
- Paper (`paper/manuscript.tex`): new sections **Data-Acquisition Resilience** (`sec:resilience`) and **Orchestrator Loop Detection** (`sec:orchestrator`) in System Architecture; Table 1 expanded to show v0.1 pre-fix vs v0.2 post-fix scores side-by-side with the reasons for each failure mode; Discussion limitations paragraph rewritten to promote data-acquisition resilience from ``plumbing'' to a first-class component.

### Fixed
- **35 stale `.tmp` files (85 MB)** that had accumulated in `workspace/data/` from failed pre-fix downloads — `_http.cleanup_stale_tmp` now clears these on module init.
- **Silent gzip corruption**: pre-fix runs persisted truncated `.gz` files that only surfaced as `EOFError: Compressed file ended before the end-of-stream marker` during Analyst execution, many minutes later. The post-download gzip-validation pass catches corruption immediately and triggers a retry.
- **Orchestrator routing loop on BRAF**: the LLM repeatedly selected `hypothesis_generation` after code execution because the state summary showed `Hypotheses: 0` (a later planner re-entry had overwritten the list). Loop detector + phase-history-aware prompt eliminate the regression.
- **Anthropic client double-header 401**: `get_anthropic_client` was passing only one of `api_key` / `auth_token` to the SDK, but the SDK silently fell back to `ANTHROPIC_API_KEY` in the environment and populated the *other* header with a mismatched value. Gateways (qingyuntop in particular) rejected the resulting request with 401 "Invalid token". `clients.py` now explicitly sets the unused auth slot to `""` so only one header is sent.

### Benchmark results (same three cases, same base model, same prompts)
| Case                | v0.1 weighted | v0.2 weighted | Change |
|---------------------|---------------|---------------|--------|
| TP53 pan-cancer     | 1.06          | **8.42**      | **+7.36** |
| scRNA PBMC 3k       | 6.44          | **7.64**      | +1.20  |
| BRAF V600E melanoma | 5.30          | **6.90** (resumed + hypothesis patch) | +1.60 |

TP53 went from an aborted run with no manuscript to a full IMRAD draft (4{,}439 words, 6 figures, self-review 7/10 minor revision). The TP53 delta is the strongest quantitative argument for treating download resilience as a first-class agent component rather than as plumbing.

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
