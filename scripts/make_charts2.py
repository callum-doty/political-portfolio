#!/usr/bin/env python3
"""Majority-probability frontier and calibration curve."""

from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.stats import norm as scipy_norm
import seaborn as sns

sns.set_theme(style="whitegrid", context="paper", font_scale=1.15)
plt.rcParams.update({
    "font.family": "sans-serif",
    "axes.spines.top": False,
    "axes.spines.right": False,
})

OUT = Path("/Users/callumdoty/Desktop/Political Portfolio/outputs")

df   = pd.read_csv(OUT / "race_table_baseline.csv")
agg  = pd.read_csv(OUT / "aggregate_summary_baseline.csv")
BUDGET = agg["total_budget"].iloc[0]
T = 218  # majority threshold

p0             = df["p_win"].values
msg_per_dollar = df["msg_i_per_1m"].values / 1e6  # seats per dollar
obs_shares     = df["observed_share"].values
rec_shares     = df["recommended_share"].values

safe_mask = df["cook_rating"].isin(["Safe D", "Safe R"]).values
comp_mask = ~safe_mask
n_comp    = int(comp_mask.sum())

p_safe         = p0[safe_mask]
safe_e         = float(p_safe.sum())
safe_sd_sq     = float((p_safe * (1 - p_safe)).sum())
safe_budget_share = float(obs_shares[safe_mask].sum())   # fraction of B


def _comp_point(comp_shares: np.ndarray) -> tuple[float, float]:
    delta_d = (comp_shares - obs_shares[comp_mask]) * BUDGET
    p_comp  = np.clip(p0[comp_mask] + msg_per_dollar[comp_mask] * delta_d, 0.0, 1.0)
    e  = safe_e + float(p_comp.sum())
    sd = float(np.sqrt(safe_sd_sq + float((p_comp * (1 - p_comp)).sum())))
    return e, sd


obs_comp  = obs_shares[comp_mask]
rec_comp  = rec_shares[comp_mask]
null_comp = obs_comp + safe_budget_share / n_comp

cook_wt = df.loc[comp_mask, "cook_rating"].map(
    {"Toss-Up": 4, "Lean D": 3, "Lean R": 3, "Likely D": 2, "Likely R": 2}
).fillna(0).values.astype(float)
cook_wt  /= cook_wt.sum()
cook_comp = obs_comp + safe_budget_share * cook_wt

dccc_e,  dccc_sd  = _comp_point(obs_comp)
null_e,  null_sd  = _comp_point(null_comp)
cook_e,  cook_sd  = _comp_point(cook_comp)
model_e, model_sd = _comp_point(rec_comp)

def p_maj(e: float, sd: float) -> float:
    return float(scipy_norm.cdf((e - T) / sd))

print("--- Allocator summary ---")
print(f"  Safe budget share (DCCC): {safe_budget_share:.1%}")
print(f"  DCCC   E={dccc_e:.2f}  SD={dccc_sd:.3f}  P(≥218)={p_maj(dccc_e,dccc_sd):.2%}")
print(f"  Null   E={null_e:.2f}  SD={null_sd:.3f}  P(≥218)={p_maj(null_e,null_sd):.2%}")
print(f"  Cook   E={cook_e:.2f}  SD={cook_sd:.3f}  P(≥218)={p_maj(cook_e,cook_sd):.2%}")
print(f"  Model  E={model_e:.2f}  SD={model_sd:.3f}  P(≥218)={p_maj(model_e,model_sd):.2%}")


# ─────────────────────────────────────────────────────────────────────────────
# Chart 1 — Majority-Probability Frontier
# ─────────────────────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(10.5, 7.5))

e_min, e_max = 204.0, 222.0
sd_lo, sd_hi = 2.70, 3.08

