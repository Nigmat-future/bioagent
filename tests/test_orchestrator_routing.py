"""Regression tests for orchestrator phase routing.

These tests exist specifically to prevent a re-introduction of the bug where
``data_acquisition`` was routed but absent from ``VALID_PHASES``, silently
falling back to ``literature_review``.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


VALID_PHASES_EXPECTED = {
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
}


def test_valid_phases_contains_expected_set():
    """The canonical VALID_PHASES list must cover every node in the graph."""
    from bioagent.agents.orchestrator import VALID_PHASES

    assert set(VALID_PHASES) == VALID_PHASES_EXPECTED, (
        "VALID_PHASES must contain every phase routed to by the orchestrator; "
        "missing a phase here silently reroutes it to literature_review."
    )


def test_data_acquisition_is_routable():
    """Specific regression: data_acquisition must be a valid phase.

    This is the bug fixed in the v0.2.0 release. The DataAcquisitionAgent
    existed and was wired into the graph, but the orchestrator's validation
    list did not include it, so every attempt to route there reset to
    literature_review.
    """
    from bioagent.agents.orchestrator import VALID_PHASES

    assert "data_acquisition" in VALID_PHASES


@pytest.mark.parametrize("phase", sorted(VALID_PHASES_EXPECTED))
def test_each_phase_round_trips_through_process_result(phase, sample_state):
    """Every valid phase in the rubric must survive process_result unchanged."""
    from bioagent.agents.orchestrator import OrchestratorAgent

    # Bypass __init__ (needs an Anthropic client) — we only need process_result.
    agent = OrchestratorAgent.__new__(OrchestratorAgent)

    result_text = json.dumps({"next_phase": phase})
    updates = agent.process_result(result_text, [], sample_state)

    assert updates["current_phase"] == phase, (
        f"Phase '{phase}' was rewritten to '{updates['current_phase']}' — "
        f"this usually means VALID_PHASES is out of sync with the graph."
    )


def test_invalid_phase_falls_back_to_literature_review(sample_state):
    """Truly invalid phase names should fall back to literature_review."""
    from bioagent.agents.orchestrator import OrchestratorAgent

    agent = OrchestratorAgent.__new__(OrchestratorAgent)
    result_text = json.dumps({"next_phase": "nonexistent_phase_xyz"})
    updates = agent.process_result(result_text, [], sample_state)

    assert updates["current_phase"] == "literature_review"


def test_markdown_fence_stripped_before_parsing(sample_state):
    """JSON wrapped in a ```json code fence must still parse."""
    from bioagent.agents.orchestrator import OrchestratorAgent

    agent = OrchestratorAgent.__new__(OrchestratorAgent)
    result_text = '```json\n{"next_phase": "data_acquisition"}\n```'
    updates = agent.process_result(result_text, [], sample_state)

    assert updates["current_phase"] == "data_acquisition"


def test_phase_history_accumulates(sample_state):
    """Every call to process_result should append to phase_history."""
    from bioagent.agents.orchestrator import OrchestratorAgent

    agent = OrchestratorAgent.__new__(OrchestratorAgent)
    initial_history = list(sample_state.get("phase_history", []))

    updates = agent.process_result('{"next_phase": "writing"}', [], sample_state)

    assert updates["phase_history"] == initial_history + ["writing"]


def test_graph_has_data_acquisition_node():
    """The compiled graph must expose data_acquisition as a node.

    Second-layer regression check: even if VALID_PHASES is correct, the
    graph itself must include the node.
    """
    from bioagent.graph.research_graph import compile_research_graph

    graph = compile_research_graph()
    nodes = set(graph.get_graph().nodes)
    assert "data_acquisition" in nodes, (
        f"data_acquisition node missing from graph. Nodes found: {sorted(nodes)}"
    )
