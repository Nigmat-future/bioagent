"""Node functions for the research graph — one per phase/agent."""

from __future__ import annotations

import logging
from typing import Any

from bioagent.state.schema import ResearchState

logger = logging.getLogger(__name__)


def orchestrator_node(state: ResearchState) -> dict[str, Any]:
    """Orchestrator: decide next phase. Delegates to OrchestratorAgent."""
    from bioagent.agents.orchestrator import OrchestratorAgent

    agent = OrchestratorAgent()
    return agent.run(state)


def literature_review_node(state: ResearchState) -> dict[str, Any]:
    """Literature review: search papers, read abstracts, build knowledge base.

    Uses LiteratureAgent with full BioMCP + ArXiv tool-use loop.
    """
    from bioagent.agents.literature import LiteratureAgent

    agent = LiteratureAgent()
    return agent.run(state)


def gap_analysis_node(state: ResearchState) -> dict[str, Any]:
    """Analyze literature to identify specific research gaps.

    Uses LLM to synthesize gaps from the literature summary and papers found.
    If gaps were already identified during literature review, refine them.
    """
    from bioagent.llm.clients import get_anthropic_client, get_anthropic_model
    from bioagent.llm.token_tracking import global_token_usage

    existing_gaps = state.get("research_gaps", [])
    summary = state.get("literature_summary", "")
    papers = state.get("papers", [])

    # If we already have substantive gaps, just pass through
    if existing_gaps and not any("placeholder" in g.lower() or "pending" in g.lower() for g in existing_gaps):
        logger.info("[gap_analysis] Gaps already identified, refining...")
    else:
        logger.info("[gap_analysis] Identifying gaps from literature...")

    client = get_anthropic_client()
    model = get_anthropic_model()

    paper_list = "\n".join(
        f"- [{p.get('id', '?')}] {p.get('title', 'Untitled')}"
        for p in papers[:20]
    ) if papers else "No papers found yet."

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=(
            "You are a bioinformatics research gap analyst. "
            "Given a literature summary and list of papers, identify 3-5 specific, "
            "actionable research gaps. Focus on computational and methodological opportunities. "
            "Output ONLY a numbered list of gaps, each as a single clear sentence."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"## Research Question\n{state.get('research_question', '')}\n\n"
                    f"## Literature Summary\n{summary[:3000]}\n\n"
                    f"## Papers Found\n{paper_list}\n\n"
                    f"## Existing Gaps\n{chr(10).join(existing_gaps) if existing_gaps else 'None yet.'}\n\n"
                    "Identify specific, actionable research gaps."
                ),
            }
        ],
    )

    if response.usage:
        global_token_usage.add(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    text = "\n".join(b.text for b in response.content if hasattr(b, "text"))

    import re
    gaps = re.findall(r"^\s*\d+[\.\)]\s*(.+)", text, re.MULTILINE)
    if not gaps:
        gaps = re.findall(r"^\s*[-*]\s*(.+)", text, re.MULTILINE)
    if not gaps:
        gaps = [text.strip()]

    return {"research_gaps": [g.strip() for g in gaps if len(g.strip()) > 10]}


def hypothesis_generation_node(state: ResearchState) -> dict[str, Any]:
    """Generate research hypotheses from identified gaps."""
    logger.info("[hypothesis_generation] Using placeholder")
    return {
        "hypotheses": [
            {
                "id": "h1",
                "text": "A novel computational approach can identify key biomarkers "
                        "associated with the research question",
                "rationale": "Based on identified gaps in current literature",
                "novelty": 7,
                "testability": 8,
            }
        ],
        "selected_hypothesis": {
            "id": "h1",
            "text": "A novel computational approach can identify key biomarkers "
                    "associated with the research question",
        },
    }


def experiment_design_node(state: ResearchState) -> dict[str, Any]:
    """Design computational experiments for the selected hypothesis."""
    logger.info("[experiment_design] Using placeholder")
    return {
        "experiment_plan": {
            "description": "Analyze public datasets to validate the hypothesis",
            "data_sources": ["GEO", "TCGA"],
            "methods": ["Differential expression analysis", "Pathway enrichment"],
            "expected_outcomes": "Identification of statistically significant biomarkers",
        },
    }


def code_execution_node(state: ResearchState) -> dict[str, Any]:
    """Execute analysis code and capture results."""
    logger.info("[code_execution] Using placeholder")
    return {
        "code_artifacts": [
            {"id": "c1", "filename": "analysis.py", "code": "# placeholder analysis code"}
        ],
        "execution_results": [
            {"id": "r1", "stdout": "Analysis completed successfully (placeholder)", "stderr": "", "exit_code": 0}
        ],
        "analysis_results": [
            {"description": "Placeholder analysis results", "significant_findings": 0}
        ],
    }


def result_validation_node(state: ResearchState) -> dict[str, Any]:
    """Validate whether execution results are satisfactory."""
    logger.info("[result_validation] Auto-passing for Phase 1")
    return {
        "validation_status": {"passed": True, "issues": []},
    }


def iteration_node(state: ResearchState) -> dict[str, Any]:
    """Handle retry/fix for failed analyses."""
    count = state.get("iteration_count", 0) + 1
    logger.info("[iteration] Iteration #%d", count)
    return {
        "iteration_count": count,
        "errors": [f"Entering iteration #{count}"],
    }


def writing_node(state: ResearchState) -> dict[str, Any]:
    """Draft paper sections."""
    logger.info("[writing] Using placeholder")
    question = state.get("research_question", "")
    return {
        "paper_sections": {
            "abstract": {
                "content": f"[Placeholder abstract for: {question}]",
                "status": "draft",
            },
            "introduction": {
                "content": "[Placeholder introduction]",
                "status": "draft",
            },
            "methods": {
                "content": "[Placeholder methods]",
                "status": "draft",
            },
            "results": {
                "content": "[Placeholder results]",
                "status": "draft",
            },
        },
    }


def figure_generation_node(state: ResearchState) -> dict[str, Any]:
    """Generate publication-quality figures."""
    logger.info("[figure_generation] Using placeholder")
    return {
        "figures": [
            {"id": "f1", "type": "heatmap", "caption": "Placeholder figure", "path": ""}
        ],
    }


def review_node(state: ResearchState) -> dict[str, Any]:
    """Self-review of the complete output."""
    logger.info("[review] Auto-approving for Phase 1")
    return {
        "review_feedback": [
            {"reviewer": "auto", "score": 8, "comments": "Auto-approved placeholder"}
        ],
    }
