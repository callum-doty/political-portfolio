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


def permutation_test_spearman_efficiency(
    races: list[RaceRecord],
    outputs: list[ModelOutputs],
    n_permutations: int = 2000,
    rng: np.random.Generator | None = None,
) -> dict:
    """
    Permutation test for the primary Spearman efficiency correlation.

    scipy.stats.spearmanr's p-value relies on an asymptotic approximation
    that is untested at the small-n categories this project already reports
    (e.g. Lean R, n=7, in spearman_by_cook_category()). This instead builds
    an exact empirical null: randomly reassign DCCC's observed per-race
    spending amounts across competitive races — breaking any link between
    spending and MSG while holding the multiset of dollar amounts and MSG
    values fixed — and recompute ρ, n_permutations times. The permutation
    p-value is the fraction of null |ρ| at least as extreme as the observed
    |ρ|, with no distributional assumption.

    Returns dict with: rho, p_value_asymptotic, p_value_permutation,
    n_permutations, n_competitive
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

    rho_obs, p_asymptotic = stats.spearmanr(observed_spend, msg_vals)

    null_rhos = np.empty(n_permutations)
    for i in range(n_permutations):
        shuffled_spend = rng.permutation(observed_spend)
        null_rhos[i], _ = stats.spearmanr(shuffled_spend, msg_vals)

    p_permutation = float(np.mean(np.abs(null_rhos) >= abs(rho_obs)))

    logger.info(
        f"Permutation test (n={n_permutations}): ρ={rho_obs:.3f}, "
        f"asymptotic p={p_asymptotic:.4g}, permutation p={p_permutation:.4g}"
    )

    return {
        "rho": float(rho_obs),
        "p_value_asymptotic": float(p_asymptotic),
        "p_value_permutation": p_permutation,
        "n_permutations": n_permutations,
        "n_competitive": len(comp_races),
    }


def spearman_by_cook_category(
    races: list[RaceRecord],
    outputs: list[ModelOutputs],
    categories: tuple[str, ...] = ("Likely D", "Lean D", "Toss-Up", "Lean R", "Likely R"),
) -> pd.DataFrame:
    """
    Spearman ρ between observed spending and MSG_i, computed separately
    within each Cook rating category (Paper I Table 2).

    Unlike spearman_efficiency_test(), this is not restricted to
    config.competitive_ratings() — it reports every category in `categories`
    so that Likely D/Likely R (outside the primary n=53/61 competitive set)
    are included alongside Lean D/Toss-Up/Lean R.
    """
    rows = []
    for cat in categories:
        pairs = [(r, o) for r, o in zip(races, outputs) if r.cook_rating == cat]
        if len(pairs) < 3:
            continue
        cat_races, cat_outputs = zip(*pairs)
        spend = np.array([r.d_total for r in cat_races])
        msg_vals = np.array([o.msg_i for o in cat_outputs])
        rho, p_value = stats.spearmanr(spend, msg_vals)
        rows.append({"cook_category": cat, "n": len(pairs), "rho": float(rho), "p_value": float(p_value)})
    return pd.DataFrame(rows)


def matched_group_efficiency_test(
    races: list[RaceRecord],
    outputs: list[ModelOutputs],
    categories: tuple[str, ...] = ("Lean D", "Toss-Up"),
    max_abs_pvi: float = 5.0,
) -> dict:
    """
    Spearman ρ restricted to races matched on partisan lean and Cook
    category (Paper I §9, "matched-group test") — the risk-tolerance-robust
    efficiency test of §3.3: within races with similar factor loadings,
    γ·∂Var[Seats]/∂sᵢ is approximately constant, so equalization of raw MSG
    is the relevant efficiency condition.
    """
    pairs = [
        (r, o) for r, o in zip(races, outputs)
        if r.cook_rating in categories and abs(r.pvi) <= max_abs_pvi
    ]
    if not pairs:
        raise ValueError("No races found for matched-group test")
    m_races, m_outputs = zip(*pairs)
    spend = np.array([r.d_total for r in m_races])
    msg_vals = np.array([o.msg_i for o in m_outputs])
    rho, p_value = stats.spearmanr(spend, msg_vals)
    return {"rho": float(rho), "p_value": float(p_value), "n": len(pairs)}


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
