"""LiteratureAgent — searches papers, reads abstracts, synthesizes findings, identifies gaps."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioagent.agents.base import BaseAgent
from bioagent.state.schema import ResearchState

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class LiteratureAgent(BaseAgent):
    """Conducts systematic literature review using BioMCP and ArXiv tools.

    Workflow:
    1. Load system prompt from prompts/literature.md
    2. Build user message with research question and state context
    3. Run agentic tool-use loop (search → read → summarize → synthesize)
    4. Parse structured output into state updates
    """

    name = "literature"

    @property
    def system_prompt(self) -> str:
        prompt_path = PROMPTS_DIR / "literature.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "You are a literature review agent for bioinformatics research."

    def get_tools(self) -> tuple[list[dict], dict[str, Any]]:
        from bioagent.tools.literature.arxiv_tools import register_tools as reg_arxiv
        from bioagent.tools.literature.biomcp_tools import register_tools as reg_biomcp
        from bioagent.tools.literature.paper_reader import register_tools as reg_reader
        from bioagent.tools.registry import registry

        # Ensure all literature tools are registered
        reg_biomcp()
        reg_arxiv()
        reg_reader()

        tool_names = [
            "search_articles",
            "get_article_details",
            "search_all",
            "discover_concepts",
            "get_gene_info",
            "enrich_genes",
            "search_arxiv",
            "get_arxiv_paper",
            "summarize_text",
            "extract_key_entities",
        ]
        return registry.get_definitions(tool_names), registry.get_functions(tool_names)

    def build_messages(self, state: ResearchState) -> list[dict[str, Any]]:
        topic = state.get("research_topic", "")
        question = state.get("research_question", "")
        existing_papers = state.get("papers", [])
        existing_summary = state.get("literature_summary", "")

        context_parts = [
            f"## Research Question\n{question}",
        ]
        if topic and topic != question:
            context_parts.append(f"## Broader Topic\n{topic}")

        if existing_papers:
            context_parts.append(
                f"## Previously Found Papers ({len(existing_papers)})\n"
                "We already have some papers. Focus on finding NEW papers "
                "and filling gaps in coverage."
            )

        if existing_summary and "placeholder" not in existing_summary.lower():
            context_parts.append(
                "## Existing Summary\n"
                "We already have a literature summary. Build upon it "
                "and identify any remaining gaps.\n\n"
                + existing_summary[:2000]
            )

        context_parts.append(
            "## Your Task\n"
            "1. Search for relevant papers using multiple queries\n"
            "2. Read the most relevant paper abstracts\n"
            "3. Summarize key findings\n"
            "4. Identify specific, actionable research gaps\n\n"
            "When done, output your findings in this format:\n\n"
            "### LITERATURE_SUMMARY\n"
            "<2-3 paragraph overview of the field>\n\n"
            "### RESEARCH_GAPS\n"
            "<numbered list of specific gaps>\n\n"
            "### KEY_PAPERS\n"
            "<list of PMID|title|relevance for top papers>"
        )

        return [
            {
                "role": "user",
                "content": "\n\n".join(context_parts),
            }
        ]

    def process_result(
        self,
        result_text: str,
        conversation: list[dict[str, Any]],
        state: ResearchState,
    ) -> dict[str, Any]:
        """Parse the literature agent's output into structured state updates."""
        # Extract structured sections from the output
        literature_summary = self._extract_section(result_text, "LITERATURE_SUMMARY")
        research_gaps = self._extract_gaps(result_text)
        key_papers = self._extract_papers(result_text, state)

        # If parsing failed, use the full text as summary
        if not literature_summary:
            literature_summary = result_text[:3000]
        if not research_gaps:
            research_gaps = ["Literature review completed — specific gaps to be refined in gap_analysis phase"]

        updates = {
            "literature_summary": literature_summary,
            "research_gaps": research_gaps,
        }
        if key_papers:
            updates["papers"] = key_papers
            # Populate references field with structured citation data for export
            references = [
                {
                    "id": p.get("id", ""),
                    "title": p.get("title", ""),
                    "authors": p.get("authors", ""),
                    "journal": p.get("journal", ""),
                    "year": p.get("year", ""),
                    "relevance": p.get("relevance", ""),
                }
                for p in key_papers
                if p.get("id")
            ]
            if references:
                updates["references"] = references

        return updates

    @staticmethod
    def _extract_section(text: str, header: str) -> str:
        """Extract text between ### HEADER and next ### or end."""
        import re
        pattern = rf"###\s*{header}\s*\n(.*?)(?=\n###\s|\Z)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def _extract_gaps(text: str) -> list[str]:
        """Extract numbered research gaps from the output."""
        import re

        gaps_section = LiteratureAgent._extract_section(text, "RESEARCH_GAPS")
        if not gaps_section:
            # Try finding numbered list anywhere in text
            gaps_section = text

        # Match numbered items: "1. ..." or "1) ..."
        gap_matches = re.findall(r"^\s*\d+[\.\)]\s*(.+)", gaps_section, re.MULTILINE)
        if gap_matches:
            return [g.strip() for g in gap_matches if len(g.strip()) > 10]

        # Match bullet items: "- ..."
        bullet_matches = re.findall(r"^\s*[-*]\s*(.+)", gaps_section, re.MULTILINE)
        if bullet_matches:
            return [g.strip() for g in bullet_matches if len(g.strip()) > 10]

        return []

    @staticmethod
    def _extract_papers(text: str, state: ResearchState) -> list[dict]:
        """Extract paper references from the output.

        Supports multiple formats:
          - PMID|Title|Relevance
          - PMID: 12345678 - Title
          - **PMID: 12345678** or **12345678** (bold markdown)
          - [PMID: 12345678] Title
          - Any line containing a 6+ digit PMID
        """
        import re

        # Search the entire text for PMIDs (not just KEY_PAPERS section)
        full_text = text
        existing_ids = {p.get("id") for p in state.get("papers", [])}
        papers = []
        seen = set()

        # Strategy 1: PMID|Title|Relevance pipe-delimited lines
        for line in full_text.splitlines():
            line = line.strip()
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                pmid_match = re.search(r"(\d{6,})", parts[0])
                if pmid_match and len(parts) >= 2:
                    pmid = pmid_match.group(1)
                    if pmid not in existing_ids and pmid not in seen:
                        seen.add(pmid)
                        papers.append({
                            "id": pmid,
                            "title": parts[1] if len(parts) > 1 else "",
                            "relevance": parts[2] if len(parts) > 2 else "",
                        })

        # Strategy 2: Find all PMIDs mentioned with context (PMID: xxx or **xxx**)
        if not papers:
            # Match patterns like "PMID: 30820047", "PMID:30820047", "**30820047**"
            pmid_pattern = r"(?:PMID:?\s*|\*\*)(\d{6,})(?:\*\*|[\s,\)\]])"
            # Also match lines that reference a PMID with a title
            line_pattern = r"(?:PMID:?\s*)(\d{6,})[\s\-–—:]*([^\n]{10,})"

            for match in re.finditer(line_pattern, full_text):
                pmid = match.group(1)
                title = match.group(2).strip().rstrip(".,;")
                if pmid not in existing_ids and pmid not in seen and len(title) > 10:
                    seen.add(pmid)
                    papers.append({"id": pmid, "title": title})

            # Fallback: just collect PMIDs without titles
            if not papers:
                for match in re.finditer(pmid_pattern, full_text):
                    pmid = match.group(1)
                    if pmid not in existing_ids and pmid not in seen:
                        seen.add(pmid)
                        papers.append({"id": pmid, "title": ""})

        return papers
