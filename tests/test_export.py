"""Unit tests for the export pipeline."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def sample_state_with_content(sample_state):
    """Extended sample state with rich content for export testing."""
    return sample_state  # conftest.py provides this


class TestMarkdownExport:
    def test_exports_without_error(self, sample_state, tmp_path):
        from bioagent.export.markdown_export import export_markdown

        out_path = export_markdown(sample_state, tmp_path)
        assert out_path.exists()
        assert out_path.suffix == ".md"

    def test_includes_title(self, sample_state, tmp_path):
        from bioagent.export.markdown_export import export_markdown

        out_path = export_markdown(sample_state, tmp_path)
        content = out_path.read_text(encoding="utf-8")
        assert "BRAF V600E in melanoma" in content

    def test_includes_all_sections(self, sample_state, tmp_path):
        from bioagent.export.markdown_export import export_markdown

        out_path = export_markdown(sample_state, tmp_path)
        content = out_path.read_text(encoding="utf-8").lower()
        for section in ["abstract", "introduction", "methods", "results", "discussion"]:
            assert section in content, f"Missing section: {section}"

    def test_includes_references(self, sample_state, tmp_path):
        from bioagent.export.markdown_export import export_markdown

        out_path = export_markdown(sample_state, tmp_path)
        content = out_path.read_text(encoding="utf-8")
        assert "12068308" in content  # PMID from sample_state references

    def test_includes_figures(self, sample_state, tmp_path):
        from bioagent.export.markdown_export import export_markdown

        out_path = export_markdown(sample_state, tmp_path)
        content = out_path.read_text(encoding="utf-8")
        assert "Figure 1" in content

    def test_empty_state_exports_cleanly(self, empty_state, tmp_path):
        from bioagent.export.markdown_export import export_markdown

        out_path = export_markdown(empty_state, tmp_path)
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert len(content) > 0

    def test_custom_filename(self, sample_state, tmp_path):
        from bioagent.export.markdown_export import export_markdown

        out_path = export_markdown(sample_state, tmp_path, filename="my_paper.md")
        assert out_path.name == "my_paper.md"


class TestLaTeXExport:
    def test_exports_tex_file(self, sample_state, tmp_path):
        from bioagent.export.latex_export import export_latex

        tex_path, bib_path = export_latex(sample_state, tmp_path, generate_bib=False)
        assert tex_path.exists()
        assert tex_path.suffix == ".tex"

    def test_tex_contains_sections(self, sample_state, tmp_path):
        from bioagent.export.latex_export import export_latex

        tex_path, _ = export_latex(sample_state, tmp_path, generate_bib=False)
        content = tex_path.read_text(encoding="utf-8")
        assert r"\begin{document}" in content
        assert r"\section{" in content

    def test_tex_contains_abstract(self, sample_state, tmp_path):
        from bioagent.export.latex_export import export_latex

        tex_path, _ = export_latex(sample_state, tmp_path, generate_bib=False)
        content = tex_path.read_text(encoding="utf-8")
        assert r"\begin{abstract}" in content
        assert "BRAF" in content

    def test_skip_bib_generation(self, sample_state, tmp_path):
        from bioagent.export.latex_export import export_latex

        _, bib_path = export_latex(sample_state, tmp_path, generate_bib=False)
        assert bib_path is None

    def test_latex_escape_special_chars(self):
        from bioagent.export.latex_export import _escape_latex

        text = "Cost: 100% & more"
        escaped = _escape_latex(text)
        assert r"\%" in escaped
        assert r"\&" in escaped

    def test_markdown_to_latex_bold(self):
        from bioagent.export.latex_export import _markdown_to_latex

        text = "This is **bold** text"
        result = _markdown_to_latex(text)
        assert r"\textbf{bold}" in result

    def test_markdown_to_latex_code(self):
        from bioagent.export.latex_export import _markdown_to_latex

        text = "Use `numpy.array()`"
        result = _markdown_to_latex(text)
        assert r"\texttt{" in result


class TestBibTeX:
    def test_generate_bibtex_empty(self):
        from bioagent.export.bibtex import generate_bibtex

        result = generate_bibtex([])
        assert result == ""

    def test_cite_key_generation(self):
        from bioagent.export.bibtex import _make_cite_key

        meta = {"authors": "Smith J, Jones A", "year": "2023"}
        key = _make_cite_key("12345678", meta)
        assert "Smith" in key or "smith" in key.lower()
        assert "2023" in key

    def test_cite_key_fallback_to_pmid(self):
        from bioagent.export.bibtex import _make_cite_key

        key = _make_cite_key("12345678", {})
        assert "12345678" in key

    def test_pmid_to_bibtex_minimal(self):
        from bioagent.export.bibtex import pmid_to_bibtex

        meta = {
            "title": "BRAF mutations in cancer",
            "authors": "Davies H",
            "journal": "Nature",
            "year": "2002",
        }
        entry = pmid_to_bibtex("12068308", meta)
        assert "@article" in entry
        assert "BRAF mutations" in entry
        assert "12068308" in entry
        assert "Nature" in entry


class TestEvaluationMetrics:
    def test_evaluate_run_full_state(self, sample_state):
        from bioagent.evaluation.metrics import evaluate_run

        report = evaluate_run(sample_state)
        assert report.research_topic == "BRAF V600E in melanoma"
        assert report.literature.papers_found == 3
        assert report.literature.gaps_identified == 3
        assert report.hypothesis.hypotheses_generated == 1
        assert report.writing.sections_written == ["abstract", "introduction", "methods", "results", "discussion"]
        assert report.figures.figure_count == 1
        assert report.weighted_score > 0

    def test_evaluate_empty_state(self, empty_state):
        from bioagent.evaluation.metrics import evaluate_run

        report = evaluate_run(empty_state)
        assert report.literature.papers_found == 0
        assert report.weighted_score >= 0

    def test_precision_recall_with_gold_standard(self, sample_state):
        from bioagent.evaluation.metrics import evaluate_run

        # Gold standard: papers in state + one extra not found
        gold = ["12068308", "20818844", "99999999"]  # third not in state
        report = evaluate_run(sample_state, gold_standard_pmids=gold)

        # 2 of 3 gold papers found
        assert report.literature.recall == pytest.approx(2 / 3, abs=0.01)
        assert report.literature.precision == pytest.approx(2 / 3, abs=0.01)

    def test_report_to_dict_structure(self, sample_state):
        from bioagent.evaluation.metrics import evaluate_run

        report = evaluate_run(sample_state)
        d = report.to_dict()
        assert "weighted_score" in d
        assert "literature" in d
        assert "analysis" in d
        assert "writing" in d
        assert "figures" in d
        assert "efficiency" in d
