"""DataAcquisitionAgent — downloads real datasets needed for analysis."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioagent.agents.base import BaseAgent
from bioagent.state.schema import ResearchState

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class DataAcquisitionAgent(BaseAgent):
    """Downloads real datasets from GEO, cBioPortal, GDC, NCBI, and ENCODE.

    Falls back through a multi-level hierarchy for each dataset; if all
    automated downloads fail, generates detailed manual download instructions.

    Never produces synthetic or simulated data.
    """

    name = "data_acquisition"

    @property
    def system_prompt(self) -> str:
        prompt_path = PROMPTS_DIR / "data_acquisition.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return (
            "You are a data acquisition agent. Download real datasets only. "
            "Never generate synthetic data."
        )

    def get_tools(self) -> tuple[list[dict], dict[str, Any]]:
        from bioagent.tools.data.register import register_data_tools
        from bioagent.tools.execution.register import register_execution_tools
        from bioagent.tools.registry import registry

        register_data_tools()
        register_execution_tools()

        tool_names = [
            "download_url",
            "download_geo_dataset",
            "search_cbioportal_studies",
            "download_cbioportal_study",
            "search_gdc_datasets",
            "download_gdc_file",
            "download_ncbi_sequences",
            "search_encode_datasets",
            "download_encode_file",
            "generate_download_instructions",
            "list_files",
            "read_file",
            "install_package",
        ]
        return registry.get_definitions(tool_names), registry.get_functions(tool_names)

    def build_messages(self, state: ResearchState) -> list[dict[str, Any]]:
        plan = state.get("experiment_plan", {})
        topic = state.get("research_topic", "")
        question = state.get("research_question", "")
        hypothesis = state.get("selected_hypothesis", {})
        existing_artifacts = state.get("data_artifacts", [])

        plan_text = plan.get("content", str(plan)) if isinstance(plan, dict) else str(plan)
        h_text = (
            hypothesis.get("text", "") if isinstance(hypothesis, dict) else str(hypothesis)
        )

        parts = [
            f"## Research Topic\n{topic}\n\n",
            f"## Research Question\n{question}\n\n",
            f"## Hypothesis\n{h_text}\n\n",
            f"## Experiment Plan\n{plan_text[:4000]}\n\n",
        ]

        if existing_artifacts:
            artifact_lines = "\n".join(
                f"- {a.get('path', '?')} — {a.get('description', '')}"
                for a in existing_artifacts
                if isinstance(a, dict)
            )
            parts.append(
                f"## Already Downloaded Data\n"
                f"These files are already in workspace/data/:\n{artifact_lines}\n\n"
                "Do not re-download files that are already present.\n\n"
            )

        parts.append(
            "## Your Task\n"
            "Based on the experiment plan above, identify all datasets required and "
            "download them using the available tools. Follow the fallback hierarchy:\n"
            "1. Try primary source (GEO, cBioPortal, GDC, NCBI, or ENCODE)\n"
            "2. If primary fails, try secondary sources\n"
            "3. Only call generate_download_instructions as a LAST resort\n\n"
            "Start by calling list_files('data') to see what is already available.\n"
            "Then download each missing dataset.\n\n"
            "Output your results in the specified format:\n"
            "### DOWNLOAD_SUMMARY\n"
            "### DATA_MANIFEST\n"
            "### MANUAL_INSTRUCTIONS"
        )

        return [{"role": "user", "content": "".join(parts)}]

    def process_result(
        self,
        result_text: str,
        conversation: list[dict[str, Any]],
        state: ResearchState,
    ) -> dict[str, Any]:
        """Parse download results and update data_artifacts and data_status."""
        import re

        # Extract sections
        summary = self._extract_section(result_text, "DOWNLOAD_SUMMARY")
        manifest = self._extract_section(result_text, "DATA_MANIFEST")
        manual = self._extract_section(result_text, "MANUAL_INSTRUCTIONS")

        # Parse DATA_MANIFEST into artifact list
        data_artifacts = []
        if manifest:
            for line in manifest.strip().splitlines():
                line = line.strip().lstrip("- ")
                if not line:
                    continue
                parts = [p.strip() for p in line.split("|")]
                path = parts[0] if parts else line
                description = parts[1] if len(parts) > 1 else ""
                size = parts[2] if len(parts) > 2 else ""
                if path:
                    data_artifacts.append({
                        "path": path,
                        "description": description,
                        "size": size,
                    })

        # Determine overall status
        manual_required = bool(
            manual
            and "none required" not in manual.lower()
            and manual.strip()
        )

        if not data_artifacts and manual_required:
            status = "manual_required"
        elif not data_artifacts:
            status = "failed"
        elif manual_required:
            status = "partial"
        else:
            status = "complete"

        # Count datasets by scanning summary for SUCCESS/ERROR keywords
        datasets_requested = len(re.findall(r"(?i)dataset|accession|study|series", summary or ""))
        datasets_acquired = len(re.findall(r"(?i)\bSUCCESS\b", summary or ""))
        datasets_failed = len(re.findall(r"(?i)\bERROR\b|\bFAILED\b", summary or ""))

        data_status = {
            "status": status,
            "datasets_requested": datasets_requested,
            "datasets_acquired": datasets_acquired,
            "datasets_failed": datasets_failed,
            "summary": summary[:1000] if summary else "",
            "manual_instructions": manual[:2000] if manual else "",
        }

        logger.info(
            "[data_acquisition] Status: %s | acquired=%d failed=%d artifacts=%d",
            status, datasets_acquired, datasets_failed, len(data_artifacts),
        )

        updates: dict[str, Any] = {
            "data_status": data_status,
        }
        if data_artifacts:
            updates["data_artifacts"] = data_artifacts

        return updates

    @staticmethod
    def _extract_section(text: str, header: str) -> str:
        """Extract a named `### HEADER` section up to the next `###` or end.

        Uses a strict single-newline separator after the header so empty
        sections (header immediately followed by another header) correctly
        extract as the empty string rather than swallowing subsequent
        section bodies.
        """
        import re

        # Match the header on its own line. Use [ \t]* (horizontal whitespace
        # only) to avoid accidentally consuming the line-terminating newline
        # — `\s*` would be greedy over `\n` and skip past empty section
        # bodies, which produced incorrect extraction when a section had no
        # content (e.g. all downloads failed).
        pattern = rf"^###[ \t]*{header}[ \t]*\n(.*?)(?=^###[ \t]|\Z)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else ""
