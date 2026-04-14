"""Tool registry — maps tool names to callables and generates Anthropic-format schemas."""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for all agent-callable tools.

    Each tool is registered with:
      - name: unique string identifier
      - description: what the tool does (seen by the LLM)
      - input_schema: JSON Schema dict for the tool's parameters
      - function: the Python callable to execute

    The registry produces tool definitions in Anthropic's ``tools`` format,
    ready to pass to ``client.messages.create(tools=...)``.
    """

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}
        self._functions: dict[str, Callable] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        function: Callable,
    ) -> None:
        """Register a single tool."""
        if name in self._tools:
            logger.warning("Overwriting existing tool: %s", name)
        self._tools[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema,
        }
        self._functions[name] = function

    def get_definitions(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        """Return Anthropic-format tool definitions.

        Parameters
        ----------
        names : list[str], optional
            If provided, only return definitions for these tool names.
            Otherwise return all registered tools.
        """
        if names is None:
            return list(self._tools.values())
        return [self._tools[n] for n in names if n in self._tools]

    def get_functions(self, names: list[str] | None = None) -> dict[str, Callable]:
        """Return name → callable mapping for the given tool names."""
        if names is None:
            return dict(self._functions)
        return {n: self._functions[n] for n in names if n in self._functions}

    def list_tools(self) -> list[str]:
        """Return all registered tool names."""
        return list(self._tools.keys())


# Global registry singleton
registry = ToolRegistry()
