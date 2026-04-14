"""Conditional edge functions for routing in the research graph."""

from __future__ import annotations

from bioagent.state.schema import ResearchState


def route_from_orchestrator(state: ResearchState) -> str:
    """Route to the node matching ``current_phase``.

    The orchestrator sets ``current_phase``; this function maps it to a node name.
    """
    phase = state.get("current_phase", "literature_review")

    # Map phase names to node names (they match 1:1 for now)
    node_map = {
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
        "complete": "__end__",
    }
    return node_map.get(phase, "__end__")


def route_after_validation(state: ResearchState) -> str:
    """After result_validation, decide whether to proceed or retry.

    Returns
    -------
    str
        "writing" if validation passed,
        "iteration" if retryable (iteration_count < max),
        "hypothesis_generation" if exhausted retries (pivot).
    """
    validation = state.get("validation_status")
    max_iters = 5  # TODO: read from settings

    if validation and validation.get("passed"):
        return "orchestrator"

    if state.get("iteration_count", 0) < max_iters:
        return "iteration"

    # Exhausted — pivot to new hypothesis
    return "orchestrator"


def route_after_review(state: ResearchState) -> str:
    """After self-review, decide whether to finalize or revise.

    Returns
    -------
    str
        "__end__" if review score passes threshold,
        "orchestrator" (→ writing revision) otherwise.
    """
    feedback = state.get("review_feedback", [])
    if not feedback:
        return "__end__"

    latest = feedback[-1] if isinstance(feedback, list) else feedback
    score = latest.get("score", 0) if isinstance(latest, dict) else 0

    if score >= 7:  # 7/10 threshold
        return "__end__"

    return "orchestrator"
