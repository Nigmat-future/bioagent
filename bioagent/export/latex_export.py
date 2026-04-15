"""LaTeX export — generates a Bioinformatics (Oxford) formatted manuscript.

Produces:
  manuscript.tex   — main LaTeX source (Bioinformatics OUP format)
  references.bib   — BibTeX bibliography
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path

from bioagent.export.bibtex import generate_bibtex
from bioagent.export.markdown_export import SECTION_ORDER
from bioagent.state.schema import ResearchState

logger = logging.getLogger(__name__)

# Bioinformatics (Oxford) article template — uses standard article class
# with common bioinformatics conventions.
_LATEX_TEMPLATE = r"""% BioAgent — auto-generated manuscript
% Target journal: Bioinformatics (Oxford University Press)
% https://academic.oup.com/bioinformatics/pages/submission_online
\documentclass[10pt,twocolumn]{{article}}

\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{lmodern}}
\usepackage{{microtype}}
\usepackage{{amsmath,amssymb}}
\usepackage{{graphicx}}
\usepackage{{hyperref}}
\usepackage{{natbib}}
\usepackage{{booktabs}}
\usepackage{{xcolor}}
\usepackage[margin=2cm]{{geometry}}

\hypersetup{{
    colorlinks=true,
    linkcolor=blue!70!black,
    citecolor=green!50!black,
    urlcolor=blue!70!black,
}}

% ── Title block ──────────────────────────────────────────────────────────────
\title{{{title}}}
\author{{BioAgent Autonomous Research System}}
\date{{{date}}}

\begin{{document}}
\maketitle

% ── Abstract ─────────────────────────────────────────────────────────────────
\begin{{abstract}}
{abstract}
\end{{abstract}}

\noindent\textbf{{Keywords:}} {keywords}

% ── Body sections ─────────────────────────────────────────────────────────────
{body}

% ── Figures ───────────────────────────────────────────────────────────────────
{figures_block}

% ── References ────────────────────────────────────────────────────────────────
\bibliographystyle{{natbib}}
\bibliography{{references}}

\end{{document}}
"""

_SECTION_TEMPLATE = r"""
\section{{{heading}}}
{content}
"""

_FIGURE_TEMPLATE = r"""
\begin{{figure}}[htbp]
  \centering
  \includegraphics[width=\columnwidth]{{{path}}}
  \caption{{{caption}}}
  \label{{fig:{label}}}
\end{{figure}}
"""


def _escape_latex(text: str) -> str:
    """Escape special LaTeX characters in free text."""
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for char, escaped in replacements:
        text = text.replace(char, escaped)
    return text


def _markdown_to_latex(text: str) -> str:
    """Convert simple Markdown formatting to LaTeX equivalents."""
    # Bold: **text** → \textbf{text}
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    # Italic: *text* → \textit{text}
    text = re.sub(r"\*(.+?)\*", r"\\textit{\1}", text)
    # Code: `text` → \texttt{text}
    text = re.sub(r"`(.+?)`", r"\\texttt{\1}", text)
    return text


def export_latex(
    state: ResearchState,
    output_dir: Path,
    generate_bib: bool = True,
) -> tuple[Path, Path | None]:
    """Generate a LaTeX manuscript and optional BibTeX file.

    Parameters
    ----------
    state : ResearchState
        Complete research state.
    output_dir : Path
        Directory to write output files.
    generate_bib : bool
        Whether to generate references.bib (requires BioMCP).

    Returns
    -------
    tuple[Path, Path | None]
        ``(tex_path, bib_path)`` — bib_path is None when not generated.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    topic = state.get("research_topic", "Untitled Research")
    paper_sections = state.get("paper_sections", {})
    figures = state.get("figures", [])
    papers = state.get("papers", [])
    today = datetime.date.today().isoformat()

    # ── Abstract ─────────────────────────────────────────────────────────────
    abstract_data = paper_sections.get("abstract", {})
    abstract_text = (
        abstract_data.get("content", "") if isinstance(abstract_data, dict) else str(abstract_data)
    )
    if not abstract_text:
        abstract_text = "Abstract not yet generated."

    # ── Body sections ─────────────────────────────────────────────────────────
    body_parts: list[str] = []
    for section_key in SECTION_ORDER:
        if section_key == "abstract":
            continue
        section_data = paper_sections.get(section_key)
        if not section_data:
            continue
        content = (
            section_data.get("content", "") if isinstance(section_data, dict) else str(section_data)
        )
        if not content.strip():
            continue
        heading = section_key.title()
        latex_content = _markdown_to_latex(_escape_latex(content.strip()))
        body_parts.append(_SECTION_TEMPLATE.format(heading=heading, content=latex_content))

    # Extra sections
    for key, val in paper_sections.items():
        if key in SECTION_ORDER:
            continue
        content = val.get("content", "") if isinstance(val, dict) else str(val)
        if content.strip():
            latex_content = _markdown_to_latex(_escape_latex(content.strip()))
            body_parts.append(_SECTION_TEMPLATE.format(heading=key.title(), content=latex_content))

    # ── Figures ───────────────────────────────────────────────────────────────
    fig_blocks: list[str] = []
    for i, fig in enumerate(figures, 1):
        if not isinstance(fig, dict):
            continue
        fig_path = fig.get("path", "")
        caption = _escape_latex(fig.get("caption", "") or fig.get("title", f"Figure {i}"))
        label = f"fig{i}"
        # For LaTeX, prefer PDF figures; fall back to PNG
        if fig_path:
            fig_blocks.append(_FIGURE_TEMPLATE.format(
                path=fig_path.replace("\\", "/"),
                caption=caption,
                label=label,
            ))

    # ── Keywords (extracted from topic) ───────────────────────────────────────
    keywords = ", ".join(topic.split()[:5]) if topic else "bioinformatics, AI, research"

    tex_content = _LATEX_TEMPLATE.format(
        title=_escape_latex(topic),
        date=today,
        abstract=_markdown_to_latex(_escape_latex(abstract_text.strip())),
        keywords=_escape_latex(keywords),
        body="\n".join(body_parts),
        figures_block="\n".join(fig_blocks),
    )

    tex_path = output_dir / "manuscript.tex"
    tex_path.write_text(tex_content, encoding="utf-8")
    logger.info("LaTeX manuscript written to %s", tex_path)

    # ── BibTeX ────────────────────────────────────────────────────────────────
    bib_path: Path | None = None
    if generate_bib and papers:
        try:
            bib_content = generate_bibtex(papers)
            bib_path = output_dir / "references.bib"
            bib_path.write_text(bib_content, encoding="utf-8")
            logger.info("BibTeX written to %s (%d entries)", bib_path, len(papers))
        except Exception as exc:
            logger.warning("BibTeX generation failed: %s", exc)

    return tex_path, bib_path
