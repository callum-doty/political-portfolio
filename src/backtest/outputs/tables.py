"""
Tabular output generation.

Produces:
  1. Per-race table (Section 7.1 of spec)
  2. Aggregate summary (Section 7.2)
  3. Concentration risk flags
"""

from __future__ import annotations
import logging
from pathlib import Path
import numpy as np
import pandas as pd
from ..types import RaceRecord, ModelOutputs, AllocationResult, UncertaintyBundle
from .. import config

logger = logging.getLogger(__name__)


def build_race_table(
    races: list[RaceRecord],
    outputs: list[ModelOutputs],
    allocation: list[AllocationResult],
    uncertainty: UncertaintyBundle | None = None,
) -> pd.DataFrame:
    """
    Assemble the per-race output table (Section 7.1).

    When uncertainty is provided, adds median recommended share, 83% CI,
    and P(model > DCCC) columns.
    """
    rows = []
    for race, out, alloc in zip(races, outputs, allocation):
        row = {
            "district_id":       race.district_id,
            "state":             race.state,
            "district":          race.district,
            "cook_rating":       race.cook_rating,
            "incumb_status":     race.incumb_status,
            "pvi":               race.pvi,
            "d_total":           race.d_total,
            "r_total":           race.r_total,
            "ratio":             out.ratio,
            "mu_hat":            round(out.mu_hat, 3),
            "sigma_i":           round(out.sigma_i, 3),
            "p_win":             round(out.p_win, 4),
            "msg_i_per_1m":      round(out.msg_i * 1e6, 6),
            "recommended_share": round(alloc.recommended_share, 6),
            "observed_share":    round(alloc.observed_share, 6),
            "difference":        round(alloc.difference, 6),
            "outcome":           race.outcome,
            "redistricting_flagged": race.redistricting_flagged,
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    if uncertainty is not None:
        district_idx = {d: i for i, d in enumerate(uncertainty.district_ids)}
        ci_lo, ci_hi = uncertainty.credible_interval()
        prob_exceed = uncertainty.prob_model_exceeds_dccc()
        median_shares = uncertainty.median_share()

        df["recommended_share_median"] = df["district_id"].map(
            lambda d: round(median_shares[district_idx[d]], 6) if d in district_idx else np.nan
        )
        df["recommended_share_ci83_lo"] = df["district_id"].map(
            lambda d: round(ci_lo[district_idx[d]], 6) if d in district_idx else np.nan
        )
        df["recommended_share_ci83_hi"] = df["district_id"].map(
            lambda d: round(ci_hi[district_idx[d]], 6) if d in district_idx else np.nan
        )
        df["prob_model_exceeds_dccc"] = df["district_id"].map(
            lambda d: round(prob_exceed[district_idx[d]], 3) if d in district_idx else np.nan
        )

    return df.sort_values("msg_i_per_1m", ascending=False).reset_index(drop=True)


def build_aggregate_summary(
    races: list[RaceRecord],
    outputs: list[ModelOutputs],
    allocation: list[AllocationResult],
    efficiency_test: dict,
    budget: float,
    concentration_cap_gap: float | None = None,
    expected_seats_model: float | None = None,
) -> dict:
    """
    Compute aggregate summary statistics (Section 7.2).
    """
    cfgout = config.outputs_cfg()
    material_threshold = cfgout["material_divergence_threshold"]
    concentration_flag = cfgout["concentration_flag_threshold"]

    p_win_observed = sum(o.p_win for o in outputs)
    # expected_seats_model comes from the optimizer result (Φ evaluated at optimal D).
    # Fallback to observed P_win sum only if not supplied — avoids stale MSG-linear approx.
    p_win_recommended = expected_seats_model if expected_seats_model is not None else p_win_observed

    material_diffs = [a for a in allocation if abs(a.difference) > material_threshold]
    material_budget_share = sum(abs(a.difference) for a in material_diffs)

    concentrated = [a for a in allocation if a.recommended_share > concentration_flag]
    if concentrated:
        logger.warning(
            f"Concentration flag: {len(concentrated)} race(s) receive > "
            f"{concentration_flag:.0%} of budget: "
            f"{[a.district_id for a in concentrated]}"
        )

    summary = {
        "expected_seats_dccc_observed":    round(p_win_observed, 3),
        "expected_seats_model_recommended": round(p_win_recommended, 3),
        "spearman_rho":                    round(efficiency_test.get("rho", float("nan")), 3),
        "spearman_p_value":                round(efficiency_test.get("p_value", float("nan")), 4),
        "spearman_ci_low":                 round(efficiency_test.get("ci_low", float("nan")), 3),
        "spearman_ci_high":                round(efficiency_test.get("ci_high", float("nan")), 3),
        "n_competitive":                   efficiency_test.get("n_competitive", 0),
        "n_material_divergence":           len(material_diffs),
        "material_divergence_budget_share": round(material_budget_share, 4),
        "n_concentration_flags":           len(concentrated),
        "total_budget":                    budget,
        # §4.6: concentration cap gap — E[Seats]_uncapped minus E[Seats]_5pct_cap.
        # Small gap → efficiency frontier is broad and politically resilient.
        # Large gap → optimizer's gains depend on extreme localized concentration.
        "concentration_cap_gap":           round(concentration_cap_gap, 4) if concentration_cap_gap is not None else None,
    }
    return summary


def save_outputs(
    race_table: pd.DataFrame,
    aggregate: dict,
    label: str = "baseline",
) -> None:
    """Write race table and aggregate summary to the outputs directory."""
    out_dir = config.outputs_path()
    out_dir.mkdir(parents=True, exist_ok=True)

    table_path = out_dir / f"race_table_{label}.csv"
    race_table.to_csv(table_path, index=False)
    logger.info(f"Race table written to {table_path}")

    agg_df = pd.DataFrame([aggregate])
    agg_path = out_dir / f"aggregate_summary_{label}.csv"
    agg_df.to_csv(agg_path, index=False)
    logger.info(f"Aggregate summary written to {agg_path}")
