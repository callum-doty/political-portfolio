#!/usr/bin/env python3
"""
Main backtest pipeline.

Requires run_estimation.py to have completed successfully first.

Steps:
  1. Load race universe for the target cycle
  2. Apply margin model at observed allocations
  3. Run validation gates
  4. Run optimizer across (γ, cap) grid
  5. Propagate β_RC uncertainty (K=1000 draws)
  6. Produce per-race table, aggregate summary, efficiency frontier chart

Usage:
    python scripts/run_backtest.py                              # 2024 standard
    python scripts/run_backtest.py --skip-uncertainty           # 2024, fast
    python scripts/run_backtest.py --cycle 2022 --processed-dir data/processed_oos_2020
"""

from __future__ import annotations
import argparse
import json
import logging
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backtest import config
from backtest.data.universe import build_universe, competitive_subset
from backtest.model.margin import MarginModelCoefficients
from backtest.model.win_prob import compute_outputs_batch
from backtest.types import BetaRC, SigmaModel, FactorModel
from backtest.optimizer.allocator import (
    optimize, optimize_nonlinear, run_sensitivity_grid, build_allocation_results
)
from backtest.comparison.efficiency import spearman_efficiency_test, characterize_misallocation
from backtest.comparison.benchmark import (
    compute_brier_comparison, null_equal_weight_shares,
    cook_proportional_shares, compare_allocators
)
from backtest.comparison.uncertainty import propagate_beta_rc_uncertainty
from backtest.validation.gates import run_all_gates, ValidationError
from backtest.outputs.tables import build_race_table, build_aggregate_summary, save_outputs
from backtest.outputs.charts import efficiency_frontier, allocation_difference_scatter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("run_backtest")


def load_processed_artifacts(processed: Path) -> tuple[BetaRC, MarginModelCoefficients, SigmaModel]:
    """Load estimation outputs produced by run_estimation.py."""
    with open(processed / "beta_rc.json") as f:
        d = json.load(f)
    beta_rc = BetaRC(estimate=d["estimate"], se=d["se"], n_pairs=d["n_pairs"])

    with open(processed / "margin_model_coef.json") as f:
        d = json.load(f)
    coef = MarginModelCoefficients(**{k: d[k] for k in
                                      ["alpha0", "alpha1", "alpha2", "alpha3", "alpha4",
                                       "beta1", "beta2", "beta3"]},
                                   beta1_open=d.get("beta1_open"))

    with open(processed / "sigma_model.json") as f:
        sigma_coef = json.load(f)
    sigma_model = SigmaModel(_coef=sigma_coef)

    return beta_rc, coef, sigma_model


