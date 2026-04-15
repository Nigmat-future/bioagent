"""Unit tests for agent process_result() parsing methods."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ── LiteratureAgent ───────────────────────────────────────────────────────────

class TestLiteratureAgentParsing:
    def _make_state(self, papers=None):
        return {"papers": papers or [], "research_gaps": []}

    def test_extract_section(self):
        from bioagent.agents.literature import LiteratureAgent

        text = "### SUMMARY\nHere is the summary content.\n### RESEARCH_GAPS\n1. Gap one\n2. Gap two"
        result = LiteratureAgent._extract_section(text, "SUMMARY")
        assert "summary content" in result

    def test_extract_gaps_numbered(self):
        from bioagent.agents.literature import LiteratureAgent

        text = "### RESEARCH_GAPS\n1. Resistance mechanisms are poorly understood\n2. Lack of biomarkers for patient selection\n3. No validated models for drug synergy"
        gaps = LiteratureAgent._extract_gaps(text)
        assert len(gaps) == 3
        assert "Resistance mechanisms" in gaps[0]

    def test_extract_gaps_bullets(self):
        from bioagent.agents.literature import LiteratureAgent

        text = "### RESEARCH_GAPS\n- Insufficient longitudinal data on tumor evolution\n- Limited understanding of off-target effects"
        gaps = LiteratureAgent._extract_gaps(text)
        assert len(gaps) == 2

    def test_extract_papers_pipe_format(self):
        from bioagent.agents.literature import LiteratureAgent

        text = "12068308 | BRAF mutations in cancer | High relevance\n"
        papers = LiteratureAgent._extract_papers(text, self._make_state())
        assert any(p.get("id") == "12068308" for p in papers)

    def test_extract_papers_pmid_pattern(self):
        from bioagent.agents.literature import LiteratureAgent

        text = "See PMID: 20818844 — Inhibition of mutated BRAF in melanoma"
        papers = LiteratureAgent._extract_papers(text, self._make_state())
        assert any(p.get("id") == "20818844" for p in papers)

    def test_extract_papers_deduplicates_existing(self):
        from bioagent.agents.literature import LiteratureAgent

        existing = [{"id": "12068308", "title": "Already found"}]
        state = self._make_state(papers=existing)
        text = "PMID: 12068308 - BRAF mutations"
        papers = LiteratureAgent._extract_papers(text, state)
        assert len(papers) == 0  # already in state, not duplicated

    def test_process_result_populates_references(self):
        from bioagent.agents.literature import LiteratureAgent

        agent = LiteratureAgent.__new__(LiteratureAgent)
        text = (
            "### SUMMARY\nBRAF V600E is a driver mutation.\n"
            "### RESEARCH_GAPS\n1. Resistance mechanisms unclear\n"
            "12068308 | BRAF mutations | key paper\n"
        )
        state = {"papers": [], "research_gaps": []}
        result = agent.process_result(text, [], state)

        assert "literature_summary" in result
        assert "research_gaps" in result
        if "references" in result:
            assert any(r.get("id") == "12068308" for r in result["references"])


# ── PlannerAgent ──────────────────────────────────────────────────────────────

class TestPlannerAgentParsing:
    def test_extract_hypotheses(self):
        from bioagent.agents.planner import PlannerAgent

        agent = PlannerAgent.__new__(PlannerAgent)
        text = (
            "### HYPOTHESES\n"
            "H1: BRAF V600E constitutively activates MAPK signaling\n"
            "Novelty: 8/10\n"
            "Testability: 9/10\n"
            "Rationale: Supported by multiple studies\n"
            "H2: BRAF inhibitors work through ERK suppression\n"
            "Novelty: 6/10\n"
            "Testability: 8/10\n"
            "Rationale: Mechanism well-studied\n"
        )
        hypotheses = agent._extract_hypotheses(text)
        assert len(hypotheses) >= 1
        assert any(h.get("text", "").startswith("BRAF") for h in hypotheses)


# ── WriterAgent ───────────────────────────────────────────────────────────────

class TestWriterAgentParsing:
    def test_parse_all_sections(self):
        from bioagent.agents.writer import WriterAgent

        agent = WriterAgent.__new__(WriterAgent)
        text = (
            "### ABSTRACT\nThis study examines BRAF V600E in melanoma. " + "A" * 60 + "\n\n"
            "### INTRODUCTION\nMelanoma is a common skin cancer. " + "B" * 60 + "\n\n"
            "### METHODS\nWe used synthetic data to simulate BRAF signaling. " + "C" * 60 + "\n\n"
            "### RESULTS\nBRAF V600E showed elevated ERK activation. " + "D" * 60 + "\n\n"
            "### DISCUSSION\nOur results support the oncogenic role. " + "E" * 60 + "\n"
        )
        result = agent.process_result(text, [], {})
        sections = result.get("paper_sections", {})
        assert "abstract" in sections
        assert "introduction" in sections
        assert "methods" in sections
        assert "results" in sections
        assert "discussion" in sections

    def test_fallback_to_results_on_parse_failure(self):
        from bioagent.agents.writer import WriterAgent

        agent = WriterAgent.__new__(WriterAgent)
        text = "Just some unstructured text without any headers at all " + "X" * 60
        result = agent.process_result(text, [], {})
        sections = result.get("paper_sections", {})
        assert len(sections) > 0

    def test_skips_trivial_sections(self):
        from bioagent.agents.writer import WriterAgent

        agent = WriterAgent.__new__(WriterAgent)
        # Abstract is < 50 chars — should be skipped
        text = "### ABSTRACT\nShort.\n\n### RESULTS\n" + "R" * 100
        result = agent.process_result(text, [], {})
        sections = result.get("paper_sections", {})
        assert "abstract" not in sections
        assert "results" in sections


# ── AnalystAgent ──────────────────────────────────────────────────────────────

class TestAnalystAgentParsing:
    def test_extract_section(self):
        from bioagent.agents.analyst import AnalystAgent

        text = (
            "### ANALYSIS_SUMMARY\nERK activation increased 3.2x.\n\n"
            "### RESULTS\np-value < 0.001\n\n"
            "### FIGURES\nworkspace/figures/erk_plot.pdf\n"
        )
        summary = AnalystAgent._extract_section(text, "ANALYSIS_SUMMARY")
        assert "ERK" in summary

        results = AnalystAgent._extract_section(text, "RESULTS")
        assert "p-value" in results

    def test_process_result_creates_analysis_entry(self):
        from bioagent.agents.analyst import AnalystAgent

        agent = AnalystAgent.__new__(AnalystAgent)
        text = (
            "### ANALYSIS_SUMMARY\nBRAF V600E shows elevated signaling.\n\n"
            "### RESULTS\nERK: 3.2 ± 0.4 (p<0.001)\n\n"
            "### FIGURES\nworkspace/figures/erk_activation.pdf\n\n"
            "### CODE_ARTIFACTS\nanalysis.py"
        )
        result = agent.process_result(text, [], {})
        assert "analysis_results" in result
        assert len(result["analysis_results"]) == 1
        assert "BRAF V600E" in result["analysis_results"][0]["summary"]


# ── VisualizationAgent ────────────────────────────────────────────────────────

class TestVisualizationAgentParsing:
    def test_parse_figure_entries(self):
        from bioagent.agents.visualization import VisualizationAgent

        agent = VisualizationAgent.__new__(VisualizationAgent)
        text = (
            "### GENERATED_FIGURES\n"
            "Figure 1: ERK Activation\n"
            "File: workspace/figures/erk.pdf\n"
            "Caption: ERK activation in BRAF V600E vs WT\n"
            "Type: bar_plot\n"
        )
        result = agent.process_result(text, [], {})
        figs = result.get("figures", [])
        assert len(figs) >= 1

    def test_fallback_to_empty_when_no_section(self):
        from bioagent.agents.visualization import VisualizationAgent

        agent = VisualizationAgent.__new__(VisualizationAgent)
        # No GENERATED_FIGURES section and no workspace/figures/ to scan
        result = agent.process_result("Some output without figures section.", [], {})
        figs = result.get("figures", [])
        # May be empty or contain scanned files — just check it doesn't crash
        assert isinstance(figs, list)


# ── OrchestratorAgent ─────────────────────────────────────────────────────────

class TestOrchestratorAgentParsing:
    def test_valid_phase_parsed(self):
        from bioagent.agents.orchestrator import OrchestratorAgent

        agent = OrchestratorAgent.__new__(OrchestratorAgent)
        result = agent.process_result('{"next_phase": "writing"}', [], {"phase_history": []})
        assert result["current_phase"] == "writing"

    def test_invalid_phase_defaults_to_literature(self):
        from bioagent.agents.orchestrator import OrchestratorAgent

        agent = OrchestratorAgent.__new__(OrchestratorAgent)
        result = agent.process_result('{"next_phase": "flying_to_moon"}', [], {"phase_history": []})
        assert result["current_phase"] == "literature_review"

    def test_malformed_json_defaults_to_literature(self):
        from bioagent.agents.orchestrator import OrchestratorAgent

        agent = OrchestratorAgent.__new__(OrchestratorAgent)
        result = agent.process_result("not json at all", [], {"phase_history": []})
        assert result["current_phase"] == "literature_review"

    def test_phase_history_appended(self):
        from bioagent.agents.orchestrator import OrchestratorAgent

        agent = OrchestratorAgent.__new__(OrchestratorAgent)
        state = {"phase_history": ["literature_review"]}
        result = agent.process_result('{"next_phase": "writing"}', [], state)
        assert "writing" in result["phase_history"]
        assert "literature_review" in result["phase_history"]
