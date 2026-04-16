"""AnalystAgent — writes and executes bioinformatics analysis code."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioagent.agents.base import BaseAgent
from bioagent.state.schema import ResearchState

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class AnalystAgent(BaseAgent):
    """Writes Python code for analyses, executes it, and iterates on failures.

    Has access to code execution, file tools, and package management.
    Runs in a tight write-execute-debug loop.
    """

    name = "analyst"

    @property
    def system_prompt(self) -> str:
        prompt_path = PROMPTS_DIR / "analyst.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "You are a code analysis agent for bioinformatics."

    def get_tools(self) -> tuple[list[dict], dict[str, Any]]:
        from bioagent.tools.bioinformatics.expression_tools import register_tools as reg_expr
        from bioagent.tools.bioinformatics.genomic_tools import register_tools as reg_genomic
        from bioagent.tools.bioinformatics.sequence_tools import register_tools as reg_seq
        from bioagent.tools.execution.register import register_execution_tools
        from bioagent.tools.registry import registry

        # Register all tools (idempotent — each function checks before registering)
        register_execution_tools()
        reg_seq()
        reg_expr()
        reg_genomic()

        tool_names = [
            "execute_python",
            "install_package",
            "write_file",
            "read_file",
            "list_files",
            "get_sequence_analysis_template",
            "get_expression_analysis_template",
            "get_genomic_analysis_template",
        ]
        return registry.get_definitions(tool_names), registry.get_functions(tool_names)

    def build_messages(self, state: ResearchState) -> list[dict[str, Any]]:
        question = state.get("research_question", "")
        hypothesis = state.get("selected_hypothesis", {})
        plan = state.get("experiment_plan", {})
        state.get("research_gaps", [])
        state.get("literature_summary", "")
        iteration = state.get("iteration_count", 0)
        errors = state.get("errors", [])
        prev_results = state.get("execution_results", [])
        data_artifacts = state.get("data_artifacts", [])
        data_status = state.get("data_status", {})

        h_text = hypothesis.get("text", "No hypothesis selected") if isinstance(hypothesis, dict) else str(hypothesis)
        plan_text = plan.get("content", str(plan)) if isinstance(plan, dict) else str(plan)

        parts = [
            f"## Research Question\n{question}\n\n",
            f"## Hypothesis to Test\n{h_text}\n\n",
            f"## Experiment Plan\n{plan_text[:3000]}\n\n",
        ]

        # Provide available data context
        if data_artifacts:
            artifact_lines = "\n".join(
                f"- {a.get('path', '?')} — {a.get('description', '')} {a.get('size', '')}"
                for a in data_artifacts
                if isinstance(a, dict)
            )
            parts.append(
                f"## Available Data Files (downloaded by data acquisition stage)\n"
                f"{artifact_lines}\n\n"
                "Load these files in your analysis code. Do NOT generate synthetic data.\n\n"
            )
        elif data_status:
            status = data_status.get("status", "") if isinstance(data_status, dict) else ""
            if status == "manual_required":
                manual = data_status.get("manual_instructions", "") if isinstance(data_status, dict) else ""
                parts.append(
                    f"## Data Status: Manual Download Required\n"
                    f"{manual[:500]}\n\n"
                    "Call list_files('data') to check if any data has been manually placed. "
                    "If data is present, use it. If not, report the missing data clearly.\n\n"
                )
            else:
                parts.append(
                    "## Data Files\nCall list_files('data') to discover available datasets "
                    "before writing analysis code.\n\n"
                )
        else:
            parts.append(
                "## Data Files\nCall list_files('data') to discover available datasets "
                "before writing analysis code.\n\n"
            )

        if iteration > 0:
            parts.append(f"## Iteration #{iteration}\n")
            if errors:
                parts.append("### Previous Errors\n" + "\n".join(errors[-5:]) + "\n\n")
            if prev_results:
                last_result = prev_results[-1] if isinstance(prev_results, list) else prev_results
                if isinstance(last_result, dict):
                    parts.append(
                        f"### Last Execution\n"
                        f"Exit code: {last_result.get('exit_code', '?')}\n"
                        f"Stdout: {last_result.get('stdout', '')[:2000]}\n"
                        f"Stderr: {last_result.get('stderr', '')[:2000]}\n\n"
                    )

        parts.append(
            "## Your Task\n"
            "Write and execute Python code to perform the analysis described in the experiment plan.\n"
            "- Load data from workspace/data/ (downloaded by data acquisition stage)\n"
            "- NEVER generate synthetic or simulated data\n"
            "- Save all figures to workspace/figures/\n"
            "- Print key results so they are captured in stdout\n"
            "- Use print() for all output\n\n"
            "When done, output:\n"
            "### ANALYSIS_SUMMARY\n<summary>\n\n"
            "### RESULTS\n<structured results>\n\n"
            "### FIGURES\n<list of figures>\n\n"
            "### CODE_ARTIFACTS\n<list of scripts>"
        )

        return [{"role": "user", "content": "".join(parts)}]

    def process_result(
        self,
        result_text: str,
        conversation: list[dict[str, Any]],
        state: ResearchState,
    ) -> dict[str, Any]:
        """Parse analysis results from the analyst's output."""
        updates: dict[str, Any] = {}

        # Extract summary
        analysis_summary = self._extract_section(result_text, "ANALYSIS_SUMMARY")
        results_text = self._extract_section(result_text, "RESULTS")
        figures_text = self._extract_section(result_text, "FIGURES")
        code_text = self._extract_section(result_text, "CODE_ARTIFACTS")

        if analysis_summary or results_text:
            updates["analysis_results"] = [{
                "summary": analysis_summary[:2000] if analysis_summary else "",
                "results": results_text[:3000] if results_text else "",
                "raw_output": result_text[:5000],
            }]

        # Track figures mentioned
        if figures_text:
            import re
            fig_paths = re.findall(r"workspace/figures/[\w\-.]+\.png|workspace/figures/[\w\-.]+\.pdf", figures_text)
            updates["figures"] = [
                {"id": f"fig_{i+1}", "path": p, "caption": "", "type": "analysis"}
                for i, p in enumerate(fig_paths)
            ]

        # Track code artifacts from conversation
        code_artifacts = []
        execution_results = []
        for msg in conversation:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            # This is a tool result — check if it's execution output
                            result_content = block.get("content", "")
                            if isinstance(result_content, str) and ("exit_code" in result_content or "stdout" in result_content):
                                try:
                                    import json
                                    parsed = json.loads(result_content)
                                    if "exit_code" in parsed:
                                        execution_results.append(parsed)
                                except (json.JSONDecodeError, TypeError):
                                    pass

        if code_text:
            code_artifacts.append({"id": "analysis_code", "description": code_text[:1000]})

        updates["code_artifacts"] = code_artifacts
        updates["execution_results"] = execution_results

        return updates

    @staticmethod
    def _extract_section(text: str, header: str) -> str:
        import re
        pattern = rf"###\s*{header}\s*\n(.*?)(?=\n###\s|\Z)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""
