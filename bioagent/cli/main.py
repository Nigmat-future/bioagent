"""BioAgent CLI — command-line interface for the research agent."""

from __future__ import annotations

import logging
import uuid
from typing import Optional

import typer
from rich.console import Console

from bioagent.cli.display import console, display_error, display_phase, display_summary

app = typer.Typer(
    name="bioagent",
    help="Autonomous bioinformatics research agent.",
    no_args_is_help=True,
)

logger = logging.getLogger(__name__)


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@app.command()
def research(
    question: str = typer.Argument(help="Research question to investigate"),
    topic: Optional[str] = typer.Option(None, "--topic", "-t", help="Broader research topic"),
    thread_id: Optional[str] = typer.Option(None, "--thread", help="Resume an existing thread"),
    max_steps: int = typer.Option(30, "--max-steps", help="Max graph steps before stopping"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
) -> None:
    """Start a new research session or resume an existing one."""
    _setup_logging(log_level)

    from bioagent.graph.research_graph import compile_research_graph
    from bioagent.tools.execution.sandbox import ensure_workspace

    # Ensure workspace exists
    ensure_workspace()

    # Compile the graph
    try:
        graph = compile_research_graph()
    except Exception as exc:
        display_error(f"Failed to compile graph: {exc}")
        raise typer.Exit(1) from exc

    # Initial state
    initial_state = {
        "research_topic": topic or question,
        "research_question": question,
        "current_phase": "literature_review",
        "phase_history": [],
        "iteration_count": 0,
        "papers": [],
        "literature_summary": "",
        "research_gaps": [],
        "knowledge_base": {},
        "hypotheses": [],
        "selected_hypothesis": None,
        "experiment_plan": None,
        "code_artifacts": [],
        "execution_results": [],
        "data_artifacts": [],
        "analysis_results": [],
        "validation_status": None,
        "paper_sections": {},
        "references": [],
        "paper_metadata": {},
        "figures": [],
        "review_feedback": [],
        "revision_notes": [],
        "messages": [],
        "errors": [],
        "human_feedback": None,
        "should_stop": False,
    }

    # Thread ID for checkpointing
    tid = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": tid}}

    console.print(f"\n[bold green]BioAgent Research Session[/bold green]")
    console.print(f"[dim]Thread: {tid}[/dim]")
    console.print(f"[bold]Question:[/bold] {question}")
    if topic:
        console.print(f"[bold]Topic:[/bold] {topic}")
    console.print()

    # Run the graph
    try:
        step = 0
        for event in graph.stream(initial_state, config=config, stream_mode="values"):
            step += 1
            phase = event.get("current_phase", "?")
            display_phase(f"{phase} (step {step})")

            if step >= max_steps:
                console.print(f"\n[yellow]Reached max steps ({max_steps}). Stopping.[/yellow]")
                break

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Session state is saved.[/yellow]")
        console.print(f"[dim]Resume with: bioagent resume --thread {tid}[/dim]")
    except Exception as exc:
        display_error(f"Graph execution failed: {exc}")
        logger.exception("Graph execution error")
        raise typer.Exit(1) from exc

    # Show final summary
    console.print("\n[bold green]Research Complete[/bold green]")
    display_summary(event if 'event' in dir() else initial_state)
    console.print(f"\n[dim]Thread ID: {tid}[/dim]")


@app.command()
def resume(
    thread_id: str = typer.Option(..., "--thread", "-t", help="Thread ID to resume"),
) -> None:
    """Resume a paused research session."""
    console.print(f"[yellow]Resume not yet implemented. Thread: {thread_id}[/yellow]")


@app.command()
def status(
    thread_id: str = typer.Option(..., "--thread", "-t", help="Thread ID to check"),
) -> None:
    """Show the status of a research session."""
    console.print(f"[yellow]Status not yet implemented. Thread: {thread_id}[/yellow]")


if __name__ == "__main__":
    app()
