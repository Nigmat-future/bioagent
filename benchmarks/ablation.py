"""Ablation runner — evaluates BioAgent variants with individual components disabled.

Variants:
    full            — unchanged baseline system
    no_literature   — skip literature_review node (empty papers)
    no_data         — skip data_acquisition node (no real data pulled)
    no_code         — skip code_execution node (writer gets empty analysis)
    no_review       — skip review_node (no iteration; export after first write)
    single_pass_llm — bypass graph entirely; single LLM call with full prompt

Usage:
    python benchmarks/ablation.py --variant full
    python benchmarks/ablation.py --variant all          # runs every variant
    python benchmarks/ablation.py --case braf_melanoma --variant no_literature
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import uuid
from pathlib import Path
from typing import Callable

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger(__name__)

ALL_VARIANTS = [
    "full",
    "no_literature",
    "no_data",
    "no_code",
    "no_review",
    "single_pass_llm",
]


def _passthrough_factory(phase: str, stub_state: dict | None = None) -> Callable:
    """Build a node function that fakes the ablated phase's outputs.

    The orchestrator routes by looking at what state fields are populated
    (e.g. empty ``papers`` -> route to literature_review). If an ablated
    node simply returns an empty update, the orchestrator will route right
    back to it, producing an infinite loop. To break that cycle while still
    reflecting the ablation in the evaluation metrics, we populate minimal
    ``stub_state`` marking the phase as done but empty.
    """

    def _node(state):  # type: ignore[no-untyped-def]
        logger.info("[ablation] Skipping '%s' (ablated)", phase)
        update = {
            "current_phase": phase,
            "phase_history": state.get("phase_history", []) + [f"{phase}:ablated"],
        }
        if stub_state:
            update.update(stub_state)
        return update

    return _node


# For each ablated phase, the minimum state required so the orchestrator
# progresses past the phase's gate without routing back to it. Keep values
# empty / sentinel so the evaluation metrics still reflect the ablation.
_ABLATION_STUBS: dict[str, dict] = {
    "literature_review": {
        # Rule 1: empty papers -> literature_review. Populate with a sentinel
        # paper so the orchestrator moves on to gap_analysis.
        "papers": [{"id": "ABLATED", "title": "[LITERATURE AGENT ABLATED]"}],
        "literature_summary": "[ablated: LiteratureAgent was disabled]",
        "research_gaps": ["[ablated: no gaps identified because LiteratureAgent was disabled]"],
    },
    "data_acquisition": {
        # Rule 5: null data_status -> data_acquisition. Mark as failed so
        # the orchestrator routes to code_execution (rule 6/7).
        "data_status": {"status": "partial", "datasets_requested": 0,
                        "datasets_acquired": 0, "summary": "[ablated]"},
    },
    "code_execution": {
        # code_execution goes to result_validation which routes back to
        # orchestrator. Stub results so the orchestrator moves to writing.
        "execution_results": [{"stdout": "[ablated]", "stderr": "", "exit_code": 0}],
        "analysis_results": [{"summary": "[ablated: AnalystAgent was disabled]"}],
        "validation_status": {"passed": True, "reason": "ablation passthrough"},
    },
    "result_validation": {
        "validation_status": {"passed": True, "reason": "ablation passthrough"},
    },
    "review": {
        # Review normally decides END vs revise. Without it, we force END
        # by marking complete.
        "current_phase": "complete",
        "review_feedback": [{"score": 0, "recommendation": "[ablated: ReviewAgent was disabled]"}],
    },
}


def _build_variant_graph(variant: str):
    """Compile a research graph with selected nodes replaced by pass-throughs."""
    from bioagent.graph import nodes as _nodes
    from bioagent.graph.research_graph import build_research_graph

    original: dict[str, Callable] = {}

    ablations = {
        "no_literature": ["literature_review_node"],
        "no_data": ["data_acquisition_node"],
        "no_code": ["code_execution_node", "result_validation_node"],
        "no_review": ["review_node"],
    }

    if variant in ablations:
        for attr in ablations[variant]:
            original[attr] = getattr(_nodes, attr)
            phase_name = attr.replace("_node", "")
            stub = _ABLATION_STUBS.get(phase_name)
            setattr(_nodes, attr, _passthrough_factory(phase_name, stub))

    try:
        graph = build_research_graph().compile()
    finally:
        for attr, fn in original.items():
            setattr(_nodes, attr, fn)

    return graph


def _run_single_pass_llm(case):  # type: ignore[no-untyped-def]
    """Baseline: a single Claude call, no tools, no graph."""
    from bioagent.llm.clients import get_anthropic_client, get_anthropic_model
    from bioagent.llm.token_tracking import global_token_usage

    client = get_anthropic_client()
    model = get_anthropic_model()

    prompt = (
        f"You are an expert bioinformatician. Write a complete research paper "
        f"(Abstract, Introduction, Methods, Results, Discussion) answering this "
        f"research question: '{case.research_question}'. "
        f"Include citations as PMIDs, list relevant genes and pathways, and propose "
        f"an analysis plan. Be thorough and publication-quality."
    )

    start = time.time()
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = time.time() - start

    text_blocks = [b.text for b in response.content if hasattr(b, "text")]
    paper_text = "\n".join(text_blocks)

    if response.usage:
        global_token_usage.add(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    return paper_text, elapsed


def run_variant(variant: str, case_name: str, output_dir: Path) -> dict:
    from benchmarks.cases import ALL_CASES
    from bioagent.evaluation.metrics import evaluate_run
    from bioagent.tools.execution.sandbox import ensure_workspace

    case = next((c for c in ALL_CASES if c.name == case_name), None)
    if case is None:
        raise ValueError(f"Unknown benchmark case: {case_name}")

    ensure_workspace()

    variant_dir = output_dir / case_name / variant
    variant_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("[ablation] variant=%s case=%s", variant, case_name)
    logger.info("=" * 70)

    t0 = time.time()

    if variant == "single_pass_llm":
        paper_text, api_elapsed = _run_single_pass_llm(case)
        (variant_dir / "paper.md").write_text(paper_text, encoding="utf-8")
        final_state = {
            "research_topic": case.research_topic,
            "research_question": case.research_question,
            "papers": [],
            "hypotheses": [],
            "execution_results": [],
            "analysis_results": [],
            "paper_sections": {"full_text": paper_text},
            "figures": [],
            "review_feedback": [],
            "messages": [],
            "errors": [],
            "iteration_count": 0,
            "phase_history": ["single_pass"],
        }
    else:
        graph = _build_variant_graph(variant)
        tid = str(uuid.uuid4())
        config = {"configurable": {"thread_id": tid}, "recursion_limit": 100}

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

        final_state = initial_state
        try:
            for event in graph.stream(initial_state, config=config, stream_mode="values"):
                final_state = event
        except Exception as exc:
            logger.error("[ablation] variant %s failed: %s", variant, exc)
            final_state.setdefault("errors", []).append(str(exc))

    wall_time = time.time() - t0

    # Evaluate
    report = evaluate_run(
        final_state,
        gold_standard_pmids=case.expected_pmids,
        benchmark_case=case_name,
    )
    report_dict = report.to_dict()
    report_dict["variant"] = variant
    report_dict["wall_time_sec"] = round(wall_time, 2)

    (variant_dir / "evaluation_report.json").write_text(
        json.dumps(report_dict, indent=2), encoding="utf-8"
    )
    (variant_dir / "final_state.json").write_text(
        json.dumps(_serializable(final_state), indent=2, default=str), encoding="utf-8"
    )

    logger.info("[ablation] variant=%s complete in %.1fs", variant, wall_time)
    return report_dict


def _serializable(state: dict) -> dict:
    """Strip non-JSON-safe items from state for logging."""
    out = {}
    skip = {"messages"}
    for k, v in state.items():
        if k in skip:
            continue
        try:
            json.dumps(v, default=str)
            out[k] = v
        except (TypeError, ValueError):
            out[k] = str(v)[:500]
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="BioAgent ablation runner")
    parser.add_argument("--variant", default="all",
                        help=f"Variant name or 'all'. Choices: {ALL_VARIANTS}")
    parser.add_argument("--case", default="braf_melanoma")
    parser.add_argument("--output", default="benchmarks/results/ablation")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    variants = ALL_VARIANTS if args.variant == "all" else [args.variant]

    all_results = {}
    for v in variants:
        if v not in ALL_VARIANTS:
            logger.error("Unknown variant: %s", v)
            continue
        try:
            all_results[v] = run_variant(v, args.case, out_dir)
        except Exception as exc:
            logger.exception("[ablation] variant %s errored: %s", v, exc)
            all_results[v] = {"error": str(exc), "variant": v}

    summary_path = out_dir / args.case / "ablation_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\nAblation summary written to {summary_path}")


if __name__ == "__main__":
    main()
