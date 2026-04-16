"""Register all data acquisition tools into the global tool registry."""

from __future__ import annotations


def register_data_tools() -> None:
    """Register data download tools (idempotent)."""
    from bioagent.tools.registry import registry

    from bioagent.tools.data.url_download import download_url
    from bioagent.tools.data.geo_tools import download_geo_dataset
    from bioagent.tools.data.cbioportal_tools import (
        search_cbioportal_studies,
        download_cbioportal_study,
    )
    from bioagent.tools.data.tcga_gdc_tools import (
        search_gdc_datasets,
        download_gdc_file,
    )
    from bioagent.tools.data.ncbi_tools import download_ncbi_sequences
    from bioagent.tools.data.encode_tools import (
        search_encode_datasets,
        download_encode_file,
    )
    from bioagent.tools.data.manual_instructions import generate_download_instructions

    _reg = registry

    if "download_url" not in _reg.list_tools():
        _reg.register(
            name="download_url",
            description=(
                "Download any file from a URL into workspace/data/. "
                "Auto-extracts .gz and .zip archives. "
                "Use when you have a direct download link."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full HTTPS URL to download"},
                    "filename": {
                        "type": "string",
                        "description": "Output filename (auto-detected if empty)",
                        "default": "",
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable description for logging",
                        "default": "",
                    },
                },
                "required": ["url"],
            },
            function=download_url,
        )

    if "download_geo_dataset" not in _reg.list_tools():
        _reg.register(
            name="download_geo_dataset",
            description=(
                "Download a GEO (Gene Expression Omnibus) dataset by accession number. "
                "Supports GSE (series), GPL (platform), GDS (dataset) accessions. "
                "Returns expression matrix CSV when possible."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "accession": {
                        "type": "string",
                        "description": "GEO accession, e.g. 'GSE12345' or 'GPL570'",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Subdirectory within workspace (default: 'data')",
                        "default": "data",
                    },
                },
                "required": ["accession"],
            },
            function=download_geo_dataset,
        )

    if "search_cbioportal_studies" not in _reg.list_tools():
        _reg.register(
            name="search_cbioportal_studies",
            description=(
                "Search cBioPortal for cancer genomics studies. "
                "Returns study IDs needed for download_cbioportal_study."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term, e.g. 'melanoma BRAF' or 'TCGA-SKCM'",
                    },
                },
                "required": ["query"],
            },
            function=search_cbioportal_studies,
        )

    if "download_cbioportal_study" not in _reg.list_tools():
        _reg.register(
            name="download_cbioportal_study",
            description=(
                "Download mutation, clinical, CNA, or expression data from cBioPortal. "
                "Use search_cbioportal_studies first to find the study_id."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "study_id": {
                        "type": "string",
                        "description": "cBioPortal study ID, e.g. 'skcm_tcga'",
                    },
                    "data_types": {
                        "type": "string",
                        "description": (
                            "Comma-separated data types: mutations, clinical, cna, "
                            "expression, methylation"
                        ),
                        "default": "mutations,clinical",
                    },
                },
                "required": ["study_id"],
            },
            function=download_cbioportal_study,
        )

    if "search_gdc_datasets" not in _reg.list_tools():
        _reg.register(
            name="search_gdc_datasets",
            description=(
                "Search the GDC (Genomic Data Commons / TCGA) for available data files. "
                "Returns file IDs and access levels."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "GDC project ID, e.g. 'TCGA-SKCM'",
                        "default": "",
                    },
                    "data_category": {
                        "type": "string",
                        "description": (
                            "Category filter: 'Transcriptome Profiling', "
                            "'Simple Nucleotide Variation', 'Copy Number Variation'"
                        ),
                        "default": "",
                    },
                    "data_type": {
                        "type": "string",
                        "description": (
                            "Type filter: 'Gene Expression Quantification', "
                            "'Masked Somatic Mutation'"
                        ),
                        "default": "",
                    },
                },
            },
            function=search_gdc_datasets,
        )

    if "download_gdc_file" not in _reg.list_tools():
        _reg.register(
            name="download_gdc_file",
            description=(
                "Download a specific open-access file from the GDC by file UUID. "
                "Use search_gdc_datasets to find file IDs. "
                "Controlled-access files require dbGaP approval."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "GDC file UUID from search results",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Output filename (auto-detected if empty)",
                        "default": "",
                    },
                },
                "required": ["file_id"],
            },
            function=download_gdc_file,
        )

    if "download_ncbi_sequences" not in _reg.list_tools():
        _reg.register(
            name="download_ncbi_sequences",
            description=(
                "Download sequences or records from NCBI via E-utilities. "
                "Supports nucleotide, protein, gene, pubmed databases."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "accession": {
                        "type": "string",
                        "description": "NCBI accession(s), e.g. 'NM_004333' or 'NM_004333,NM_000038'",
                    },
                    "database": {
                        "type": "string",
                        "description": "NCBI database: nucleotide, protein, gene, pubmed",
                        "default": "nucleotide",
                    },
                    "format": {
                        "type": "string",
                        "description": "Return format: fasta, genbank, json, xml",
                        "default": "fasta",
                    },
                },
                "required": ["accession"],
            },
            function=download_ncbi_sequences,
        )

    if "search_encode_datasets" not in _reg.list_tools():
        _reg.register(
            name="search_encode_datasets",
            description=(
                "Search ENCODE for functional genomics datasets "
                "(ChIP-seq, ATAC-seq, RNA-seq, etc.). "
                "Returns experiment accessions and file counts."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "assay": {
                        "type": "string",
                        "description": "Assay type, e.g. 'ChIP-seq', 'ATAC-seq', 'RNA-seq'",
                        "default": "",
                    },
                    "biosample": {
                        "type": "string",
                        "description": "Biosample term, e.g. 'melanoma cell line', 'A375'",
                        "default": "",
                    },
                    "target": {
                        "type": "string",
                        "description": "Target protein or histone mark, e.g. 'BRAF', 'H3K27ac'",
                        "default": "",
                    },
                },
            },
            function=search_encode_datasets,
        )

    if "download_encode_file" not in _reg.list_tools():
        _reg.register(
            name="download_encode_file",
            description=(
                "Download a specific ENCODE file by its file accession (ENCF...). "
                "Use search_encode_datasets to find file accessions."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "file_accession": {
                        "type": "string",
                        "description": "ENCODE file accession, e.g. 'ENCFF123ABC'",
                    },
                },
                "required": ["file_accession"],
            },
            function=download_encode_file,
        )

    if "generate_download_instructions" not in _reg.list_tools():
        _reg.register(
            name="generate_download_instructions",
            description=(
                "Generate human-readable manual download instructions when automated "
                "download fails. Writes detailed instructions with exact URLs and "
                "shell commands to workspace/data/DOWNLOAD_INSTRUCTIONS.md."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "dataset_description": {
                        "type": "string",
                        "description": "Plain-English description of the needed dataset",
                    },
                    "accession": {
                        "type": "string",
                        "description": "Dataset accession number if known",
                        "default": "",
                    },
                    "source": {
                        "type": "string",
                        "description": "Source database name, e.g. 'GEO', 'cBioPortal', 'GDC'",
                        "default": "",
                    },
                    "url": {
                        "type": "string",
                        "description": "Direct URL if known",
                        "default": "",
                    },
                },
                "required": ["dataset_description"],
            },
            function=generate_download_instructions,
        )
