"""Integration tests for the BioAgent research system.

Tests cover:
1. Graph compilation and node topology
2. Orchestrator routing decisions
3. Writer output parsing
4. Review score extraction
5. Token budget enforcement
6. API retry logic
7. Human-in-the-loop node passthrough
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ── Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def sample_state():
    """Minimal valid ResearchState for testing."""
    return {
        "research_topic": "TP53 mutations in cancer",
        "research_question": "How do TP53 loss-of-function mutations affect treatment response?",
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
def state_with_results(sample_state):
    """State with analysis results and paper content."""
    state = dict(sample_state)
    state["current_phase"] = "writing"
    state["literature_summary"] = "TP53 is a tumor suppressor..."
    state["papers"] = [
        {"id": "PMID:12345", "title": "TP53 in cancer", "abstract": "..."},
    ]
    state["research_gaps"] = ["Lack of computational models for TP53 mutation impact"]
    state["hypotheses"] = [
        {"id": "h1", "text": "TP53 LOF mutations predict poor response", "novelty": 8, "testability": 7},
    ]
    state["selected_hypothesis"] = {"text": "TP53 LOF mutations predict poor response"}
    state["experiment_plan"] = {"content": "Analyze TCGA data..."}
    state["analysis_results"] = [
        {"summary": "Found significant association", "results": "p < 0.001, OR = 2.3"},
    ]
    return state


# ── Test 1: Graph Compilation ──────────────────────────────────

class TestGraphCompilation:
    def test_graph_compiles_default_mode(self):
        """Graph should compile with 12 nodes in default mode."""
        from bioagent.graph.research_graph import compile_research_graph
        graph = compile_research_graph()
        nodes = list(graph.nodes.keys())
        assert "orchestrator" in nodes
        assert "literature_review" in nodes
        assert "writing" in nodes
        assert "figure_generation" in nodes
        assert "review" in nodes
        assert "human_approval" not in nodes  # not in default mode

    def test_graph_compiles_human_in_loop(self):
        """Graph should include human_approval node when enabled."""
        import os
        os.environ["BIOAGENT_HUMAN_IN_LOOP"] = "true"
        try:
            import importlib
            import bioagent.config.settings as s
            importlib.reload(s)
            import bioagent.graph.research_graph as g
            importlib.reload(g)
            graph = g.compile_research_graph()
            nodes = list(graph.nodes.keys())
            assert "human_approval" in nodes
        finally:
            del os.environ["BIOAGENT_HUMAN_IN_LOOP"]


# ── Test 2: Orchestrator Routing ──────────────────────────────

class TestOrchestratorRouting:
    def test_route_to_literature_when_empty(self):
        from bioagent.graph.routing import route_from_orchestrator
        state = {"current_phase": "literature_review"}
        assert route_from_orchestrator(state) == "literature_review"

    def test_route_to_writing(self):
        from bioagent.graph.routing import route_from_orchestrator
        state = {"current_phase": "writing"}
        assert route_from_orchestrator(state) == "writing"

    def test_route_to_end_on_complete(self):
        from bioagent.graph.routing import route_from_orchestrator
        state = {"current_phase": "complete"}
        assert route_from_orchestrator(state) == "__end__"

    def test_route_to_review(self):
        from bioagent.graph.routing import route_from_orchestrator
        state = {"current_phase": "review"}
        assert route_from_orchestrator(state) == "review"

    def test_route_unknown_phase_to_end(self):
        from bioagent.graph.routing import route_from_orchestrator
        state = {"current_phase": "unknown_phase"}
        assert route_from_orchestrator(state) == "__end__"

    def test_phase_history_append(self):
        """Orchestrator should append to phase_history, not replace."""
        from bioagent.agents.orchestrator import OrchestratorAgent
        agent = OrchestratorAgent()
        state = {
            "phase_history": ["literature_review", "gap_analysis"],
            "current_phase": "hypothesis_generation",
        }
        result = agent.process_result(
            '{"next_phase": "experiment_design"}',
            [],
            state,
        )
        assert len(result["phase_history"]) == 3
        assert result["phase_history"][-1] == "experiment_design"

    def test_route_after_validation_pass(self):
        from bioagent.graph.routing import route_after_validation
        state = {"validation_status": {"passed": True}}
        assert route_after_validation(state) == "orchestrator"

    def test_route_after_validation_fail_retry(self):
        from bioagent.graph.routing import route_after_validation
        state = {
            "validation_status": {"passed": False},
            "iteration_count": 2,
        }
        assert route_after_validation(state) == "iteration"

    def test_route_after_validation_exhausted(self):
        from bioagent.graph.routing import route_after_validation
        state = {
            "validation_status": {"passed": False},
            "iteration_count": 10,
        }
        assert route_after_validation(state) == "orchestrator"

    def test_route_after_review_accept(self):
        from bioagent.graph.routing import route_after_review
        state = {"review_feedback": [{"score": 8}]}
        assert route_after_review(state) == "__end__"

    def test_route_after_review_revise(self):
        from bioagent.graph.routing import route_after_review
        state = {"review_feedback": [{"score": 5}]}
        assert route_after_review(state) == "orchestrator"


# ── Test 3: Writer Output Parsing ─────────────────────────────

class TestWriterParsing:
    def test_parse_all_sections(self):
        from bioagent.agents.writer import WriterAgent
        agent = WriterAgent()
        text = (
            "### ABSTRACT\nThis is the abstract with enough content to pass the threshold check for validation.\n\n"
            "### INTRODUCTION\nThis is the introduction section with enough content to pass validation checks.\n\n"
            "### METHODS\nThese are the methods with enough detail to pass validation threshold.\n\n"
            "### RESULTS\nThe results show significant findings with enough content to validate.\n\n"
            "### DISCUSSION\nThe discussion interprets results with enough content for validation.\n"
        )
        result = agent.process_result(text, [], {})
        sections = result["paper_sections"]
        assert "abstract" in sections
        assert "introduction" in sections
        assert "methods" in sections
        assert "results" in sections
        assert "discussion" in sections
        assert sections["abstract"]["status"] == "draft"

    def test_fallback_on_no_sections(self):
        from bioagent.agents.writer import WriterAgent
        agent = WriterAgent()
        text = "This is just plain text without any section headers."
        result = agent.process_result(text, [], {})
        sections = result["paper_sections"]
        assert "results" in sections  # fallback


# ── Test 4: Review Score Parsing ──────────────────────────────

class TestReviewParsing:
    def _make_review_mocks(self, response_text):
        """Create mock client and response for review tests."""
        mock_response = MagicMock()
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.content = [MagicMock(text=response_text)]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        return mock_client

    def test_parse_score_and_set_complete(self):
        from bioagent.graph.nodes import review_node
        mock_client = self._make_review_mocks(
            "### REVIEW_SUMMARY\nGood paper.\n\n"
            "### SCORE\n8\n\n"
            "### STRENGTHS\n- Good methods\n\n"
            "### WEAKNESSES\n- None\n\n"
            "### SPECIFIC_ISSUES\n- Section: methods -- Issue: too brief -- Suggestion: expand\n\n"
            "### RECOMMENDATION\naccept\n"
        )
        with patch("bioagent.llm.clients.get_anthropic_client", return_value=mock_client), \
             patch("bioagent.llm.clients.get_anthropic_model", return_value="test-model"):
            result = review_node({"paper_sections": {"abstract": {"content": "test"}}, "figures": []})
            assert result["current_phase"] == "complete"
            assert result["review_feedback"][0]["score"] == 8

    def test_low_score_routes_to_writing(self):
        from bioagent.graph.nodes import review_node
        mock_client = self._make_review_mocks(
            "### REVIEW_SUMMARY\nNeeds work.\n\n"
            "### SCORE\n4\n\n"
            "### RECOMMENDATION\nmajor_revision\n"
        )
        with patch("bioagent.llm.clients.get_anthropic_client", return_value=mock_client), \
             patch("bioagent.llm.clients.get_anthropic_model", return_value="test-model"):
            result = review_node({"paper_sections": {"abstract": {"content": "test"}}, "figures": []})
            assert result["current_phase"] == "writing"
            assert result["review_feedback"][0]["score"] == 4


# ── Test 5: Token Budget ─────────────────────────────────────

class TestTokenBudget:
    def test_budget_not_exceeded(self):
        from bioagent.llm.token_tracking import TokenUsage
        usage = TokenUsage(token_budget=10000, cost_budget_usd=100.0)
        usage.add(input_tokens=100, output_tokens=50)
        usage.check_budget()  # should not raise

    def test_token_budget_exceeded(self):
        from bioagent.llm.token_tracking import TokenUsage, BudgetExceeded
        usage = TokenUsage(token_budget=100)
        usage.add(input_tokens=80, output_tokens=30)
        with pytest.raises(BudgetExceeded, match="Token budget"):
            usage.check_budget()

    def test_cost_budget_exceeded(self):
        from bioagent.llm.token_tracking import TokenUsage, BudgetExceeded
        usage = TokenUsage(cost_budget_usd=0.001, INPUT_COST_PER_M=100.0)
        usage.add(input_tokens=100)
        with pytest.raises(BudgetExceeded, match="Cost budget"):
            usage.check_budget()

    def test_unlimited_budget(self):
        from bioagent.llm.token_tracking import TokenUsage
        usage = TokenUsage()  # default 0 = unlimited
        usage.add(input_tokens=9999999, output_tokens=9999999)
        usage.check_budget()  # should not raise

    def test_summary_includes_budget(self):
        from bioagent.llm.token_tracking import TokenUsage
        usage = TokenUsage(token_budget=1000, cost_budget_usd=5.0)
        usage.add(input_tokens=100)
        s = usage.summary()
        assert "budget" in s
        assert "cost" in s


# ── Test 6: API Retry Logic ──────────────────────────────────

class TestAPIRetry:
    def test_retry_on_connection_error(self):
        from bioagent.llm.tool_loop import _call_with_retry
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            ConnectionError("timeout"),
            ConnectionError("timeout"),
            MagicMock(content=[]),  # success on 3rd attempt
        ]
        # Should succeed after retries
        result = _call_with_retry(
            mock_client, "model", "system", [], [],
            max_tokens=100, max_retries=3,
        )
        assert mock_client.messages.create.call_count == 3

    def test_retry_exhausted_raises(self):
        from bioagent.llm.tool_loop import _call_with_retry
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = ConnectionError("persistent failure")
        with pytest.raises(ConnectionError):
            _call_with_retry(
                mock_client, "model", "system", [], [],
                max_tokens=100, max_retries=2,
            )
        assert mock_client.messages.create.call_count == 2

    def test_non_retryable_error_raises_immediately(self):
        from bioagent.llm.tool_loop import _call_with_retry
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = ValueError("bad input")
        with pytest.raises(ValueError):
            _call_with_retry(
                mock_client, "model", "system", [], [],
                max_tokens=100, max_retries=3,
            )
        assert mock_client.messages.create.call_count == 1


# ── Test 7: Human-in-the-Loop ─────────────────────────────────

class TestHumanInLoop:
    def test_passthrough_when_disabled(self):
        from bioagent.graph.nodes import human_approval_node
        mock_settings = MagicMock()
        mock_settings.human_in_loop = False
        with patch("bioagent.config.settings.settings", mock_settings):
            result = human_approval_node({"current_phase": "writing"})
            assert result == {}

    def test_approval_returns_feedback(self):
        from bioagent.graph.nodes import human_approval_node
        mock_settings = MagicMock()
        mock_settings.human_in_loop = True
        with patch("bioagent.config.settings.settings", mock_settings), \
             patch("builtins.input", return_value="y"):
            result = human_approval_node({
                "current_phase": "writing",
                "research_question": "test",
            })
            assert result["human_feedback"] is None  # approved

    def test_rejection_returns_error(self):
        from bioagent.graph.nodes import human_approval_node
        mock_settings = MagicMock()
        mock_settings.human_in_loop = True
        with patch("bioagent.config.settings.settings", mock_settings), \
             patch("builtins.input", return_value="n"):
            result = human_approval_node({
                "current_phase": "writing",
                "research_question": "test",
            })
            assert result["human_feedback"] is not None
            assert len(result["errors"]) > 0


# ── Test 8: Tool Execution ────────────────────────────────────

class TestToolExecution:
    def test_unknown_tool_returns_error(self):
        from bioagent.llm.tool_loop import _execute_tool
        result = _execute_tool("nonexistent_tool", {"arg": "value"}, {})
        assert "Error" in result
        assert "unknown tool" in result

    def test_empty_input_returns_error(self):
        from bioagent.llm.tool_loop import _execute_tool
        result = _execute_tool("some_tool", {}, {"some_tool": lambda: "ok"})
        assert "Error" in result
        assert "requires parameters" in result

    def test_successful_tool_call(self):
        from bioagent.llm.tool_loop import _execute_tool
        result = _execute_tool("echo", {"text": "hello"}, {"echo": lambda text: text})
        assert result == "hello"

    def test_tool_exception_caught(self):
        from bioagent.llm.tool_loop import _execute_tool
        def failing_tool(**kwargs):
            raise RuntimeError("boom")
        result = _execute_tool("fail", {"x": 1}, {"fail": failing_tool})
        assert "Error" in result
        assert "boom" in result


# ── Test 9: Validation Node ───────────────────────────────────

class TestValidationNode:
    def test_passes_with_results(self):
        from bioagent.graph.nodes import result_validation_node
        state = {
            "analysis_results": [{"summary": "Found something", "results": "p < 0.05"}],
            "execution_results": [],
            "errors": [],
        }
        result = result_validation_node(state)
        assert result["validation_status"]["passed"] is True

    def test_fails_on_execution_error(self):
        from bioagent.graph.nodes import result_validation_node
        state = {
            "analysis_results": [],
            "execution_results": [{"exit_code": 1, "stderr": "ImportError"}],
            "errors": [],
        }
        result = result_validation_node(state)
        assert result["validation_status"]["passed"] is False

    def test_fails_on_no_results(self):
        from bioagent.graph.nodes import result_validation_node
        state = {
            "analysis_results": [],
            "execution_results": [],
            "errors": [],
        }
        result = result_validation_node(state)
        assert result["validation_status"]["passed"] is False


# ── Test 10: Visualization Parsing ─────────────────────────────

class TestVisualizationParsing:
    def test_parse_figure_entries(self):
        from bioagent.agents.visualization import VisualizationAgent
        agent = VisualizationAgent()
        text = (
            "### GENERATED_FIGURES\n"
            "Figure 1: Volcano plot of DE genes\n"
            "  File: workspace/figures/volcano.pdf\n"
            "  Caption: Differential expression analysis results\n"
            "  Type: volcano\n\n"
            "Figure 2: Heatmap of top genes\n"
            "  File: workspace/figures/heatmap.pdf\n"
            "  Caption: Expression heatmap of top 50 DE genes\n"
            "  Type: heatmap\n"
        )
        result = agent.process_result(text, [], {})
        figures = result["figures"]
        assert len(figures) == 2
        assert figures[0]["type"] == "volcano"
        assert figures[1]["type"] == "heatmap"

    def test_fallback_empty_output(self):
        from bioagent.agents.visualization import VisualizationAgent
        agent = VisualizationAgent()
        result = agent.process_result("No figures generated.", [], {})
        # Should return empty figures list or fallback
        assert "figures" in result
