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
    """Generate research hypotheses from identified gaps using PlannerAgent."""
    from bioagent.agents.planner import PlannerAgent

    logger.info("[hypothesis_generation] Running PlannerAgent...")
    agent = PlannerAgent()
    return agent.run(state)


def experiment_design_node(state: ResearchState) -> dict[str, Any]:
    """Design computational experiments for the selected hypothesis.

    If a hypothesis is already selected, refine the experiment plan.
    If not, delegate to the PlannerAgent for full planning.
    """
    from bioagent.agents.planner import PlannerAgent

    selected = state.get("selected_hypothesis")
    if not selected:
        logger.info("[experiment_design] No hypothesis selected, running PlannerAgent...")
        agent = PlannerAgent()
        return agent.run(state)

    # If hypothesis exists but plan is missing or placeholder, re-run planner
    plan = state.get("experiment_plan")
    if not plan or (isinstance(plan, dict) and "placeholder" in str(plan).lower()):
        logger.info("[experiment_design] Refining experiment plan...")
        agent = PlannerAgent()
        return agent.run(state)

    logger.info("[experiment_design] Plan already exists, passing through")
    return {}


def code_execution_node(state: ResearchState) -> dict[str, Any]:
    """Execute analysis code using AnalystAgent."""
    from bioagent.agents.analyst import AnalystAgent

    logger.info("[code_execution] Running AnalystAgent...")
    agent = AnalystAgent()
    return agent.run(state)


def result_validation_node(state: ResearchState) -> dict[str, Any]:
    """Validate whether execution results are satisfactory.

    Checks if analysis_results contain meaningful output.
    If code failed (errors in execution_results), marks as failed.
    """
    results = state.get("analysis_results", [])
    exec_results = state.get("execution_results", [])
    errors = state.get("errors", [])

    # Check if there are any actual results
    if results:
        last_result = results[-1] if isinstance(results, list) else results
        if isinstance(last_result, dict):
            summary = last_result.get("summary", "")
            results_text = last_result.get("results", "")
            if summary or results_text:
                logger.info("[result_validation] Results validated successfully")
                return {
                    "validation_status": {
                        "passed": True,
                        "issues": [],
                        "summary": "Analysis produced meaningful results",
                    }
                }

    # Check if execution had errors
    if exec_results:
        last_exec = exec_results[-1] if isinstance(exec_results, list) else exec_results
        if isinstance(last_exec, dict) and last_exec.get("exit_code", 0) != 0:
            stderr = last_exec.get("stderr", "Unknown error")
            logger.warning("[result_validation] Code execution failed: %s", stderr[:200])
            return {
                "validation_status": {
                    "passed": False,
                    "issues": [f"Code execution failed: {stderr[:500]}"],
                },
                "errors": [f"Analysis code failed: {stderr[:300]}"],
            }

    # No results and no errors — likely the analyst didn't produce output
    logger.info("[result_validation] No results found, marking for retry")
    return {
        "validation_status": {
            "passed": False,
            "issues": ["No analysis results produced"],
        },
        "errors": ["Analyst did not produce analyzable results"],
    }


def iteration_node(state: ResearchState) -> dict[str, Any]:
    """Handle retry/fix for failed analyses.

    Sets phase to code_execution so the AnalystAgent re-runs with
    the error context from the previous attempt.
    """
    count = state.get("iteration_count", 0) + 1
    logger.info("[iteration] Iteration #%d — routing back to code_execution", count)
    return {
        "iteration_count": count,
        "current_phase": "code_execution",
    }


