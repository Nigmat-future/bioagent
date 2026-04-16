"""WriterAgent — drafts publication-quality paper sections."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioagent.agents.base import BaseAgent
from bioagent.state.schema import ResearchState

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class WriterAgent(BaseAgent):
    """Drafts paper sections based on research findings.

    Uses LLM to write each section with full context from state:
    literature, hypothesis, experiment plan, and analysis results.
    """

    name = "writer"

    @property
    def system_prompt(self) -> str:
        prompt_path = PROMPTS_DIR / "writer.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "You are a scientific paper writing agent."

    def get_tools(self) -> tuple[list[dict], dict[str, Any]]:
        # Writer doesn't need tools — pure text generation
        return [], {}

    def build_messages(self, state: ResearchState) -> list[dict[str, Any]]:
        question = state.get("research_question", "")
        hypothesis = state.get("selected_hypothesis", {})
        plan = state.get("experiment_plan", {})
        analysis_results = state.get("analysis_results", [])
        literature = state.get("literature_summary", "")
        gaps = state.get("research_gaps", [])
        papers = state.get("papers", [])
        figures = state.get("figures", [])
        existing_sections = state.get("paper_sections", {})
        revision_notes = state.get("revision_notes", [])
        review_feedback = state.get("review_feedback", [])

        h_text = hypothesis.get("text", "") if isinstance(hypothesis, dict) else str(hypothesis)
        plan_text = plan.get("content", str(plan)) if isinstance(plan, dict) else str(plan)

        # Build results context
        results_text = ""
        for r in analysis_results:
            if isinstance(r, dict):
                results_text += r.get("summary", "") + "\n"
                results_text += r.get("results", "") + "\n"

        # Build paper references
        paper_refs = "\n".join(
            f"- PMID: {p.get('id', '?')} — {p.get('title', 'Untitled')}"
            for p in papers[:20]
        )

        # Build figure context
        fig_context = ""
        for i, f in enumerate(figures, 1):
            if isinstance(f, dict):
                fig_context += f"- Figure {i}: {f.get('caption', f.get('type', 'Analysis figure'))}\n"

        context_parts = [
            f"## Research Question\n{question}\n\n",
            f"## Hypothesis\n{h_text}\n\n",
            f"## Experiment Plan\n{plan_text[:2000]}\n\n",
        ]

        if results_text:
            context_parts.append(f"## Analysis Results\n{results_text[:3000]}\n\n")
        if literature:
            context_parts.append(f"## Literature Summary\n{literature[:2000]}\n\n")
        if paper_refs:
            context_parts.append(f"## Key Papers (cite by PMID)\n{paper_refs}\n\n")
        if fig_context:
            context_parts.append(f"## Generated Figures\n{fig_context}\n\n")
        if gaps:
            context_parts.append("## Research Gaps Addressed\n" + "\n".join(gaps[:5]) + "\n\n")

        # Revision mode: reviewer has already scored the paper and left specific issues
        is_revision = bool(revision_notes) and bool(existing_sections)
        if is_revision:
            latest_review = review_feedback[-1] if review_feedback else {}
            score = latest_review.get("score", "?") if isinstance(latest_review, dict) else "?"
            notes_text = "\n".join(f"- {note}" for note in revision_notes)
            context_parts.append(
                f"## Reviewer Score: {score}/10 — Revision Required\n\n"
                f"## Required Revisions\n{notes_text}\n\n"
                "## Your Task\n"
                "REVISE the existing paper sections to address ALL the reviewer issues listed above. "
                "Rewrite every section that needs improvement. "
                "Output each section using the same ### SECTION_NAME format."
            )
        elif existing_sections:
            existing_names = ", ".join(existing_sections.keys())
            context_parts.append(
                f"## Already Written Sections: {existing_names}\n"
                "Focus on writing the MISSING sections. Don't rewrite existing ones."
            )
        else:
            context_parts.append(
                "## Your Task\n"
                "Write ALL paper sections: Abstract, Introduction, Methods, Results, Discussion."
            )

        return [{"role": "user", "content": "".join(context_parts)}]

    def process_result(
        self,
        result_text: str,
        conversation: list[dict[str, Any]],
        state: ResearchState,
    ) -> dict[str, Any]:
        """Parse paper sections from the writer's output.

        Merges new/revised sections into existing ones so that sections the
        writer did not touch are preserved (paper_sections has no list reducer
        — returning a partial dict would replace and lose the rest).
        """
        import re

        existing_sections = state.get("paper_sections", {})
        # Start from a copy of existing sections; only overwrite what the writer produced
        sections = dict(existing_sections)
        headers = ["ABSTRACT", "INTRODUCTION", "METHODS", "RESULTS", "DISCUSSION"]
        found_any = False

        for header in headers:
            pattern = rf"###\s*{header}\s*\n(.*?)(?=\n###\s|\Z)"
            match = re.search(pattern, result_text, re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                if len(content) > 50:  # Skip trivial sections
                    old_version = existing_sections.get(header.lower(), {}).get("version", 0)
                    sections[header.lower()] = {
                        "content": content,
                        "status": "draft",
                        "version": old_version + 1,
                    }
                    found_any = True

        if not found_any:
            # Fallback: treat entire output as results section
            old_version = existing_sections.get("results", {}).get("version", 0)
            sections["results"] = {
                "content": result_text[:5000],
                "status": "draft",
                "version": old_version + 1,
            }

        return {"paper_sections": sections}