def build_dummy_factor_model(races: list, generic_ballot: float) -> FactorModel:
    """
    Placeholder factor model using only the national generic ballot factor.
    Replace with estimation.factors.build_factor_matrix() when urbanicity
    and regional data are available.
    """
    n = len(races)
    loadings = np.ones((n, 1)) * generic_ballot
    factor_cov = np.array([[1.0]])
    return FactorModel(
        loadings=loadings,
        factor_cov=factor_cov,
        district_ids=[r.district_id for r in races],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the House backtest")
    parser.add_argument("--skip-uncertainty", action="store_true",
                        help="Skip β_RC uncertainty propagation (faster for debugging)")
    parser.add_argument("--gamma-mid",  type=float, default=None,
                        help="Override γ_mid (default: calibrated post-estimation)")
    parser.add_argument("--gamma-high", type=float, default=None,
                        help="Override γ_high")
    parser.add_argument("--cycle", type=int, default=2024,
                        help="Election cycle to backtest (default: 2024)")
    parser.add_argument("--processed-dir", type=str, default=None,
                        help="Path to estimation artifacts directory "
                             "(default: data/processed). Use with --cycle for OOS runs.")
    parser.add_argument("--eta", type=float, default=0.0,
                        help="Adversarial response coefficient η ∈ [0, 1]. "
                             "Fraction of each new DCCC dollar the NRCC/CLF match "
                             "(0 = fixed R, retrospective; 1 = dollar-for-dollar). "
                             "Late-cycle deployments ≈ 0 (ad inventory sold out).")
    args = parser.parse_args()

    if args.processed_dir:
        processed = Path(args.processed_dir)
    else:
        processed = config.processed_path()

    cycle = args.cycle
    suffix = f"_{cycle}" if cycle != 2024 else ""
    out_dir = config.outputs_path()
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Load estimation artifacts ──────────────────────────────────────────
    logger.info("Loading estimation artifacts…")
    beta_rc, coef, sigma_model = load_processed_artifacts(processed)

    # ── 2. Build race universe ────────────────────────────────────────────────
    logger.info(f"Building {cycle} race universe…")
    races = build_universe(cycle=cycle)
    logger.info(f"Universe: {len(races)} races")
    budget = sum(r.d_total for r in races)
    party_budget = sum(r.d_total - r.cand_d_total for r in races)
    logger.info(f"Total Democratic budget: ${budget:,.0f}")
    logger.info(f"DCCC party-controlled budget: ${party_budget:,.0f}")

    cand_floors = np.array([r.cand_d_total for r in races])

    # ── 3. Compute model outputs at observed 2024 spending ────────────────────
    logger.info("Computing model outputs (observed spending)…")
    outputs = compute_outputs_batch(races, coef, sigma_model)

    # ── 4. Factor model (simplified until urbanicity data loaded) ─────────────
    factor_model = build_dummy_factor_model(races, config.generic_ballot_2024())
    cov_matrix = factor_model.race_covariance()

    # ── 5. Validation gates ───────────────────────────────────────────────────
    logger.info("Running validation gates…")
    opt_cfg = config.optimizer_cfg()
    gamma_values = opt_cfg["gamma_values"]
    cap_fractions = opt_cfg["cap_regimes"]

    # Run baseline optimizer to get convergence diagnostics for gate 5
    gamma0 = 0.0
    cap_baseline = cap_fractions[-1]   # 15% cap
    eta = args.eta
    if eta > 0:
        logger.info(f"Adversarial response η={eta:.2f}: NRCC/CLF match {eta:.0%} of new DCCC spend")

    baseline_result = optimize_nonlinear(
        races, coef, sigma_model, budget, cov_matrix, gamma0, cap_baseline,
        party_budget=party_budget, eta=eta)

    brier = compute_brier_comparison(races, outputs)
    brier_model = brier.get("model", 0.5)
    brier_cook  = brier.get("cook",  0.5)

    r2 = json.load(open(processed / "margin_model_coef.json"))["r2_competitive"]

    try:
        gate_results = run_all_gates(
            races=races, outputs=outputs, sigma_model=sigma_model,
            margin_r2_competitive=r2,
            optimizer_status=baseline_result.status,
            n_corner_solutions=baseline_result.n_corner_solutions,
            brier_model=brier_model, brier_cook=brier_cook,
            budget=budget,
        )
    except ValidationError as e:
        logger.error(f"Validation failed: {e}")
        logger.error("Stopping. Fix the issue identified above before proceeding.")
        sys.exit(1)

    # ── 6. Sensitivity grid: all (γ, cap) combinations ───────────────────────
    logger.info("Running optimizer sensitivity grid…")

    # Calibrate mid/high gamma if not overridden
    sd_seats = math.sqrt(baseline_result.var_seats)
    gamma_mid  = args.gamma_mid  if args.gamma_mid  is not None else (0.5 / max(sd_seats, 1e-6))
    gamma_high = args.gamma_high if args.gamma_high is not None else (1.0 / max(sd_seats, 1e-6))
    active_gammas = [0.0, gamma_mid, gamma_high]
    logger.info(f"γ values: risk_neutral=0.0, mid={gamma_mid:.4f}, high={gamma_high:.4f}")

    grid_results = run_sensitivity_grid(
        outputs, budget, cov_matrix, active_gammas, cap_fractions,
        floor_allocations=cand_floors, party_budget=party_budget,
        races=races, coef=coef, sigma_model=sigma_model, eta=eta)

    # ── 7. Primary allocation (γ=0, 15% cap) ─────────────────────────────────
    primary_result = grid_results[(0.0, cap_baseline)]
    allocation = build_allocation_results(races, outputs, primary_result, budget)

    # ── 7b. Concentration cap gap (§4.6) ─────────────────────────────────────
    # Uncapped optimizer (cap=100% of party budget per race = effectively uncapped).
    # Gap = E[Seats]_uncapped − E[Seats]_5%-cap. Large gap means the optimizer's
    # gains depend on extreme localized concentration (fragile, politically implausible).
    logger.info("Running uncapped optimizer for concentration gap (§4.6)…")
    uncapped_result = optimize_nonlinear(
        races, coef, sigma_model, budget, cov_matrix, 0.0, 1.0,
        party_budget=party_budget, eta=eta)
    five_pct_result = grid_results.get((0.0, 0.05))
    concentration_cap_gap: float | None = None
    if five_pct_result is not None:
        concentration_cap_gap = uncapped_result.expected_seats - five_pct_result.expected_seats
        logger.info(
            f"Concentration gap: {uncapped_result.expected_seats:.3f} (uncapped) − "
            f"{five_pct_result.expected_seats:.3f} (5% cap) = "
            f"{concentration_cap_gap:+.3f} seats"
        )

    # ── 8. Efficiency tests ───────────────────────────────────────────────────
    logger.info("Running efficiency tests…")
    efficiency = spearman_efficiency_test(races, outputs)
    misalloc = characterize_misallocation(
        races, outputs, [a.difference for a in allocation], budget
    )

    # ── 9. β_RC uncertainty propagation ──────────────────────────────────────
    uncertainty = None
    if not args.skip_uncertainty:
        logger.info("Running β_RC uncertainty propagation (K=1000 draws)…")
        uncertainty = propagate_beta_rc_uncertainty(
            races=races, beta_rc=beta_rc, coef=coef, sigma_model=sigma_model,
            factor_model=factor_model, budget=budget,
            gamma=0.0, cap_fraction=cap_baseline,
            party_budget=party_budget,
        )

    # ── 10. Benchmark comparisons ─────────────────────────────────────────────
    logger.info("Computing benchmark comparisons…")
    null_shares = null_equal_weight_shares(races)
    cook_shares = cook_proportional_shares(races)
    model_shares = primary_result.shares
    allocator_table = compare_allocators(races, outputs, model_shares, null_shares, cook_shares, budget)
    logger.info("\n" + allocator_table.to_string(index=False))

    # ── 11. Outputs ───────────────────────────────────────────────────────────
    logger.info("Building output tables…")
    race_table = build_race_table(races, outputs, allocation, uncertainty)
    aggregate = build_aggregate_summary(races, outputs, allocation, efficiency, budget,
                                       concentration_cap_gap=concentration_cap_gap,
                                       expected_seats_model=primary_result.expected_seats)
    save_outputs(race_table, aggregate, label=f"baseline{suffix}")

    # ── 12. Charts ────────────────────────────────────────────────────────────
    logger.info("Generating charts…")

    dccc_sd = math.sqrt(np.array([r.d_total / budget for r in races]) @ cov_matrix @
                        np.array([r.d_total / budget for r in races]))
    model_points = []
    for (g, cap), res in grid_results.items():
        if cap == cap_baseline:
            sd = math.sqrt(res.shares @ cov_matrix @ res.shares)
            model_points.append((res.expected_seats, sd, f"γ={g:.3f}"))

    null_sd  = math.sqrt(null_shares @ cov_matrix @ null_shares)
    cook_sd  = math.sqrt(cook_shares @ cov_matrix @ cook_shares)

    efficiency_frontier(
        dccc_point=(sum(o.p_win for o in outputs), dccc_sd),
        model_points=model_points,
        null_point=(
            sum(o.p_win for o in outputs),  # approximate
            null_sd
        ),
        save_path=out_dir / f"efficiency_frontier{suffix}.png",
    )

    allocation_difference_scatter(
        race_ids=[a.district_id for a in allocation],
        pvi_vals=[r.pvi for r in races],
        differences=[a.difference for a in allocation],
        cook_ratings=[r.cook_rating for r in races],
        save_path=out_dir / f"allocation_difference{suffix}.png",
    )

    logger.info(f"All outputs written to {out_dir}/")
    logger.info(
        f"\nSummary:\n"
        f"  Spearman ρ: {efficiency['rho']:.3f} (p={efficiency['p_value']:.4f})\n"
        f"  Competitive races: {efficiency['n_competitive']}\n"
        f"  Material divergence races: {aggregate['n_material_divergence']}\n"
        f"  Allocator comparison:\n{allocator_table.to_string(index=False)}"
    )


if __name__ == "__main__":
    main()
