"""LangGraph research graph — wires together all nodes and routing."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from bioagent.state.schema import ResearchState

logger = logging.getLogger(__name__)


def build_research_graph() -> StateGraph:
    """Construct and compile the research workflow graph.

    The graph flows:
        START → orchestrator → (phase node) → orchestrator → ... → END

    The orchestrator decides which phase to enter next. Each phase node
    returns to the orchestrator for re-routing. Special cases:
      - result_validation can route to iteration (retry) or orchestrator
      - review can route to END or back to orchestrator for revision
      - When human_in_loop is enabled, a human_approval gate sits between
        orchestrator and phase nodes at critical decision points.
    """
    from bioagent.config.settings import settings
    from bioagent.graph.nodes import (
        code_execution_node,
        experiment_design_node,
        figure_generation_node,
        gap_analysis_node,
        human_approval_node,
        hypothesis_generation_node,
        iteration_node,
        literature_review_node,
        orchestrator_node,
        result_validation_node,
        review_node,
        writing_node,
    )
    from bioagent.graph.routing import (
        route_after_review,
        route_after_validation,
        route_from_orchestrator,
    )

    graph = StateGraph(ResearchState)

    # ── Add all nodes ──────────────────────────────────────────
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("literature_review", literature_review_node)
    graph.add_node("gap_analysis", gap_analysis_node)
    graph.add_node("hypothesis_generation", hypothesis_generation_node)
    graph.add_node("experiment_design", experiment_design_node)
    graph.add_node("code_execution", code_execution_node)
    graph.add_node("result_validation", result_validation_node)
    graph.add_node("iteration", iteration_node)
    graph.add_node("writing", writing_node)
    graph.add_node("figure_generation", figure_generation_node)
    graph.add_node("review", review_node)

    # Human approval node (only active when human_in_loop is True)
    if settings.human_in_loop:
        graph.add_node("human_approval", human_approval_node)

    # ── Entry point ────────────────────────────────────────────
    graph.set_entry_point("orchestrator")

    # ── Orchestrator → phase nodes (conditional) ───────────────
    # When human_in_loop: orchestrator routes to human_approval first,
    # then human_approval routes to the actual phase node.
    # Otherwise: orchestrator routes directly to phase nodes.
    if settings.human_in_loop:
        from bioagent.graph.routing import route_from_orchestrator_with_approval

        graph.add_conditional_edges(
            "orchestrator",
            route_from_orchestrator_with_approval,
            {
                "human_approval": "human_approval",
                "__end__": END,
            },
        )

        # human_approval routes to the actual phase node
        graph.add_conditional_edges(
            "human_approval",
            route_from_orchestrator,  # re-use the same phase mapping
            {
                "literature_review": "literature_review",
                "gap_analysis": "gap_analysis",
                "hypothesis_generation": "hypothesis_generation",
                "experiment_design": "experiment_design",
                "code_execution": "code_execution",
                "result_validation": "result_validation",
                "iteration": "iteration",
                "writing": "writing",
                "figure_generation": "figure_generation",
                "review": "review",
                "__end__": END,
            },
        )
    else:
        graph.add_conditional_edges(
            "orchestrator",
            route_from_orchestrator,
            {
                "literature_review": "literature_review",
                "gap_analysis": "gap_analysis",
                "hypothesis_generation": "hypothesis_generation",
                "experiment_design": "experiment_design",
                "code_execution": "code_execution",
                "result_validation": "result_validation",
                "iteration": "iteration",
                "writing": "writing",
                "figure_generation": "figure_generation",
                "review": "review",
                "__end__": END,
            },
        )

    # ── Phase nodes → orchestrator (standard flow) ─────────────
    for node in [
        "literature_review",
        "gap_analysis",
        "hypothesis_generation",
        "experiment_design",
        "writing",
        "figure_generation",
    ]:
        graph.add_edge(node, "orchestrator")

    # ── Iteration → code execution (retry loop) ────────────────
    graph.add_edge("iteration", "code_execution")

    # ── Code execution → result validation ─────────────────────
    graph.add_edge("code_execution", "result_validation")

    # ── Result validation → orchestrator or iteration ───────────
    graph.add_conditional_edges(
        "result_validation",
        route_after_validation,
        {
            "orchestrator": "orchestrator",
            "iteration": "iteration",
        },
    )

    # ── Review → END or back to orchestrator ───────────────────
    graph.add_conditional_edges(
        "review",
        route_after_review,
        {
            "__end__": END,
            "orchestrator": "orchestrator",
        },
    )

    return graph


def compile_research_graph():
    """Build and compile the graph with optional checkpointing."""
    graph = build_research_graph()

    try:
        from bioagent.config.settings import settings

        if settings.use_sqlite_checkpoints:
            from langgraph.checkpoint.sqlite import SqliteSaver

            checkpoint_path = settings.checkpoint_path / "research.db"
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            checkpointer = SqliteSaver.from_conn_string(str(checkpoint_path))
            return graph.compile(checkpointer=checkpointer)
    except ImportError:
        logger.warning("sqlite checkpointer not available, using in-memory")
    except Exception as exc:
        logger.warning("Checkpointing failed (%s), compiling without", exc)

    return graph.compile()
