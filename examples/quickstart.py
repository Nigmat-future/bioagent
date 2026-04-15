"""BioAgent quickstart — minimal programmatic usage example.

Run from the project root:
    python examples/quickstart.py
"""

from __future__ import annotations

import uuid

from bioagent.graph.research_graph import compile_research_graph
from bioagent.tools.execution.sandbox import ensure_workspace
from bioagent.utils.logging_config import setup_logging

setup_logging(level="INFO")

# Prepare workspace directories
ensure_workspace()

# Compile the LangGraph research graph
graph = compile_research_graph()

# Define the initial research state
initial_state = {
    "research_topic": "BRAF V600E mutation in melanoma",
    "research_question": (
        "What is the mechanistic role of BRAF V600E mutation in melanoma "
        "pathogenesis, and what are the most effective targeted therapeutic strategies?"
    ),
    "current_phase": "literature_review",
    "phase_history": [],
    "iteration_count": 0,
    "papers": [],
    "literature_summary": "",
    "research_gaps": [],
    "knowledge_base": {},
    "hypotheses": [],
    "selected_hypothesis": None,
    "experiment_plan": None,
    "code_artifacts": [],
    "execution_results": [],
    "data_artifacts": [],
    "analysis_results": [],
    "validation_status": None,
    "paper_sections": {},
    "references": [],
    "paper_metadata": {},
    "figures": [],
    "review_feedback": [],
    "revision_notes": [],
    "messages": [],
    "errors": [],
    "human_feedback": None,
    "should_stop": False,
}

thread_id = str(uuid.uuid4())
config = {"configurable": {"thread_id": thread_id}}

print(f"Starting BioAgent research (thread: {thread_id})")
print(f"Question: {initial_state['research_question']}\n")

final_state = initial_state
for step, event in enumerate(graph.stream(initial_state, config=config, stream_mode="values"), 1):
    final_state = event
    phase = event.get("current_phase", "?")
    papers = len(event.get("papers", []))
    sections = list(event.get("paper_sections", {}).keys())
    print(f"Step {step:2d} | Phase: {phase:<25} | Papers: {papers} | Sections: {sections}")

    if step >= 50:
        print("Stopping at 50 steps.")
        break

# Summary
print(f"\n{'='*60}")
print(f"Research complete!")
print(f"Papers found: {len(final_state.get('papers', []))}")
print(f"Hypotheses: {len(final_state.get('hypotheses', []))}")
print(f"Sections written: {list(final_state.get('paper_sections', {}).keys())}")
print(f"Figures: {len(final_state.get('figures', []))}")
print(f"Thread ID: {thread_id}")
print(f"\nResume with: bioagent resume --thread {thread_id}")
print(f"Export with: bioagent export --thread {thread_id} --format both")
