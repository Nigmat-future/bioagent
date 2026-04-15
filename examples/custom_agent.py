"""How to add a custom agent to BioAgent.

This example adds a MetaAnalysisAgent that synthesizes results
from multiple existing analyses in the state.
"""

from __future__ import annotations

from typing import Any

from bioagent.agents.base import BaseAgent
from bioagent.state.schema import ResearchState


class MetaAnalysisAgent(BaseAgent):
    """Synthesizes multiple analysis results into a meta-analysis summary."""

    name = "meta_analysis"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a meta-analysis specialist. Given multiple analysis results, "
            "synthesize them into a coherent summary with effect sizes, confidence "
            "intervals, and heterogeneity assessments. Always report I² statistics "
            "for heterogeneity and use random-effects models when I² > 50%."
        )

    def get_tools(self) -> tuple[list[dict], dict[str, Any]]:
        # This agent only needs code execution to run forest plot generation
        from bioagent.tools.execution.register import register_execution_tools
        from bioagent.tools.registry import registry

        register_execution_tools()
        tool_names = ["execute_python", "write_file"]
        return registry.get_definitions(tool_names), registry.get_functions(tool_names)

    def build_messages(self, state: ResearchState) -> list[dict[str, Any]]:
        analysis_results = state.get("analysis_results", [])
        hypothesis = state.get("selected_hypothesis", {})
        h_text = hypothesis.get("text", "") if isinstance(hypothesis, dict) else ""

        results_text = "\n\n".join(
            f"Analysis {i+1}:\n{r.get('results', str(r))[:1000]}"
            for i, r in enumerate(analysis_results)
            if isinstance(r, dict)
        )

        return [
            {
                "role": "user",
                "content": (
                    f"## Hypothesis\n{h_text}\n\n"
                    f"## Individual Analysis Results\n{results_text}\n\n"
                    "## Task\n"
                    "Perform a meta-analysis:\n"
                    "1. Extract effect sizes and standard errors from each analysis\n"
                    "2. Compute pooled effect size using random-effects model\n"
                    "3. Calculate I² heterogeneity statistic\n"
                    "4. Generate a forest plot\n"
                    "5. Interpret the synthesized evidence\n\n"
                    "Output:\n"
                    "### META_ANALYSIS_SUMMARY\n<summary>\n\n"
                    "### POOLED_EFFECT\n<effect size ± CI>\n\n"
                    "### HETEROGENEITY\n<I² and interpretation>"
                ),
            }
        ]

    def process_result(
        self,
        result_text: str,
        conversation: list[dict[str, Any]],
        state: ResearchState,
    ) -> dict[str, Any]:
        import re

        def _extract(text: str, header: str) -> str:
            pattern = rf"###\s*{header}\s*\n(.*?)(?=\n###\s|\Z)"
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            return match.group(1).strip() if match else ""

        summary = _extract(result_text, "META_ANALYSIS_SUMMARY")
        effect = _extract(result_text, "POOLED_EFFECT")
        heterogeneity = _extract(result_text, "HETEROGENEITY")

        new_result = {
            "summary": summary,
            "results": f"Pooled effect: {effect}\nHeterogeneity: {heterogeneity}",
            "type": "meta_analysis",
        }

        return {"analysis_results": [new_result]}


# ── To wire this into the graph ───────────────────────────────────────────────
# 1. Add a node function to bioagent/graph/nodes.py:
#
#    def meta_analysis_node(state: ResearchState) -> dict:
#        from examples.custom_agent import MetaAnalysisAgent
#        return MetaAnalysisAgent().run(state)
#
# 2. Add the node and edge to build_research_graph() in research_graph.py:
#
#    graph.add_node("meta_analysis", meta_analysis_node)
#    graph.add_edge("result_validation", "meta_analysis")  # or conditional
#
# 3. Add "meta_analysis" to VALID_PHASES in orchestrator.py and the routing map.
