"""Rich terminal display for research progress."""

from __future__ import annotations

import logging

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
logger = logging.getLogger(__name__)


def display_phase(phase: str) -> None:
    """Show current research phase."""
    console.print(f"\n[bold blue]>>> Phase:[/bold blue] {phase}")


def display_agent_result(agent_name: str, result: str) -> None:
    """Show agent output in a panel."""
    console.print(Panel(
        result[:500] + ("..." if len(result) > 500 else ""),
        title=f"[bold]{agent_name}[/bold]",
        border_style="green",
    ))


def display_error(message: str) -> None:
    """Show an error message."""
    console.print(f"[bold red]ERROR:[/bold red] {message}")


def display_summary(state: dict) -> None:
    """Show a summary table of the research state."""
    table = Table(title="Research Summary")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Topic", str(state.get("research_topic", "")))
    table.add_row("Phase", str(state.get("current_phase", "")))
    table.add_row("Papers", str(len(state.get("papers", []))))
    table.add_row("Hypotheses", str(len(state.get("hypotheses", []))))
    table.add_row("Code runs", str(len(state.get("execution_results", []))))
    table.add_row("Figures", str(len(state.get("figures", []))))
    table.add_row("Iterations", str(state.get("iteration_count", 0)))
    table.add_row("Errors", str(len(state.get("errors", []))))

    # Validation and review status
    validation = state.get("validation_status")
    if validation and isinstance(validation, dict):
        status_str = "PASSED" if validation.get("passed") else "FAILED"
        table.add_row("Validation", status_str)

    review_feedback = state.get("review_feedback", [])
    if review_feedback:
        latest = review_feedback[-1] if isinstance(review_feedback, list) else review_feedback
        if isinstance(latest, dict):
            score = latest.get("score", "?")
            rec = latest.get("recommendation", "?")
            table.add_row("Review", f"{score}/10 ({rec})")

    # Paper sections
    sections = state.get("paper_sections", {})
    if sections:
        table.add_row("Paper sections", ", ".join(sections.keys()))

    # Token usage
    try:
        from bioagent.llm.token_tracking import global_token_usage
        table.add_row("Tokens", global_token_usage.summary())
    except Exception:
        pass

    console.print(table)


def display_session_status(
    state: dict,
    thread_id: str,
    channels: dict | None = None,
) -> None:
    """Display the status of a research session."""
    console.print(f"\n[bold]Session Status[/bold] — [dim]{thread_id}[/dim]\n")

    table = Table()
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Thread ID", thread_id)
    table.add_row("Current Phase", str(state.get("current_phase", "unknown")))
    table.add_row("Phase History", " → ".join(state.get("phase_history", [])[-10:]))
    table.add_row("Iteration Count", str(state.get("iteration_count", 0)))
    table.add_row("Papers Found", str(len(state.get("papers", []))))
    table.add_row("Research Gaps", str(len(state.get("research_gaps", []))))
    table.add_row("Hypotheses", str(len(state.get("hypotheses", []))))
    table.add_row("Code Artifacts", str(len(state.get("code_artifacts", []))))
    table.add_row("Figures", str(len(state.get("figures", []))))
    table.add_row("Errors", str(len(state.get("errors", []))))

    validation = state.get("validation_status")
    if validation and isinstance(validation, dict):
        table.add_row("Validation", "PASSED" if validation.get("passed") else "FAILED")

    sections = state.get("paper_sections", {})
    if sections:
        table.add_row("Paper Sections", ", ".join(sections.keys()))

    review_feedback = state.get("review_feedback", [])
    if review_feedback:
        latest = review_feedback[-1] if isinstance(review_feedback, list) else review_feedback
        if isinstance(latest, dict):
            table.add_row("Review Score", f"{latest.get('score', '?')}/10")

    console.print(table)

    # Show literature summary preview
    summary = state.get("literature_summary", "")
    if summary:
        console.print(Panel(
            summary[:300] + ("..." if len(summary) > 300 else ""),
            title="[bold]Literature Summary[/bold]",
            border_style="blue",
        ))

    # Show errors if any
    errors = state.get("errors", [])
    if errors:
        console.print("\n[bold red]Recent Errors:[/bold red]")
        for err in errors[-5:]:
            console.print(f"  - {err[:200]}")

    console.print(f"\n[dim]Resume with: bioagent resume --thread {thread_id}[/dim]")


def display_code_execution(filename: str, status: str) -> None:
    """Show code execution status."""
    icon = "[green]OK[/green]" if status == "success" else "[red]FAIL[/red]"
    console.print(f"  {icon} {filename}")


def display_figure_generated(fig_path: str, fig_type: str) -> None:
    """Show figure generation notification."""
    console.print(f"  [green]Figure:[/green] {fig_path} ({fig_type})")


def display_literature_progress(papers_found: int, gaps_identified: int) -> None:
    """Show literature search progress."""
    console.print(f"  [cyan]Papers:[/cyan] {papers_found} | [cyan]Gaps:[/cyan] {gaps_identified}")
