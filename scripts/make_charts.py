#!/usr/bin/env python3
"""Generate three portfolio visualization PNGs."""

from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import seaborn as sns

sns.set_theme(style="whitegrid", context="paper", font_scale=1.15)
plt.rcParams.update({
    "font.family": "sans-serif",
    "axes.spines.top": False,
    "axes.spines.right": False,
})

OUT = Path("/Users/callumdoty/Desktop/Political Portfolio/outputs")

RATING_ORDER = ["Safe D", "Likely D", "Lean D", "Toss-Up", "Lean R", "Likely R", "Safe R"]
RATING_COLORS = {
    "Safe D":    "#1a4480",
    "Likely D":  "#2e75b6",
    "Lean D":    "#9dc3e6",
    "Toss-Up":   "#f4b942",
    "Lean R":    "#f4a08c",
    "Likely R":  "#c00000",
    "Safe R":    "#6b0000",
}

df = pd.read_csv(OUT / "race_table_baseline.csv")
agg = pd.read_csv(OUT / "aggregate_summary_baseline.csv")
BUDGET = agg["total_budget"].iloc[0]


# ─────────────────────────────────────────────────────────────────────────────
# Chart 1 — Allocation difference vs PVI
# ─────────────────────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(13, 6.5))

# Background PVI bands
band_edges = [(-30, -15), (-15, -7), (-7, -2), (-2, 2), (2, 7), (7, 15), (15, 35)]
band_colors = ["#6b0000", "#c00000", "#f4a08c", "#f4b942", "#9dc3e6", "#2e75b6", "#1a4480"]
for (lo, hi), bc in zip(band_edges, band_colors):
    ax.axvspan(lo, hi, alpha=0.06, color=bc, lw=0)

ax.axhline(0, color="#333333", lw=0.9, ls="--", alpha=0.8, zorder=2)

safe_ratings = {"Safe D", "Safe R"}
for rating in RATING_ORDER:
    sub = df[df["cook_rating"] == rating]
    color = RATING_COLORS[rating]
    is_safe = rating in safe_ratings
    alpha = 0.30 if is_safe else 0.80
    size = 20 if is_safe else 50
    ax.scatter(
        sub["pvi"], sub["difference"] * 100,
        color=color, alpha=alpha, s=size, zorder=4,
        linewidths=0.5, edgecolors="none",
    )

# Label the two outliers (NC-13 and CT-02 with huge positive differences)
outliers = df[df["difference"] * 100 > 5].sort_values("difference", ascending=False)
for _, row in outliers.head(5).iterrows():
    ax.annotate(
        row["district_id"],
        xy=(row["pvi"], row["difference"] * 100),
        xytext=(5, 2), textcoords="offset points",
        fontsize=7.5, color="#333333", fontstyle="italic",
        arrowprops=dict(arrowstyle="-", color="#888888", lw=0.5),
    )

ax.set_xlabel("Cook PVI  (D+ → more Democratic district)", fontsize=11)
ax.set_ylabel("Allocation difference  (pp of total budget)", fontsize=11)
ax.set_title(
    "Allocation Difference vs PVI: Where Model and DCCC Diverge",
    fontsize=13, fontweight="bold", pad=12,
)

ax.text(
    0.012, 0.97, "↑ Above zero: model recommends more than DCCC spent",
    transform=ax.transAxes, fontsize=8.5, color="#1a6630", va="top", alpha=0.9,
)
ax.text(
    0.012, 0.04, "↓ Below zero: DCCC overspent vs model",
    transform=ax.transAxes, fontsize=8.5, color="#8b1a1a", va="bottom", alpha=0.9,
)

legend_patches = [
    mpatches.Patch(color=RATING_COLORS[r], label=r, alpha=0.85)
    for r in RATING_ORDER
]
ax.legend(
    handles=legend_patches, title="Cook Rating",
    loc="upper right", fontsize=8.5, ncol=2,
    framealpha=0.92, edgecolor="#cccccc",
)

x_range = df["pvi"].agg(["min", "max"])
ax.set_xlim(x_range["min"] - 1, x_range["max"] + 1)
ax.tick_params(axis="both", labelsize=9)

