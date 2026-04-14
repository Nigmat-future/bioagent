"""Core LLM ↔ Tools agentic loop — the engine powering every agent.

This module talks directly to the Anthropic SDK. No LangChain wrappers.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from anthropic import Anthropic

from bioagent.config.settings import settings
from bioagent.llm.token_tracking import global_token_usage

logger = logging.getLogger(__name__)


def run_tool_loop(
    *,
    client: Anthropic,
    model: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_functions: dict[str, Callable],
    max_iterations: int | None = None,
    max_tokens: int | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Run the LLM ↔ tool-use loop until the model stops requesting tools.

    Parameters
    ----------
    client : Anthropic
        Configured Anthropic client.
    model : str
        Model identifier (e.g. ``"claude-sonnet-4-5-20250929"``).
    system_prompt : str
        System prompt for this agent.
    messages : list[dict]
        Conversation history in Anthropic message format.
    tools : list[dict]
        Tool definitions in Anthropic's ``tools`` format.
    tool_functions : dict[str, Callable]
        Mapping from tool name to Python callable.
    max_iterations : int, optional
        Max tool-use iterations before forcing stop. Defaults to ``settings.max_tool_calls``.
    max_tokens : int, optional
        Max output tokens per LLM call. Defaults to ``settings.max_tokens``.

    Returns
    -------
    tuple[str, list[dict]]
        ``(final_text, updated_conversation)``
    """
    if max_iterations is None:
        max_iterations = settings.max_tool_calls
    if max_tokens is None:
        max_tokens = settings.max_tokens

    conversation: list[dict[str, Any]] = list(messages)

    for iteration in range(max_iterations):
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=conversation,
            tools=tools if tools else [],
        )

        # Track token usage
        if response.usage:
            global_token_usage.add(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cache_creation=getattr(response.usage, "cache_creation_input_tokens", 0),
                cache_read=getattr(response.usage, "cache_read_input_tokens", 0),
            )

        # Extract assistant content blocks
        assistant_content = response.content
        conversation.append({"role": "assistant", "content": assistant_content})

        # Check if the model wants to use tools
        tool_use_blocks = [
            block for block in assistant_content if block.type == "tool_use"
        ]

        if not tool_use_blocks:
            # Model finished — extract text
            text_parts = [
                block.text for block in assistant_content if hasattr(block, "text")
            ]
            final_text = "\n".join(text_parts)
            return final_text, conversation

        # Execute each tool call
        tool_results: list[dict[str, Any]] = []
        for tool_block in tool_use_blocks:
            tool_name = tool_block.name
            tool_input = tool_block.input
            tool_id = tool_block.id

            logger.info("Tool call [%d/%d]: %s(%s)", iteration + 1, max_iterations,
                        tool_name, json.dumps(tool_input, default=str)[:200])

            try:
                func = tool_functions.get(tool_name)
                if func is None:
                    result = f"Error: unknown tool '{tool_name}'"
                elif not tool_input:
                    result = f"Error: {tool_name} requires parameters but none were provided. Check the tool schema."
                else:
                    result = func(**tool_input) if isinstance(tool_input, dict) else func(tool_input)
                # Ensure result is a string
                if not isinstance(result, str):
                    result = json.dumps(result, default=str, indent=2)
            except Exception as exc:
                result = f"Error executing {tool_name}: {exc}"
                logger.exception("Tool %s failed", tool_name)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result,
            })

        conversation.append({"role": "user", "content": tool_results})

    # Exhausted iterations
    logger.warning("Tool loop reached max iterations (%d)", max_iterations)
    return "Max tool-use iterations reached.", conversation
