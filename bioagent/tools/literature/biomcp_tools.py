"""BioMCP CLI wrappers — call biomcp subprocess and return structured text."""

from __future__ import annotations

import logging
import re
import subprocess

from bioagent.tools.registry import registry

logger = logging.getLogger(__name__)

_BIOMCP_TIMEOUT = 30


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from biomcp output."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _run_biomcp(*args: str, timeout: int = _BIOMCP_TIMEOUT) -> str:
    """Run a biomcp CLI command and return stdout as clean text."""
    cmd = ["biomcp", *args]
    logger.info("Running: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        output = _strip_ansi(result.stdout)
        if result.stderr:
            # Include warnings as informational notes, not errors
            stderr_clean = _strip_ansi(result.stderr)
            warnings = [
                line for line in stderr_clean.splitlines()
                if "WARN" in line and "Semantic Scholar" in line
            ]
            if warnings:
                output += "\n[Note: Some sources unavailable, using available data]"
        return output.strip() if output.strip() else "No results found."
    except subprocess.TimeoutExpired:
        return f"Error: biomcp command timed out after {timeout}s."
    except FileNotFoundError:
        return "Error: biomcp CLI not found. Install with: pip install biomcp"
    except Exception as exc:
        return f"Error running biomcp: {exc}"


# ── Tool functions ─────────────────────────────────────────


def search_articles(
    query: str,
    source: str = "pubmed",
    max_results: int = 10,
    date_from: str = "",
    date_to: str = "",
    sort: str = "relevance",
) -> str:
    """Search PubMed / EuropePMC for scientific articles.

    Parameters
    ----------
    query : str
        Search query (e.g. ``"BRAF melanoma drug resistance"``).
    source : str
        ``"pubmed"`` (default) or ``"europepmc"`` or ``"all"``.
    max_results : int
        Maximum results to return (default 10).
    date_from : str
        Start date filter (YYYY, YYYY-MM, or YYYY-MM-DD).
    date_to : str
        End date filter.
    sort : str
        Sort order: ``"relevance"``, ``"date"``, or ``"citations"``.
    """
    args = ["search", "article", query, "--limit", str(max_results), "--sort", sort]
    if source != "pubmed":
        args.extend(["--source", source])
    if date_from:
        args.extend(["--date-from", date_from])
    if date_to:
        args.extend(["--date-to", date_to])
    return _run_biomcp(*args)


def get_article_details(article_id: str, sections: str = "") -> str:
    """Get detailed information about an article by PMID.

    Parameters
    ----------
    article_id : str
        PMID (e.g. ``"30210277"``) or DOI.
    sections : str
        Additional sections: ``"annotations"``, ``"fulltext"``, ``"tldr"``, ``"all"``.
    """
    args = ["get", "article", str(article_id)]
    if sections:
        args.extend(sections.split())
    return _run_biomcp(*args, timeout=45)


def search_all(
    gene: str = "",
    disease: str = "",
    drug: str = "",
    keyword: str = "",
) -> str:
    """Cross-entity search across genes, variants, diseases, drugs, and articles.

    Parameters
    ----------
    gene : str
        Gene symbol (e.g. ``"BRAF"``).
    disease : str
        Disease name (e.g. ``"melanoma"``).
    drug : str
        Drug name.
    keyword : str
        General keyword for article search.
    """
    args = ["search", "all"]
    if gene:
        args.extend(["--gene", gene])
    if disease:
        args.extend(["--disease", disease])
    if drug:
        args.extend(["--drug", drug])
    if keyword:
        args.extend(["--keyword", keyword])
    return _run_biomcp(*args, timeout=45)


def discover_concepts(query: str) -> str:
    """Discover and resolve biomedical concepts from free text.

    Useful for understanding what entities (genes, diseases, drugs) are
    mentioned in a research question.

    Parameters
    ----------
    query : str
        Free-text to resolve (e.g. ``"BRAF inhibitor resistance in melanoma"``).
    """
    return _run_biomcp("discover", query)


def get_gene_info(symbol: str) -> str:
    """Get detailed gene information.

    Parameters
    ----------
    symbol : str
        Gene symbol (e.g. ``"BRAF"``, ``"TP53"``).
    """
    return _run_biomcp("get", "gene", symbol)


def enrich_genes(gene_list: str) -> str:
    """Run gene-set enrichment analysis via g:Profiler.

    Parameters
    ----------
    gene_list : str
        Comma-separated gene symbols (e.g. ``"BRAF,TP53,EGFR,KRAS"``).
    """
    return _run_biomcp("enrich", gene_list, timeout=60)


# ── Registration ───────────────────────────────────────────


def register_tools() -> None:
    """Register all BioMCP tools in the global registry."""
    registry.register(
        name="search_articles",
        description="Search PubMed/EuropePMC for scientific articles by query. Returns titles, PMIDs, dates, and citation counts.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "source": {"type": "string", "description": "Data source: pubmed (default), europepmc, or all", "default": "pubmed"},
                "max_results": {"type": "integer", "description": "Max results (default 10, max 30)", "default": 10},
                "date_from": {"type": "string", "description": "Start date (YYYY or YYYY-MM or YYYY-MM-DD)"},
                "date_to": {"type": "string", "description": "End date"},
                "sort": {"type": "string", "description": "Sort: relevance (default), date, or citations", "default": "relevance"},
            },
            "required": ["query"],
        },
        function=search_articles,
    )
    registry.register(
        name="get_article_details",
        description="Get full details of an article by PMID: abstract, authors, DOI, journal, citations. Optionally include annotations, fulltext, or tldr.",
        input_schema={
            "type": "object",
            "properties": {
                "article_id": {"type": "string", "description": "PMID (e.g. '30210277')"},
                "sections": {"type": "string", "description": "Extra sections: annotations, fulltext, tldr, all (space-separated)"},
            },
            "required": ["article_id"],
        },
        function=get_article_details,
    )
    registry.register(
        name="search_all",
        description="Cross-entity biomedical search: simultaneously search genes, variants, diseases, drugs, and articles.",
        input_schema={
            "type": "object",
            "properties": {
                "gene": {"type": "string", "description": "Gene symbol (e.g. 'BRAF')"},
                "disease": {"type": "string", "description": "Disease name (e.g. 'melanoma')"},
                "drug": {"type": "string", "description": "Drug name"},
                "keyword": {"type": "string", "description": "General keyword for article search"},
            },
        },
        function=search_all,
    )
    registry.register(
        name="discover_concepts",
        description="Resolve free-text biomedical concepts into structured entities (genes, diseases, drugs, phenotypes).",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text query to resolve"},
            },
            "required": ["query"],
        },
        function=discover_concepts,
    )
    registry.register(
        name="get_gene_info",
        description="Get detailed gene information: function, pathways, disease associations, protein data.",
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Gene symbol (e.g. 'BRAF', 'TP53')"},
            },
            "required": ["symbol"],
        },
        function=get_gene_info,
    )
    registry.register(
        name="enrich_genes",
        description="Run gene-set enrichment analysis (g:Profiler) to find overrepresented pathways and GO terms.",
        input_schema={
            "type": "object",
            "properties": {
                "gene_list": {"type": "string", "description": "Comma-separated gene symbols (e.g. 'BRAF,TP53,EGFR')"},
            },
            "required": ["gene_list"],
        },
        function=enrich_genes,
    )
