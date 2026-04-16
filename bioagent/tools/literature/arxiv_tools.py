"""ArXiv search tools via the arxiv Python package."""

from __future__ import annotations

import logging

from bioagent.tools.registry import registry

logger = logging.getLogger(__name__)


def search_arxiv(query: str, max_results: int = 10, sort_by: str = "relevance") -> str:
    """Search ArXiv for preprints related to bioinformatics and computational biology.

    Parameters
    ----------
    query : str
        Search query (e.g. ``"single cell RNA sequencing clustering"``).
    max_results : int
        Maximum number of results (default 10, max 30).
    sort_by : str
        Sort order: ``"relevance"`` or ``"date"``.
    """
    try:
        import arxiv

        sort_map = {
            "relevance": arxiv.SortCriterion.Relevance,
            "date": arxiv.SortCriterion.SubmittedDate,
        }
        criterion = sort_map.get(sort_by, arxiv.SortCriterion.Relevance)

        search = arxiv.Search(
            query=query,
            max_results=min(max_results, 10),
            sort_by=criterion,
        )

        results = []
        for i, paper in enumerate(search.results(), 1):
            entry = (
                f"[{i}] {paper.title}\n"
                f"    Authors: {', '.join(a.name for a in paper.authors[:5])}"
                f"{'...' if len(paper.authors) > 5 else ''}\n"
                f"    Date: {paper.published.strftime('%Y-%m-%d') if paper.published else 'N/A'}\n"
                f"    ArXiv: {paper.entry_id}\n"
                f"    Categories: {', '.join(paper.categories[:3])}\n"
                f"    Abstract: {(paper.summary or '')[:300]}...\n"
            )
            results.append(entry)

        if not results:
            return f"No ArXiv results found for: '{query}'"

        header = f"# ArXiv Search: '{query}' ({len(results)} results)\n\n"
        return header + "\n".join(results)

    except ImportError:
        return "Error: arxiv package not installed. Run: pip install arxiv"
    except Exception as exc:
        logger.exception("ArXiv search failed")
        return f"Error searching ArXiv: {exc}"


def get_arxiv_paper(arxiv_id: str) -> str:
    """Get full details of an ArXiv paper by its ID.

    Parameters
    ----------
    arxiv_id : str
        ArXiv paper ID (e.g. ``"2312.1245"`` or full URL).
    """
    try:
        import arxiv

        # Extract ID from URL if needed
        if "/" in arxiv_id:
            arxiv_id = arxiv_id.rsplit("/", 1)[-1]

        search = arxiv.Search(id_list=[arxiv_id])
        papers = list(search.results())

        if not papers:
            return f"ArXiv paper not found: {arxiv_id}"

        paper = papers[0]
        return (
            f"# {paper.title}\n\n"
            f"**ArXiv:** {paper.entry_id}\n"
            f"**Published:** {paper.published.strftime('%Y-%m-%d') if paper.published else 'N/A'}\n"
            f"**Updated:** {paper.updated.strftime('%Y-%m-%d') if paper.updated else 'N/A'}\n"
            f"**Authors:** {', '.join(a.name for a in paper.authors)}\n"
            f"**Categories:** {', '.join(paper.categories)}\n"
            f"**PDF:** {paper.pdf_url}\n\n"
            f"## Abstract\n\n{paper.summary}\n\n"
            f"## Links\n"
            f"- ArXiv: {paper.entry_id}\n"
            f"- PDF: {paper.pdf_url}\n"
        )

    except Exception as exc:
        return f"Error fetching ArXiv paper: {exc}"


def register_tools() -> None:
    """Register ArXiv tools in the global registry."""
    registry.register(
        name="search_arxiv",
        description="Search ArXiv preprints for computational biology, bioinformatics, and ML papers.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results (default 10, max 30)", "default": 10},
                "sort_by": {"type": "string", "description": "Sort: relevance (default) or date", "default": "relevance"},
            },
            "required": ["query"],
        },
        function=search_arxiv,
    )
    registry.register(
        name="get_arxiv_paper",
        description="Get full details of an ArXiv paper by its ID.",
        input_schema={
            "type": "object",
            "properties": {
                "arxiv_id": {"type": "string", "description": "ArXiv ID (e.g. '2312.1245')"},
            },
            "required": ["arxiv_id"],
        },
        function=get_arxiv_paper,
    )
