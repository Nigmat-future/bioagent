"""Tests for the orchestrator loop detector.

Covers the BRAF-melanoma regression where the LLM repeatedly re-selected
`hypothesis_generation` after code_execution completed (because the state
summary showed `Hypotheses: 0` when the planner's later re-runs dropped the
field, making rule 3 win over rule 10 in the prompt).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def _agent():
    from bioagent.agents.orchestrator import OrchestratorAgent

    # Bypass BaseAgent.__init__ which requires API credentials.
    return OrchestratorAgent.__new__(OrchestratorAgent)


class TestLoopDetector:
    def test_third_consecutive_same_phase_forces_forward(self):
        """3rd consecutive hypothesis_generation -> forced to experiment_design."""
        agent = _agent()
        state = {
            "phase_history": [
                "literature_review",
                "hypothesis_generation",
                "hypothesis_generation",
            ],
        }
        updates = agent.process_result(
            '{"next_phase": "hypothesis_generation"}', [], state
        )
        assert updates["current_phase"] == "experiment_design"
        assert updates["phase_history"][-1] == "experiment_design"

    def test_braf_scenario_code_execution_then_stuck_on_hypothesis(self):
        """Real BRAF log scenario: code ran, then hypothesis picked repeatedly."""
        agent = _agent()
        state = {
            "phase_history": [
                "literature_review",
                "hypothesis_generation",
                "data_acquisition",
                "code_execution",
                "hypothesis_generation",
                "hypothesis_generation",
            ],
        }
        updates = agent.process_result(
            '{"next_phase": "hypothesis_generation"}', [], state
        )
        # Forward from hypothesis_generation is experiment_design.
        assert updates["current_phase"] == "experiment_design"

    def test_two_repeats_do_not_trigger(self):
        """2 consecutive occurrences are fine — only 3rd triggers override."""
        agent = _agent()
        state = {
            "phase_history": ["literature_review", "hypothesis_generation"],
        }
        updates = agent.process_result(
            '{"next_phase": "hypothesis_generation"}', [], state
        )
        assert updates["current_phase"] == "hypothesis_generation"

    def test_different_phase_resets_loop_counter(self):
        """An interleaved phase breaks the streak."""
        agent = _agent()
        state = {
            "phase_history": [
                "hypothesis_generation",
                "data_acquisition",
                "hypothesis_generation",
            ],
        }
        updates = agent.process_result(
            '{"next_phase": "hypothesis_generation"}', [], state
        )
        assert updates["current_phase"] == "hypothesis_generation"

    def test_iteration_exempt_from_loop_detector(self):
        """iteration uses iteration_count for its own limit — no override."""
        agent = _agent()
        state = {
            "phase_history": ["iteration", "iteration"],
        }
        updates = agent.process_result('{"next_phase": "iteration"}', [], state)
        assert updates["current_phase"] == "iteration"

    def test_complete_exempt(self):
        agent = _agent()
        state = {"phase_history": ["complete", "complete"]}
        updates = agent.process_result('{"next_phase": "complete"}', [], state)
        assert updates["current_phase"] == "complete"

    def test_markdown_fenced_json_still_parses(self):
        agent = _agent()
        state = {"phase_history": []}
        updates = agent.process_result(
            '```json\n{"next_phase": "literature_review"}\n```', [], state
        )
        assert updates["current_phase"] == "literature_review"


class TestStateSummaryIncludesPhaseHistory:
    """Verify phase_history is surfaced to the LLM so the prompt's anti-backtrack
    rule has something to anchor on."""

    def test_phase_history_in_user_message(self):
        agent = _agent()
        state = {
            "research_topic": "BRAF",
            "research_question": "Q",
            "current_phase": "hypothesis_generation",
            "phase_history": [
                "literature_review",
                "hypothesis_generation",
                "data_acquisition",
                "code_execution",
            ],
            "papers": [],
            "research_gaps": [],
            "hypotheses": [],
            "experiment_plan": {},
            "code_artifacts": [],
            "execution_results": [],
            "paper_sections": {},
            "figures": [],
        }
        messages = agent.build_messages(state)
        content = messages[0]["content"]
        assert "Phase history" in content
        assert "code_execution" in content


class TestForwardProgressionMap:
    """Sanity-check the fallback progression graph for common transitions."""

    def test_map_covers_all_non_terminal_phases(self):
        from bioagent.agents.orchestrator import FORWARD_PROGRESSION

        expected = {
            "literature_review",
            "gap_analysis",
            "hypothesis_generation",
            "experiment_design",
            "data_acquisition",
            "code_execution",
            "writing",
            "figure_generation",
            "review",
        }
        assert expected.issubset(set(FORWARD_PROGRESSION.keys()))

    def test_code_execution_forwards_to_writing(self):
        from bioagent.agents.orchestrator import FORWARD_PROGRESSION

        assert FORWARD_PROGRESSION["code_execution"] == "writing"

    def test_hypothesis_forwards_to_experiment_design(self):
        from bioagent.agents.orchestrator import FORWARD_PROGRESSION

        assert FORWARD_PROGRESSION["hypothesis_generation"] == "experiment_design"
