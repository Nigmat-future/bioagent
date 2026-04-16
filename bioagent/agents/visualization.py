"""VisualizationAgent — creates publication-quality figures."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from bioagent.agents.base import BaseAgent
from bioagent.state.schema import ResearchState

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class VisualizationAgent(BaseAgent):
    """Creates publication-quality figures from analysis results.

    Uses matplotlib/seaborn with Nature/Science themes.
    """

    name = "visualization"

    @property
    def system_prompt(self) -> str:
        prompt_path = PROMPTS_DIR / "visualization.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "You are a scientific figure generation agent."

    def get_tools(self) -> tuple[list[dict], dict[str, Any]]:
        from bioagent.tools.execution.register import register_execution_tools
        from bioagent.tools.registry import registry

        # Idempotent registration — works even if AnalystAgent has not run yet
        register_execution_tools()

        tool_names = ["execute_python", "install_package", "write_file", "read_file", "list_files"]
        return registry.get_definitions(tool_names), registry.get_functions(tool_names)

    def build_messages(self, state: ResearchState) -> list[dict[str, Any]]:
        question = state.get("research_question", "")
        hypothesis = state.get("selected_hypothesis", {})
        analysis_results = state.get("analysis_results", [])
        paper_sections = state.get("paper_sections", {})
        existing_figures = state.get("figures", [])

        h_text = hypothesis.get("text", "") if isinstance(hypothesis, dict) else str(hypothesis)

        # Get results section to know what figures are needed
        results_text = paper_sections.get("results", {}).get("content", "") if isinstance(paper_sections, dict) else ""
        if not results_text:
            for r in analysis_results:
                if isinstance(r, dict):
                    results_text += r.get("results", "") + "\n"

        fig_count = len(existing_figures)

        return [
            {
                "role": "user",
                "content": (
                    f"## Research Question\n{question}\n\n"
                    f"## Hypothesis\n{h_text}\n\n"
                    f"## Results Text (determines what figures are needed)\n{results_text[:3000]}\n\n"
                    f"## Existing Figures: {fig_count}\n\n"
                    "## Your Task\n"
                    "1. Read the Results section to identify what figures are needed\n"
                    "2. Read any data files from workspace/data/ for plotting\n"
                    "3. Write matplotlib/seaborn code using the Nature theme\n"
                    "4. Execute the code and verify figures are saved\n"
                    "5. Report all generated figures\n\n"
                    "IMPORTANT: Always use these imports:\n"
                    "```python\n"
                    "from bioagent.tools.visualization.themes import apply_nature_theme, save_figure, create_figure\n"
                    "```\n\n"
                    "Output:\n"
                    "### GENERATED_FIGURES\n<figure list>"
                ),
            }
        ]

    def process_result(
        self,
        result_text: str,
        conversation: list[dict[str, Any]],
        state: ResearchState,
    ) -> dict[str, Any]:
        """Parse generated figures from output."""
        figures = []

        # Look for figure references in the output
        section = ""
        match = re.search(r"###\s*GENERATED_FIGURES\s*\n(.*?)(?:\n###|\Z)", result_text, re.DOTALL | re.IGNORECASE)
        if match:
            section = match.group(1)

        # Match figure entries
        fig_matches = re.finditer(
            r"Figure\s*(\d+):\s*(.+?)(?:\n|$).*?File:\s*(.+?)(?:\n|$).*?Caption:\s*(.+?)(?:\n|$).*?Type:\s*(.+?)(?:\n|$)",
            section, re.DOTALL | re.IGNORECASE,
        )
        for m in fig_matches:
            figures.append({
                "id": f"fig_{m.group(1)}",
                "title": m.group(2).strip(),
                "path": m.group(3).strip(),
                "caption": m.group(4).strip(),
                "type": m.group(5).strip(),
            })

        # Fallback: scan workspace/figures/ for generated files
        if not figures:

            from bioagent.config.settings import settings
            fig_dir = settings.workspace_path / "figures"
            if fig_dir.exists():
                for f in sorted(fig_dir.glob("*.pdf")):
                    figures.append({
                        "id": f"fig_{len(figures)+1}",
                        "title": f.stem.replace("_", " ").title(),
                        "path": str(f),
                        "caption": "",
                        "type": "analysis",
                    })

        return {"figures": figures}
