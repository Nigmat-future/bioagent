"""PlannerAgent — generates hypotheses and designs computational experiments."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from bioagent.agents.base import BaseAgent
from bioagent.state.schema import ResearchState

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PlannerAgent(BaseAgent):
    """Generates research hypotheses from literature gaps and designs experiments.

    Uses BioMCP tools for gene/pathway context, then outputs structured
    hypotheses and experiment plans.
    """

    name = "planner"

    @property
    def system_prompt(self) -> str:
        prompt_path = PROMPTS_DIR / "planner.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "You are a research planning agent for bioinformatics."

    def get_tools(self) -> tuple[list[dict], dict[str, Any]]:
        from bioagent.tools.literature.biomcp_tools import register_tools as reg_biomcp
        from bioagent.tools.registry import registry

        reg_biomcp()
        tool_names = [
            "get_gene_info",
            "enrich_genes",
            "search_articles",
            "search_all",
        ]
        return registry.get_definitions(tool_names), registry.get_functions(tool_names)

    def build_messages(self, state: ResearchState) -> list[dict[str, Any]]:
        question = state.get("research_question", "")
        summary = state.get("literature_summary", "")
        gaps = state.get("research_gaps", [])
        papers = state.get("papers", [])

        gaps_text = "\n".join(f"  {i}. {g}" for i, g in enumerate(gaps, 1)) if gaps else "No gaps identified."
        paper_count = len(papers)

        return [
            {
                "role": "user",
                "content": (
                    f"## Research Question\n{question}\n\n"
                    f"## Literature Summary ({paper_count} papers found)\n"
                    f"{summary[:3000]}\n\n"
                    f"## Identified Research Gaps\n{gaps_text}\n\n"
                    "## Your Task\n"
                    "1. Generate 2-3 novel, computationally testable hypotheses\n"
                    "2. Select the best one (highest novelty + testability)\n"
                    "3. Design a detailed computational experiment\n\n"
                    "Output your results using the sections:\n"
                    "### HYPOTHESES\n### SELECTED_HYPOTHESIS\n### EXPERIMENT_PLAN"
                ),
            }
        ]

    def process_result(
        self,
        result_text: str,
        conversation: list[dict[str, Any]],
        state: ResearchState,
    ) -> dict[str, Any]:
        """Parse hypotheses and experiment plan from planner output."""
        hypotheses = self._extract_hypotheses(result_text)
        selected = self._extract_selected(result_text, hypotheses)
        experiment_plan = self._extract_section(result_text, "EXPERIMENT_PLAN")

        updates: dict[str, Any] = {}
        if hypotheses:
            updates["hypotheses"] = hypotheses
        if selected:
            updates["selected_hypothesis"] = selected
        if experiment_plan:
            updates["experiment_plan"] = {"content": experiment_plan}
        else:
            # Fallback: use the full text as the plan
            updates["experiment_plan"] = {"content": result_text[:5000]}

        return updates

    @staticmethod
    def _extract_section(text: str, header: str) -> str:
        pattern = rf"###\s*{header}\s*\n(.*?)(?=\n###\s|\Z)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_hypotheses(text: str) -> list[dict]:
        section = PlannerAgent._extract_section(text, "HYPOTHESES")
        if not section:
            return []

        hypotheses = []
        # Match "H1: ..." or "Hypothesis 1: ..." patterns
        blocks = re.split(r"\n(?=H\d+:|\*\*H\d+)", section)

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # Extract hypothesis text
            h_match = re.match(r"(?:\*\*)?H(\d+):\s*(.+?)(?:\*\*)?(?:\n|$)", block, re.DOTALL)
            if not h_match:
                continue

            h_id = f"h{h_match.group(1)}"
            h_text = h_match.group(2).strip()

            # Extract scores
            novelty = 5
            testability = 5
            novelty_m = re.search(r"Novelty:\s*(\d+)", block)
            testability_m = re.search(r"Testability:\s*(\d+)", block)
            if novelty_m:
                novelty = int(novelty_m.group(1))
            if testability_m:
                testability = int(testability_m.group(1))

            # Extract rationale
            rationale = ""
            rat_m = re.search(r"Rationale:\s*(.+?)(?:\n\s*(?:Data|Methods|Novelty)|$)", block, re.DOTALL)
            if rat_m:
                rationale = rat_m.group(1).strip()

            hypotheses.append({
                "id": h_id,
                "text": h_text[:500],
                "novelty": novelty,
                "testability": testability,
                "rationale": rationale[:500],
            })

        return hypotheses

    @staticmethod
    def _extract_selected(text: str, hypotheses: list[dict]) -> dict | None:
        section = PlannerAgent._extract_section(text, "SELECTED_HYPOTHESIS")
        if not section:
            # Default: return the highest-scoring hypothesis
            if hypotheses:
                best = max(hypotheses, key=lambda h: h.get("novelty", 0) + h.get("testability", 0))
                return best
            return None

        # Try to match a hypothesis ID
        for h in hypotheses:
            if h["id"].upper() in section.upper() or h["text"][:50] in section:
                return h

        # Return as free-text selection
        return {
            "id": "selected",
            "text": section[:500],
            "novelty": 0,
            "testability": 0,
            "rationale": "",
        }
