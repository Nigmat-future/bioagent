"""Research state schema — the single source of truth flowing through the graph."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, Optional, TypedDict

from langgraph.graph.message import add_messages

from bioagent.state.reducers import dedup_add


# Phase names used in current_phase and routing
PhaseName = Literal[
    "literature_review",
    "gap_analysis",
    "hypothesis_generation",
    "experiment_design",
    "data_acquisition",
    "code_execution",
    "result_validation",
    "iteration",
    "writing",
    "figure_generation",
    "review",
    "complete",
]


class ResearchState(TypedDict, total=False):
    """Full state that flows through the research graph.

    Fields with Annotated[list, ...] use custom reducers so agents can
    append new items without overwriting previous ones.
    """

    # ── Input ──────────────────────────────────────────────
    research_topic: str
    research_question: str
    constraints: list[str]

    # ── Phase tracking ─────────────────────────────────────
    current_phase: str
    phase_history: Annotated[list[str], dedup_add]
    iteration_count: int

    # ── Literature knowledge ───────────────────────────────
    papers: Annotated[list[dict], dedup_add]
    literature_summary: str
    research_gaps: Annotated[list[str], dedup_add]
    knowledge_base: dict

    # ── Hypotheses & planning ──────────────────────────────
    hypotheses: Annotated[list[dict], dedup_add]
    selected_hypothesis: Optional[dict]
    experiment_plan: Optional[dict]

    # ── Data acquisition ──────────────────────────────────────
    data_status: Optional[dict]

    #── Code & execution ───────────────────────────────────
    code_artifacts: Annotated[list[dict], dedup_add]
    execution_results: Annotated[list[dict], dedup_add]
    data_artifacts: Annotated[list[dict], dedup_add]

    # ── Analysis results ───────────────────────────────────
    analysis_results: Annotated[list[dict], dedup_add]
    validation_status: Optional[dict]

    # ── Writing ────────────────────────────────────────────
    paper_sections: dict
    references: Annotated[list[dict], dedup_add]
    paper_metadata: dict

    # ── Figures ────────────────────────────────────────────
    figures: Annotated[list[dict], dedup_add]

    # ── Review ─────────────────────────────────────────────
    review_feedback: Annotated[list[dict], operator.add]
    revision_notes: Annotated[list[str], dedup_add]
    review_count: int

    # ── LLM conversation (for within-agent tool loops) ─────
    messages: Annotated[list[dict], add_messages]

    # ── Control flow ───────────────────────────────────────
    errors: Annotated[list[str], dedup_add]
    human_feedback: Optional[str]
    should_stop: bool
