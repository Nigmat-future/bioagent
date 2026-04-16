"""Tests for the DataAcquisitionAgent and its underlying data tools.

External network calls are mocked; these tests verify the agent's parsing
logic, fallback hierarchy, and status-classification rules without hitting
real GEO/TCGA/NCBI endpoints.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── Agent parsing ─────────────────────────────────────────────────────────────

class TestDataAcquisitionAgentParsing:
    def _agent(self):
        from bioagent.agents.data_acquisition import DataAcquisitionAgent

        return DataAcquisitionAgent.__new__(DataAcquisitionAgent)

    def test_parse_complete_success(self):
        """Full-success LLM output should produce status='complete'."""
        agent = self._agent()
        text = (
            "### DOWNLOAD_SUMMARY\n"
            "- dataset GSE65904: SUCCESS\n"
            "- study skcm_tcga: SUCCESS\n"
            "\n"
            "### DATA_MANIFEST\n"
            "- data/GSE65904_matrix.csv | expression matrix | 12 MB\n"
            "- data/skcm_tcga_mutations.tsv | TCGA mutations | 4 MB\n"
            "\n"
            "### MANUAL_INSTRUCTIONS\n"
            "None required.\n"
        )
        updates = agent.process_result(text, [], {})
        assert updates["data_status"]["status"] == "complete"
        assert len(updates["data_artifacts"]) == 2
        assert updates["data_artifacts"][0]["path"] == "data/GSE65904_matrix.csv"

    def test_parse_partial_with_manual_fallback(self):
        """When SOME files downloaded but manual instructions exist -> partial."""
        agent = self._agent()
        text = (
            "### DOWNLOAD_SUMMARY\n"
            "- accession GSE50509: SUCCESS\n"
            "- study protected_cohort: ERROR\n"
            "\n"
            "### DATA_MANIFEST\n"
            "- data/GSE50509.csv | expression | 8 MB\n"
            "\n"
            "### MANUAL_INSTRUCTIONS\n"
            "Download protected_cohort via dbGaP approval.\n"
        )
        updates = agent.process_result(text, [], {})
        assert updates["data_status"]["status"] == "partial"

    def test_parse_full_failure(self):
        """When no files downloaded -> failed or manual_required."""
        agent = self._agent()
        text = (
            "### DOWNLOAD_SUMMARY\n- dataset X: ERROR\n\n"
            "### DATA_MANIFEST\n\n"
            "### MANUAL_INSTRUCTIONS\n"
            "Download dataset X manually from <url>.\n"
        )
        updates = agent.process_result(text, [], {})
        # No artefacts were produced; the status must reflect that manual
        # intervention is required (either 'manual_required' or 'partial'
        # are acceptable — both indicate the pipeline did not auto-complete).
        assert updates["data_status"]["status"] in {"manual_required", "partial", "failed"}
        # Crucially: no real data_artifacts should be populated.
        assert not updates.get("data_artifacts")

    def test_parse_missing_sections_is_failed(self):
        """Output lacking any recognisable section -> status='failed'."""
        agent = self._agent()
        updates = agent.process_result("garbage output", [], {})
        assert updates["data_status"]["status"] == "failed"

    def test_name_is_data_acquisition(self):
        from bioagent.agents.data_acquisition import DataAcquisitionAgent

        assert DataAcquisitionAgent.name == "data_acquisition"


# ── Tool registration ─────────────────────────────────────────────────────────

class TestDataToolRegistration:
    def test_register_is_idempotent(self):
        """Calling register_data_tools twice should not crash."""
        from bioagent.tools.data.register import register_data_tools

        register_data_tools()
        register_data_tools()  # Must not raise.

    def test_all_tools_registered(self):
        from bioagent.tools.data.register import register_data_tools
        from bioagent.tools.registry import registry

        register_data_tools()

        expected = {
            "download_url",
            "download_geo_dataset",
            "search_cbioportal_studies",
            "download_cbioportal_study",
            "search_gdc_datasets",
            "download_gdc_file",
            "download_ncbi_sequences",
            "search_encode_datasets",
            "download_encode_file",
            "generate_download_instructions",
        }
        registered = set(registry.list_tools())
        missing = expected - registered
        assert not missing, f"Tools not registered: {missing}"


# ── URL download safety ───────────────────────────────────────────────────────

class TestUrlDownload:
    def test_rejects_non_http_urls(self):
        """URL downloader should reject non-http(s) schemes."""
        from bioagent.tools.data.url_download import download_url

        result = download_url("file:///etc/passwd")
        assert result.startswith("ERROR")

    def test_manual_instructions_produces_markdown_file(self, tmp_path, monkeypatch):
        """Manual-instructions generator should produce a markdown file."""
        from bioagent.tools.data.manual_instructions import generate_download_instructions

        # generate_download_instructions imports settings + ensure_workspace
        # lazily inside the function, so patching them on their source
        # modules works without racing with prior imports.
        mock_settings = MagicMock()
        mock_settings.workspace_path = tmp_path
        monkeypatch.setattr(
            "bioagent.config.settings.settings", mock_settings
        )
        # ensure_workspace just mkdirs the workspace; our tmp_path already
        # exists so we stub it to a no-op to keep the test hermetic.
        monkeypatch.setattr(
            "bioagent.tools.execution.sandbox.ensure_workspace", lambda: None
        )

        result = generate_download_instructions(
            dataset_description="Test dataset for unit test",
            accession="GSE99999",
            source="GEO",
            url="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE99999",
        )
        assert result  # non-empty status string
        data_dir = tmp_path / "data"
        assert data_dir.exists(), "data directory was not created"
        md_files = list(data_dir.glob("*.md"))
        assert md_files, "No manual-instructions markdown file was produced"
