"""
Efficiency tests: rank correlation and misallocation characterization.

Primary test: Spearman ρ between MSG_i and observed spending rank across
competitive races. Under efficient DCCC allocation this should be strongly
positive. A weak or negative ρ is evidence of systematic misallocation.
"""

from __future__ import annotations
import logging
import numpy as np
import pandas as pd
from scipy import stats
from ..types import ModelOutputs, RaceRecord
from .. import config

logger = logging.getLogger(__name__)


def spearman_efficiency_test(
    races: list[RaceRecord],
    outputs: list[ModelOutputs],
    n_bootstrap: int = 1000,
    rng: np.random.Generator | None = None,
) -> dict:
    """
    Compute Spearman ρ between observed spending rank and MSG_i rank,
    restricted to competitive races.

    Returns dict with: rho, p_value, ci_low, ci_high, n_competitive
    """
    rng = rng or np.random.default_rng(42)
    competitive = set(config.competitive_ratings())

    pairs = [
        (r, o) for r, o in zip(races, outputs)
        if r.cook_rating in competitive
    ]

    if not pairs:
        raise ValueError("No competitive races found for efficiency test")

    comp_races, comp_outputs = zip(*pairs)
    observed_spend = np.array([r.d_total for r in comp_races])
    msg_vals = np.array([o.msg_i for o in comp_outputs])

    rho, p_value = stats.spearmanr(observed_spend, msg_vals)
    logger.info(f"Spearman ρ (competitive, n={len(comp_races)}): {rho:.3f} (p={p_value:.4f})")

    # Bootstrap CI
    bootstrap_rhos = []
    n = len(comp_races)
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        r_boot, _ = stats.spearmanr(observed_spend[idx], msg_vals[idx])
        bootstrap_rhos.append(r_boot)

    ci_low = float(np.percentile(bootstrap_rhos, 2.5))
    ci_high = float(np.percentile(bootstrap_rhos, 97.5))

    return {
        "rho": float(rho),
        "p_value": float(p_value),
        "ci_low": ci_low,
        "ci_high": ci_high,
        "n_competitive": len(comp_races),
    }


def characterize_misallocation(
    races: list[RaceRecord],
    outputs: list[ModelOutputs],
    allocation_diffs: list[float],
    budget: float,
) -> dict:
    """
    For races with material allocation divergence (|diff| > 1% of budget),
    characterize the direction by cook_rating, PVI, and incumbency status.

    Returns dict with "overfunded" and "underfunded" summaries.
    """
    threshold = config.outputs_cfg()["material_divergence_threshold"]
    material = threshold * budget

    over, under = [], []
    for race, out, diff in zip(races, outputs, allocation_diffs):
        if diff < -material:
            over.append({"race": race, "output": out, "diff": diff})
        elif diff > material:
            under.append({"race": race, "output": out, "diff": diff})

    def _summarize(items: list) -> dict:
        if not items:
            return {"count": 0, "by_rating": {}, "by_incumb": {}, "by_pvi_bin": {}}

        by_rating = pd.Series([i["race"].cook_rating for i in items]).value_counts().to_dict()
        by_incumb = pd.Series([i["race"].incumb_status for i in items]).value_counts().to_dict()

        pvi_vals = np.array([abs(i["race"].pvi) for i in items])
        bins = [0, 5, 10, 20, 100]
        labels = ["0-5", "5-10", "10-20", "20+"]
        bin_counts = pd.cut(pvi_vals, bins=bins, labels=labels).value_counts().to_dict()

        return {
            "count": len(items),
            "total_diff_pp": sum(abs(i["diff"]) for i in items),
            "by_rating": by_rating,
            "by_incumb": by_incumb,
            "by_pvi_bin": bin_counts,
        }

    return {
        "overfunded": _summarize(over),
        "underfunded": _summarize(under),
    }
