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

    console.print(table)
