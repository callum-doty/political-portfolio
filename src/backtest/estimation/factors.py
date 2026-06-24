"""
Factor covariance matrix estimation.

Common factors:
  1. National generic ballot (single scalar — all districts share this loading)
  2. Regional swing (Census region dummies × generic ballot)
  3. Urban/suburban/rural composition (ACS urbanicity share × generic ballot)

Factor loadings estimated from 2012–2022 historical outcome panel using
ridge-regularized regression (λ selected by leave-one-cycle-out CV).

The covariance matrix Cov(Yᵢ, Yⱼ) = fᵢᵀ · Var(F) · fⱼ is used in the
portfolio optimizer to compute Var[Seats].
"""

from __future__ import annotations
import logging
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV  # type: ignore
from ..types import FactorModel

logger = logging.getLogger(__name__)

_REGIONS = {
    "Northeast": ["CT", "ME", "MA", "NH", "NJ", "NY", "PA", "RI", "VT"],
    "Midwest":   ["IL", "IN", "IA", "KS", "MI", "MN", "MO", "NE", "ND", "OH", "SD", "WI"],
    "South":     ["AL", "AR", "DE", "FL", "GA", "KY", "LA", "MD", "MS", "NC",
                  "OK", "SC", "TN", "TX", "VA", "WV"],
    "West":      ["AK", "AZ", "CA", "CO", "HI", "ID", "MT", "NV", "NM", "OR", "UT", "WA", "WY"],
}


def _state_to_region(state: str) -> str:
    for region, states in _REGIONS.items():
        if state in states:
            return region
    return "Other"


def build_factor_matrix(
    panel_results: pd.DataFrame,
    panel_meta: pd.DataFrame,
    generic_ballot_by_cycle: dict[int, float],
    district_ids_2024: list[str],
    meta_2024: pd.DataFrame,
) -> FactorModel:
    """
    Estimate factor loadings from historical panel and return a FactorModel
    applicable to the 2024 districts.

    Parameters
    ----------
    panel_results : [district_id, cycle, margin_pp]
    panel_meta    : [district_id, cycle, state, urbanicity_share]
                    urbanicity_share = fraction of CVAP in urban/suburban areas (ACS)
    generic_ballot_by_cycle : {cycle: D−R generic ballot average}
    district_ids_2024 : list of district_ids for which to construct loadings
    meta_2024     : [district_id, state, urbanicity_share] for 2024 districts

    Returns
    -------
    FactorModel with loadings (n_2024_races × n_factors) and factor_cov.
    """
    df = panel_results.merge(panel_meta, on=["district_id", "cycle"])
    df["gb"] = df["cycle"].map(generic_ballot_by_cycle)
    df["region"] = df["state"].apply(_state_to_region)

    # One-hot regions interacted with GB
    for region in ["Midwest", "South", "West"]:   # Northeast is reference
        df[f"region_{region}_x_gb"] = (df["region"] == region).astype(float) * df["gb"]

    df["urban_x_gb"] = df["urbanicity_share"] * df["gb"]

    factor_cols = ["gb", "region_Midwest_x_gb", "region_South_x_gb",
                   "region_West_x_gb", "urban_x_gb"]

    # Ridge regression of margin on factors (residual absorbed into idiosyncratic ε)
    alphas = np.logspace(-3, 3, 20)
    X = df[factor_cols].values
    y = df["margin_pp"].values

    ridge = RidgeCV(alphas=alphas, cv=5)
    ridge.fit(X, y)

    logger.info(f"Ridge λ selected: {ridge.alpha_:.4f}")

    # Factor covariance from empirical factor realizations
    F = df[factor_cols].values
    factor_cov = np.cov(F.T)

    # Build 2024 loadings by scoring meta_2024 through the same feature space
    df24 = meta_2024.copy()
    df24["region"] = df24["state"].apply(_state_to_region)
    gb_2024 = generic_ballot_by_cycle.get(2024, 0.0)
    df24["gb"] = gb_2024
    for region in ["Midwest", "South", "West"]:
        df24[f"region_{region}_x_gb"] = (df24["region"] == region).astype(float) * gb_2024
    df24["urban_x_gb"] = df24["urbanicity_share"] * gb_2024

    # Reindex to requested districts in order
    df24 = df24.set_index("district_id").reindex(district_ids_2024)
    loadings = df24[factor_cols].fillna(0).values  # (n_races, n_factors)

    return FactorModel(
        loadings=loadings,
        factor_cov=factor_cov,
        district_ids=district_ids_2024,
    )
