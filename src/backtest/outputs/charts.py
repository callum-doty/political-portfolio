"""
Chart generation.

Primary deliverable: risk-return frontier chart (Section 7.3).
  - DCCC observed allocation (point)
  - Model optimizer at each γ (curve)
  - Cook-rating-implied allocation (reference point)
  - Null equal-weight allocation (reference point)

Also: MSG rank chart and allocation difference scatter.
"""

from __future__ import annotations
import logging
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from ..types import RaceRecord, ModelOutputs
from .. import config

logger = logging.getLogger(__name__)
sns.set_theme(style="whitegrid", context="paper", font_scale=1.1)

_COLORS = {
    "dccc":    "#1f4e9c",
    "model":   "#d62728",
    "cook":    "#2ca02c",
    "null":    "#9467bd",
    "scatter": "#7f7f7f",
}


def efficiency_frontier(
    dccc_point: tuple[float, float],
    model_points: list[tuple[float, float, str]],
    cook_point: tuple[float, float] | None = None,
    null_point: tuple[float, float] | None = None,
    save_path: Path | None = None,
    cycle: int = 2024,
) -> plt.Figure:
    """
    Plot E[Seats] vs SD[Seats] for all allocators.

    Parameters
    ----------
    dccc_point    : (expected_seats, sd_seats) for observed DCCC allocation
    model_points  : list of (expected_seats, sd_seats, label) for model at each γ
    cook_point    : (expected_seats, sd_seats) or None
    null_point    : (expected_seats, sd_seats) or None
    save_path     : write PNG if provided
    cycle         : election cycle shown in the title (defaults to 2024;
                    pass the actual --cycle for OOS runs like 2022)
    """
    fig, ax = plt.subplots(figsize=(8, 6))

    # Model curve
    if model_points:
        xs = [p[1] for p in model_points]
        ys = [p[0] for p in model_points]
        ax.plot(xs, ys, "-o", color=_COLORS["model"], lw=2, label="Model optimizer (γ frontier)")
        for es, sd, lbl in model_points:
            ax.annotate(lbl, xy=(sd, es), xytext=(4, 2), textcoords="offset points",
                        fontsize=8, color=_COLORS["model"])

    # Reference points
    ax.scatter(*dccc_point[::-1], color=_COLORS["dccc"], s=120, zorder=5,
               label="DCCC observed")
    ax.annotate("DCCC", xy=(dccc_point[1], dccc_point[0]),
                xytext=(4, -8), textcoords="offset points", fontsize=9)

    if cook_point:
        ax.scatter(*cook_point[::-1], color=_COLORS["cook"], s=100, marker="^", zorder=5,
                   label="Cook-implied")
    if null_point:
        ax.scatter(*null_point[::-1], color=_COLORS["null"], s=100, marker="s", zorder=5,
                   label="Null (equal-weight)")

    ax.set_xlabel("SD[Seats]")
    ax.set_ylabel("E[Seats]")
    ax.set_title(f"Risk-Return Frontier: Democratic House Spending Allocations ({cycle})")
    ax.legend(loc="lower right", framealpha=0.9)

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        logger.info(f"Efficiency frontier chart saved to {save_path}")
    return fig


def allocation_difference_scatter(
    race_ids: list[str],
    pvi_vals: list[float],
    differences: list[float],
    cook_ratings: list[str],
    save_path: Path | None = None,
) -> plt.Figure:
    """
    Scatter of allocation difference (model − DCCC) vs PVI.
    Dot color encodes Cook rating. Horizontal dashed line at 0.
    """
    fig, ax = plt.subplots(figsize=(10, 5))

    rating_colors = {
        "Safe D": "#0b5394", "Likely D": "#3d85c8", "Lean D": "#6fa8dc",
        "Toss-Up": "#f6b26b",
        "Lean R":  "#e06666", "Likely R": "#cc0000", "Safe R": "#660000",
    }

    for pid, pvi, diff, rating in zip(race_ids, pvi_vals, differences, cook_ratings):
        color = rating_colors.get(rating, _COLORS["scatter"])
        ax.scatter(pvi, diff * 100, color=color, alpha=0.7, s=40, zorder=3)

    ax.axhline(0, color="black", lw=0.8, ls="--")
    ax.set_xlabel("Cook PVI (D-positive)")
    ax.set_ylabel("Allocation difference (pp of budget)")
    ax.set_title("Model vs DCCC Allocation Difference by District PVI")

    patches = [mpatches.Patch(color=c, label=r) for r, c in rating_colors.items()]
    ax.legend(handles=patches, loc="upper right", fontsize=8, ncol=2)

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        logger.info(f"Allocation scatter saved to {save_path}")
    return fig
