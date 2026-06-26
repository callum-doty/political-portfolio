#!/usr/bin/env python3
"""
Run historical panel estimation.

Estimates and persists:
  1. β_RC — repeat-challenger spending coefficient
  2. Full margin model coefficients (α, β₂, β₃)
  3. σᵢ heteroskedastic model

Outputs go to data/processed/ (default) or a suffixed sub-directory
when --panel-end-cycle is used for cross-cycle validation.

Usage:
    python scripts/run_estimation.py                        # standard 2012–2022 panel
    python scripts/run_estimation.py --panel-end-cycle 2020 # OOS 2022 validation
"""

from __future__ import annotations
import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from backtest import config
from backtest.data import fec, elections, incumbency, census
from backtest.estimation import beta_rc as beta_rc_module
from backtest.estimation import sigma as sigma_module
from backtest.model import margin as margin_module

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("run_estimation")


def _load_generic_ballot() -> dict[int, float]:
    """
    Load historical generic ballot values from data/raw/generic_ballot/generic_ballot_by_cycle.csv.
    Falls back to hardcoded values if the file is missing.
    """
    gb_path = config.raw_path("generic_ballot") / "generic_ballot_by_cycle.csv"
    if gb_path.exists():
        df = pd.read_csv(gb_path)
        result = dict(zip(df["cycle"].astype(int), df["generic_ballot"].astype(float)))
        logger.info(f"Loaded generic ballot values from {gb_path.name}: {result}")
        return result
    logger.warning(
        f"Generic ballot file not found at {gb_path}. "
        "Using hardcoded fallback values. Create the file to manage GB values properly."
    )
    return {
        2012: 1.2,
        2014: -5.8,
        2016: 1.3,
        2018: 8.6,
        2020: 7.0,
        2022: -1.0,
    }


GENERIC_BALLOT_BY_CYCLE: dict[int, float] = _load_generic_ballot()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run panel estimation")
    parser.add_argument(
        "--panel-end-cycle", type=int, default=None,
        help="Exclude cycles after this year (e.g. 2020 for OOS 2022 validation). "
             "Outputs written to data/processed_oos_{year}/",
    )
    args = parser.parse_args()

    all_cycles = config.panel_cycles()
    if args.panel_end_cycle is not None:
        cycles = [c for c in all_cycles if c <= args.panel_end_cycle]
        out_dir = config.processed_path().parent / f"processed_oos_{args.panel_end_cycle}"
        logger.info(f"OOS mode: panel cycles {cycles}, writing to {out_dir.name}/")
    else:
        cycles = all_cycles
        out_dir = config.processed_path()

    processed = out_dir
    processed.mkdir(parents=True, exist_ok=True)

    # ── Load panel data ───────────────────────────────────────────────────────
    logger.info(f"Loading panel results for cycles {cycles}…")
    panel_results = pd.concat([elections.load_results(c) for c in cycles], ignore_index=True)

    logger.info("Loading panel spend…")
    spend_frames = [fec.build_total_spend(c) for c in cycles]
    panel_spend = pd.concat(spend_frames, ignore_index=True)

    logger.info("Loading panel incumbency…")
    incumb_frames = [incumbency.load_incumbency(c) for c in cycles]
    panel_incumb = pd.concat(incumb_frames, ignore_index=True)

    from backtest.data.cook import load_pvi
    logger.info("Loading panel PVI…")
    pvi_frames = [load_pvi(c).assign(cycle=c) for c in cycles]
    panel_pvi = pd.concat(pvi_frames, ignore_index=True)

    # ── Step 1: β_RC ─────────────────────────────────────────────────────────
    logger.info("Identifying repeat-challenger pairs…")
    pairs = beta_rc_module.identify_repeat_pairs(panel_results, panel_spend, panel_incumb)
    logger.info(f"Found {len(pairs)} pairs across cycles")

    logger.info("Estimating β_RC…")
    beta_rc = beta_rc_module.estimate_beta_rc(pairs)

    beta_path = processed / "beta_rc.json"
    with open(beta_path, "w") as f:
        json.dump({"estimate": beta_rc.estimate, "se": beta_rc.se, "n_pairs": beta_rc.n_pairs}, f, indent=2)
    logger.info(f"β_RC saved to {beta_path}")

    # ── Step 2: Full margin model ─────────────────────────────────────────────
    logger.info("Loading CVAP data…")
    cvap_df = census.load_cvap()

    logger.info("Fitting margin model on panel…")
    coef, r2 = margin_module.estimate_from_panel(
        panel_results=panel_results,
        panel_spend=panel_spend,
        panel_incumb=panel_incumb,
        panel_pvi=panel_pvi,
        generic_ballot_by_cycle=GENERIC_BALLOT_BY_CYCLE,
        beta_rc_estimate=beta_rc.estimate,
        cvap_df=cvap_df,
    )

    coef_path = processed / "margin_model_coef.json"
    with open(coef_path, "w") as f:
        json.dump({
            "alpha0": coef.alpha0, "alpha1": coef.alpha1,
            "alpha2": coef.alpha2, "alpha3": coef.alpha3,
            "alpha4": coef.alpha4,
            "beta1":  coef.beta1,  "beta2":  coef.beta2,
            "beta3":  coef.beta3,
            "r2_competitive": r2,
        }, f, indent=2)
    logger.info(f"Margin model coefficients saved to {coef_path}")

    # ── Step 3: σᵢ model ─────────────────────────────────────────────────────
    logger.info("Computing margin residuals for σᵢ estimation…")
    alpha_coef = {"intercept": coef.alpha0, "pvi": coef.alpha1,
                  "incumb": coef.alpha2, "gb": coef.alpha3, "alpha4": coef.alpha4}
    beta_coef = {"b1": coef.beta1, "b2": coef.beta2, "b3": coef.beta3}

    residuals = sigma_module.compute_residuals_from_panel(
        panel_results=panel_results,
        panel_spend=panel_spend,
        panel_incumb=panel_incumb,
        panel_pvi=panel_pvi,
        alpha_coef=alpha_coef,
        beta_coef=beta_coef,
        generic_ballot_by_cycle=GENERIC_BALLOT_BY_CYCLE,
        cvap_df=cvap_df,
    )

    logger.info("Estimating σᵢ model…")
    sigma_model = sigma_module.estimate_sigma(residuals)

    sigma_path = processed / "sigma_model.json"
    with open(sigma_path, "w") as f:
        json.dump(sigma_model._coef, f, indent=2)
    logger.info(f"σᵢ model saved to {sigma_path}")

    logger.info("Estimation complete. Run scripts/run_backtest.py to execute the backtest.")


if __name__ == "__main__":
    main()
