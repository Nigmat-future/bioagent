# Supplementary Material S2 — Methods Detail

This document provides the implementation-level detail omitted from the main-text Methods section for space. All references are to `bioagent/` in the v0.2.0 release (tag `v0.2.0`).

## S2.1 State Schema

`bioagent/state/schema.py` declares `ResearchState` as a TypedDict with 33 typed fields, each annotated with a reducer (the LangGraph convention for merge semantics):

| Field | Type | Reducer | Purpose |
|---|---|---|---|
| `research_topic` | `str` | replace | Short topic label |
| `research_question` | `str` | replace | Full natural-language question |
| `constraints` | `list[str]` | `dedup_add` | User constraints |
| `current_phase` | `str` | replace | Active phase name |
| `phase_history` | `list[str]` | append | Trace of visited phases |
| `papers` | `list[dict]` | `dedup_add` | PMID-keyed literature hits |
| `literature_summary` | `str` | replace | LLM-generated synthesis |
| `research_gaps` | `list[str]` | `dedup_add` | Identified open problems |
| `hypotheses` | `list[dict]` | `dedup_add` | Generated hypotheses with scores |
| `selected_hypothesis` | `dict \| None` | replace | Top-ranked hypothesis |
| `experiment_plan` | `dict \| None` | replace | Detailed plan |
| `data_status` | `dict \| None` | replace | `{status, datasets_requested, datasets_acquired, summary, manual_instructions}` |
| `data_artifacts` | `list[dict]` | `dedup_add` | `[{path, description, size}, ...]` |
| `code_artifacts` | `list[dict]` | `dedup_add` | Generated scripts |
| `execution_results` | `list[dict]` | `dedup_add` | stdout/stderr/exit codes |
| `analysis_results` | `list[dict]` | `dedup_add` | Structured findings |
| `validation_status` | `str \| None` | replace | `passed` / `failed` / `pending` |
| `paper_sections` | `dict[str, str]` | replace | IMRAD sections by name |
| `references` | `list[dict]` | `dedup_add` | Citation entries |
| `paper_metadata` | `dict` | replace | Title, authors, keywords |
| `figures` | `list[dict]` | `dedup_add` | Generated figures |
| `review_feedback` | `list[str]` | append | Reviewer comments |
| `revision_notes` | `list[str]` | append | Writer's revision notes |
| `review_count` | `int` | increment | Review loop counter |
| `iteration_count` | `int` | increment | Code-exec retry counter |
| `errors` | `list[str]` | append | All captured errors |
| `messages` | `list[dict]` | append | LLM message history |
| `human_feedback` | `str \| None` | replace | Human-in-loop input |
| `should_stop` | `bool` | replace | Emergency halt flag |

The `dedup_add` reducer (`bioagent/state/reducers.py`) computes a SHA-256 hash of each item's stable representation and appends only if the hash is new. This prevents duplicated tool calls across iterations and keeps state size linear in unique facts.

## S2.2 Tool-Use Loop

The core LLM/tool interaction is a ~120-line function `bioagent.llm.tool_loop.run_tool_loop` shared by every agent. It implements the Anthropic tool-use protocol:

1. Call `client.messages.create(...)` with tools and conversation history.
2. If the response contains `tool_use` blocks: execute each corresponding Python callable, capture output, append `tool_result` blocks.
3. Repeat until the model returns only `text` blocks (no more tool calls) or the iteration budget is exhausted.
4. Accumulate token usage in a global `TokenUsage` counter for budget enforcement.

The loop is defensively coded for:
- empty `tool_input` (defaults to `{}`),
- `cache_creation_input_tokens` being `None` in glm-5.1 (uses `or 0`),
- subprocess encoding errors on Windows (all `subprocess.run` calls pin `encoding="utf-8", errors="replace"`),
- TLS/proxy bypass (`httpx.Client(proxy=None, verify=settings.tls_verify)` at `bioagent/llm/clients.py:13`).

## S2.3 DataAcquisition Fallback Hierarchy

For every primary data source, `bioagent.tools.data.*` implements three tiers:

