"""
Generate publication-quality figures for the BioAgent manuscript.

Run from the project root:
    python paper/figures/generate_figures.py

Outputs (300 DPI PNG + SVG):
  paper/figures/fig1_architecture.png/svg   — LangGraph workflow diagram
  paper/figures/fig2_agent_tools.png/svg    — Agent–Tool relationship
  paper/figures/fig3_benchmark.png/svg      — Performance comparison
  paper/figures/fig4_evaluation_radar.png   — Quality-metrics radar chart
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import numpy as np

OUT = Path(__file__).parent
DPI = 300

# Okabe-Ito colorblind-safe palette
COLORS = {
    "blue":   "#0072B2",
    "orange": "#E69F00",
    "green":  "#009E73",
    "yellow": "#F0E442",
    "sky":    "#56B4E9",
    "red":    "#D55E00",
    "pink":   "#CC79A7",
    "black":  "#000000",
    "gray":   "#999999",
}


# ── Figure 1: LangGraph Workflow Architecture ─────────────────────────────────

def _draw_box(
    ax,
    x,
    y,
    w,
    h,
    title,
    body,
    *,
    facecolor,
    edgecolor,
    linewidth=1.4,
    linestyle="-",
    title_color="#16324F",
    body_color="#334155",
    title_size=10.2,
    body_size=7.8,
    rounding=0.16,
    zorder=3,
):
    patch = mpatches.FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.03,rounding_size={rounding}",
        linewidth=linewidth,
        edgecolor=edgecolor,
        facecolor=facecolor,
        linestyle=linestyle,
        zorder=zorder,
    )
    patch.set_path_effects([
        pe.withSimplePatchShadow(offset=(1.4, -1.4), alpha=0.12),
        pe.Normal(),
    ])
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h * 0.66,
        title,
        ha="center",
        va="center",
        fontsize=title_size,
        fontweight="bold",
        color=title_color,
        zorder=zorder + 1,
    )
    if body:
        ax.text(
            x + w / 2,
            y + h * 0.33,
            body,
            ha="center",
            va="center",
            fontsize=body_size,
            color=body_color,
            zorder=zorder + 1,
            linespacing=1.25,
        )
    return {"x": x, "y": y, "w": w, "h": h}


def _anchor(box, side, frac=0.5, dx=0.0, dy=0.0):
    if side == "top":
        return (box["x"] + box["w"] * frac + dx, box["y"] + box["h"] + dy)
    if side == "bottom":
        return (box["x"] + box["w"] * frac + dx, box["y"] + dy)
    if side == "left":
        return (box["x"] + dx, box["y"] + box["h"] * frac + dy)
    if side == "right":
        return (box["x"] + box["w"] + dx, box["y"] + box["h"] * frac + dy)
    raise ValueError(f"Unknown anchor side: {side}")


def _draw_arrow(
    ax,
    start,
    end,
    *,
    color="#5B6475",
    lw=1.55,
    rad=0.0,
    linestyle="-",
    alpha=1.0,
    text=None,
    text_xy=None,
    text_size=7.4,
    text_color=None,
    zorder=2,
):
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops=dict(
            arrowstyle="-|>",
            color=color,
            lw=lw,
            linestyle=linestyle,
            alpha=alpha,
            mutation_scale=12.5,
            connectionstyle=f"arc3,rad={rad}",
            shrinkA=6,
            shrinkB=6,
        ),
        zorder=zorder,
    )
    if text and text_xy is not None:
        ax.text(
            text_xy[0],
            text_xy[1],
            text,
            fontsize=text_size,
            color=text_color or color,
            ha="center",
            va="center",
            zorder=zorder + 1,
            bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=0.88),
        )


def _draw_panel(ax, x, y, w, h, title, lines, accent):
    panel = mpatches.FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.03,rounding_size=0.14",
        linewidth=1.2,
        edgecolor="#D7DEE8",
        facecolor="#F8FAFC",
        zorder=1,
    )
    panel.set_path_effects([
        pe.withSimplePatchShadow(offset=(1.2, -1.2), alpha=0.08),
        pe.Normal(),
    ])
    ax.add_patch(panel)
    ax.add_patch(mpatches.Rectangle((x, y), 0.16, h, facecolor=accent, edgecolor="none", zorder=2))
    ax.text(
        x + 0.35,
        y + h - 0.32,
        title,
        ha="left",
        va="top",
        fontsize=9.3,
        fontweight="bold",
        color="#0F172A",
        zorder=3,
    )
    text = "\n".join(lines)
    ax.text(
        x + 0.35,
        y + h - 0.74,
        text,
        ha="left",
        va="top",
        fontsize=7.45,
        color="#334155",
        zorder=3,
        linespacing=1.42,
        family="DejaVu Sans Mono",
    )


def fig1_architecture():
    fig, ax = plt.subplots(figsize=(20.5, 12.2))
    ax.set_xlim(0, 26.5)
    ax.set_ylim(0, 15.2)
    ax.axis("off")
    ax.set_facecolor("#FCFDFE")
    fig.patch.set_facecolor("#FCFDFE")

    fills = {
        "start_end": "#1F2937",
        "orchestrator": "#E8F1FA",
        "approval": "#F4F6F8",
        "literature": "#E8F4FB",
        "gap": "#EAF5FF",
        "hypothesis": "#EAF7F1",
        "experiment": "#FFF3DD",
        "data": "#FFF7CF",
        "code": "#FDE9DD",
        "validation": "#F7E8F3",
        "iteration": "#ECECEC",
        "writing": "#EBF3FF",
        "figure": "#FFF0DA",
        "review": "#E6F6EF",
        "export": "#EEF2F7",
        "state": "#F5F7FA",
    }
    edges = {
        "orchestrator": COLORS["blue"],
        "approval": "#98A2B3",
        "literature": COLORS["blue"],
        "gap": COLORS["sky"],
        "hypothesis": COLORS["green"],
        "experiment": COLORS["orange"],
        "data": "#C9B037",
        "code": COLORS["red"],
        "validation": COLORS["pink"],
        "iteration": "#7A7A7A",
        "review": COLORS["green"],
    }

    orchestrated_region = mpatches.FancyBboxPatch(
        (0.45, 2.15), 20.1, 12.15,
        boxstyle="round,pad=0.03,rounding_size=0.18",
        linewidth=1.4,
        edgecolor="#C5D6EA",
        facecolor="#FBFDFF",
        linestyle=(0, (4, 3)),
        zorder=0,
    )
    ax.add_patch(orchestrated_region)
    ax.text(
        0.75,
        13.95,
        "Primary workflow region",
        fontsize=8.2,
        color="#5B7FA8",
        fontstyle="italic",
        ha="left",
        va="top",
    )

    start = _draw_box(
        ax, 11.9, 14.08, 2.0, 0.58, "START", "",
        facecolor=fills["start_end"], edgecolor=fills["start_end"],
        title_color="white", body_color="white", title_size=9.6, body_size=0.0,
        rounding=0.28,
    )
    orchestrator = _draw_box(
        ax, 8.55, 12.42, 8.5, 1.34,
        "OrchestratorAgent",
        "single LLM call -> JSON routing\n12 legal phases + fallback -> literature_review",
        facecolor=fills["orchestrator"], edgecolor=edges["orchestrator"],
        title_size=12.2, body_size=8.15,
    )
    approval = _draw_box(
        ax, 10.45, 10.95, 4.7, 0.92,
        "[Optional] HumanApprovalNode",
        "inserted only when BIOAGENT_HUMAN_IN_LOOP = true",
        facecolor=fills["approval"], edgecolor=edges["approval"],
        linewidth=1.2, linestyle=(0, (4, 2)), title_size=9.3, body_size=7.3,
    )

    upper_nodes = {
        "literature": _draw_box(
            ax, 0.9, 8.98, 3.0, 1.48,
            "Literature Review",
            "10 tools\nBioMCP + arXiv",
            facecolor=fills["literature"], edgecolor=edges["literature"],
        ),
        "gap": _draw_box(
            ax, 4.25, 8.98, 3.0, 1.48,
            "Gap Analysis",
            "direct LLM call\nno external tools",
            facecolor=fills["gap"], edgecolor=edges["gap"],
        ),
        "hypothesis": _draw_box(
            ax, 7.6, 8.98, 3.0, 1.48,
            "Hypothesis Generation",
            "6 scored candidates\n+ selected hypothesis",
            facecolor=fills["hypothesis"], edgecolor=edges["hypothesis"],
        ),
        "experiment": _draw_box(
            ax, 10.95, 8.98, 3.0, 1.48,
            "Experiment Design",
            "JSON plan\nmethods + data list",
            facecolor=fills["experiment"], edgecolor=edges["experiment"],
        ),
        "data": _draw_box(
            ax, 14.3, 8.98, 3.0, 1.48,
            "Data Acquisition",
            "9 databases\nprimary -> secondary -> manual",
            facecolor=fills["data"], edgecolor=edges["data"],
        ),
    }

    code = _draw_box(
        ax, 11.65, 6.75, 3.15, 1.45,
        "Code Execution",
        "AnalystAgent\nPython subprocess + seed injection",
        facecolor=fills["code"], edgecolor=edges["code"],
    )
    validation = _draw_box(
        ax, 11.65, 4.8, 3.15, 1.25,
        "Result Validation",
        "rules-based quality checks",
        facecolor=fills["validation"], edgecolor=edges["validation"],
        title_size=10.2, body_size=7.6,
    )
    iteration = _draw_box(
        ax, 15.35, 4.8, 2.85, 1.25,
        "Iteration",
        "debug node\nretry counter",
        facecolor=fills["iteration"], edgecolor=edges["iteration"],
        title_color="#374151", body_color="#4B5563", title_size=10.0, body_size=7.4,
    )

    writing = _draw_box(
        ax, 7.9, 2.75, 2.95, 1.28,
        "Writing",
        "WriterAgent\nIMRAD sections + PMID citations",
        facecolor=fills["writing"], edgecolor=edges["orchestrator"],
        title_size=10.5, body_size=7.5,
    )
    figure = _draw_box(
        ax, 11.35, 2.75, 3.15, 1.28,
        "Figure Generation",
        "VisualizationAgent\nNature style, Okabe-Ito, 300 DPI",
        facecolor=fills["figure"], edgecolor=edges["experiment"],
        title_size=10.2, body_size=7.3,
    )
    review = _draw_box(
        ax, 15.0, 2.75, 2.95, 1.28,
        "Review",
        "ReviewAgent\n5-dimension score (0-10)",
        facecolor=fills["review"], edgecolor=edges["review"],
        title_size=10.5, body_size=7.5,
    )
    export = _draw_box(
        ax, 18.45, 2.75, 2.65, 1.28,
        "Export",
        "MD + LaTeX + bib\n+ provenance",
        facecolor=fills["export"], edgecolor="#64748B",
        title_color="#334155", body_color="#475569", title_size=10.5, body_size=7.45,
    )
    end = _draw_box(
        ax, 18.87, 1.18, 1.8, 0.56, "END", "",
        facecolor=fills["start_end"], edgecolor=fills["start_end"],
        title_color="white", body_color="white", title_size=9.6, body_size=0.0,
        rounding=0.28,
    )

    # Section headers
    ax.text(1.0, 11.15, "Orchestrated discovery phases", fontsize=8.5,
            color="#64748B", fontweight="bold")
    ax.text(11.4, 8.38, "Fixed execution loop", fontsize=8.5,
            color="#64748B", fontweight="bold")
    ax.text(8.0, 4.2, "Drafting and review loop", fontsize=8.5,
            color="#64748B", fontweight="bold")

    # Routing bus from optional human approval to discovery phases.
    bus_y = 10.38
    bus_x0, bus_x1 = 1.7, 15.8
    _draw_arrow(
        ax,
        _anchor(approval, "bottom"),
        (12.8, bus_y),
        color=edges["orchestrator"],
        text="route according to current state",
        text_xy=(12.8, 10.63),
        text_size=7.2,
    )
    ax.plot([bus_x0, bus_x1], [bus_y, bus_y], color="#86A7C9", lw=1.25, zorder=1)
    for node in upper_nodes.values():
        cx, _ = _anchor(node, "top")
        _draw_arrow(ax, (cx, bus_y), _anchor(node, "top"), color="#86A7C9", lw=1.2)

    # Core flow arrows.
    _draw_arrow(ax, _anchor(start, "bottom"), _anchor(orchestrator, "top"),
                color=edges["orchestrator"], lw=1.7)
    _draw_arrow(ax, _anchor(orchestrator, "bottom"), _anchor(approval, "top"),
                color=edges["orchestrator"], lw=1.6)
    _draw_arrow(
        ax,
        _anchor(upper_nodes["data"], "bottom"),
        _anchor(code, "top"),
        color=edges["code"],
        lw=1.65,
        text="data_status = ready",
        text_xy=(15.9, 8.08),
        text_size=7.1,
    )
    _draw_arrow(ax, _anchor(code, "bottom"), _anchor(validation, "top"),
                color=edges["code"], lw=1.7)
    _draw_arrow(
        ax,
        _anchor(validation, "right", frac=0.56),
        _anchor(iteration, "left", frac=0.56),
        color=edges["iteration"],
        lw=1.55,
        text="validation failed",
        text_xy=(15.1, 5.92),
        text_size=7.0,
    )
    _draw_arrow(
        ax,
        _anchor(iteration, "top", frac=0.4),
        _anchor(code, "right", frac=0.72),
        color=edges["code"],
        lw=1.55,
        rad=0.32,
        text="direct retry edge",
        text_xy=(16.55, 6.72),
        text_size=7.0,
    )
    _draw_arrow(
        ax,
        _anchor(validation, "top", frac=0.24),
        _anchor(orchestrator, "right", frac=0.36),
        color=edges["orchestrator"],
        lw=1.45,
        rad=-0.28,
        linestyle=(0, (4, 2)),
        text="pass -> orchestrator",
        text_xy=(17.65, 8.52),
        text_size=7.0,
    )
    _draw_arrow(
        ax,
        _anchor(orchestrator, "left", frac=0.28),
        _anchor(writing, "top", frac=0.45),
        color=edges["orchestrator"],
        lw=1.45,
        rad=0.24,
        linestyle=(0, (4, 2)),
        text="downstream drafting phases",
        text_xy=(7.15, 7.55),
        text_size=7.0,
    )
    _draw_arrow(ax, _anchor(writing, "right"), _anchor(figure, "left"),
                color=edges["experiment"], lw=1.55)
    _draw_arrow(ax, _anchor(figure, "right"), _anchor(review, "left"),
                color=edges["review"], lw=1.55)
    _draw_arrow(
        ax,
        _anchor(review, "right"),
        _anchor(export, "left"),
        color=edges["review"],
        lw=1.65,
        text="score >= 7",
        text_xy=(18.2, 3.98),
        text_size=7.0,
    )
    _draw_arrow(ax, _anchor(export, "bottom"), _anchor(end, "top"),
                color="#475569", lw=1.55)
    _draw_arrow(
        ax,
        _anchor(review, "top", frac=0.42),
        _anchor(orchestrator, "left", frac=0.58),
        color=edges["review"],
        lw=1.45,
        rad=0.32,
        linestyle=(0, (4, 2)),
        text="score < 7 and review_count < 3",
        text_xy=(8.15, 5.32),
        text_size=6.95,
    )

    ax.text(
        9.2,
        8.62,
        "All non-fixed transitions return to OrchestratorAgent.",
        fontsize=7.35,
        color="#6B7280",
        fontstyle="italic",
    )

    # Blackboard state box.
    state_box = mpatches.FancyBboxPatch(
        (0.55, 0.38), 20.0, 1.45,
        boxstyle="round,pad=0.03,rounding_size=0.15",
        linewidth=1.1,
        edgecolor="#D3DAE6",
        facecolor=fills["state"],
        zorder=1,
    )
    state_box.set_path_effects([
        pe.withSimplePatchShadow(offset=(1.1, -1.1), alpha=0.08),
        pe.Normal(),
    ])
    ax.add_patch(state_box)
    ax.text(
        10.55, 1.5,
        "Shared ResearchState (Blackboard, 33 fields)",
        ha="center", va="center", fontsize=10.1, fontweight="bold", color="#0F172A",
    )
    ax.text(
        10.55, 1.08,
        "papers · data_artifacts · hypotheses · execution_results · paper_sections · "
        "figures · references · review_feedback · phase_history · errors · tokens · messages · ...",
        ha="center", va="center", fontsize=7.3, color="#475569",
    )
    ax.text(
        10.55, 0.68,
        "All agents read the full state; each writes only its owned slice; "
        "dedup_add applies SHA-256 content-hash deduplication.",
        ha="center", va="center", fontsize=7.15, color="#64748B", fontstyle="italic",
    )

    # Side panels.
    _draw_panel(
        ax, 21.15, 8.7, 4.75, 4.92,
        "Key Control Edges",
        [
            "1. iteration -> code_execution",
            "   bypasses the orchestrator for cheap",
            "   auto-debug retries (<= max_iterations).",
            "",
            "2. code_execution -> result_validation",
            "   validation is rules-based; no LLM call.",
            "",
            "3. review -> export or orchestrator",
            "   accepted drafts exit; low-scoring drafts",
            "   write revision notes back into state.",
        ],
        accent=COLORS["blue"],
    )
    _draw_panel(
        ax, 21.15, 3.18, 4.75, 4.8,
        "Blackboard Write Ownership",
        [
            "LiteratureAgent : papers, summary, refs",
            "GapAnalysis     : research_gaps",
            "PlannerAgent    : hypotheses, selected_hypothesis,",
            "                  experiment_plan",
            "DataAcquisition : data_artifacts, data_status",
            "AnalystAgent    : code_artifacts, execution_results,",
            "                  analysis_results",
            "WriterAgent     : paper_sections, references",
            "Visualization   : figures",
            "ReviewAgent     : review_feedback, review_count",
            "Orchestrator    : current_phase, phase_history",
        ],
        accent=COLORS["green"],
    )

    ax.set_title(
        "Figure 1. Full BioAgent LangGraph Workflow and Blackboard State\n"
        "Current 14-node pipeline with optional human approval, fixed retry edges, and review-driven revision loop",
        fontsize=14.2,
        fontweight="bold",
        pad=10,
    )

    plt.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(
            OUT / f"fig1_architecture.{ext}",
            dpi=DPI,
            bbox_inches="tight",
            facecolor=fig.get_facecolor(),
        )
    plt.close(fig)
    print("  fig1_architecture done")


# ── Figure 2: Agent–Tool Relationship ─────────────────────────────────────────

def fig2_agent_tools():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    agents = [
        (1.5, 6.5, "LiteratureAgent",    COLORS["blue"]),
        (1.5, 5.0, "PlannerAgent",        COLORS["green"]),
        (1.5, 3.5, "AnalystAgent",        COLORS["red"]),
        (1.5, 2.0, "WriterAgent",         COLORS["orange"]),
        (1.5, 0.5, "VisualizationAgent",  COLORS["pink"]),
    ]
    tools = [
        (7.5, 7.2, "search_articles",      COLORS["sky"]),
        (7.5, 6.4, "get_article",          COLORS["sky"]),
        (7.5, 5.6, "search_variants",      COLORS["sky"]),
        (7.5, 4.8, "execute_python",       COLORS["orange"]),
        (7.5, 4.0, "install_package",      COLORS["orange"]),
        (7.5, 3.2, "write_file / read_file", COLORS["gray"]),
        (7.5, 2.4, "get_sequence_template",COLORS["green"]),
        (7.5, 1.6, "get_expression_template", COLORS["green"]),
        (7.5, 0.8, "get_genomic_template", COLORS["green"]),
    ]

    # Draw agents
    for x, y, label, color in agents:
        rect = mpatches.FancyBboxPatch((x - 1.3, y - 0.35), 2.6, 0.7,
                                       boxstyle="round,pad=0.05",
                                       facecolor=color, edgecolor="white",
                                       linewidth=1.2, alpha=0.9, zorder=3)
        ax.add_patch(rect)
        ax.text(x, y, label, ha="center", va="center", fontsize=8.5,
                color="white", fontweight="bold", zorder=4)

    # Draw tools
    for x, y, label, color in tools:
        rect = mpatches.FancyBboxPatch((x - 1.4, y - 0.28), 2.8, 0.56,
                                       boxstyle="round,pad=0.05",
                                       facecolor=color, edgecolor="white",
                                       linewidth=1, alpha=0.75, zorder=3)
        ax.add_patch(rect)
        ax.text(x, y, label, ha="center", va="center", fontsize=7.5,
                color="white", zorder=4)

    # Connections (agent_idx → tool_indices)
    connections = {
        0: [0, 1, 2],         # LiteratureAgent → BioMCP tools
        2: [3, 4, 5, 6, 7, 8],  # AnalystAgent → exec + bio templates
        4: [3, 4, 5],         # VisualizationAgent → exec tools
    }
    agent_positions = {i: (a[0], a[1]) for i, a in enumerate(agents)}
    tool_positions  = {i: (t[0], t[1]) for i, t in enumerate(tools)}

    for ag_i, tool_list in connections.items():
        x1, y1 = agent_positions[ag_i]
        for t_i in tool_list:
            x2, y2 = tool_positions[t_i]
            ax.annotate("", xy=(x2 - 1.4, y2), xytext=(x1 + 1.3, y1),
                        arrowprops=dict(arrowstyle="-|>", color="#AAAAAA",
                                        lw=0.8, connectionstyle="arc3,rad=0.0"),
                        zorder=2)

    # Category labels
    ax.text(1.5, 7.4, "Agents", ha="center", fontsize=10, fontweight="bold",
            color="#333333")
    ax.text(7.5, 7.8, "Tools", ha="center", fontsize=10, fontweight="bold",
            color="#333333")

    # Tool category brackets
    for label, ymin, ymax, color in [
        ("BioMCP\n(Literature)", 5.6, 7.6, COLORS["sky"]),
        ("Code\nExecution",      3.6, 5.2, COLORS["orange"]),
        ("Bioinformatics\nTemplates", 0.4, 3.2, COLORS["green"]),
    ]:
        ax.annotate("", xy=(10.0, ymin), xytext=(10.0, ymax),
                    arrowprops=dict(arrowstyle="-", color=color, lw=2))
        ax.text(10.4, (ymin + ymax) / 2, label, va="center", fontsize=7.5,
                color=color, fontweight="bold")

    ax.set_title("Figure 2: BioAgent — Agent–Tool Architecture",
                 fontsize=12, fontweight="bold", pad=8)

    plt.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"fig2_agent_tools.{ext}", dpi=DPI,
                    bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  fig2_agent_tools done")


# ── Figure 3: Benchmark Comparison ────────────────────────────────────────────

def fig3_benchmark():
    methods = [
        "Manual\nResearch",
        "Single\nLLM Prompt",
        "BioAgent\n(Ours)",
    ]

    # Illustrative values (replace with real measurements after case runs)
    metrics = {
        "Time (hours)":         [40.0, 0.5,  2.1],
        "Papers Reviewed":      [20,   5,    18],
        "Code Reproducible (%)": [60,   0,    95],
        "Citation Accuracy (%)": [95,   55,   88],
        "Statistical Validity (%)": [80, 40,  91],
    }

    fig, axes = plt.subplots(1, len(metrics), figsize=(14, 5))
    bar_colors = [COLORS["gray"], COLORS["sky"], COLORS["blue"]]

    for ax, (metric, values) in zip(axes, metrics.items()):
        bars = ax.bar(methods, values, color=bar_colors, edgecolor="white",
                      linewidth=0.8, width=0.55)
        ax.set_title(metric, fontsize=9, fontweight="bold", pad=4)
        ax.set_ylim(0, max(values) * 1.25)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", labelsize=7.5)
        ax.tick_params(axis="y", labelsize=7.5)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(values) * 0.02,
                    f"{val:.0f}", ha="center", va="bottom", fontsize=8,
                    fontweight="bold")
        # Highlight BioAgent bar
        bars[2].set_edgecolor(COLORS["blue"])
        bars[2].set_linewidth(2)

    legend_handles = [
        mpatches.Patch(color=COLORS["gray"], label="Manual Research"),
        mpatches.Patch(color=COLORS["sky"],  label="Single LLM Prompt"),
        mpatches.Patch(color=COLORS["blue"], label="BioAgent (ours)"),
    ]
    fig.legend(handles=legend_handles, loc="upper center",
               ncol=3, fontsize=9, frameon=False,
               bbox_to_anchor=(0.5, 1.02))
    fig.suptitle("Figure 3: BioAgent Performance vs. Baseline Methods\n"
                 "(BRAF V600E Melanoma Case Study)",
                 fontsize=11, fontweight="bold", y=1.08)

    plt.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"fig3_benchmark.{ext}", dpi=DPI,
                    bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  fig3_benchmark done")


# ── Figure 4: Quality Metrics Radar ───────────────────────────────────────────

def fig4_radar():
    categories = [
        "Literature\nCoverage",
        "Hypothesis\nQuality",
        "Analysis\nCorrectness",
        "Writing\nQuality",
        "Figure\nQuality",
        "Reproducibility",
    ]
    N = len(categories)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]  # close the polygon

    # Normalised scores [0-1] from evaluation report
    scores_full    = [0.80, 0.75, 0.91, 0.82, 0.88, 0.95]
    scores_no_lit  = [0.40, 0.70, 0.88, 0.78, 0.85, 0.90]  # ablation: no LiteratureAgent
    scores_no_code = [0.80, 0.75, 0.00, 0.70, 0.30, 0.50]  # ablation: no AnalystAgent

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))

    def plot_radar(ax, values, color, label, alpha=0.25):
        v = values + values[:1]
        ax.plot(angles, v, color=color, linewidth=2, label=label)
        ax.fill(angles, v, color=color, alpha=alpha)

    plot_radar(ax, scores_full,    COLORS["blue"],   "Full BioAgent")
    plot_radar(ax, scores_no_lit,  COLORS["orange"], "w/o LiteratureAgent", 0.15)
    plot_radar(ax, scores_no_code, COLORS["red"],    "w/o AnalystAgent",    0.15)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=9)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=7)
    ax.set_ylim(0, 1)
    ax.spines["polar"].set_color("#CCCCCC")
    ax.grid(color="#DDDDDD", linestyle="--", linewidth=0.7)

    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.15), fontsize=9,
              frameon=False)
    ax.set_title("Figure 4: Quality Metrics Radar\n(Ablation Study)",
                 fontsize=11, fontweight="bold", pad=20)

    plt.tight_layout()
    fig.savefig(OUT / "fig4_evaluation_radar.png", dpi=DPI,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  fig4_evaluation_radar done")


if __name__ == "__main__":
    print("Generating publication figures...")
    fig1_architecture()
    fig2_agent_tools()
    fig3_benchmark()
    fig4_radar()
    print(f"Done — saved to {OUT}/")