fig.tight_layout()
fig.savefig(OUT / "alloc_diff_pvi.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("✓ Chart 1: alloc_diff_pvi.png")


# ─────────────────────────────────────────────────────────────────────────────
# Chart 2 — MSG rank vs DCCC Spend rank
# ─────────────────────────────────────────────────────────────────────────────

FOCUS_RATINGS = ["Toss-Up", "Lean D", "Lean R"]
FOCUS_COLORS = {"Toss-Up": "#f4b942", "Lean D": "#2e75b6", "Lean R": "#c00000"}

focus = df[df["cook_rating"].isin(FOCUS_RATINGS)].copy()
focus["msg_rank"] = focus["msg_i_per_1m"].rank(ascending=False, method="first").astype(int)
focus["spend_rank"] = focus["observed_share"].rank(ascending=False, method="first").astype(int)
n = len(focus)

fig, ax = plt.subplots(figsize=(8, 8))

# Quadrant shading
ax.fill_between([1, n / 2], [n / 2, n / 2], [n + 0.5, n + 0.5],
                alpha=0.055, color="#c00000")   # high MSG, low spend → under-targeted
ax.fill_between([n / 2, n + 0.5], [0.5, 0.5], [n / 2, n / 2],
                alpha=0.055, color="#1a4480")   # low MSG, high spend → over-targeted

# Diagonal
ax.plot([0.5, n + 0.5], [0.5, n + 0.5], color="#555555", lw=1.1, ls="--",
        alpha=0.65, label="Perfect alignment", zorder=2)

# Points
for _, row in focus.iterrows():
    color = FOCUS_COLORS[row["cook_rating"]]
    d_win = row["outcome"] == "D"
    ax.scatter(
        row["msg_rank"], row["spend_rank"],
        s=90, marker="o",
        facecolors=color if d_win else "white",
        edgecolors=color, linewidths=1.8,
        alpha=0.88, zorder=5,
    )

# Labels for notable misalignments (rank difference > 20)
for _, row in focus.iterrows():
    rdiff = abs(row["msg_rank"] - row["spend_rank"])
    if rdiff >= 22:
        ax.annotate(
            row["district_id"],
            xy=(row["msg_rank"], row["spend_rank"]),
            xytext=(5, 3), textcoords="offset points",
            fontsize=6.5, color="#333333", alpha=0.9,
        )

ax.set_xlim(0.5, n + 0.5)
ax.set_ylim(0.5, n + 0.5)
ax.set_xlabel("MSG rank  (1 = highest return per $)", fontsize=11)
ax.set_ylabel("DCCC spending rank  (1 = most spent)", fontsize=11)
ax.set_title(
    "MSG vs DCCC Spending Rank: Targeted Competitive Races",
    fontsize=13, fontweight="bold", pad=12,
)

# Quadrant labels
ax.text(1.5, n - 1, "Under-targeted\nhigh-MSG", fontsize=7.5, color="#8b1a1a",
        alpha=0.7, va="top")
ax.text(n - 1, 2.5, "Over-targeted\nlow-MSG", fontsize=7.5, color="#1a4480",
        alpha=0.7, va="top", ha="right")

legend_elements = [
    mpatches.Patch(color=FOCUS_COLORS[r], label=r, alpha=0.85)
    for r in FOCUS_RATINGS
] + [
    Line2D([0], [0], marker="o", color="w", label="● D win",
           markerfacecolor="#777777", markeredgecolor="#777777", markersize=9),
    Line2D([0], [0], marker="o", color="w", label="○ R win",
           markerfacecolor="white", markeredgecolor="#777777",
           markersize=9, markeredgewidth=1.8),
    Line2D([0], [0], color="#555555", ls="--", label="Diagonal = perfect alignment"),
]
ax.legend(handles=legend_elements, loc="upper left", fontsize=8.5,
          framealpha=0.92, edgecolor="#cccccc")

ax.tick_params(axis="both", labelsize=9)
fig.tight_layout()
fig.savefig(OUT / "msg_vs_spend_rank.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("✓ Chart 2: msg_vs_spend_rank.png")


# ─────────────────────────────────────────────────────────────────────────────
# Chart 3 — Efficiency Frontier
#
# Strategy: fix safe district p_win at observed (their MSG ≈ 0, so spending
# there barely changes outcomes); only vary competitive district allocations
# using the linearized model.  This avoids log(ratio)→−∞ extrapolation.
# ─────────────────────────────────────────────────────────────────────────────

obs_shares = df["observed_share"].values
rec_shares = df["recommended_share"].values
p0         = df["p_win"].values
msg_per_dollar = df["msg_i_per_1m"].values / 1e6  # seats per dollar

safe_mask = df["cook_rating"].isin(["Safe D", "Safe R"]).values
comp_mask = ~safe_mask
n_comp    = int(comp_mask.sum())

# Safe district baseline (fixed across all strategies)
p_safe = p0[safe_mask]
safe_e  = float(p_safe.sum())
safe_sd_sq = float((p_safe * (1 - p_safe)).sum())

# Total budget allocated to safe vs competitive under DCCC
safe_budget_dccc = float(obs_shares[safe_mask].sum())   # share of B
comp_budget_total = 1.0 - safe_budget_dccc              # the rest goes to competitive


def _comp_point(comp_shares: np.ndarray) -> tuple[float, float]:
    """
    Given a share vector for competitive races (len = n_comp, sum ≤ 1),
    return (E[Seats_total], SD[Seats_total]) using linearised model + safe
    baseline.  comp_shares should be a fraction of TOTAL budget B.
    """
    delta_d = (comp_shares - obs_shares[comp_mask]) * BUDGET
    p_comp = np.clip(p0[comp_mask] + msg_per_dollar[comp_mask] * delta_d, 0.0, 1.0)
    e  = safe_e + float(p_comp.sum())
    sd = float(np.sqrt(safe_sd_sq + float((p_comp * (1 - p_comp)).sum())))
    return e, sd


# Baseline strategies as share-of-B vectors for competitive districts
obs_comp  = obs_shares[comp_mask]
rec_comp  = rec_shares[comp_mask]

# Null: redistribute ALL safe budget equally across competitive
null_comp = obs_comp + safe_budget_dccc / n_comp

# Cook: redistribute ALL safe budget proportionally by cook weight
cook_wt_comp = df.loc[comp_mask, "cook_rating"].map(
    {"Toss-Up": 4, "Lean D": 3, "Lean R": 3, "Likely D": 2, "Likely R": 2}
).fillna(0).values.astype(float)
cook_wt_comp = cook_wt_comp / cook_wt_comp.sum() if cook_wt_comp.sum() > 0 else np.ones(n_comp) / n_comp
cook_comp = obs_comp + safe_budget_dccc * cook_wt_comp

dccc_e,  dccc_sd  = _comp_point(obs_comp)
null_e,  null_sd  = _comp_point(null_comp)
cook_e,  cook_sd  = _comp_point(cook_comp)
model_e, model_sd = _comp_point(rec_comp)

# Path 1: DCCC → Null  (gradually move safe budget into competitive equally)
# Path 2: Null → Model (re-concentrate within competitive toward MSG)
path_e_all, path_sd_all, path_cols = [], [], []
_path_defs = [
    (obs_comp,  null_comp, 70, "#9467bd", "DCCC → Null  (redeploy safe-race budget)"),
    (null_comp, rec_comp,  70, "#d62728", "Null → Model  (target by MSG within competitive)"),
]
for start, end, n_pts, col, _ in _path_defs:
    for t in np.linspace(0.0, 1.0, n_pts):
        s = (1 - t) * start + t * end
        e, sd = _comp_point(s)
        path_e_all.append(e)
        path_sd_all.append(sd)
        path_cols.append(col)

# ── Plot ──────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9.5, 6.5))

idx = 0
for (_, _, n_pts, col, lbl) in _path_defs:
    sds = path_sd_all[idx: idx + n_pts]
    es  = path_e_all[idx: idx + n_pts]
    ax.plot(sds, es, "-", color=col, lw=2.2, alpha=0.75, label=lbl)
    idx += n_pts

# Reference points
_pts = [
    (dccc_sd,  dccc_e,  "#1f4e9c", "o", 180, "DCCC observed",      (8, -14)),
    (null_sd,  null_e,  "#8b5cf6", "s", 130, "Null (equal-weight)", (8,   5)),
    (cook_sd,  cook_e,  "#059669", "^", 130, "Cook-implied",        (8,   5)),
    (model_sd, model_e, "#d62728", "*", 240, "Model (γ=0)",         (8,   5)),
]
for sd, e, col, mk, sz, lbl, off in _pts:
    ax.scatter(sd, e, s=sz, color=col, marker=mk, zorder=7,
               edgecolors="white", linewidths=0.8)
    ax.annotate(lbl, xy=(sd, e), xytext=off, textcoords="offset points",
                fontsize=8.5, color=col, fontweight="semibold")

ax.set_xlabel("SD[Seats]  (binomial independence approximation)", fontsize=11)
ax.set_ylabel("E[Seats]  (linearized model expectation)", fontsize=11)
ax.set_title(
    "Efficiency Frontier: Democratic House Seat Expectations (2024)",
    fontsize=13, fontweight="bold", pad=12,
)

legend_lines = [
    Line2D([0], [0], color=col, lw=2.2, label=lbl)
    for (_, _, _, col, lbl) in _path_defs
]
ax.legend(handles=legend_lines, loc="lower right", fontsize=8.5,
          framealpha=0.92, edgecolor="#cccccc", handlelength=1.8)

ax.text(
    0.02, 0.02,
    "E[Seats] = linearized model expectation at each allocation  ·  SD = binomial independence approximation",
    transform=ax.transAxes, fontsize=7.5, color="#777777", style="italic",
)

ax.tick_params(axis="both", labelsize=9)
fig.tight_layout()
fig.savefig(OUT / "efficiency_frontier_v2.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("✓ Chart 3: efficiency_frontier_v2.png")
