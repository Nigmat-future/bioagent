# BioAgent Architecture

## Overview

BioAgent implements a **blackboard multi-agent architecture** using LangGraph's `StateGraph`. All agents share a single `ResearchState` object (the blackboard). Each agent reads relevant fields, invokes tools via the Anthropic SDK's native tool-use protocol, and writes structured results back to state. The orchestrator agent directs which agent runs next.

## LangGraph StateGraph

```
START
  │
  ▼
orchestrator ──┐
  ▲            │ route_from_orchestrator()
  │            ▼
  ├── literature_review
  ├── gap_analysis
  ├── hypothesis_generation
  ├── experiment_design
  ├── code_execution ──► result_validation ──► iteration ──┐
  │                           │                            │
  │                           │ pass                       └──► code_execution
  ├── writing                 ▼
  ├── figure_generation    orchestrator
  └── review ──► END (score ≥ 7) or orchestrator (revision)
```

### Nodes

| Node | Agent / Logic | Key State Outputs |
|------|--------------|-------------------|
| `orchestrator` | OrchestratorAgent (single LLM call) | `current_phase`, `phase_history` |
| `literature_review` | LiteratureAgent + 10 tools | `papers`, `literature_summary`, `research_gaps`, `references` |
| `gap_analysis` | Direct LLM call | `research_gaps` (refined) |
| `hypothesis_generation` | PlannerAgent | `hypotheses`, `selected_hypothesis` |
| `experiment_design` | PlannerAgent | `experiment_plan` |
| `code_execution` | AnalystAgent + 8 tools | `code_artifacts`, `execution_results`, `analysis_results`, `figures` |
| `result_validation` | Rules-based | `validation_status` |
| `iteration` | Counter increment | `iteration_count` |
| `writing` | WriterAgent | `paper_sections` |
| `figure_generation` | VisualizationAgent + 5 tools | `figures` |
| `review` | Direct LLM call | `review_feedback`, `revision_notes`, auto-export |

### Conditional Routing

- **`route_from_orchestrator()`** — maps `current_phase` to node names
- **`route_after_validation()`** — pass → orchestrator; fail + retries → iteration; exhausted → orchestrator
- **`route_after_review()`** — score ≥ 7 → END (auto-export); else → orchestrator for revision

## ResearchState Schema

The full state (`bioagent/state/schema.py`) has 30+ fields organized in 9 groups:

```python
class ResearchState(TypedDict, total=False):
    # Input
    research_topic: str
    research_question: str
    constraints: list[str]

    # Phase tracking
    current_phase: str
    phase_history: Annotated[list[str], dedup_add]
    iteration_count: int

    # Literature knowledge
    papers: Annotated[list[dict], dedup_add]      # PMIDs + metadata
    literature_summary: str
    research_gaps: Annotated[list[str], dedup_add]

    # Hypotheses & planning
    hypotheses: Annotated[list[dict], dedup_add]  # with novelty/testability scores
    selected_hypothesis: Optional[dict]
    experiment_plan: Optional[dict]

    # Code & execution
    code_artifacts: Annotated[list[dict], dedup_add]
    execution_results: Annotated[list[dict], dedup_add]

    # Analysis & writing
    analysis_results: Annotated[list[dict], dedup_add]
    paper_sections: dict                          # {"abstract": {"content":..., "version":1}}
    references: Annotated[list[dict], dedup_add] # for BibTeX generation
    figures: Annotated[list[dict], dedup_add]

    # Review
    review_feedback: Annotated[list[dict], dedup_add]
    revision_notes: Annotated[list[str], dedup_add]
```

**Reducers:** List fields use `dedup_add` (SHA-256 content-hash deduplication) so agents can freely append without creating duplicates across retries.

## Agent Lifecycle

Every agent inherits from `BaseAgent` and follows this lifecycle:

```
agent.run(state)
  │
  ├── get_system_prompt(state)  → loads prompts/<name>.md
  ├── get_tools()               → registers tools (idempotent), returns definitions
  ├── build_messages(state)     → constructs user message from state fields
  │
  └── run_tool_loop(...)        → Anthropic SDK tool-use loop
        │
        ├── client.messages.create(tools=..., messages=...)
        ├── [tool block] → execute_tool() → append result
        └── [text block] → return (final_text, conversation)
           │
           └── process_result(final_text, conversation, state)
                 → parse structured output → return state update dict
```

## Tool Registry

`bioagent/tools/registry.py` provides a singleton `ToolRegistry` that:
1. Maps tool names to Python callables and Anthropic `tools=` format dicts
2. Supports name-filtered retrieval (`get_definitions(names)`, `get_functions(names)`)
3. Warns on overwrite (all `register_tools()` functions guard with idempotency checks)

## LLM Tool Loop

`bioagent/llm/tool_loop.py` implements the core agentic loop:

```python
def run_tool_loop(client, model, system_prompt, messages, tools, tool_functions, ...):
    for iteration in range(max_iterations):
        response = _call_with_retry(...)           # exponential backoff on 429/5xx
        global_token_usage.add(...).check_budget() # budget enforcement
        if response has tool_use blocks:
            for each tool: _execute_tool(name, input, tool_functions)
            append tool_results to conversation
        else:
            return (final_text, conversation)
```

## Export Pipeline

On review acceptance (score ≥ 7), `_auto_export()` in `nodes.py` triggers:

1. `export_markdown()` — assembles `manuscript.md` from `paper_sections` + figures + references
2. `export_latex()` — renders `manuscript.tex` (Bioinformatics OUP format) + `references.bib`
3. `record_provenance()` — writes `provenance.json` with model/seed/env/hash audit trail

## Evaluation Framework

`bioagent/evaluation/metrics.py` computes `EvaluationReport` with:
- 6 dimension scores (0–10 each)
- Weighted composite score matching Bioinformatics journal rubric
- Precision/Recall vs. gold-standard PMIDs (when benchmark case provided)
- Flesch-Kincaid readability score for writing

## Reproducibility

Every Python script executed by AnalystAgent/VisualizationAgent is prefixed with:
```python
import random; random.seed(42)
import numpy as np; np.random.seed(42)
# (torch seed if available)
```

The seed is configured via `BIOAGENT_RANDOM_SEED` (default 42). Provenance JSON records the seed, model, environment, and content hashes of all inputs/outputs.
