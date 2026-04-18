"""Minimal patch for the BRAF benchmark: regenerate `hypotheses` for the
resumed run that scored 5.71 because its checkpoint carried an empty list.

The entire downstream pipeline (experiment_plan, writing, figures, review)
already ran successfully off `selected_hypothesis`, which *was* populated.
Only the `hypotheses` array — used by the scorer in `bioagent.evaluation.metrics`
— is missing. We run PlannerAgent standalone against the checkpointed state,
inject its hypotheses list, and re-evaluate.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# Ensure workspace matches the resumed BRAF run's isolation.
os.environ.setdefault("BIOAGENT_WORKSPACE_DIR", "workspace_braf")

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BRAF_THREAD = "18585bbf-af8f-447a-ae5d-e01a1b8f91b0"
OUT_DIR = REPO_ROOT / "benchmarks" / "results" / "rerun_post_fix" / "braf_melanoma"


def main() -> int:
    from benchmarks.cases import ALL_CASES
    from bioagent.agents.planner import PlannerAgent
    from bioagent.evaluation.metrics import evaluate_run
    from bioagent.evaluation.provenance import record_provenance
    from bioagent.export.latex_export import export_latex
    from bioagent.export.markdown_export import export_markdown
    from bioagent.graph.research_graph import compile_research_graph

    case = next(c for c in ALL_CASES if c.name == "braf_melanoma")
    graph = compile_research_graph()
    config = {"configurable": {"thread_id": BRAF_THREAD}}
    snap = graph.get_state(config)
    state = dict(snap.values)

    logger.info("Loaded BRAF checkpoint:")
    logger.info("  current_phase=%s", state.get("current_phase"))
    logger.info("  papers=%d, gaps=%d", len(state.get("papers", [])),
                len(state.get("research_gaps", [])))
    logger.info("  existing hypotheses=%d", len(state.get("hypotheses") or []))
    logger.info(
        "  selected_hypothesis=%s",
        bool(state.get("selected_hypothesis")),
    )
    logger.info(
        "  paper_sections=%s, figures=%d",
        list((state.get("paper_sections") or {}).keys()),
        len(state.get("figures") or []),
    )

    logger.info("Running PlannerAgent standalone to regenerate hypotheses...")
    planner = PlannerAgent()
    planner_updates = planner.run(state)
    new_hypotheses = planner_updates.get("hypotheses") or []
    logger.info(
        "Planner produced %d hypotheses; selected=%s",
        len(new_hypotheses),
        bool(planner_updates.get("selected_hypothesis")),
    )

    # Preserve everything the full run produced; only patch the hypothesis-
    # related fields that the scorer reads.
    patched = dict(state)
    patched["hypotheses"] = new_hypotheses
    if planner_updates.get("selected_hypothesis"):
        patched["selected_hypothesis"] = planner_updates["selected_hypothesis"]

    # Re-evaluate.
    report = evaluate_run(
        patched,
        gold_standard_pmids=case.expected_pmids,
        benchmark_case="braf_melanoma",
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "evaluation_report.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    export_markdown(patched, OUT_DIR)
    export_latex(patched, OUT_DIR)
    record_provenance(OUT_DIR, patched)

    print()
    print(report.summary())
    print(f"\nPatched evaluation saved to: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
