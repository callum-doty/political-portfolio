"""
Heteroskedastic σᵢ estimation from 2012–2022 margin residuals.

σᵢ is the standard deviation of the margin prediction error, conditional on:
  - |PVI| (absolute partisan lean)
  - Incumbency status (three categories)
  - National environment (generic ballot)

Fitting a log-linear model:
  log(|residual_i|) = a0 + a1·|PVI_i| + a2·is_open_i + a3·is_challenger_i + νᵢ

The fitted model is carried forward to 2024 district characteristics.
No 2024 outcome data enters σᵢ estimation.

Expected ordering: σ^open > σ^challenger > σ^incumbent at matched |PVI|.
"""

from __future__ import annotations
import logging
import numpy as np
import pandas as pd
import statsmodels.api as sm
from ..types import SigmaModel

logger = logging.getLogger(__name__)


def estimate_sigma(residuals: pd.DataFrame) -> SigmaModel:
    """
    Fit the heteroskedastic σᵢ model on historical margin residuals.

    Parameters
    ----------
    residuals : DataFrame with columns
        district_id, cycle, abs_pvi, incumb_status, margin_residual
        where margin_residual = actual_margin − fitted_margin (from the panel regression)

    Returns
    -------
    SigmaModel ready for predict(abs_pvi, incumb_status).
    """
    df = residuals.copy()
    df = df[df["margin_residual"].notna() & (df["margin_residual"].abs() > 0.01)]

    df["log_abs_resid"] = np.log(df["margin_residual"].abs())
    df["is_open"] = (df["incumb_status"] == "Open").astype(float)
    df["is_challenger"] = (df["incumb_status"] == "Challenger").astype(float)

    X = sm.add_constant(df[["abs_pvi", "is_open", "is_challenger"]])
    y = df["log_abs_resid"]
    fit = sm.OLS(y, X).fit()

    coef = {
        "intercept":     float(fit.params["const"]),
        "abs_pvi":       float(fit.params["abs_pvi"]),
        "is_open":       float(fit.params["is_open"]),
        "is_challenger": float(fit.params["is_challenger"]),
    }

    logger.info(
        f"σ model: intercept={coef['intercept']:.3f}, abs_pvi={coef['abs_pvi']:.3f}, "
        f"is_open={coef['is_open']:.3f}, is_challenger={coef['is_challenger']:.3f}"
    )

    _check_sigma_ordering(SigmaModel(_coef=coef))
    return SigmaModel(_coef=coef)


def _check_sigma_ordering(model: SigmaModel) -> None:
    """Validate σ^open > σ^challenger > σ^incumbent at each |PVI| level."""
    pvi_bins = np.arange(0, 25, 5)
    violations = 0
    for pvi in pvi_bins:
        s_open = model.predict(float(pvi), "Open")
        s_chall = model.predict(float(pvi), "Challenger")
        s_incumb = model.predict(float(pvi), "Incumbent")
        if not (s_open > s_chall > s_incumb):
            violations += 1
            logger.warning(
                f"|PVI|={pvi}: ordering violated — open={s_open:.2f}, "
                f"chall={s_chall:.2f}, incumb={s_incumb:.2f}"
            )
    n_bins = len(pvi_bins)
    frac_ok = 1 - violations / n_bins
    logger.info(f"σ ordering holds in {frac_ok:.0%} of PVI bins ({n_bins - violations}/{n_bins})")


def compute_residuals_from_panel(
    panel_results: pd.DataFrame,
    panel_spend: pd.DataFrame,
    panel_incumb: pd.DataFrame,
    panel_pvi: pd.DataFrame,
    alpha_coef: dict,
    beta_coef: dict,
    generic_ballot_by_cycle: dict[int, float],
    cvap_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Compute margin residuals for all historical panel observations.

    Uses the fitted margin model (α and β coefficients from panel estimation)
    to produce residuals: actual_margin − fitted_margin.

    Parameters
    ----------
    panel_results : [district_id, cycle, margin_pp]
    panel_spend   : [district_id, cycle, d_total, r_total]
    panel_incumb  : [district_id, cycle, incumb_status]
    panel_pvi     : [district_id, cycle, pvi]
    alpha_coef    : {"intercept", "pvi", "incumb", "gb"} — control surface coefficients
    beta_coef     : {"b1", "b2", "b3"} — spending response coefficients
    generic_ballot_by_cycle : {cycle: GB_value}

    Returns
    -------
    DataFrame with columns: district_id, cycle, abs_pvi, incumb_status, margin_residual
    """
    df = (
        panel_results
        .merge(panel_spend, on=["district_id", "cycle"])
        .merge(panel_incumb, on=["district_id", "cycle"])
        .merge(panel_pvi, on=["district_id", "cycle"])
    )

    df["gb"] = df["cycle"].map(generic_ballot_by_cycle)
    df = df[df["d_total"] + df["r_total"] > 0]
    df["ratio"] = df["d_total"] / (df["d_total"] + df["r_total"])
    df = df[df["ratio"] > 0]
    df["log_ratio"] = np.log(df["ratio"])
    df["abs_pvi"] = df["pvi"].abs()
    df["is_incumb"] = (df["incumb_status"] == "Incumbent").astype(float)
    df["is_open"] = (df["incumb_status"] == "Open").astype(float)

    if cvap_df is not None:
        df = df.merge(cvap_df[["district_id", "cvap"]], on="district_id", how="left")
        df["cvap"] = df["cvap"].fillna(df["cvap"].median()).clip(lower=1)
    else:
        df["cvap"] = 500_000
    df["log_total_per_voter"] = np.log((df["d_total"] + df["r_total"]) / df["cvap"])

    # Fitted margin from the full model
    a = alpha_coef
    b = beta_coef
    df["mu_hat"] = (
        a["intercept"]
        + a["pvi"] * df["pvi"]
        + a["incumb"] * df["is_incumb"]
        + a["gb"] * df["gb"]
        + a.get("alpha4", 0.0) * df["log_total_per_voter"]
        + b["b1"] * df["log_ratio"]
        + b["b2"] * df["log_ratio"] * df["abs_pvi"]
        + b["b3"] * df["log_ratio"] * df["is_incumb"]
    )

    df["margin_residual"] = df["margin_pp"] - df["mu_hat"]

    return df[["district_id", "cycle", "abs_pvi", "incumb_status", "margin_residual"]]
