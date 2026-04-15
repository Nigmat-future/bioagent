"""Shared pytest fixtures and configuration for all tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ── Markers ──────────────────────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line("markers", "api: tests that require a real API key")
    config.addinivalue_line("markers", "slow: tests that take >10 seconds")
    config.addinivalue_line("markers", "integration: full end-to-end integration tests")


# ── Sample research state ────────────────────────────────────────────────────

@pytest.fixture
def sample_state() -> dict[str, Any]:
    """A realistic ResearchState for testing agents and nodes."""
    return {
        "research_topic": "BRAF V600E in melanoma",
        "research_question": "What is the mechanistic role of BRAF V600E in melanoma?",
        "current_phase": "writing",
        "phase_history": ["literature_review", "gap_analysis", "hypothesis_generation",
                          "experiment_design", "code_execution", "result_validation"],
        "iteration_count": 1,
        "papers": [
            {"id": "12068308", "title": "Mutations of the BRAF gene in human cancer",
             "authors": "Davies H et al.", "journal": "Nature", "year": "2002"},
            {"id": "20818844", "title": "Inhibition of mutated, activated BRAF in metastatic melanoma",
             "authors": "Flaherty KT et al.", "journal": "N Engl J Med", "year": "2010"},
            {"id": "21639808", "title": "Improved survival with vemurafenib in melanoma with BRAF V600E",
             "authors": "Chapman PB et al.", "journal": "N Engl J Med", "year": "2011"},
        ],
        "literature_summary": (
            "BRAF V600E is the most common activating mutation in melanoma (~50%), "
            "causing constitutive MAPK/ERK signaling. Targeted therapies (vemurafenib, "
            "dabrafenib) achieve 48-53% response rates but resistance typically emerges."
        ),
        "research_gaps": [
            "Mechanisms of acquired BRAF inhibitor resistance are incompletely understood",
            "Optimal combination strategies to prevent resistance remain unclear",
            "Role of tumor microenvironment in therapeutic response is underexplored",
        ],
        "hypotheses": [
            {
                "text": "BRAF V600E drives melanoma through constitutive MAPK activation",
                "novelty_score": 7.5,
                "testability_score": 8.0,
                "rationale": "Supported by vemurafenib efficacy data",
            }
        ],
        "selected_hypothesis": {
            "text": "BRAF V600E drives melanoma through constitutive MAPK activation",
            "novelty_score": 7.5,
            "testability_score": 8.0,
        },
        "experiment_plan": {
            "content": "Simulate BRAF V600E signaling using synthetic MAPK cascade data"
        },
        "code_artifacts": [{"id": "analysis_code", "description": "MAPK simulation"}],
        "execution_results": [
            {"stdout": "Analysis complete", "stderr": "", "exit_code": 0, "duration": 2.1}
        ],
        "analysis_results": [
            {
                "summary": "BRAF V600E simulation shows 3.2x elevated ERK activity",
                "results": "Mean ERK activation: 3.2 ± 0.4 (p < 0.001 vs WT)",
                "raw_output": "ERK activation analysis complete",
            }
        ],
        "validation_status": {"passed": True, "reason": "Results present, no errors"},
        "paper_sections": {
            "abstract": {"content": "BRAF V600E is the most frequent mutation in melanoma.", "status": "draft", "version": 1},
            "introduction": {"content": "Melanoma is an aggressive skin cancer with rising incidence.", "status": "draft", "version": 1},
            "methods": {"content": "We simulated BRAF V600E signaling using a kinetic model.", "status": "draft", "version": 1},
            "results": {"content": "BRAF V600E showed 3.2-fold elevated ERK activation (p<0.001).", "status": "draft", "version": 1},
            "discussion": {"content": "Our findings confirm the oncogenic role of BRAF V600E.", "status": "draft", "version": 1},
        },
        "references": [
            {"id": "12068308", "title": "Mutations of the BRAF gene in human cancer",
             "authors": "Davies H et al.", "journal": "Nature", "year": "2002"},
        ],
        "paper_metadata": {},
        "figures": [
            {"id": "fig_1", "title": "ERK Activation", "path": "workspace/figures/erk_activation.pdf",
             "caption": "ERK activation in BRAF V600E vs wildtype cells", "type": "bar_plot"},
        ],
        "review_feedback": [],
        "revision_notes": [],
        "messages": [],
        "errors": [],
        "human_feedback": None,
        "should_stop": False,
    }


@pytest.fixture
def empty_state() -> dict[str, Any]:
    """Minimal initial state for testing graph initialization."""
    return {
        "research_topic": "test topic",
        "research_question": "What is X?",
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


@pytest.fixture
def mock_anthropic_client():
    """A mocked Anthropic client that returns a simple text response."""
    with patch("bioagent.llm.clients.get_anthropic_client") as mock_getter:
        client = MagicMock()
        response = MagicMock()
        response.usage.input_tokens = 100
        response.usage.output_tokens = 50
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = '{"next_phase": "gap_analysis"}'
        response.content = [text_block]
        response.stop_reason = "end_turn"
        client.messages.create.return_value = response
        mock_getter.return_value = client
        yield client