# Iso-probability contours  E = T + Φ⁻¹(P) · SD  (lines through T on E-axis)
sd_range = np.linspace(sd_lo, sd_hi + 0.06, 400)
contours = [
    (0.01, "#dddddd", ":", 0.9),
    (0.05, "#bbbbbb", ":", 1.0),
    (0.10, "#ffaaaa", "--", 0.85),
    (0.20, "#ff7777", "--", 0.95),
    (0.30, "#ff3333", "-",  0.85),
    (0.40, "#cc0000", "-",  0.95),
    (0.50, "#880000", "-",  1.0),
]
for p_lev, col, ls, alpha in contours:
    k = scipy_norm.ppf(p_lev)
    e_c = T + k * sd_range
    vis = (e_c >= e_min) & (e_c <= e_max)
    if vis.any():
        ax.plot(sd_range[vis], e_c[vis], color=col, lw=1.0, ls=ls, alpha=alpha, zorder=2)
        ri = np.where(vis)[0][-1]
        ax.text(sd_range[ri] + 0.006, e_c[ri],
                f"P={p_lev:.0%}", fontsize=7.5, color=col, va="center", alpha=min(alpha + 0.1, 1))

# Majority threshold
ax.axhline(T, color="#333333", lw=1.0, ls="--", alpha=0.5, zorder=3)
ax.text(sd_hi + 0.007, T + 0.25, "218 seats\n(majority)",
        fontsize=7.5, color="#333333", va="bottom")
ax.fill_between([sd_lo, sd_hi + 0.1], T, e_max + 0.5, alpha=0.04, color="#059669", zorder=1)

# Allocator points
pts = [
    ("DCCC observed",       dccc_e,  dccc_sd,  "#1f4e9c", "o", 180, (10, -18)),
    ("Null (equal-weight)", null_e,  null_sd,  "#8b5cf6", "s", 140, (10,   7)),
    ("Cook-implied",        cook_e,  cook_sd,  "#059669", "^", 140, (-92,  7)),
    ("Model (γ=0)",         model_e, model_sd, "#d62728", "*", 240, (10, -18)),
]
for name, e, sd, col, mk, sz, off in pts:
    p = p_maj(e, sd)
    ax.scatter(sd, e, s=sz, color=col, marker=mk, zorder=7,
               edgecolors="white", linewidths=0.8)
    ax.annotate(f"{name}\nE={e:.1f},  P(maj)={p:.1%}",
                xy=(sd, e), xytext=off, textcoords="offset points",
                fontsize=8.2, color=col, fontweight="semibold",
                bbox=dict(boxstyle="round,pad=0.22", fc="white", ec=col, alpha=0.88, lw=0.9))

ax.set_xlabel("SD[Seats]  (binomial independence)", fontsize=11)
ax.set_ylabel("E[Seats]  (linearized model)", fontsize=11)
ax.set_title(
    "Majority-Probability Frontier — 2024 House\n"
    r"P(Seats $\geq$ 218) iso-contours  ·  paper §3.2",
    fontsize=13, fontweight="bold", pad=12,
)
ax.set_xlim(sd_lo, sd_hi + 0.08)
ax.set_ylim(e_min, e_max + 0.5)
ax.tick_params(labelsize=9)

# Contour legend
h = [Line2D([0], [0], color=col, lw=1.1, ls=ls, alpha=alpha,
            label=f"P(majority) = {p:.0%}")
     for p, col, ls, alpha in contours]
ax.legend(handles=h, loc="lower left", fontsize=7.5,
          framealpha=0.93, edgecolor="#cccccc",
          title="Iso-probability contours", title_fontsize=8)

ax.text(0.02, 0.01,
        r"Normal approx: P(Seats $\geq$ 218) $\approx$ $\Phi$((E − 218) / SD)  "
        r"·  iso-contour: E = 218 + $\Phi^{-1}$(P) · SD  ·  paper §3.2",
        transform=ax.transAxes, fontsize=6.8, color="#888888", style="italic")

