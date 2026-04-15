"""Orchestrator agent — research director that routes between phases."""

from __future__ import annotations

import json
import logging
from typing import Any

from bioagent.agents.base import BaseAgent
from bioagent.state.schema import ResearchState

logger = logging.getLogger(__name__)

# Valid phase transitions
VALID_PHASES = [
    "literature_review",
    "gap_analysis",
    "hypothesis_generation",
    "experiment_design",
    "code_execution",
    "result_validation",
    "iteration",
    "writing",
    "figure_generation",
    "review",
    "complete",
]


class OrchestratorAgent(BaseAgent):
    """Routes between research phases based on current state.

    The orchestrator is *not* a full agentic loop — it makes a single LLM call
    with structured output to decide the next phase.
    """

    name = "orchestrator"

    def get_system_prompt(self, state: ResearchState) -> str:
        from pathlib import Path
        prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "orchestrator.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return (
            "You are the research director of a bioinformatics research system. "
            "Decide the next phase. Respond with ONLY JSON: "
            '{"next_phase": "<phase_name>"}'
        )

    def get_tools(self) -> tuple[list[dict], dict[str, Any]]:
        # Orchestrator uses no tools — pure structured output
        return [], {}

    def build_messages(self, state: ResearchState) -> list[dict[str, Any]]:
        # Build a concise state summary for the orchestrator
        summary_parts = []

        if state.get("research_topic"):
            summary_parts.append(f"Topic: {state['research_topic']}")
        if state.get("research_question"):
            summary_parts.append(f"Question: {state['research_question']}")
        summary_parts.append(f"Current phase: {state.get('current_phase', 'unknown')}")
        summary_parts.append(f"Papers found: {len(state.get('papers', []))}")
        summary_parts.append(f"Gaps identified: {len(state.get('research_gaps', []))}")
        summary_parts.append(f"Hypotheses: {len(state.get('hypotheses', []))}")
        summary_parts.append(f"Experiment plan: {'yes' if state.get('experiment_plan') else 'no'}")
        summary_parts.append(f"Code artifacts: {len(state.get('code_artifacts', []))}")
        summary_parts.append(f"Execution results: {len(state.get('execution_results', []))}")
        summary_parts.append(f"Validation: {state.get('validation_status')}")
        summary_parts.append(f"Paper sections: {list(state.get('paper_sections', {}).keys())}")
        summary_parts.append(f"Figures: {len(state.get('figures', []))}")
        summary_parts.append(f"Iteration count: {state.get('iteration_count', 0)}")
        summary_parts.append(f"Errors: {len(state.get('errors', []))}")

        if state.get("errors"):
            summary_parts.append(f"Recent errors: {state['errors'][-3:]}")

        return [
            {
                "role": "user",
                "content": "Here is the current research state:\n\n"
                           + "\n".join(summary_parts)
                           + "\n\nWhat should the next phase be? Respond with the JSON only.",
            }
        ]

    def process_result(
        self,
        result_text: str,
        conversation: list[dict[str, Any]],
        state: ResearchState,
    ) -> dict[str, Any]:
        """Parse the orchestrator's JSON response into state updates."""
        try:
            # Strip markdown code fences if present
            text = result_text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            parsed = json.loads(text)
            next_phase = parsed.get("next_phase", "")

            if next_phase not in VALID_PHASES:
                logger.warning("Invalid phase '%s', defaulting to literature_review", next_phase)
                next_phase = "literature_review"

        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to parse orchestrator output: %s", result_text[:200])
            next_phase = "literature_review"

        return {
            "current_phase": next_phase,
            "phase_history": state.get("phase_history", []) + [next_phase],
        }

    def run(self, state: ResearchState) -> dict[str, Any]:
        """Single LLM call (no tool loop) to decide next phase."""
        from bioagent.llm.token_tracking import global_token_usage

        logger.info("[orchestrator] Deciding next phase...")

        system_prompt = self.get_system_prompt(state)
        messages = self.build_messages(state)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=256,
            system=system_prompt,
            messages=messages,
        )

        # Track token usage
        if response.usage:
            global_token_usage.add(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        text_blocks = [b.text for b in response.content if hasattr(b, "text")]
        result_text = "\n".join(text_blocks)
        logger.info("[orchestrator] Raw response: %s", result_text[:200])

        return self.process_result(result_text, messages, state)