def human_approval_node(state: ResearchState) -> dict[str, Any]:
    """Pause for human approval at key decision points.

    Only active when settings.human_in_loop is True.
    Automatically passes through otherwise.
    """
    from bioagent.config.settings import settings

    if not settings.human_in_loop:
        return {}

    phase = state.get("current_phase", "unknown")
    question = state.get("research_question", "")

    # Build context summary for the user
    context_parts = [f"Current phase: {phase}"]
    if state.get("selected_hypothesis"):
        h = state["selected_hypothesis"]
        h_text = h.get("text", "") if isinstance(h, dict) else str(h)
        context_parts.append(f"Hypothesis: {h_text[:200]}")
    if state.get("experiment_plan"):
        plan = state["experiment_plan"]
        plan_text = plan.get("content", str(plan))[:200] if isinstance(plan, dict) else str(plan)[:200]
        context_parts.append(f"Plan: {plan_text}")

    print(f"\n{'='*60}")
    print(f"  Human Approval Required")
    print(f"  Question: {question}")
    print(f"\n  " + "\n  ".join(context_parts))
    print(f"{'='*60}")

    try:
        feedback = input("\n  Approve? (y/n/edit): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        feedback = "y"

    if feedback in ("n", "no"):
        return {
            "human_feedback": "User rejected the current direction. Please reconsider.",
            "errors": ["Human rejected at phase: " + phase],
        }
    elif feedback in ("edit", "e"):
        try:
            user_input = input("  Enter guidance: ").strip()
        except (EOFError, KeyboardInterrupt):
            user_input = ""
        return {"human_feedback": user_input or "User requested revision."}

    return {"human_feedback": None}


def writing_node(state: ResearchState) -> dict[str, Any]:
    """Draft paper sections using WriterAgent."""
    from bioagent.agents.writer import WriterAgent

    logger.info("[writing] Running WriterAgent...")
    agent = WriterAgent()
    return agent.run(state)


def figure_generation_node(state: ResearchState) -> dict[str, Any]:
    """Generate publication-quality figures using VisualizationAgent."""
    from bioagent.agents.visualization import VisualizationAgent

    logger.info("[figure_generation] Running VisualizationAgent...")
    agent = VisualizationAgent()
    return agent.run(state)


def review_node(state: ResearchState) -> dict[str, Any]:
    """Self-review of the complete paper draft using LLM reviewer."""
    from pathlib import Path

    from bioagent.llm.clients import get_anthropic_client, get_anthropic_model
    from bioagent.llm.token_tracking import global_token_usage

    logger.info("[review] Running self-review...")

    # Load review prompt
    prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
    review_prompt = (prompts_dir / "review.md").read_text(encoding="utf-8")

    # Assemble the full paper for review
    sections = state.get("paper_sections", {})
    paper_text = ""
    for name, section in sections.items():
        if isinstance(section, dict):
            content = section.get("content", "")
        else:
            content = str(section)
        paper_text += f"\n\n### {name.upper()}\n{content}\n"

    figures = state.get("figures", [])
    fig_summary = "\n".join(
        f"- Figure {i+1}: {f.get('caption', f.get('type', 'figure'))} ({f.get('type', 'unknown')})"
        for i, f in enumerate(figures)
        if isinstance(f, dict)
    ) if figures else "No figures generated."

    hypothesis = state.get("selected_hypothesis", {})
    h_text = hypothesis.get("text", "") if isinstance(hypothesis, dict) else str(hypothesis)

    client = get_anthropic_client()
    model = get_anthropic_model()

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=review_prompt,
        messages=[
            {
                "role": "user",
                "content": (
                    f"## Research Question\n{state.get('research_question', '')}\n\n"
                    f"## Hypothesis\n{h_text}\n\n"
                    f"## Paper Draft\n{paper_text[:8000]}\n\n"
                    f"## Figures\n{fig_summary}\n\n"
                    "Please review this paper draft thoroughly. "
                    "Provide a score (1-10), strengths, weaknesses, and specific issues."
                ),
            }
        ],
    )

    if response.usage:
        global_token_usage.add(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    review_text = "\n".join(b.text for b in response.content if hasattr(b, "text"))

    # Parse score from review
    import re

    score = 5  # default
    score_match = re.search(r"###\s*SCORE\s*\n\s*(\d+)", review_text, re.IGNORECASE)
    if not score_match:
        score_match = re.search(r"(?:score|rating)[:\s]+(\d+)(?:\s*/\s*10)?", review_text, re.IGNORECASE)
    if score_match:
        score = int(score_match.group(1))
        score = min(max(score, 1), 10)  # clamp to 1-10

    # Parse recommendation
    recommendation = "minor_revision"
    rec_match = re.search(
        r"###\s*RECOMMENDATION\s*\n\s*(accept|minor_revision|major_revision|reject)",
        review_text, re.IGNORECASE,
    )
    if rec_match:
        recommendation = rec_match.group(1).lower()

    # Parse revision notes from SPECIFIC_ISSUES
    revision_notes = []
    issues_section = re.search(
        r"###\s*SPECIFIC_ISSUES\s*\n(.*?)(?=\n###|\Z)",
        review_text, re.DOTALL | re.IGNORECASE,
    )
    if issues_section:
        for line in issues_section.group(1).strip().split("\n"):
            line = line.strip().lstrip("- ")
            if line:
                revision_notes.append(line)

    logger.info("[review] Score: %d/10, Recommendation: %s", score, recommendation)

    return {
        "review_feedback": [
            {
                "reviewer": "self_review",
                "score": score,
                "recommendation": recommendation,
                "comments": review_text,
            }
        ],
        "revision_notes": revision_notes,
        "current_phase": "complete" if score >= 7 else "writing",
    }
