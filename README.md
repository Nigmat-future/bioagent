# BioAgent: Autonomous Multi-Agent System for End-to-End Bioinformatics Research

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0+-green.svg)](https://github.com/langchain-ai/langgraph)
[![Anthropic Claude](https://img.shields.io/badge/Claude-Sonnet%204.6-orange.svg)](https://www.anthropic.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-143%20passing-brightgreen.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-48%25-yellow.svg)](pyproject.toml)

Author: Nigmat Rahim    Email: nigmatrahim4@gmail.com/nigmatrahim@stu.pku.edu.cn
BioAgent is an autonomous research system that conducts **end-to-end bioinformatics research** — from literature review and hypothesis generation through computational analysis, scientific writing, and self-review — without human intervention between steps.

## Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │                  ResearchState                  │
                    │  (papers, data_artifacts, hypotheses, results,  │
                    │   paper_sections, figures, review_feedback, …)  │
                    └─────────────────┬───────────────────────────────┘
                                      │ shared by every agent (blackboard)
                               ┌──────▼──────┐
                    ┌──────────│ Orchestrator │◄──────────────────────┐
                    │          │    Agent     │                       │
                    │          └──────┬───────┘                       │
                    │                 │ routes to next phase           │
    ┌──────┬──────┬─┴──────┬────────┬─────────┬──────────┬──────────┐ │
    ▼      ▼      ▼        ▼        ▼         ▼          ▼          ▼ │
┌──────┐┌─────┐┌──────┐┌───────┐┌────────┐┌────────┐┌─────────┐┌──────┐│
│ Lit  ││ Gap ││Planr.││ Exp.  ││ Data   ││Analyst ││ Writer  ││Figure││
│Agent ││Anal.││Agent ││Design ││Acquir. ││Agent   ││ Agent   ││Agent ││
│BioMCP││ LLM ││Hyp+  ││  LLM  ││TCGA/GEO││PyCode +││ IMRAD   ││Nature││
│+ArXiv││     ││rubric││       ││cBio/GDC││sandbox ││sections ││theme ││
│      ││     ││      ││       ││ENCODE  ││+ retry ││ + cites ││+ DPI ││
└──────┘└─────┘└──────┘└───────┘└────────┘└───┬────┘└─────────┘└──────┘│
                                              │ exit 0?               │
                                       ┌──────▼──────┐                │
                                       │ Validation  │─── retry ──┐   │
                                       │ (rules)     │            │   │
                                       └──────┬──────┘            │   │
                                              ▼                   │   │
                                       ┌─────────────┐            │   │
                                       │ Iteration   │────────────┘   │
                                       │ (debug loop)│                │
                                       └─────────────┘                │
                                                                      │
                                             ┌────────────────────────┘
                                      ┌──────▼──────┐
                                      │  Reviewer   │  score ≥ 7 → END
                                      │   Agent     │──────────────────┐
                                      │ (5 dims)    │◄── revise ──┐    │
                                      └─────────────┘             │    │
                                              │ < 7, round < 3    │    │
                                              └───────────────────┘    │
                                                                       ▼
                                                                ┌────────────┐
                                                                │ Export MD  │
                                                                │ + LaTeX    │
                                                                │ + BibTeX   │
                                                                └────────────┘
```

**14-node LangGraph StateGraph** with a conditional orchestrator, a code-execution retry loop, and a review revision loop (max 3 rounds). An optional `human_approval` node sits between the orchestrator and every phase when `BIOAGENT_HUMAN_IN_LOOP=true` for interactive gating.

## Key Features

| Agent | Tools | Capability |
|-------|-------|------------|
| **OrchestratorAgent** | — | LLM-directed phase routing (12 valid phases) |
| **LiteratureAgent** | BioMCP (PubMed/ClinicalTrials/ClinVar/gnomAD/OncoKB/Reactome/KEGG/UniProt/GWAS) + ArXiv | Systematic literature review |
| **PlannerAgent** | BioMCP biological context | Hypothesis generation + experiment design |
| **DataAcquisitionAgent** ★ | 9 tools: GEO / cBioPortal / GDC-TCGA / NCBI E-utilities / ENCODE / direct URL + manual-instructions fallback | Real dataset download with 3-tier fallback hierarchy (never fabricates data) |
| **AnalystAgent** | Python sandbox + 8 bioinformatics templates (scRNA-seq/DE/GWAS/survival) | Code generation + execution + debug loop |
| **WriterAgent** | — | Publication-quality IMRAD paper sections with PMID citations |
| **VisualizationAgent** | Python sandbox + Nature matplotlib theme | Publication figures (300 DPI, Okabe-Ito palette, colour-blind safe) |
| **ReviewAgent** | — | 5-dimension self-review with revision loop gating |

**Infrastructure:**
- LangGraph StateGraph with 14 nodes, conditional routing, iteration loops, and optional human-in-the-loop gating
- Direct Anthropic SDK tool loop (no LangChain overhead)
- SQLite checkpointing for session persistence and resume
- Budget enforcement (token + cost limits)
- Exponential backoff with jitter on API errors
- Path-sandboxed file execution, TLS-configurable network

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/Nigmat-future/bioagent.git
cd bioagent

# Install in development mode (editable)
pip install -e ".[dev]"

# Or, for byte-identical reproduction of benchmark results:
pip install -r requirements-lock.txt
pip install -e .

# Or run in Docker:
docker build -t bioagent:0.2.0 .
docker run --rm -e BIOAGENT_ANTHROPIC_API_KEY=$KEY bioagent:0.2.0 research "Your question"
```

### Configuration

Create a `.env` file in the project root:

```env
BIOAGENT_ANTHROPIC_API_KEY=your-api-key-here
# Optional: override model
BIOAGENT_PRIMARY_MODEL=claude-sonnet-4-5-20250929
# Optional: budget limits
BIOAGENT_TOKEN_BUDGET=500000
BIOAGENT_COST_BUDGET_USD=10.0
```

Or set environment variables directly. BioAgent auto-detects Claude Code's own credentials (`ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_MODEL`, `ANTHROPIC_BASE_URL`).

### Run Research

```bash
# Start a new research session
bioagent research "What is the mechanistic role of BRAF V600E in melanoma pathogenesis?"

# With explicit topic
bioagent research "What are the most effective BRAF inhibitors?" --topic "BRAF melanoma"

# Export a completed session to Markdown + LaTeX
bioagent export --thread <thread-id> --format both

# Check session status
bioagent status --thread <thread-id>

# Resume a paused session
bioagent resume --thread <thread-id>
```

### Programmatic Usage

```python
from bioagent.graph.research_graph import compile_research_graph
from bioagent.tools.execution.sandbox import ensure_workspace

ensure_workspace()
graph = compile_research_graph()

initial_state = {
    "research_topic": "BRAF V600E in melanoma",
    "research_question": "What is the mechanistic role of BRAF V600E?",
    "current_phase": "literature_review",
    # ... (see examples/quickstart.py for full state)
}

for event in graph.stream(initial_state, config={"configurable": {"thread_id": "my-session"}}):
    print(f"Phase: {event.get('current_phase')}")
```

## Configuration Reference

All settings use the `BIOAGENT_` prefix. Full reference:

| Variable | Default | Description |
|----------|---------|-------------|
| `BIOAGENT_ANTHROPIC_API_KEY` | — | Anthropic API key |
| `BIOAGENT_PRIMARY_MODEL` | `claude-sonnet-4-5-20250929` | Model to use |
| `BIOAGENT_MAX_TOKENS` | `4096` | Max output tokens per LLM call |
| `BIOAGENT_MAX_TOOL_CALLS` | `20` | Max tool-use iterations per agent |
| `BIOAGENT_MAX_ITERATIONS` | `5` | Max code execution retries |
| `BIOAGENT_TOKEN_BUDGET` | `500000` | Total token budget (0 = unlimited) |
| `BIOAGENT_COST_BUDGET_USD` | `10.0` | Cost budget in USD (0 = unlimited) |
| `BIOAGENT_CODE_TIMEOUT` | `120` | Code execution timeout (seconds) |
| `BIOAGENT_RANDOM_SEED` | `42` | Random seed for reproducibility |
| `BIOAGENT_WORKSPACE_DIR` | `workspace` | Working directory for outputs |
| `BIOAGENT_CHECKPOINT_DIR` | `checkpoints` | SQLite checkpoint directory |
| `BIOAGENT_USE_SQLITE_CHECKPOINTS` | `true` | Enable session persistence |
| `BIOAGENT_HUMAN_IN_LOOP` | `false` | Require human approval per phase |
| `BIOAGENT_TLS_VERIFY` | `true` | TLS certificate verification |
| `BIOAGENT_LOG_LEVEL` | `INFO` | Logging verbosity |

## Evaluation

BioAgent includes a benchmark framework for systematic evaluation:

```bash
# Run the BRAF melanoma benchmark case
python benchmarks/run_benchmark.py --case braf_melanoma

# Run all three benchmark cases
python benchmarks/run_benchmark.py --case all --output benchmarks/results/
```

Evaluation metrics are computed across six dimensions:
- **Literature coverage** — Precision/Recall vs. gold-standard PMIDs
- **Hypothesis quality** — Novelty, testability, literature grounding
- **Analysis correctness** — Code execution success rate, statistical validity
- **Writing completeness** — Section coverage, word count, readability (Flesch score)
- **Figure quality** — Count, caption coverage, file presence
- **Efficiency** — Token usage, cost, self-review score

## Output Structure

After a successful run, the workspace contains:

```
workspace/
├── data/           — input data files (CSV, HDF5, etc.)
├── scripts/        — auto-generated Python analysis scripts
├── figures/        — publication-ready figures (PDF + PNG, 300 DPI)
└── output/
    ├── manuscript.md    — Markdown manuscript
    ├── manuscript.tex   — LaTeX manuscript (Bioinformatics OUP format)
    ├── references.bib   — BibTeX bibliography
    └── provenance.json  — full audit trail (model, seed, hashes, timings)
```

## Citation

If you use BioAgent in your research, please cite:

```bibtex
@article{rahim2026bioagent,
  title   = {BioAgent: An Autonomous Multi-Agent System for End-to-End Bioinformatics Research},
  author  = {Rahim, Nigmat},
  journal = {Bioinformatics},
  year    = {2026},
  note    = {Under review. Preprint at \url{https://github.com/Nigmat-future/bioagent}}
}
```

## License

MIT License. See [LICENSE](LICENSE) for details.
