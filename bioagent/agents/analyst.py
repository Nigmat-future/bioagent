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
        from bioagent.tools.execution.python_runner import execute_python
        from bioagent.tools.execution.package_manager import install_package
        from bioagent.tools.general.file_tools import read_file, write_file, list_files
        from bioagent.tools.registry import registry

        # Register execution tools if not already
        if "execute_python" not in registry.list_tools():
            registry.register(
                name="execute_python",
                description="Execute Python code in a subprocess and return output. Code runs in the workspace directory with a timeout.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to execute"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds (default 120, max 300)", "default": 120},
                    },
                    "required": ["code"],
                },
                function=execute_python,
            )
        if "install_package" not in registry.list_tools():
            registry.register(
                name="install_package",
                description="Install a Python package via pip if not already installed.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "package_name": {"type": "string", "description": "Package name (e.g. 'scanpy', 'scikit-learn')"},
                    },
                    "required": ["package_name"],
                },
                function=install_package,
            )
        if "write_file" not in registry.list_tools():
            registry.register(
                name="write_file",
                description="Write content to a file in the workspace.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path relative to workspace (e.g. 'figures/plot.py')"},
                        "content": {"type": "string", "description": "File content"},
                    },
                    "required": ["path", "content"],
                },
                function=write_file,
            )
        if "read_file" not in registry.list_tools():
            registry.register(
                name="read_file",
                description="Read a file from the workspace.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path relative to workspace"},
                    },
                    "required": ["path"],
                },
                function=read_file,
            )
        if "list_files" not in registry.list_tools():
            registry.register(
                name="list_files",
                description="List files in a workspace directory.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "description": "Directory path relative to workspace (empty for root)", "default": ""},
                    },
                },
                function=list_files,
            )

        tool_names = ["execute_python", "install_package", "write_file", "read_file", "list_files"]
        return registry.get_definitions(tool_names), registry.get_functions(tool_names)

    def build_messages(self, state: ResearchState) -> list[dict[str, Any]]:
        question = state.get("research_question", "")
        hypothesis = state.get("selected_hypothesis", {})
        plan = state.get("experiment_plan", {})
        gaps = state.get("research_gaps", [])
        summary = state.get("literature_summary", "")
        iteration = state.get("iteration_count", 0)
        errors = state.get("errors", [])
        prev_results = state.get("execution_results", [])

        h_text = hypothesis.get("text", "No hypothesis selected") if isinstance(hypothesis, dict) else str(hypothesis)
        plan_text = plan.get("content", str(plan)) if isinstance(plan, dict) else str(plan)

        parts = [
            f"## Research Question\n{question}\n\n",
            f"## Hypothesis to Test\n{h_text}\n\n",
            f"## Experiment Plan\n{plan_text[:3000]}\n\n",
        ]

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
            "- If real data is unavailable, generate realistic synthetic data\n"
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
