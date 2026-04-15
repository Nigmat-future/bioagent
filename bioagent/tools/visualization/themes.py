"""Publication-quality matplotlib themes for scientific journals."""

from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
from pathlib import Path

# Standard figure sizes in mm
SINGLE_COLUMN_MM = 89
DOUBLE_COLUMN_MM = 183
MAX_HEIGHT_MM = 247


def mm_to_inches(mm: float) -> float:
    return mm / 25.4


# ── Nature Theme ────────────────────────────────────────────
NATURE_THEME = {
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 7,
    "axes.titlesize": 8,
    "axes.labelsize": 7,
    "xtick.labelsize": 6,
    "ytick.labelsize": 6,
    "legend.fontsize": 6,
    "figure.titlesize": 8,
    "axes.linewidth": 0.5,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
    "xtick.minor.width": 0.3,
    "ytick.minor.width": 0.3,
    "lines.linewidth": 1.0,
    "lines.markersize": 3,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
    "figure.autolayout": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
}

# Color-blind friendly palette (Okabe-Ito)
OKABE_ITO_COLORS = [
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#009E73",  # bluish green
    "#F0E442",  # yellow
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#CC79A7",  # reddish purple
    "#000000",  # black
]


def apply_nature_theme():
    """Apply Nature journal style to matplotlib."""
    plt.rcParams.update(NATURE_THEME)
    plt.rcParams["axes.prop_cycle"] = matplotlib.cycler(color=OKABE_ITO_COLORS)


def apply_science_theme():
    """Apply Science journal style (similar to Nature with slight differences)."""
    apply_nature_theme()
    plt.rcParams["font.size"] = 6
    plt.rcParams["axes.labelsize"] = 7


def create_figure(
    n_cols: int = 1,
    n_rows: int = 1,
    width_mm: float | None = None,
    height_mm: float | None = None,
    theme: str = "nature",
) -> tuple[plt.Figure, list[plt.Axes] | plt.Axes]:
    """Create a publication-quality figure with proper dimensions.

    Parameters
    ----------
    n_cols : int
        Number of subplot columns.
    n_rows : int
        Number of subplot rows.
    width_mm : float, optional
        Figure width in mm. Default: single column (89mm).
    height_mm : float, optional
        Figure height in mm. Default: auto-calculated.
    theme : str
        Journal theme: "nature" or "science".

    Returns
    -------
    tuple[Figure, Axes]
    """
    if theme == "science":
        apply_science_theme()
    else:
        apply_nature_theme()

    if width_mm is None:
        width_mm = SINGLE_COLUMN_MM if n_cols == 1 else DOUBLE_COLUMN_MM
    if height_mm is None:
        height_mm = min(width_mm * 0.75 * n_rows / n_cols, MAX_HEIGHT_MM)

    width_in = mm_to_inches(width_mm)
    height_in = mm_to_inches(height_mm)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(width_in, height_in))
    return fig, axes


def save_figure(fig: plt.Figure, filename: str, formats: list[str] | None = None,
                figures_dir: str | Path | None = None) -> list[str]:
    """Save figure in multiple formats.

    Parameters
    ----------
    fig : Figure
        Matplotlib figure to save.
    filename : str
        Base filename (without extension).
    formats : list[str], optional
        Output formats. Default: ["pdf", "png"].
    figures_dir : str or Path, optional
        Directory to save to. Default: workspace/figures/.

    Returns
    -------
    list[str]
        Paths of saved files.
    """
    if formats is None:
        formats = ["pdf", "png"]

    if figures_dir is None:
        from bioagent.config.settings import settings
        figures_dir = settings.workspace_path / "figures"

    figures_dir = Path(figures_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for fmt in formats:
        path = figures_dir / f"{filename}.{fmt}"
        fig.savefig(str(path), format=fmt, dpi=300, bbox_inches="tight")
        saved.append(str(path))

    plt.close(fig)
    return saved
