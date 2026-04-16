"""
Real end-to-end BioAgent run: BRAF V600E melanoma drug resistance.

Records timing, token usage, and all outputs for the manuscript.
Run from the project root:
    python run_braf_case.py
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── Setup logging to both console and file ────────────────────────────────────
from bioagent.utils.logging_config import setup_logging
setup_logging(level="INFO")

import logging
logger = logging.getLogger(__name__)

from bioagent.graph.research_graph import compile_research_graph
from bioagent.tools.execution.sandbox import ensure_workspace
from bioagent.llm.token_tracking import global_token_usage

RESEARCH_QUESTION = (
    "Investigate the role of BRAF V600E mutation in melanoma drug resistance. "
    "Focus on molecular mechanisms of acquired resistance to BRAF inhibitors "
    "(vemurafenib, dabrafenib) and identify potential combination therapy targets "
    "through computational analysis."
)
TOPIC = "BRAF V600E melanoma drug resistance"

THREAD_ID = f"braf-melanoma-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
LOG_PATH = Path("examples/braf_melanoma/run_log.json")


def main():
    ensure_workspace()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*65}")
    print("  BioAgent — BRAF V600E Melanoma Case Study")
    print(f"  Thread: {THREAD_ID}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}\n")

    graph = compile_research_graph()

    initial_state = {
        "research_topic": TOPIC,
        "research_question": RESEARCH_QUESTION,
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

    config = {"configurable": {"thread_id": THREAD_ID}, "recursion_limit": 100}
    run_start = time.time()
    phase_timings: dict[str, float] = {}
    phase_start = run_start
    current_phase = "literature_review"
    final_state = initial_state
    step = 0

    try:
        for event in graph.stream(initial_state, config=config, stream_mode="values"):
            step += 1
            new_phase = event.get("current_phase", current_phase)

            if new_phase != current_phase:
                elapsed = time.time() - phase_start
                phase_timings[current_phase] = round(elapsed, 1)
                print(f"\n[{elapsed:>6.0f}s] DONE {current_phase}")
                print(f"         -> {new_phase}")
                phase_start = time.time()
                current_phase = new_phase

            # Progress indicators
            papers = len(event.get("papers", []))
            gaps   = len(event.get("research_gaps", []))
            hyps   = len(event.get("hypotheses", []))
            sects  = list(event.get("paper_sections", {}).keys())
            figs   = len(event.get("figures", []))
            errs   = len(event.get("errors", []))

            tokens_in  = global_token_usage.input_tokens
            tokens_out = global_token_usage.output_tokens
            cost_usd   = global_token_usage.estimated_cost_usd

            print(
                f"  step={step:>3d} | papers={papers} gaps={gaps} hyps={hyps} "
                f"sects={len(sects)} figs={figs} errs={errs} | "
                f"tok={tokens_in+tokens_out:,} ${cost_usd:.3f}",
                flush=True,
            )

            final_state = event

    except KeyboardInterrupt:
        print("\n\n[Interrupted by user]")
    except Exception as exc:
        logger.exception("Run failed at step %d", step)
        print(f"\n[ERROR at step {step}]: {exc}")

    # Record final phase timing
    phase_timings[current_phase] = round(time.time() - phase_start, 1)
    total_elapsed = round(time.time() - run_start, 1)

    print(f"\n{'='*65}")
    print(f"  Run complete in {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
    print(f"  Steps taken: {step}")
    print(f"  Papers found: {len(final_state.get('papers', []))}")
    print(f"  Sections written: {list(final_state.get('paper_sections', {}).keys())}")
    print(f"  Figures: {len(final_state.get('figures', []))}")
    review = final_state.get("review_feedback", [])
    if review:
        r = review[-1] if isinstance(review, list) else review
        print(f"  Review score: {r.get('score','?')}/10")
    print(f"  Tokens in/out: {global_token_usage.input_tokens:,} / {global_token_usage.output_tokens:,}")
    print(f"  Estimated cost: ${global_token_usage.estimated_cost_usd:.4f}")
    print(f"{'='*65}\n")

    # ── Save provenance log ───────────────────────────────────────────────────
    log = {
        "thread_id": THREAD_ID,
        "research_question": RESEARCH_QUESTION,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "total_elapsed_s": total_elapsed,
        "steps": step,
        "phase_timings_s": phase_timings,
        "papers_found": len(final_state.get("papers", [])),
        "gaps_identified": len(final_state.get("research_gaps", [])),
        "hypotheses": len(final_state.get("hypotheses", [])),
        "sections_written": list(final_state.get("paper_sections", {}).keys()),
        "figures": len(final_state.get("figures", [])),
        "errors": final_state.get("errors", []),
        "review_feedback": final_state.get("review_feedback", []),
        "token_usage": {
            "input": global_token_usage.input_tokens,
            "output": global_token_usage.output_tokens,
            "cost_usd": global_token_usage.estimated_cost_usd,
        },
        "papers": [
            {"id": p.get("id", ""), "title": p.get("title", "")}
            for p in final_state.get("papers", [])
        ],
        "selected_hypothesis": final_state.get("selected_hypothesis"),
    }

    LOG_PATH.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    print(f"Provenance log -> {LOG_PATH}")
    print(f"Manuscript     -> workspace/output/")
    print(f"Resume thread  -> bioagent resume --thread {THREAD_ID}\n")


if __name__ == "__main__":
    main()
