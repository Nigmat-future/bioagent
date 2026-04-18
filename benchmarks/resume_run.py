"""Resume a benchmark run from its LangGraph checkpoint.

Usage:
    python -m benchmarks.resume_run --case tp53_pancancer \
        --thread-id cae881ec-475d-459d-88b1-284fbea7d252 \
        --output benchmarks/results/rerun_post_fix

Set ``BIOAGENT_WORKSPACE_DIR`` to resume into an isolated workspace.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger(__name__)


def resume_case(case_name: str, thread_id: str, output_dir: Path) -> dict:
    from benchmarks.cases import ALL_CASES
    from bioagent.evaluation.metrics import evaluate_run
    from bioagent.evaluation.provenance import get_tracker, record_provenance
    from bioagent.export.latex_export import export_latex
    from bioagent.export.markdown_export import export_markdown
    from bioagent.graph.research_graph import compile_research_graph
    from bioagent.llm.clients import get_anthropic_model
    from bioagent.tools.execution.sandbox import ensure_workspace

    case = next((c for c in ALL_CASES if c.name == case_name), None)
    if case is None:
        raise ValueError(f"Unknown case: {case_name}")

    ensure_workspace()
    graph = compile_research_graph()
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}

    # Verify checkpoint exists before attempting resume.
    state_snapshot = graph.get_state(config)
    if state_snapshot is None or state_snapshot.values is None:
        raise RuntimeError(
            f"No checkpoint found for thread_id={thread_id}. "
            "Start a fresh run with benchmarks/run_benchmark.py instead."
        )
    checkpointed = state_snapshot.values
    logger.info(
        "Resuming %s from thread %s (phase=%s, history=%s)",
        case_name,
        thread_id,
        checkpointed.get("current_phase"),
        checkpointed.get("phase_history", [])[-6:],
    )

    tracker = get_tracker()
    tracker.start_run(run_id=thread_id, model=get_anthropic_model())

    final_state = dict(checkpointed)
    try:
        # Passing ``None`` tells LangGraph to resume from the saved checkpoint
        # rather than re-applying an initial_state (which would overwrite it).
        for event in graph.stream(None, config=config, stream_mode="values"):
            final_state = event
    except Exception as exc:
        logger.error("Resume run failed: %s", exc)

    report = evaluate_run(
        final_state,
        gold_standard_pmids=case.expected_pmids,
        benchmark_case=case_name,
    )

    case_dir = output_dir / case_name
    case_dir.mkdir(parents=True, exist_ok=True)

    report_path = case_dir / "evaluation_report.json"
    report_path.write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )

    export_markdown(final_state, case_dir)
    export_latex(final_state, case_dir)
    record_provenance(case_dir, final_state)

    print(report.summary())
    print(f"\nOutputs saved to: {case_dir}")

    return report.to_dict()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resume a BioAgent benchmark run from its LangGraph checkpoint"
    )
    parser.add_argument("--case", required=True, help="Benchmark case name")
    parser.add_argument(
        "--thread-id",
        required=True,
        help="LangGraph thread_id from the original (failed) run",
    )
    parser.add_argument(
        "--output",
        default="benchmarks/results",
        help="Output directory for results",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper()))

    print(f"\n{'=' * 60}")
    print(f"Resuming: {args.case} (thread={args.thread_id})")
    print("=" * 60)

    try:
        resume_case(args.case, args.thread_id, Path(args.output))
    except Exception as exc:
        logger.error("Resume failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