| Source | Tier 1 (preferred) | Tier 2 | Tier 3 (human) |
|---|---|---|---|
| GEO | GEOparse library | Direct FTP to `_series_matrix.txt.gz` | `manual_instructions.py` |
| cBioPortal | BioMCP `cbioportal` commands | REST API `www.cbioportal.org/api` | Manual |
| GDC/TCGA | GDC REST filter API | File-UUID direct download | Manual |
| NCBI | BioPython Entrez | E-utilities raw HTTP | Manual |
| ENCODE | ENCODE REST API + file href | Direct S3 URL | Manual |

Every downloader returns a status string formatted as `SUCCESS: ...`, `ERROR: ...`, or `MANUAL: path/to/instructions.md`. The `DataAcquisitionAgent.process_result` parser counts these to populate `data_status.datasets_acquired` / `datasets_failed`.

## S2.4 Reproducibility Hooks

Seeds are injected into three places:

- `numpy.random.seed(settings.random_seed)` and `random.seed(settings.random_seed)` at the top of every AnalystAgent-generated script via a template prelude.
- `BIOAGENT_RANDOM_SEED` is read from the environment by `bioagent.config.settings` and defaults to `42`.
- Scanpy's `sc.settings.seed` is set when scanpy is imported.

Provenance is captured by `bioagent.evaluation.provenance.record_provenance`, which writes a `PROVENANCE.json` file to the output directory containing: model name, timestamp, git SHA of the BioAgent repo, SHA-256 hashes of every file in `workspace/data/` and `workspace/figures/`, and total token usage. The reproducibility test (`scripts/verify_hashes.py`) compares this manifest against `benchmarks/expected_hashes.json` for byte-level verification.

## S2.5 Evaluation Metrics (Formal Definitions)

Let $P$ = retrieved PMID set, $G$ = gold-standard PMID set (from `benchmarks/cases/*.py`).

- **Literature precision** = $|P \cap G| / |P|$ (0 when $|P| = 0$)
- **Literature recall** = $|P \cap G| / |G|$
- **Literature score** = $10 \cdot (0.5 \cdot \text{precision} + 0.5 \cdot \text{recall})$
- **Hypothesis score** = $\min(10, \text{novelty} + \text{testability})$ for the selected hypothesis (0 if none selected)
- **Analysis score** = $10 \cdot (\text{exit-0 rate}) \cdot (1 + 0.1 \cdot |\text{code\_artifacts}|)$ capped at 10
- **Figure score** = $\min(10, 2 \cdot |\text{figures}|)$
- **Writing score** = $10 \cdot \min(1, |\text{sections}| / 5)$ (IMRAD completeness)
- **Efficiency score** = $10 \cdot \exp(-\text{cost\_usd} / 5)$

The **weighted composite** reported in the paper is:

$$
\text{Composite} = 0.25 \cdot \text{lit} + 0.15 \cdot \text{hyp} + 0.25 \cdot \text{anal} + 0.15 \cdot \text{fig} + 0.15 \cdot \text{write} + 0.05 \cdot \text{eff}
$$

Weights and the closed-form formulas are in `bioagent/evaluation/metrics.py`. The rubric was chosen to reward grounded retrieval and executable analysis over pure text generation — this is intentionally biased toward the full pipeline and against baselines that cannot ground claims or run code.

## S2.6 Prompt Templates

All prompt templates live in `bioagent/prompts/` as Markdown files:

- `orchestrator.md` — phase-routing rubric (~2 KB)
- `literature.md` — BioMCP query strategy and extraction format
- `planner.md` — hypothesis generation with novelty/testability scoring rubric
- `data_acquisition.md` — fallback hierarchy and output format contract
- `analyst.md` — code-writing constraints (no synthetic data, use `workspace/data/` only)
- `writer.md` — IMRAD structure and citation format
- `visualization.md` — Nature-theme matplotlib code templates
- `review.md` — 5-dimension scoring rubric

Each template is loaded lazily at agent-run time so that users can edit them without reinstalling the package.
