"""
Spending response surface — the margin model.

Margin_i = α₀ + α₁·PVI_i + α₂·incumb_i + α₃·GB
         + β₁·log(ratio_i) + β₂·log(ratio_i)·|PVI_i|
         + β₃·log(ratio_i)·incumb_i + εᵢ

β₁ = β_RC (fixed from 2012–2022 estimation, not re-estimated on 2024 data)
β₂, β₃ are interaction modifiers from the historical panel.
α₀–α₃ are control surface coefficients from the historical panel.

This module provides:
  - estimate_from_panel(): fit α and β on the 2012–2022 panel
  - predict(): apply the model to 2024 districts at a given β_RC draw
"""

from __future__ import annotations
import logging
import numpy as np
import pandas as pd
import statsmodels.api as sm
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MarginModelCoefficients:
    """All estimated coefficients for the spending response surface."""
    alpha0: float    # intercept
    alpha1: float    # PVI
    alpha2: float    # incumbency (Incumbent dummy)
    alpha3: float    # generic ballot
    beta1:  float    # β_RC — log(ratio)
    beta2:  float    # log(ratio) × |PVI|
    beta3:  float    # log(ratio) × Incumbent


def estimate_from_panel(
    panel_results: pd.DataFrame,
    panel_spend: pd.DataFrame,
    panel_incumb: pd.DataFrame,
    panel_pvi: pd.DataFrame,
    generic_ballot_by_cycle: dict[int, float],
    beta_rc_estimate: float,
) -> tuple[MarginModelCoefficients, float]:
    """
    Fit the margin model on the 2012–2022 panel.

    β₁ (β_RC) is constrained to its repeat-challenger estimate.
    α and β₂, β₃ are estimated by OLS with β₁ pre-imposed via offset.

    Parameters
    ----------
    beta_rc_estimate : pre-estimated β_RC from estimation.beta_rc

    Returns
    -------
    (MarginModelCoefficients, r_squared_competitive)
    """
    df = (
        panel_results
        .merge(panel_spend, on=["district_id", "cycle"])
        .merge(panel_incumb, on=["district_id", "cycle"])
        .merge(panel_pvi, on=["district_id", "cycle"])
    )

    df["gb"] = df["cycle"].map(generic_ballot_by_cycle)
    df = df[(df["d_total"] + df["r_total"]) > 0]
    df["ratio"] = df["d_total"] / (df["d_total"] + df["r_total"])
    df = df[df["ratio"] > 0]
    df["log_ratio"] = np.log(df["ratio"])
    df["abs_pvi"] = df["pvi"].abs()
    df["is_incumb"] = (df["incumb_status"] == "Incumbent").astype(float)

    # Impose β_RC via offset: y* = margin − β_RC·log(ratio)
    df["y_offset"] = df["margin_pp"] - beta_rc_estimate * df["log_ratio"]

    feature_cols = ["pvi", "is_incumb", "gb",
                    "log_ratio_x_abs_pvi", "log_ratio_x_incumb"]
    df["log_ratio_x_abs_pvi"] = df["log_ratio"] * df["abs_pvi"]
    df["log_ratio_x_incumb"] = df["log_ratio"] * df["is_incumb"]

    X = sm.add_constant(df[feature_cols])
    y = df["y_offset"]
    fit = sm.OLS(y, X).fit(cov_type="HC3")

    coef = MarginModelCoefficients(
        alpha0=float(fit.params["const"]),
        alpha1=float(fit.params["pvi"]),
        alpha2=float(fit.params["is_incumb"]),
        alpha3=float(fit.params["gb"]),
        beta1=beta_rc_estimate,
        beta2=float(fit.params["log_ratio_x_abs_pvi"]),
        beta3=float(fit.params["log_ratio_x_incumb"]),
    )

    # R² on competitive subset
    df["fitted"] = predict_batch(df, coef)
    competitive_mask = df["abs_pvi"] <= 10   # rough competitive proxy for panel
    ss_res = ((df.loc[competitive_mask, "margin_pp"] - df.loc[competitive_mask, "fitted"]) ** 2).sum()
    ss_tot = ((df.loc[competitive_mask, "margin_pp"] - df.loc[competitive_mask, "margin_pp"].mean()) ** 2).sum()
    r2 = 1 - ss_res / ss_tot

    logger.info(f"Margin model R² (competitive subset): {r2:.3f}")
    for name, val in coef.__dict__.items():
        logger.info(f"  {name}: {val:.4f}")

    return coef, r2


def predict(
    pvi: float,
    incumb_status: str,
    generic_ballot: float,
    ratio: float,
    coef: MarginModelCoefficients,
    beta1_override: float | None = None,
) -> float:
    """
    Compute fitted expected margin for a single district.

    Parameters
    ----------
    beta1_override : if provided, substitute this value for coef.beta1
                     (used during β_RC uncertainty draws)

    Returns
    -------
    μ̂ᵢ in percentage points.
    """
    b1 = beta1_override if beta1_override is not None else coef.beta1
    is_incumb = 1.0 if incumb_status == "Incumbent" else 0.0
    log_ratio = np.log(ratio)
    abs_pvi = abs(pvi)

    return (
        coef.alpha0
        + coef.alpha1 * pvi
        + coef.alpha2 * is_incumb
        + coef.alpha3 * generic_ballot
        + b1 * log_ratio
        + coef.beta2 * log_ratio * abs_pvi
        + coef.beta3 * log_ratio * is_incumb
    )


def predict_batch(df: pd.DataFrame, coef: MarginModelCoefficients) -> pd.Series:
    """Vectorised version of predict() for a DataFrame with precomputed columns."""
    return (
        coef.alpha0
        + coef.alpha1 * df["pvi"]
        + coef.alpha2 * df["is_incumb"]
        + coef.alpha3 * df["gb"]
        + coef.beta1 * df["log_ratio"]
        + coef.beta2 * df["log_ratio"] * df["pvi"].abs()
        + coef.beta3 * df["log_ratio"] * df["is_incumb"]
    )