fig.tight_layout()
fig.savefig(OUT / "majority_prob_frontier.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("✓ Chart 1: majority_prob_frontier.png")


# ─────────────────────────────────────────────────────────────────────────────
# Chart 2 — Calibration Curve (Reliability Diagram)
# ─────────────────────────────────────────────────────────────────────────────

p_win_all  = df["p_win"].values
out_all    = (df["outcome"] == "D").astype(float).values

comp_df    = df[~df["cook_rating"].isin(["Safe D", "Safe R"])]
p_win_comp = comp_df["p_win"].values
out_comp   = (comp_df["outcome"] == "D").astype(float).values


def calib_bins(pw, oc, n_bins):
    edges = np.linspace(0, 1, n_bins + 1)
    pred_m, act_r, ns, lo_ci, hi_ci = [], [], [], [], []
    z = 1.96
    for i in range(n_bins):
        lo, hi = edges[i], edges[i+1]
        mask = (pw >= lo) & (pw <= hi) if i == n_bins - 1 else (pw >= lo) & (pw < hi)
        n = int(mask.sum())
        if n < 1:
            continue
        act  = oc[mask].mean()
        pred = pw[mask].mean()
        c = act + z**2 / (2*n)
        m = z * np.sqrt(act*(1-act)/n + z**2/(4*n**2))
        d = 1 + z**2/n
        pred_m.append(pred);    act_r.append(act);   ns.append(n)
        lo_ci.append((c-m)/d); hi_ci.append((c+m)/d)
    return (np.array(pred_m), np.array(act_r), np.array(ns),
            np.array(lo_ci),  np.array(hi_ci))


fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

panels = [
    (p_win_all,  out_all,  "All 432 districts",
     "#1f4e9c", 10),
    (p_win_comp, out_comp, f"Competitive only  (n={len(comp_df)}, excl. Safe D/R)",
     "#d62728", 7),
]

for ax, (pw, oc, title, col, nb) in zip(axes, panels):
    pred, actual, counts, lo, hi = calib_bins(pw, oc, nb)

    # Perfect calibration line
    ax.plot([0,1], [0,1], "--", color="#888888", lw=1.0, label="Perfect calibration", zorder=2)

    # Soft shading for over/under-confidence zones
    ax.fill_between([0,1], [0,0], [0,1], alpha=0.025, color="#d62728")
    ax.fill_between([0,1], [0,1], [1,1], alpha=0.025, color="#059669")

    # Model calibration with Wilson CIs
    ax.errorbar(pred, actual,
                yerr=[actual - lo, hi - actual],
                fmt="o", color=col, capsize=4, ms=7,
                markeredgecolor="white", markeredgewidth=0.7,
                elinewidth=1.2, label="Model  P_win", zorder=5)

    # Bin count annotations
    for px, ay, n in zip(pred, actual, counts):
        ax.annotate(str(n), xy=(px, ay), xytext=(5, 4),
                   textcoords="offset points", fontsize=6.5, color="#666666")

    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.03, 1.03)
    ax.set_xlabel("Model P(D win)", fontsize=10)
    ax.set_ylabel("Actual D win rate", fontsize=10)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.legend(fontsize=8.5, loc="upper left")
    ax.tick_params(labelsize=9)
    ax.text(0.53, 0.07, "← overconfident", fontsize=7.5, color="#c55", transform=ax.transAxes)
    ax.text(0.05, 0.84, "underconfident →", fontsize=7.5, color="#494", transform=ax.transAxes)

fig.suptitle("Win Probability Calibration — Reliability Diagram — 2024 House",
             fontsize=13, fontweight="bold", y=1.01)
fig.text(0.5, -0.025,
         "Numbers = races per bin  ·  Bars = 95% Wilson CI  ·  "
         "Systematic S-curve below diagonal → σᵢ too narrow (paper §4.2 / §7.4)",
         ha="center", fontsize=8, color="#777777", style="italic")

fig.tight_layout()
fig.savefig(OUT / "calibration_curve.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("✓ Chart 2: calibration_curve.png")
