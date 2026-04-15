"""Unit tests for state reducers and deduplication logic."""

from __future__ import annotations

import pytest


class TestDeduplication:
    def test_dedup_add_prevents_duplicates(self):
        from bioagent.state.reducers import dedup_add

        item = {"id": "12068308", "title": "BRAF mutations"}
        result = dedup_add([item], [item])
        assert len(result) == 1  # duplicate not added

    def test_dedup_add_allows_new_items(self):
        from bioagent.state.reducers import dedup_add

        item1 = {"id": "12068308", "title": "BRAF mutations"}
        item2 = {"id": "20818844", "title": "Vemurafenib trial"}
        result = dedup_add([item1], [item2])
        assert len(result) == 2

    def test_dedup_add_empty_inputs(self):
        from bioagent.state.reducers import dedup_add

        result = dedup_add([], [])
        assert result == []

    def test_dedup_add_left_empty(self):
        from bioagent.state.reducers import dedup_add

        items = [{"id": "1", "val": "a"}, {"id": "2", "val": "b"}]
        result = dedup_add([], items)
        assert len(result) == 2

    def test_dedup_add_strings(self):
        """Strings are valid items for research_gaps field."""
        from bioagent.state.reducers import dedup_add

        result = dedup_add(["gap one", "gap two"], ["gap two", "gap three"])
        assert len(result) == 3
        assert "gap one" in result
        assert "gap three" in result
        assert result.count("gap two") == 1

    def test_dedup_add_right_empty(self):
        from bioagent.state.reducers import dedup_add

        existing = [{"id": "1"}]
        result = dedup_add(existing, [])
        assert result == existing

    def test_content_hash_is_deterministic(self):
        from bioagent.state.reducers import _content_hash

        item = {"id": "12068308", "title": "BRAF mutations", "year": "2002"}
        hash1 = _content_hash(item)
        hash2 = _content_hash(item)
        assert hash1 == hash2

    def test_different_items_have_different_hashes(self):
        from bioagent.state.reducers import _content_hash

        item1 = {"id": "12068308"}
        item2 = {"id": "20818844"}
        assert _content_hash(item1) != _content_hash(item2)


class TestPhaseName:
    def test_valid_phase_names(self):
        from bioagent.state.schema import PhaseName
        import typing

        valid = typing.get_args(PhaseName)
        expected = {
            "literature_review", "gap_analysis", "hypothesis_generation",
            "experiment_design", "code_execution", "result_validation",
            "iteration", "writing", "figure_generation", "review", "complete",
        }
        assert set(valid) == expected
