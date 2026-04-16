# BioAgent Development Guide

Deeper dive into the architecture and internals, complementary to `docs/architecture.md` (overview) and `paper/supplementary/S2_methods_detail.md` (academic detail).

## Repository layout

```
bioagent/
├── agents/           Specialised BaseAgent subclasses (one per phase)
├── config/           Pydantic Settings (BIOAGENT_* env vars)
├── state/            ResearchState TypedDict + dedup_add reducer
├── graph/            LangGraph StateGraph (research_graph.py), nodes.py, routing.py
├── llm/              Anthropic client factory + 120-line tool loop
├── tools/
│   ├── literature/   BioMCP, ArXiv, LLM summariser
│   ├── data/         GEO, cBioPortal, GDC, NCBI, ENCODE, URL download
│   ├── execution/    Subprocess Python runner + workspace sandbox
│   ├── bioinformatics/  Template tools (DESeq2, scanpy, GWAS, survival)
│   ├── visualization/   Nature/Science matplotlib themes
│   └── general/      File I/O tools
├── evaluation/       metrics.py (six-dimension scoring), provenance.py
├── export/           Markdown + LaTeX (OUP template) + BibTeX generation
├── cli/              Typer CLI entry points
└── prompts/          Markdown prompt templates (one per agent)

benchmarks/
├── cases/            BenchmarkCase dataclasses (BRAF, TP53, PBMC scRNA)
├── data/             Dataset provenance documentation
├── baselines/        single_prompt, autogen (executed) + biogpt reference
├── ablation.py       Variant factory + runner
└── run_benchmark.py  Full pipeline on a single case

paper/
├── manuscript.tex    Bioinformatics (OUP) format
├── references.bib    28 entries
├── figures/          Generated figures
└── supplementary/    S1-S5

scripts/
├── reproduce_benchmark.sh   Unix
├── reproduce_benchmark.ps1  Windows
└── verify_hashes.py         SHA-256 manifest check

tests/                Pytest modules, 143 tests
.github/workflows/ci.yml   Test + Typecheck + Docker reproducibility jobs
```

## Design decisions

### Why LangGraph?

LangGraph is used *only* for the StateGraph execution model. We do not use LangChain's agent abstractions, tool wrappers, or prompt templates. This keeps the agent loop in `bioagent/llm/tool_loop.py` to ~120 lines, directly against the Anthropic SDK, so debugging is straightforward and there is no hidden behavior layer.

### Why Anthropic SDK directly?

Claude's tool-use API is stable and well-documented. Wrapping it in LangChain adds indirection (message format translation, implicit retries, opaque error handling) that makes failures harder to diagnose. The direct loop is shared by every agent and is covered by unit tests.

### Why no Pydantic on state?

LangGraph requires `TypedDict` (or a compatible dict type) for reducers to work correctly. Pydantic models would add serialization overhead on every state merge. We use Pydantic only for `Settings` where validation is valuable.

### Why subprocess execution, not exec?

`subprocess.run` isolates the AnalystAgent's code in its own Python process with a timeout, matching the security model of a research compute cluster. Any RCE is constrained to the workspace directory and cannot crash the parent LangGraph process.

### Why three-tier data-acquisition fallback?

Empirically, biomedical APIs fail: GDC throttles, cBioPortal occasionally returns HTTP 503, GEO FTP has intermittent timeouts. A single primary source is unreliable. We chose a `primary → secondary → manual instructions` hierarchy so the pipeline always advances, even if the user must complete the download manually. The key invariant: the system never fabricates data.

## State flow

Every node receives the full `ResearchState` and returns a partial update. LangGraph applies updates via the reducer annotated on each field:

- `replace` — last writer wins (default).
- `append` — new items are concatenated.
- `dedup_add` — content-hash-based append (prevents duplicates across iterations).

The orchestrator is special: its `process_result` method writes only `current_phase` and `phase_history`. All other state fields are written exclusively by their owning phase node.

## Adding a new LLM provider

Edit `bioagent/llm/clients.py::get_anthropic_client`. The tool loop uses the Anthropic-compatible `messages.create` signature; any provider with a compatible adapter (including OpenAI via their Anthropic-compat endpoint) works without changes. For a genuinely different API (no `messages.create`), wrap it in a thin compatibility shim.

## Benchmarking a new model

1. Set `BIOAGENT_PRIMARY_MODEL` and `BIOAGENT_ANTHROPIC_BASE_URL` in `.env`.
2. `python benchmarks/run_benchmark.py --case braf_melanoma`.
3. Numbers land in `benchmarks/results/braf_melanoma/evaluation_report.json`.
4. Append a row to `paper/manuscript.tex` Table 1 if you plan to include it.

## Debugging a stuck run

```bash
# See phase history
python -c "
from bioagent.config.settings import settings
import sqlite3
conn = sqlite3.connect(str(settings.checkpoint_path / 'research.db'))
for row in conn.execute('SELECT thread_id, metadata FROM checkpoints ORDER BY created_at DESC LIMIT 5'):
    print(row)
"
```

The per-phase log lines begin with `[<agent_name>]` and are tagged with the thread ID; grep for those.

## Budget protection

`bioagent.llm.token_tracking.global_token_usage` aggregates all Anthropic calls. Before every LLM call, the tool loop checks whether adding the predicted tokens would exceed `settings.cost_budget_usd`; if so, the loop returns early with an explicit budget-exhausted error state. This is also respected by the ReviewAgent revision loop.

## When to open an issue vs a PR

- Small bug with an obvious one-line fix: PR with regression test.
- Behavioural change to an agent or prompt: issue first to discuss scope.
- New agent or tool: PR after reading the "Adding an agent" / "Adding a tool" sections in `CONTRIBUTING.md`.
- Anything that changes the state schema or reducer semantics: issue first.
