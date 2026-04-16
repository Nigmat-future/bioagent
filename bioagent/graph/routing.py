"""Conditional edge functions for routing in the research graph."""

from __future__ import annotations

import logging

from bioagent.state.schema import ResearchState

logger = logging.getLogger(__name__)


def route_from_orchestrator(state: ResearchState) -> str:
    """Route to the node matching ``current_phase``.

    The orchestrator sets ``current_phase``; this function maps it to a node name.
    """
    if state.get("should_stop"):
        logger.info("[orchestrator] should_stop=True — terminating graph")
        return "__end__"

    phase = state.get("current_phase", "literature_review")

    # Map phase names to node names (they match 1:1 for now)
    node_map = {
        "literature_review": "literature_review",
        "gap_analysis": "gap_analysis",
        "hypothesis_generation": "hypothesis_generation",
        "experiment_design": "experiment_design",
        "data_acquisition": "data_acquisition",
        "code_execution": "code_execution",
        "result_validation": "result_validation",
        "iteration": "iteration",
        "writing": "writing",
        "figure_generation": "figure_generation",
        "review": "review",
        "complete": "__end__",
    }
    return node_map.get(phase, "__end__")


def route_from_orchestrator_with_approval(state: ResearchState) -> str:
    """Route to human_approval gate before the actual phase node.

    Only routes to __end__ directly for 'complete' phase or when should_stop
    is set; all other phases go through the human_approval gate first.
    """
    if state.get("should_stop"):
        logger.info("[orchestrator] should_stop=True — terminating graph")
        return "__end__"
    phase = state.get("current_phase", "literature_review")
    if phase == "complete":
        return "__end__"
    return "human_approval"


def route_after_validation(state: ResearchState) -> str:
    """After result_validation, decide whether to proceed or retry.

    Returns
    -------
    str
        "writing" if validation passed,
        "iteration" if retryable (iteration_count < max),
        "hypothesis_generation" if exhausted retries (pivot).
    """
    from bioagent.config.settings import settings
    validation = state.get("validation_status")
    max_iters = settings.max_iterations

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
        "__end__" if review score passes threshold, max rounds exhausted,
        or score has plateaued (no improvement vs previous round).
        "orchestrator" (→ writing revision) otherwise.
    """
    from bioagent.config.settings import settings

    feedback = state.get("review_feedback", [])
    if not feedback:
        return "__end__"

    latest = feedback[-1] if isinstance(feedback, list) else feedback
    score = latest.get("score", 0) if isinstance(latest, dict) else 0

    # Pass: score meets threshold
    if score >= 7:
        return "__end__"

    # Exit: max review rounds exhausted
    review_count = state.get("review_count", 0)
    if review_count >= settings.max_review_rounds:
        logger.info(
            "[review] Max review rounds reached (%d/%d, score=%d/10) — accepting best draft",
            review_count, settings.max_review_rounds, score,
        )
        return "__end__"

    # Exit: score plateau — revision did not improve the paper
    if len(feedback) >= 2:
        prev = feedback[-2]
        prev_score = prev.get("score", 0) if isinstance(prev, dict) else 0
        if score <= prev_score:
            logger.info(
                "[review] Score plateaued (%d → %d/10) — no improvement detected, accepting draft",
                prev_score, score,
            )
            return "__end__"

    return "orchestrator"
