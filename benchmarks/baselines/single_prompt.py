"""Single-prompt LLM baseline.

Runs a single Anthropic call with a comprehensive prompt and no tools. Used as
a reference point in the paper for "one-shot LLM" performance — demonstrates
that stateful orchestration, tool use, and iteration are genuinely additive.

Usage:
    python benchmarks/baselines/single_prompt.py --case braf_melanoma
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def run(case_name: str, output_dir: Path) -> dict:
    from benchmarks.cases import ALL_CASES
    from bioagent.evaluation.metrics import evaluate_run
    from bioagent.llm.clients import get_anthropic_client, get_anthropic_model
    from bioagent.llm.token_tracking import global_token_usage

    case = next((c for c in ALL_CASES if c.name == case_name), None)
    if case is None:
        raise ValueError(f"Unknown benchmark case: {case_name}")

    out = output_dir / case_name / "single_prompt"
    out.mkdir(parents=True, exist_ok=True)

    prompt = (
        "You are an expert bioinformatician writing a research paper.\n\n"
        f"Research topic: {case.research_topic}\n"
        f"Research question: {case.research_question}\n\n"
        "Produce a complete manuscript with the following sections:\n"
        "  1. Abstract (structured: Motivation / Results / Availability)\n"
        "  2. Introduction (cite at least 5 PMIDs)\n"
        "  3. Methods (detail datasets, statistical tests, software)\n"
        "  4. Results (include quantitative claims)\n"
        "  5. Discussion (limitations, future work)\n"
        "  6. References (PMID-formatted)\n\n"
        "Be rigorous, quantitative, and publication-ready."
    )

    client = get_anthropic_client()
    model = get_anthropic_model()

    t0 = time.time()
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    wall = time.time() - t0

    text_blocks = [b.text for b in response.content if hasattr(b, "text")]
    paper_text = "\n".join(text_blocks)

    if response.usage:
        global_token_usage.add(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    (out / "paper.md").write_text(paper_text, encoding="utf-8")

    fake_state = {
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
        "phase_history": ["single_prompt"],
    }

    report = evaluate_run(
        fake_state,
        gold_standard_pmids=case.expected_pmids,
        benchmark_case=case_name,
    )
    report_dict = report.to_dict()
    report_dict["variant"] = "single_prompt"
    report_dict["wall_time_sec"] = round(wall, 2)
    report_dict["input_tokens"] = response.usage.input_tokens if response.usage else None
    report_dict["output_tokens"] = response.usage.output_tokens if response.usage else None

    (out / "evaluation_report.json").write_text(
        json.dumps(report_dict, indent=2), encoding="utf-8"
    )

    print(f"[single_prompt] {wall:.1f}s, paper length={len(paper_text)} chars")
    print(f"  Saved to {out}")
    return report_dict


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--case", default="braf_melanoma")
    p.add_argument("--output", default="benchmarks/results/baselines")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run(args.case, Path(args.output))


if __name__ == "__main__":
    main()
