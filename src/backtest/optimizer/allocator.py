"""
Portfolio optimizer: maximize E[Seats] − γ·Var[Seats]
subject to: Σ sᵢ ≤ B,  0 ≤ sᵢ ≤ cap·B

The objective is linearized around the observed 2024 spending allocation:

  E[Seats] ≈ Σ [P_win_i⁰ + MSG_i · (sᵢ − sᵢ⁰)]
            = const + Σ MSG_i · sᵢ

  Var[Seats] = sᵀ · Cov · s   (factor covariance matrix)

So the full objective is:
  maximize  Σ MSG_i · sᵢ − γ · sᵀ · Cov · s
  s.t.      Σ sᵢ ≤ B,  0 ≤ sᵢ ≤ cap · B

This is a standard quadratic program solved via cvxpy.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
import numpy as np
import cvxpy as cp
from ..types import ModelOutputs, AllocationResult, FactorModel

logger = logging.getLogger(__name__)


@dataclass
class OptimizerResult:
    """Allocation vector and objective diagnostics from one optimizer run."""
    allocations: np.ndarray       # (n_races,) dollar amounts
    shares: np.ndarray            # (n_races,) = allocations / B
    expected_seats: float
    var_seats: float
    objective_value: float
    budget_used: float
    status: str
    n_corner_solutions: int       # races at 0 or cap


def optimize(
    race_outputs: list[ModelOutputs],
    budget: float,
    cov_matrix: np.ndarray,
    gamma: float,
    cap_fraction: float,
) -> OptimizerResult:
    """
    Run the portfolio QP for a given γ and concentration cap.

    Parameters
    ----------
    race_outputs  : list of ModelOutputs (one per race, ordered consistently with cov_matrix)
    budget        : total Democratic-aligned budget B ($)
    cov_matrix    : (n_races × n_races) Cov(Yᵢ, Yⱼ) from FactorModel.race_covariance()
    gamma         : risk-aversion coefficient
    cap_fraction  : maximum fraction of B allocatable to any single race

    Returns
    -------
    OptimizerResult
    """
    n = len(race_outputs)
    msg = np.array([o.msg_i for o in race_outputs])
    p_win0 = np.array([o.p_win for o in race_outputs])

    s = cp.Variable(n, nonneg=True)
    cap = cap_fraction * budget

    constraints = [
        cp.sum(s) <= budget,
        s <= cap,
    ]

    if gamma == 0.0:
        # Pure LP — must NOT include quad_form (even × 0) or SCIPY treats it as QP
        # and may return an interior-point solution instead of a corner solution.
        objective = cp.Maximize(msg @ s)
        prob = cp.Problem(objective, constraints)
        for solver in [cp.SCIPY, cp.CLARABEL, cp.SCS]:
            try:
                prob.solve(solver=solver, verbose=False)
                if prob.status in ("optimal", "optimal_inaccurate"):
                    break
            except Exception:
                continue
    else:
        # QP: MSG · s − γ · sᵀ Cov s
        objective = cp.Maximize(msg @ s - gamma * cp.quad_form(s, cov_matrix))
        prob = cp.Problem(objective, constraints)
        for solver in [cp.CLARABEL, cp.SCS]:
            try:
                prob.solve(solver=solver, verbose=False)
                if prob.status in ("optimal", "optimal_inaccurate"):
                    break
            except Exception:
                continue

    if prob.status not in ("optimal", "optimal_inaccurate"):
        logger.warning(f"Optimizer status: {prob.status}")

    allocs = np.maximum(s.value if s.value is not None else np.zeros(n), 0.0)
    shares = allocs / budget

    # E[Seats] at recommended allocation (linearized)
    delta_s = allocs - np.array([o.p_win for o in race_outputs]) * budget / max(budget, 1)
    expected_seats = float(np.sum(p_win0) + np.dot(msg, allocs))
    var_seats = float(allocs @ cov_matrix @ allocs)

    tol = 1e-3 * budget
    n_corner = int(np.sum((allocs < tol) | (allocs > cap - tol)))

    return OptimizerResult(
        allocations=allocs,
        shares=shares,
        expected_seats=expected_seats,
        var_seats=var_seats,
        objective_value=float(prob.value) if prob.value is not None else float("nan"),
        budget_used=float(allocs.sum()),
        status=str(prob.status),
        n_corner_solutions=n_corner,
    )


def run_sensitivity_grid(
    race_outputs: list[ModelOutputs],
    budget: float,
    cov_matrix: np.ndarray,
    gamma_values: list[float],
    cap_fractions: list[float],
) -> dict[tuple[float, float], OptimizerResult]:
    """
    Run the optimizer across all (γ, cap) combinations.

    Returns dict keyed by (gamma, cap_fraction) → OptimizerResult.
    """
    results = {}
    for gamma in gamma_values:
        if gamma is None:
            continue
        for cap in cap_fractions:
            logger.info(f"Running optimizer: γ={gamma}, cap={cap:.0%}")
            results[(gamma, cap)] = optimize(race_outputs, budget, cov_matrix, gamma, cap)
    return results


def build_allocation_results(
    races: list,            # list[RaceRecord]
    race_outputs: list[ModelOutputs],
    optimizer_result: OptimizerResult,
    budget: float,
) -> list[AllocationResult]:
    """Convert optimizer shares to AllocationResult objects."""
    results = []
    for i, (race, out) in enumerate(zip(races, race_outputs)):
        observed_share = race.d_total / budget if budget > 0 else 0.0
        results.append(AllocationResult(
            district_id=race.district_id,
            recommended_share=float(optimizer_result.shares[i]),
            observed_share=observed_share,
            difference=float(optimizer_result.shares[i]) - observed_share,
        ))
    return results
