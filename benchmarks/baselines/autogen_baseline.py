"""AutoGen-style baseline: a minimal two-agent chat loop without BioAgent's
tool infrastructure.

This emulates the capability envelope of using AutoGen "out of the box" for a
bioinformatics research question: two agents converse, neither has BioMCP /
data acquisition / code execution hooks. Used in the paper as a reference
point to demonstrate that multi-agent chat alone does not close the capability
gap; it is the combination of multi-agent orchestration + tool grounding +
iteration that matters.

We deliberately implement this directly in the Anthropic SDK rather than
pulling in the full AutoGen dependency, because:
  (a) the configuration surface of AutoGen changes frequently and pinning it
      would inflate our lock file;
  (b) the reference behaviour we care about is trivially reproducible.

Usage:
    python benchmarks/baselines/autogen_baseline.py --case braf_melanoma
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger(__name__)

MAX_TURNS = 6

ASSISTANT_SYSTEM = (
    "You are ResearchAssistant, an expert bioinformatician. You collaborate "
    "with a UserProxy to draft a research paper. You have no tools, no "
    "database access, and no code execution. Use only your training knowledge."
)

USER_PROXY_SYSTEM = (
    "You are UserProxy, representing a researcher. You ask sharp follow-up "
    "questions to drive the ResearchAssistant towards a publication-quality "
    "manuscript covering Abstract, Introduction, Methods, Results, Discussion. "
    "After 3 rounds, request a final consolidated paper."
)


def run(case_name: str, output_dir: Path) -> dict:
    from benchmarks.cases import ALL_CASES
    from bioagent.evaluation.metrics import evaluate_run
    from bioagent.llm.clients import get_anthropic_client, get_anthropic_model
    from bioagent.llm.token_tracking import global_token_usage

    case = next((c for c in ALL_CASES if c.name == case_name), None)
    if case is None:
        raise ValueError(f"Unknown benchmark case: {case_name}")

    out = output_dir / case_name / "autogen"
    out.mkdir(parents=True, exist_ok=True)

    client = get_anthropic_client()
    model = get_anthropic_model()

    transcript: list[dict] = []
    assistant_history: list[dict] = []
    user_history: list[dict] = []

    # Seed: UserProxy opens the conversation with the research question
    opening = (
        f"Please produce a rigorous research paper answering:\n"
        f"Topic: {case.research_topic}\n"
        f"Question: {case.research_question}\n"
        f"Begin with an outline, then expand each section."
    )
    transcript.append({"role": "UserProxy", "content": opening})
    assistant_history.append({"role": "user", "content": opening})

    t0 = time.time()
    total_in = 0
    total_out = 0

    for turn in range(MAX_TURNS):
        # ResearchAssistant responds
        resp = client.messages.create(
            model=model,
            max_tokens=4096,
            system=ASSISTANT_SYSTEM,
            messages=assistant_history,
        )
        assistant_text = "\n".join(b.text for b in resp.content if hasattr(b, "text"))
        if resp.usage:
            total_in += resp.usage.input_tokens
            total_out += resp.usage.output_tokens
        transcript.append({"role": "ResearchAssistant", "turn": turn, "content": assistant_text})
        assistant_history.append({"role": "assistant", "content": assistant_text})
        user_history.append({"role": "user", "content": assistant_text})

        if turn == MAX_TURNS - 1:
            break

        # UserProxy asks the next question
        user_history_with_prompt = user_history + [
            {
                "role": "user",
                "content": (
                    "As UserProxy, reply with ONE short sharpening question "
                    "(max 3 sentences) for the ResearchAssistant. On turn "
                    f"{turn + 1}, if you feel the paper is complete, instead "
                    "reply 'Please consolidate everything into a final paper now.'"
                ),
            }
        ]
        user_resp = client.messages.create(
            model=model,
            max_tokens=512,
            system=USER_PROXY_SYSTEM,
            messages=user_history_with_prompt,
        )
        user_text = "\n".join(b.text for b in user_resp.content if hasattr(b, "text"))
        if user_resp.usage:
            total_in += user_resp.usage.input_tokens
            total_out += user_resp.usage.output_tokens
        transcript.append({"role": "UserProxy", "turn": turn, "content": user_text})
        assistant_history.append({"role": "user", "content": user_text})
        user_history.append({"role": "assistant", "content": user_text})

    wall = time.time() - t0
    global_token_usage.add(input_tokens=total_in, output_tokens=total_out)

    # Concatenate ResearchAssistant outputs as the "paper"
    paper_text = "\n\n---\n\n".join(
        t["content"] for t in transcript if t["role"] == "ResearchAssistant"
    )

    (out / "paper.md").write_text(paper_text, encoding="utf-8")
    (out / "transcript.json").write_text(
        json.dumps(transcript, indent=2), encoding="utf-8"
    )

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
        "iteration_count": MAX_TURNS,
        "phase_history": ["autogen_chat"],
    }

    report = evaluate_run(
        fake_state,
        gold_standard_pmids=case.expected_pmids,
        benchmark_case=case_name,
    )
    report_dict = report.to_dict()
    report_dict["variant"] = "autogen"
    report_dict["wall_time_sec"] = round(wall, 2)
    report_dict["input_tokens"] = total_in
    report_dict["output_tokens"] = total_out

    (out / "evaluation_report.json").write_text(
        json.dumps(report_dict, indent=2), encoding="utf-8"
    )

    print(f"[autogen] {wall:.1f}s over {MAX_TURNS} turns, paper length={len(paper_text)} chars")
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
