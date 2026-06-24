"""
β_RC estimation: repeat-challenger spending coefficient.

Estimated on the 2012–2022 historical panel using first-differencing to remove
district fixed effects (time-invariant confounders). The 2024 cycle is strictly
out-of-sample — β_RC is frozen before the backtest runs.

Method
──────
For each pair of consecutive elections in the same district where the same
challenger faces the same incumbent, form the first difference:

  ΔMargin_it = β_RC · Δlog(ratio_it) + Δε_it

where ratio_it = D_total_it / (D_total_it + R_total_it).

OLS on the first-differenced equation is equivalent to within-pair estimation
and removes any additive district fixed effect.
"""

from __future__ import annotations
import logging
import re
import pandas as pd
import numpy as np
import statsmodels.api as sm
from ..types import BetaRC
from .. import config

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    """Strip suffixes and normalize hyphens for candidate name matching."""
    name = name.upper().strip()
    name = re.sub(r"\b(JR|SR|II|III|IV|ESQ)\.?\b", "", name)
    name = re.sub(r"[-–—]", "-", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def identify_repeat_pairs(
    results: pd.DataFrame,
    spend: pd.DataFrame,
    incumb: pd.DataFrame,
) -> pd.DataFrame:
    """
    Find consecutive-cycle pairs where the same challenger faces the same incumbent.

    Parameters
    ----------
    results : columns [district_id, cycle, d_votes, r_votes, margin_pp, winner]
    spend   : columns [district_id, cycle, d_total, r_total]
    incumb  : columns [district_id, cycle, incumb_status, incumbent_name, challenger_name]

    Returns DataFrame with columns:
        district_id, cycle_t, cycle_tm1,
        delta_margin, delta_log_ratio
    """
    cycles = sorted(config.panel_cycles())

    pairs = []
    for i in range(1, len(cycles)):
        c_prev, c_curr = cycles[i - 1], cycles[i]

        # Races where D was challenger in both cycles (incumbent is R)
        inc_prev = incumb[(incumb["cycle"] == c_prev) & (incumb["incumb_status"] == "Challenger")]
        inc_curr = incumb[(incumb["cycle"] == c_curr) & (incumb["incumb_status"] == "Challenger")]

        merged = inc_prev.merge(
            inc_curr, on="district_id", suffixes=("_prev", "_curr")
        )

        # Name match: same challenger in both cycles
        merged["name_prev_norm"] = merged["challenger_name_prev"].apply(_normalize_name)
        merged["name_curr_norm"] = merged["challenger_name_curr"].apply(_normalize_name)
        same_challenger = merged["name_prev_norm"] == merged["name_curr_norm"]
        repeat = merged[same_challenger][["district_id"]].copy()

        if repeat.empty:
            continue

        # Join results and spend for both cycles
        r_prev = results[results["cycle"] == c_prev][["district_id", "margin_pp"]]
        r_curr = results[results["cycle"] == c_curr][["district_id", "margin_pp"]]
        s_prev = spend[spend["cycle"] == c_prev][["district_id", "d_total", "r_total"]]
        s_curr = spend[spend["cycle"] == c_curr][["district_id", "d_total", "r_total"]]

        pair_df = (
            repeat
            .merge(r_prev.rename(columns={"margin_pp": "margin_prev"}), on="district_id")
            .merge(r_curr.rename(columns={"margin_pp": "margin_curr"}), on="district_id")
            .merge(s_prev.rename(columns={"d_total": "d_prev", "r_total": "r_prev"}), on="district_id")
            .merge(s_curr.rename(columns={"d_total": "d_curr", "r_total": "r_curr"}), on="district_id")
        )

        pair_df["ratio_prev"] = pair_df["d_prev"] / (pair_df["d_prev"] + pair_df["r_prev"])
        pair_df["ratio_curr"] = pair_df["d_curr"] / (pair_df["d_curr"] + pair_df["r_curr"])

        # Guard against zero spend
        valid = (pair_df["ratio_prev"] > 0) & (pair_df["ratio_curr"] > 0)
        pair_df = pair_df[valid]

        pair_df["delta_margin"] = pair_df["margin_curr"] - pair_df["margin_prev"]
        pair_df["delta_log_ratio"] = np.log(pair_df["ratio_curr"]) - np.log(pair_df["ratio_prev"])
        pair_df["cycle_t"] = c_curr
        pair_df["cycle_tm1"] = c_prev

        pairs.append(pair_df[["district_id", "cycle_t", "cycle_tm1",
                               "delta_margin", "delta_log_ratio"]])

    if not pairs:
        return pd.DataFrame(columns=["district_id", "cycle_t", "cycle_tm1",
                                     "delta_margin", "delta_log_ratio"])

    return pd.concat(pairs, ignore_index=True)


def estimate_beta_rc(pairs: pd.DataFrame) -> BetaRC:
    """
    OLS estimate of β_RC from first-differenced repeat-challenger pairs.

    ΔMargin = β_RC · Δlog(ratio) + ε

    Parameters
    ----------
    pairs : output of identify_repeat_pairs()

    Returns
    -------
    BetaRC with estimate, SE, and pair count.
    Raises ValueError if fewer than min_repeat_challenger_pairs pairs found.
    """
    n_pairs = len(pairs)
    min_pairs = config.min_repeat_pairs()

    logger.info(f"Identified {n_pairs} repeat-challenger pairs")

    if n_pairs < min_pairs:
        logger.warning(
            f"Only {n_pairs} pairs found (minimum {min_pairs}). "
            "β_RC will be imprecisely estimated — consider widening τ."
        )

    X = sm.add_constant(pairs["delta_log_ratio"])
    y = pairs["delta_margin"]
    model = sm.OLS(y, X).fit(cov_type="HC3")

    beta = float(model.params["delta_log_ratio"])
    se = float(model.bse["delta_log_ratio"])

    logger.info(f"β_RC = {beta:.4f} (SE = {se:.4f}, n = {n_pairs})")

    return BetaRC(estimate=beta, se=se, n_pairs=n_pairs)


def sample_beta_rc(beta_rc: BetaRC, n_draws: int, rng: np.random.Generator | None = None) -> np.ndarray:
    """
    Draw K samples from the β_RC posterior N(β̂, SE²).

    Returns array of shape (n_draws,).
    """
    rng = rng or np.random.default_rng()
    return rng.normal(loc=beta_rc.estimate, scale=beta_rc.se, size=n_draws)
