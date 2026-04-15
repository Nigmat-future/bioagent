"""Benchmark runner — executes BioAgent on standard cases and saves evaluation reports.

Usage:
    python benchmarks/run_benchmark.py --case braf_melanoma
    python benchmarks/run_benchmark.py --case all --output benchmarks/results/
"""

from __future__ import annotations

import argparse
import json
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


def run_case(case_name: str, output_dir: Path) -> dict:
    """Run BioAgent on a single benchmark case and return the evaluation report."""
    from benchmarks.cases import ALL_CASES

    case = next((c for c in ALL_CASES if c.name == case_name), None)
    if case is None:
        raise ValueError(f"Unknown benchmark case: {case_name}. "
                         f"Available: {[c.name for c in ALL_CASES]}")

    from bioagent.graph.research_graph import compile_research_graph
    from bioagent.tools.execution.sandbox import ensure_workspace
    from bioagent.evaluation.metrics import evaluate_run
    from bioagent.evaluation.provenance import get_tracker, record_provenance
    from bioagent.export.markdown_export import export_markdown
    from bioagent.export.latex_export import export_latex

    ensure_workspace()

    graph = compile_research_graph()
    tid = str(uuid.uuid4())
    config = {"configurable": {"thread_id": tid}}

    initial_state = {
        "research_topic": case.research_topic,
        "research_question": case.research_question,
        "constraints": case.constraints,
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

    # Track provenance
    from bioagent.llm.clients import get_anthropic_model
    tracker = get_tracker()
    tracker.start_run(run_id=tid, model=get_anthropic_model())

    logging.info("Running benchmark case: %s (thread: %s)", case_name, tid)

    final_state = initial_state
    try:
        for event in graph.stream(initial_state, config=config, stream_mode="values"):
            final_state = event
    except Exception as exc:
        logger.error("Benchmark run failed: %s", exc)

    # Evaluate
    report = evaluate_run(
        final_state,
        gold_standard_pmids=case.expected_pmids,
        benchmark_case=case_name,
    )

    # Save outputs
    case_dir = output_dir / case_name
    case_dir.mkdir(parents=True, exist_ok=True)

    report_path = case_dir / "evaluation_report.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    export_markdown(final_state, case_dir)
    export_latex(final_state, case_dir)
    record_provenance(case_dir, final_state)

    print(report.summary())
    print(f"\nOutputs saved to: {case_dir}")

    return report.to_dict()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BioAgent benchmark cases")
    parser.add_argument("--case", default="braf_melanoma",
                        help="Benchmark case name or 'all'")
    parser.add_argument("--output", default="benchmarks/results",
                        help="Output directory for results")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper()))

    output_dir = Path(args.output)

    from benchmarks.cases import ALL_CASES

    if args.case == "all":
        cases = [c.name for c in ALL_CASES]
    else:
        cases = [args.case]

    all_results = {}
    for case_name in cases:
        print(f"\n{'='*60}")
        print(f"Running: {case_name}")
        print("=" * 60)
        try:
            result = run_case(case_name, output_dir)
            all_results[case_name] = result
        except Exception as exc:
            logger.error("Case %s failed: %s", case_name, exc)
            all_results[case_name] = {"error": str(exc)}

    # Save summary
    summary_path = output_dir / "benchmark_summary.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\nBenchmark summary saved to: {summary_path}")


if __name__ == "__main__":
    main()
