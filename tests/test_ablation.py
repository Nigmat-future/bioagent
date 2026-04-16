"""Tests for the ablation variant factories.

Does not actually execute any LLM calls; only verifies that each variant
compiles to a graph that still contains every expected node, with the
ablated ones replaced by pass-through callables.
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "variant",
    ["full", "no_literature", "no_data", "no_code", "no_review"],
)
def test_variant_compiles(variant):
    from benchmarks.ablation import _build_variant_graph

    graph = _build_variant_graph(variant)
    nodes = set(graph.get_graph().nodes)

    # All core phase nodes remain in the graph topology regardless of ablation
    # (ablation replaces the NODE FUNCTION, not the node's existence).
    for required in [
        "orchestrator",
        "literature_review",
        "data_acquisition",
        "code_execution",
        "writing",
        "review",
    ]:
        assert required in nodes, (
            f"Variant {variant!r} lost required node {required!r} "
            f"(got nodes: {sorted(nodes)})"
        )


def test_passthrough_factory_returns_phase_update():
    from benchmarks.ablation import _passthrough_factory

    fn = _passthrough_factory("literature_review")
    state = {"phase_history": ["orchestrator"]}
    update = fn(state)

    assert update["current_phase"] == "literature_review"
    assert update["phase_history"] == ["orchestrator", "literature_review:ablated"]


def test_ablation_restores_original_nodes():
    """After building a variant, the original node functions must be restored."""
    from bioagent.graph import nodes as _nodes

    original_lit = _nodes.literature_review_node

    from benchmarks.ablation import _build_variant_graph

    _build_variant_graph("no_literature")

    assert _nodes.literature_review_node is original_lit, (
        "Ablation runner did not restore the original node — "
        "subsequent un-ablated runs would silently use the pass-through."
    )


def test_all_variants_declared():
    """ALL_VARIANTS must match the expected set so the --variant all sweep is complete."""
    from benchmarks.ablation import ALL_VARIANTS

    assert set(ALL_VARIANTS) == {
        "full",
        "no_literature",
        "no_data",
        "no_code",
        "no_review",
        "single_pass_llm",
    }
