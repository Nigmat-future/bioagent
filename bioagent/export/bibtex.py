"""BibTeX generation from PMID / paper metadata stored in ResearchState.

Converts the ``papers`` list (each entry has at minimum an ``id`` field
containing a PMID) into valid BibTeX entries using BioMCP for metadata
retrieval.  Falls back to a minimal entry when lookup fails.
"""

from __future__ import annotations

import logging
import re
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def _fetch_article_metadata(pmid: str) -> dict[str, str]:
    """Fetch article metadata via BioMCP CLI.

    Returns a flat dict with keys: title, authors, journal, year, volume,
    pages, doi.  All values are strings; missing fields default to empty string.
    """
    try:
        result = subprocess.run(
            ["biomcp", "get", "article", pmid],
            capture_output=True,
            text=True,
            timeout=30,
        )
        text = result.stdout
    except Exception as exc:
        logger.warning("BioMCP lookup failed for PMID %s: %s", pmid, exc)
        return {}

    meta: dict[str, str] = {}

    # Title
    m = re.search(r"(?:Title|title)[:\s]+(.+)", text)
    if m:
        meta["title"] = m.group(1).strip()

    # Authors — take first line after "Authors:"
    m = re.search(r"(?:Authors?)[:\s]+(.+)", text)
    if m:
        meta["authors"] = m.group(1).strip()

    # Journal
    m = re.search(r"(?:Journal|Source)[:\s]+(.+)", text)
    if m:
        meta["journal"] = m.group(1).strip()

    # Year — look for 4-digit year
    m = re.search(r"\b(20\d{2}|19\d{2})\b", text)
    if m:
        meta["year"] = m.group(1)

    # DOI
    m = re.search(r"(?:DOI|doi)[:\s]+(10\.\S+)", text)
    if m:
        meta["doi"] = m.group(1).strip().rstrip(".")

    # Volume / Pages
    m = re.search(r"Volume[:\s]+(\d+)", text, re.IGNORECASE)
    if m:
        meta["volume"] = m.group(1)
    m = re.search(r"Pages?[:\s]+([\d\-]+)", text, re.IGNORECASE)
    if m:
        meta["pages"] = m.group(1)

    return meta


def _make_cite_key(pmid: str, meta: dict[str, str]) -> str:
    """Generate a cite key like 'Smith2023' from metadata."""
    authors = meta.get("authors", "")
    year = meta.get("year", "")
    first_author = ""
    if authors:
        # Take surname of first author (before comma or 'and')
        first = re.split(r",|\band\b", authors)[0].strip()
        words = first.split()
        # Surname is typically the first word in "Surname Initial(s)" format
        # or the last word in "First Surname" format.
        # Heuristic: if ≥2 words and last word is 1-2 chars (initial), use first word.
        if len(words) >= 2 and len(words[-1]) <= 2:
            first_author = re.sub(r"[^A-Za-z]", "", words[0])
        else:
            first_author = re.sub(r"[^A-Za-z]", "", words[-1]) if words else ""
    if first_author and year:
        return f"{first_author}{year}"
    return f"PMID{pmid}"


def pmid_to_bibtex(pmid: str, meta: dict[str, str] | None = None) -> str:
    """Convert a single PMID to a BibTeX @article entry.

    Parameters
    ----------
    pmid : str
        PubMed ID.
    meta : dict, optional
        Pre-fetched metadata dict. If None, BioMCP is queried automatically.
    """
    if meta is None:
        meta = _fetch_article_metadata(pmid)

    cite_key = _make_cite_key(pmid, meta)
    title = meta.get("title", f"Article {pmid}")
    authors = meta.get("authors", "Unknown")
    journal = meta.get("journal", "Unknown")
    year = meta.get("year", "0000")

    lines = [
        f"@article{{{cite_key},",
        f"  author  = {{{authors}}},",
        f"  title   = {{{title}}},",
        f"  journal = {{{journal}}},",
        f"  year    = {{{year}}},",
    ]
    if meta.get("volume"):
        lines.append(f"  volume  = {{{meta['volume']}}},")
    if meta.get("pages"):
        lines.append(f"  pages   = {{{meta['pages']}}},")
    if meta.get("doi"):
        lines.append(f"  doi     = {{{meta['doi']}}},")
    lines.append(f"  pmid    = {{{pmid}}},")
    lines.append("}")

    return "\n".join(lines)


def generate_bibtex(papers: list[dict[str, Any]]) -> str:
    """Convert the papers list from ResearchState into a BibTeX string.

    Parameters
    ----------
    papers : list[dict]
        Each dict must have at minimum an ``id`` field (PMID).
        Optional fields: ``title``, ``authors``, ``journal``, ``year``.
    """
    entries: list[str] = []
    seen_pmids: set[str] = set()

    for paper in papers:
        pmid = str(paper.get("id", "")).strip()
        if not pmid or pmid in seen_pmids:
            continue
        seen_pmids.add(pmid)

        # Use any pre-existing metadata from the paper dict
        meta: dict[str, str] = {}
        for key in ("title", "authors", "journal", "year", "doi", "volume", "pages"):
            val = paper.get(key)
            if val:
                meta[key] = str(val)

        # Only call BioMCP if we're missing title / year
        if not (meta.get("title") and meta.get("year")):
            fetched = _fetch_article_metadata(pmid)
            meta = {**fetched, **meta}  # prefer pre-existing values

        entry = pmid_to_bibtex(pmid, meta)
        entries.append(entry)

    return "\n\n".join(entries)
