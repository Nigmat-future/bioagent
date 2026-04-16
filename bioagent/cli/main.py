"""BioAgent CLI — command-line interface for the research agent."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from bioagent.cli.display import (
    console,
    display_error,
    display_phase,
    display_session_status,
    display_summary,
)

app = typer.Typer(
    name="bioagent",
    help="Autonomous bioinformatics research agent.",
    no_args_is_help=True,
)

logger = logging.getLogger(__name__)


def _display_state_progress(state: dict, prev_state: dict | None) -> None:
    """Display incremental progress from state changes between steps."""
    if prev_state is None:
        return

    # New papers found
    prev_papers = len(prev_state.get("papers", []))
    curr_papers = len(state.get("papers", []))
    if curr_papers > prev_papers:
        new_count = curr_papers - prev_papers
        console.print(f"  [cyan]Papers:[/cyan] +{new_count} found (total: {curr_papers})")

    # New research gaps
    prev_gaps = len(prev_state.get("research_gaps", []))
    curr_gaps = len(state.get("research_gaps", []))
    if curr_gaps > prev_gaps:
        new_count = curr_gaps - prev_gaps
        console.print(f"  [cyan]Gaps:[/cyan] +{new_count} identified (total: {curr_gaps})")

    # New hypotheses
    prev_hyp = len(prev_state.get("hypotheses", []))
    curr_hyp = len(state.get("hypotheses", []))
    if curr_hyp > prev_hyp:
        new_count = curr_hyp - prev_hyp
        console.print(f"  [cyan]Hypotheses:[/cyan] +{new_count} generated (total: {curr_hyp})")

    # Code execution
    prev_code = len(prev_state.get("code_artifacts", []))
    curr_code = len(state.get("code_artifacts", []))
    if curr_code > prev_code:
        new_count = curr_code - prev_code
        console.print(f"  [green]Code:[/green] +{new_count} scripts executed (total: {curr_code})")

    # Validation result
    validation = state.get("validation_status")
    prev_validation = prev_state.get("validation_status")
    if validation and validation != prev_validation:
        if isinstance(validation, dict):
            status = "PASSED" if validation.get("passed") else "FAILED"
            color = "green" if validation.get("passed") else "red"
            console.print(f"  [{color}]Validation:[/{color}] {status}")

    # New paper sections
    prev_sections = set(prev_state.get("paper_sections", {}).keys())
    curr_sections = set(state.get("paper_sections", {}).keys())
    new_sections = curr_sections - prev_sections
    if new_sections:
        console.print(f"  [cyan]Sections written:[/cyan] {', '.join(sorted(new_sections))}")

    # New figures
    prev_figs = len(prev_state.get("figures", []))
    curr_figs = len(state.get("figures", []))
    if curr_figs > prev_figs:
        new_count = curr_figs - prev_figs
        console.print(f"  [green]Figures:[/green] +{new_count} generated (total: {curr_figs})")

    # Review score
    prev_review = prev_state.get("review_feedback", [])
    curr_review = state.get("review_feedback", [])
    if len(curr_review) > len(prev_review):
        latest = curr_review[-1] if isinstance(curr_review, list) else curr_review
        if isinstance(latest, dict):
            score = latest.get("score", "?")
            rec = latest.get("recommendation", "?")
            color = "green" if (isinstance(score, int) and score >= 7) else "yellow"
            console.print(f"  [{color}]Review:[/{color}] {score}/10 ({rec})")

    # Errors
    prev_errs = len(prev_state.get("errors", []))
    curr_errs = len(state.get("errors", []))
    if curr_errs > prev_errs:
        console.print(f"  [red]Errors:[/red] +{curr_errs - prev_errs} new")

    # Iteration
    prev_iter = prev_state.get("iteration_count", 0)
    curr_iter = state.get("iteration_count", 0)
    if curr_iter > prev_iter:
        console.print(f"  [yellow]Retry iteration #{curr_iter}[/yellow]")


@app.command()
def research(
    question: str = typer.Argument(help="Research question to investigate"),
    topic: Optional[str] = typer.Option(None, "--topic", "-t", help="Broader research topic"),
    thread_id: Optional[str] = typer.Option(None, "--thread", help="Resume an existing thread"),
    max_steps: int = typer.Option(30, "--max-steps", help="Max graph steps before stopping"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
) -> None:
    """Start a new research session or resume an existing one."""
    from bioagent.utils.logging_config import setup_logging

    setup_logging(level=log_level)

    from bioagent.graph.research_graph import compile_research_graph
    from bioagent.tools.execution.sandbox import ensure_workspace

    ensure_workspace()

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
        "data_status": None,
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
        "review_count": 0,
        "messages": [],
        "errors": [],
        "human_feedback": None,
        "should_stop": False,
    }

    tid = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": tid}, "recursion_limit": 100}

    console.print(f"\n[bold green]BioAgent Research Session[/bold green]")
    console.print(f"[dim]Thread: {tid}[/dim]")
    console.print(f"[bold]Question:[/bold] {question}")
    if topic:
        console.print(f"[bold]Topic:[/bold] {topic}")
    console.print()

    final_state = initial_state
    prev_state: dict | None = None
    try:
        step = 0
        for event in graph.stream(initial_state, config=config, stream_mode="values"):
            step += 1
            final_state = event
            phase = event.get("current_phase", "?")
            display_phase(f"{phase} (step {step})")
            _display_state_progress(event, prev_state)

            if step >= max_steps:
                console.print(f"\n[yellow]Reached max steps ({max_steps}). Stopping.[/yellow]")
                break

            prev_state = event

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Session state is saved.[/yellow]")
        console.print(f"[dim]Resume with: bioagent resume --thread {tid}[/dim]")
    except Exception as exc:
        display_error(f"Graph execution failed: {exc}")
        logger.exception("Graph execution error")
        raise typer.Exit(1) from exc

    console.print("\n[bold green]Research Complete[/bold green]")
    display_summary(final_state)
    console.print(f"\n[dim]Thread ID: {tid}[/dim]")


@app.command()
def resume(
    thread_id: str = typer.Option(..., "--thread", "-t", help="Thread ID to resume"),
    max_steps: int = typer.Option(30, "--max-steps", help="Max additional graph steps"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
) -> None:
    """Resume a paused research session from its last checkpoint."""
    from bioagent.utils.logging_config import setup_logging

    setup_logging(level=log_level)

    from bioagent.graph.research_graph import compile_research_graph
    from bioagent.tools.execution.sandbox import ensure_workspace

    ensure_workspace()

    try:
        graph = compile_research_graph()
    except Exception as exc:
        display_error(f"Failed to compile graph: {exc}")
        raise typer.Exit(1) from exc

    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}

    console.print(f"\n[bold green]Resuming Research Session[/bold green]")
    console.print(f"[dim]Thread: {thread_id}[/dim]")
    console.print()

    final_state: dict = {}
    prev_state: dict | None = None
    try:
        step = 0
        for event in graph.stream(None, config=config, stream_mode="values"):
            step += 1
            final_state = event
            phase = event.get("current_phase", "?")
            display_phase(f"{phase} (step {step})")
            _display_state_progress(event, prev_state)

            if step >= max_steps:
                console.print(f"\n[yellow]Reached max steps ({max_steps}). Stopping.[/yellow]")
                break

            prev_state = event

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Session state is saved.[/yellow]")
        console.print(f"[dim]Resume with: bioagent resume --thread {thread_id}[/dim]")
    except Exception as exc:
        display_error(f"Resume failed: {exc}")
        logger.exception("Resume error")
        raise typer.Exit(1) from exc

    if final_state:
        console.print("\n[bold green]Research Complete[/bold green]")
        display_summary(final_state)
    console.print(f"\n[dim]Thread ID: {thread_id}[/dim]")


@app.command()
def status(
    thread_id: str = typer.Option(..., "--thread", "-t", help="Thread ID to check"),
) -> None:
    """Show the status of a research session."""
    try:
        from bioagent.config.settings import settings

        db_path = settings.checkpoint_path / "research.db"
        if not db_path.exists():
            display_error(f"No checkpoint database found at {db_path}")
            raise typer.Exit(1)

        import json
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM checkpoints WHERE thread_id = ? ORDER BY checkpoint_id DESC LIMIT 1",
            (thread_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            display_error(f"No checkpoint found for thread: {thread_id}")
            raise typer.Exit(1)

        # Parse checkpoint state
        state_data = row["state"] if "state" in row.keys() else None
        if state_data:
            if isinstance(state_data, str):
                state = json.loads(state_data)
            elif isinstance(state_data, bytes):
                state = json.loads(state_data.decode("utf-8"))
            else:
                state = dict(state_data) if state_data else {}
        else:
            state = {}

        # Try to get channel values (LangGraph's newer format)
        channels = {}
        try:
            conn2 = sqlite3.connect(str(db_path))
            conn2.row_factory = sqlite3.Row
            cur = conn2.cursor()
            cur.execute(
                "SELECT channel, value FROM checkpoint_writes WHERE thread_id = ? "
                "ORDER BY checkpoint_id DESC",
                (thread_id,),
            )
            channels = {r["channel"]: r["value"] for r in cur.fetchall()}
            conn2.close()
        except Exception:
            pass

        display_session_status(state, thread_id, channels)

    except Exception as exc:
        if "No checkpoint" in str(exc) or "typer.Exit" in str(type(exc)):
            raise
        display_error(f"Failed to read session status: {exc}")
        logger.exception("Status check error")
        raise typer.Exit(1) from exc


@app.command()
def export(
    thread_id: str = typer.Option(..., "--thread", "-t", help="Thread ID to export"),
    format: str = typer.Option("both", "--format", "-f", help="Output format: md, latex, or both"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", "-o", help="Output directory"),
) -> None:
    """Export a completed research session as a manuscript (Markdown and/or LaTeX)."""
    from bioagent.utils.logging_config import setup_logging

    setup_logging()

    from bioagent.config.settings import settings

    out = Path(output_dir) if output_dir else settings.workspace_path / "output"

    # Load state from checkpoint
    state = _load_state_from_checkpoint(thread_id)
    if not state:
        display_error(f"No state found for thread: {thread_id}")
        raise typer.Exit(1)

    topic = state.get("research_topic", "research")
    console.print(f"\n[bold green]Exporting research: {topic}[/bold green]")
    console.print(f"[dim]Output directory: {out}[/dim]\n")

    from bioagent.export.markdown_export import export_markdown
    from bioagent.export.latex_export import export_latex

    if format in ("md", "both"):
        try:
            md_path = export_markdown(state, out)
            console.print(f"[green]✓[/green] Markdown: {md_path}")
        except Exception as exc:
            display_error(f"Markdown export failed: {exc}")

    if format in ("latex", "both"):
        try:
            tex_path, bib_path = export_latex(state, out)
            console.print(f"[green]✓[/green] LaTeX: {tex_path}")
            if bib_path:
                console.print(f"[green]✓[/green] BibTeX: {bib_path}")
        except Exception as exc:
            display_error(f"LaTeX export failed: {exc}")


def _load_state_from_checkpoint(thread_id: str) -> dict:
    """Load the most recent state for a thread from the SQLite checkpoint."""
    import json
    import sqlite3

    from bioagent.config.settings import settings

    db_path = settings.checkpoint_path / "research.db"
    if not db_path.exists():
        return {}

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Try blobs table first (LangGraph >=0.2 stores state as msgpack blobs)
        try:
            cur.execute(
                "SELECT value FROM checkpoint_blobs WHERE thread_id = ? ORDER BY checkpoint_id DESC",
                (thread_id,),
            )
            rows = cur.fetchall()
            if rows:
                import pickle

                state_blob = rows[0]["value"]
                if isinstance(state_blob, bytes):
                    try:
                        return pickle.loads(state_blob)
                    except Exception:
                        pass
        except Exception:
            pass

        # Fallback: try the channel writes
        cur.execute(
            "SELECT channel, value FROM checkpoint_writes WHERE thread_id = ? ORDER BY checkpoint_id DESC",
            (thread_id,),
        )
        channels = {}
        for row in cur.fetchall():
            ch = row["channel"]
            val = row["value"]
            if ch not in channels:
                channels[ch] = val
        conn.close()

        # Deserialize channel values
        state: dict = {}
        for ch, val in channels.items():
            if isinstance(val, bytes):
                try:
                    import pickle

                    state[ch] = pickle.loads(val)
                except Exception:
                    try:
                        state[ch] = json.loads(val.decode())
                    except Exception:
                        pass
            elif isinstance(val, str):
                try:
                    state[ch] = json.loads(val)
                except Exception:
                    state[ch] = val
        return state
    except Exception as exc:
        logger.warning("Could not load checkpoint state: %s", exc)
        return {}


if __name__ == "__main__":
    app()
