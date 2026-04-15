"""Unit tests for individual tool functions."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Tool Registry ─────────────────────────────────────────────────────────────

class TestToolRegistry:
    def test_register_and_retrieve(self):
        from bioagent.tools.registry import ToolRegistry

        reg = ToolRegistry()
        reg.register(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
            function=lambda x: f"result: {x}",
        )
        assert "test_tool" in reg.list_tools()
        defs = reg.get_definitions(["test_tool"])
        assert len(defs) == 1
        assert defs[0]["name"] == "test_tool"
        funcs = reg.get_functions(["test_tool"])
        assert funcs["test_tool"]("hello") == "result: hello"

    def test_missing_name_returns_empty(self):
        from bioagent.tools.registry import ToolRegistry

        reg = ToolRegistry()
        defs = reg.get_definitions(["nonexistent"])
        assert defs == []
        funcs = reg.get_functions(["nonexistent"])
        assert funcs == {}

    def test_overwrite_warns(self, caplog):
        import logging
        from bioagent.tools.registry import ToolRegistry

        reg = ToolRegistry()
        reg.register("x", "desc1", {}, lambda: None)
        with caplog.at_level(logging.WARNING):
            reg.register("x", "desc2", {}, lambda: None)
        assert any("Overwriting" in r.message for r in caplog.records)


# ── File Tools ────────────────────────────────────────────────────────────────

class TestFileTools:
    def test_path_traversal_blocked(self, tmp_path, monkeypatch):
        from bioagent.config.settings import settings
        monkeypatch.setattr(settings, "workspace_dir", str(tmp_path))
        # Force workspace_path to use tmp_path
        monkeypatch.setattr(type(settings), "workspace_path",
                            property(lambda self: tmp_path))

        from bioagent.tools.general.file_tools import read_file

        result = read_file("../../etc/passwd")
        assert "Error" in result
        assert "traversal" in result.lower() or "blocked" in result.lower()

    def test_write_and_read_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(type(__import__("bioagent.config.settings", fromlist=["settings"]).settings),
                            "workspace_path", property(lambda self: tmp_path))
        from bioagent.tools.general.file_tools import read_file, write_file

        result = write_file("test_output.txt", "hello world")
        assert "Successfully" in result

        content = read_file("test_output.txt")
        assert content == "hello world"

    def test_read_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(type(__import__("bioagent.config.settings", fromlist=["settings"]).settings),
                            "workspace_path", property(lambda self: tmp_path))
        from bioagent.tools.general.file_tools import read_file

        result = read_file("nonexistent.txt")
        assert "Error" in result or "not found" in result


# ── Bioinformatics Templates ───────────────────────────────────────────────────

class TestSequenceTools:
    def test_known_templates_exist(self):
        from bioagent.tools.bioinformatics.sequence_tools import get_sequence_analysis_template

        for t in ["blast", "alignment", "gc_content"]:
            result = get_sequence_analysis_template(t)
            assert "def " in result or "import" in result, f"Template {t} seems empty"

    def test_unknown_template_returns_message(self):
        from bioagent.tools.bioinformatics.sequence_tools import get_sequence_analysis_template

        result = get_sequence_analysis_template("nonexistent_type")
        assert "not found" in result.lower()

    def test_register_is_idempotent(self):
        from bioagent.tools.bioinformatics.sequence_tools import register_tools
        from bioagent.tools.registry import registry

        initial_count = len(registry.list_tools())
        register_tools()
        first = len(registry.list_tools())
        register_tools()  # second call should not add duplicates
        second = len(registry.list_tools())
        assert first == second


class TestExpressionTools:
    def test_scanpy_template_present(self):
        from bioagent.tools.bioinformatics.expression_tools import get_expression_analysis_template

        result = get_expression_analysis_template("scanpy_basic")
        assert "scanpy" in result.lower() or "sc.pp" in result

    def test_differential_expression_template(self):
        from bioagent.tools.bioinformatics.expression_tools import get_expression_analysis_template

        result = get_expression_analysis_template("differential_expression")
        assert "ttest" in result.lower() or "statsmodels" in result.lower()

    def test_pydeseq2_template(self):
        from bioagent.tools.bioinformatics.expression_tools import get_expression_analysis_template

        result = get_expression_analysis_template("pydeseq2")
        assert "pydeseq2" in result.lower() or "DeseqDataSet" in result

    def test_survival_analysis_template(self):
        from bioagent.tools.bioinformatics.expression_tools import get_expression_analysis_template

        result = get_expression_analysis_template("survival_analysis")
        assert "KaplanMeier" in result or "lifelines" in result


class TestGenomicTools:
    def test_gwas_simulation_template(self):
        from bioagent.tools.bioinformatics.genomic_tools import get_genomic_analysis_template

        result = get_genomic_analysis_template("gwas_simulation")
        assert "simulate_gwas" in result

    def test_manhattan_plot_template_no_bug(self):
        from bioagent.tools.bioinformatics.genomic_tools import get_genomic_analysis_template

        result = get_genomic_analysis_template("manhattan_plot")
        # Check that the fixed offset calculation is present
        assert "chr_offsets" in result
        assert "cumulative" in result

    def test_gene_set_analysis_template(self):
        from bioagent.tools.bioinformatics.genomic_tools import get_genomic_analysis_template

        result = get_genomic_analysis_template("gene_set_analysis")
        assert "fisher_exact" in result or "fisher" in result.lower()


# ── Python Runner ──────────────────────────────────────────────────────────────

class TestPythonRunner:
    def test_simple_execution(self, tmp_path, monkeypatch):
        from bioagent.config.settings import settings
        monkeypatch.setattr(type(settings), "workspace_path", property(lambda self: tmp_path))
        monkeypatch.setattr(settings, "code_timeout", 10)
        monkeypatch.setattr(settings, "random_seed", 42)

        from bioagent.tools.execution.python_runner import execute_python

        result = execute_python("print('hello from test')")
        assert result["exit_code"] == 0
        assert "hello from test" in result["stdout"]

    def test_syntax_error_captured(self, tmp_path, monkeypatch):
        from bioagent.config.settings import settings
        monkeypatch.setattr(type(settings), "workspace_path", property(lambda self: tmp_path))
        monkeypatch.setattr(settings, "code_timeout", 10)
        monkeypatch.setattr(settings, "random_seed", 42)

        from bioagent.tools.execution.python_runner import execute_python

        result = execute_python("this is not python")
        assert result["exit_code"] != 0
        assert result["stderr"] != ""

    def test_seed_injection(self, tmp_path, monkeypatch):
        """Check that the random seed header is injected into the script."""
        from bioagent.config.settings import settings
        from bioagent.tools.execution.python_runner import execute_python
        monkeypatch.setattr(type(settings), "workspace_path", property(lambda self: tmp_path))
        monkeypatch.setattr(settings, "code_timeout", 10)
        monkeypatch.setattr(settings, "random_seed", 99)

        # Run something that uses the seed
        code = "import random; print(random.random())"
        result = execute_python(code)
        assert result["exit_code"] == 0
        # The output should be reproducible — seeded with 99
        first_run = result["stdout"].strip()

        result2 = execute_python(code)
        second_run = result2["stdout"].strip()
        assert first_run == second_run


# ── BioMCP Tools ──────────────────────────────────────────────────────────────

class TestBioMCPTools:
    def test_ansi_stripping(self):
        from bioagent.tools.literature.biomcp_tools import _strip_ansi

        colored = "\x1b[32mgreen text\x1b[0m"
        stripped = _strip_ansi(colored)
        assert stripped == "green text"
        assert "\x1b" not in stripped

    def test_register_tools_idempotent(self):
        from bioagent.tools.literature.biomcp_tools import register_tools
        from bioagent.tools.registry import registry

        register_tools()
        count1 = len([t for t in registry.list_tools() if "article" in t or "gene" in t])
        register_tools()
        count2 = len([t for t in registry.list_tools() if "article" in t or "gene" in t])
        assert count1 == count2
