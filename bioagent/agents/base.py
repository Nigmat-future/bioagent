"""BaseAgent — abstract foundation for all bioinformatics research agents."""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import Anthropic

from bioagent.config.settings import settings
from bioagent.llm.clients import get_anthropic_client, get_anthropic_model
from bioagent.llm.tool_loop import run_tool_loop
from bioagent.state.schema import ResearchState
from bioagent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for research agents.

    Subclasses must implement:
      - ``system_prompt`` property or ``get_system_prompt(state)`` method
      - ``get_tools()`` — returns (tool_definitions, tool_functions)
      - ``process_result(result_text, conversation, state)`` — maps output back to state updates

    The ``run(state)`` method handles the full lifecycle:
      1. Read relevant state slice
      2. Build conversation from state
      3. Run tool loop
      4. Return state update dict
    """

    name: str = "base"

    def __init__(self, client: Anthropic | None = None) -> None:
        self.client = client or get_anthropic_client()
        self.model = get_anthropic_model()

    @property
    def system_prompt(self) -> str:
        """Default system prompt — override in subclasses or use prompts/ files."""
        return "You are a helpful AI research assistant."

    def get_system_prompt(self, state: ResearchState) -> str:
        """Build system prompt with state context. Override for dynamic prompts."""
        return self.system_prompt

    def get_tools(self) -> tuple[list[dict], dict[str, Any]]:
        """Return (tool_definitions, tool_functions) for this agent.

        Override to provide agent-specific tools.
        """
        return [], {}

    def build_messages(self, state: ResearchState) -> list[dict[str, Any]]:
        """Build initial conversation messages from state.

        Default: a single user message summarizing the current task.
        Override for agents that need multi-turn context from state.
        """
        topic = state.get("research_topic", "")
        question = state.get("research_question", "")
        phase = state.get("current_phase", "unknown")

        return [
            {
                "role": "user",
                "content": (
                    f"Research topic: {topic}\n"
                    f"Research question: {question}\n"
                    f"Current phase: {phase}\n\n"
                    "Please proceed with your task."
                ),
            }
        ]

    def process_result(
        self,
        result_text: str,
        conversation: list[dict[str, Any]],
        state: ResearchState,
    ) -> dict[str, Any]:
        """Map the agent's output to state updates.

        Returns a dict of state fields to update (merged into state by the node).
        Override in each subclass.
        """
        return {}

    def run(self, state: ResearchState) -> dict[str, Any]:
        """Execute the full agent lifecycle and return state updates."""
        logger.info("[%s] Starting agent run for phase: %s",
                     self.name, state.get("current_phase", "?"))

        system_prompt = self.get_system_prompt(state)
        messages = self.build_messages(state)
        tool_defs, tool_funcs = self.get_tools()

        result_text, conversation = run_tool_loop(
            client=self.client,
            model=self.model,
            system_prompt=system_prompt,
            messages=messages,
            tools=tool_defs,
            tool_functions=tool_funcs,
        )

        updates = self.process_result(result_text, conversation, state)
        logger.info("[%s] Agent run complete. State updates: %s",
                     self.name, list(updates.keys()))
        return updates
