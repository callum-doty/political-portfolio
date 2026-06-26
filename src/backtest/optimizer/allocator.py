"""
Portfolio optimizer: maximize E[Seats] − γ·Var[Seats]
subject to: Σ party_i ≤ B_party,  0 ≤ party_i ≤ cap·B_party
            where party_i = total_i − cand_floor_i

E[Seats] = Σ Φ(μᵢ(Dᵢ) / σᵢ)  (non-linear in Dᵢ = cand_floor_i + party_i)

The non-linear form with direct Φ evaluation avoids the linear MSG approximation,
which breaks down for races with very low observed spending (1/D² sensitivity).
The LP formulation (MSG @ s) is kept only for the risk-penalized (γ>0) QP.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
import numpy as np
import cvxpy as cp
from scipy.optimize import minimize
from scipy.stats import norm as scipy_norm
from ..types import ModelOutputs, AllocationResult, RaceRecord
from ..model.margin import MarginModelCoefficients
from ..types import SigmaModel

logger = logging.getLogger(__name__)


@dataclass
class OptimizerResult:
    """Allocation vector and objective diagnostics from one optimizer run."""
    allocations: np.ndarray       # (n_races,) dollar amounts (total D spend)
    shares: np.ndarray            # (n_races,) = allocations / B_total
    expected_seats: float
    var_seats: float
    objective_value: float
    budget_used: float
    status: str
    n_corner_solutions: int       # races at floor or party cap


def _precompute_race_arrays(
    races: list[RaceRecord],
    coef: MarginModelCoefficients,
    sigma_model: SigmaModel,
    eta: float = 0.0,
) -> dict:
    """
    Pre-compute per-race static arrays for the non-linear optimizer.

    Parameters
    ----------
    eta : adversarial response coefficient (0 ≤ η ≤ 1).
          η = 0  → Republican spending fixed (retrospective mode).
          η = 0.5 → NRCC matches 50¢ per new DCCC dollar above observed.
          η = 1.0 → dollar-for-dollar matching (MSG → 0 at spending parity).
          Late-cycle deployments behave as if η ≈ 0 because ad inventory
          is exhausted and NRCC cannot effectively redirect capital.
    """
    n = len(races)
    pvi = np.array([r.pvi for r in races])
    abs_pvi = np.abs(pvi)
    incumb = np.array([1.0 if r.incumb_status == "Incumbent" else 0.0 for r in races])
    gb = np.array([r.generic_ballot for r in races])

    mu_const = (coef.alpha0
                + coef.alpha1 * pvi
                + coef.alpha2 * incumb
                + coef.alpha3 * gb)
    c_spend = coef.beta1 + coef.beta2 * abs_pvi + coef.beta3 * incumb
    # §8.3: open-seat Bayesian-shrunk elasticity overrides beta1 for open seats.
    if coef.beta1_open is not None:
        is_open = np.array([1.0 if r.incumb_status == "Open" else 0.0 for r in races])
        c_spend = np.where(is_open,
                           coef.beta1_open + coef.beta2 * abs_pvi,
                           c_spend)

    sigma = np.array([
        sigma_model.predict(abs_pvi[i], races[i].incumb_status, races[i].generic_ballot)
        for i in range(n)
    ])
    r_total = np.array([r.r_total for r in races])
    floors = np.array([r.cand_d_total for r in races])
    # Observed DCCC party spend per race (used as the η reaction threshold)
    party_obs = np.maximum(np.array([r.d_total for r in races]) - floors, 0.0)

    cvap = np.array([max(r.cvap, 1) for r in races])
    alpha4 = coef.alpha4

    return dict(mu_const=mu_const, c_spend=c_spend, sigma=sigma,
                r_total=r_total, floors=floors, cvap=cvap, alpha4=alpha4,
                party_obs=party_obs, eta=eta)


def _reactive_r(party: np.ndarray, arrays: dict) -> np.ndarray:
    """
    R_i(D_i) = R_i_base + η × max(0, party_i − party_i_obs)

    When DCCC increases spending above observed levels, the NRCC/CLF are
    assumed to partially match the increment at rate η.  Spending at or
    below observed levels draws no adversarial response.
    """
    eta = arrays["eta"]
    if eta == 0.0:
        return np.maximum(arrays["r_total"], 1.0)
    increment = np.maximum(party - arrays["party_obs"], 0.0)
    return np.maximum(arrays["r_total"] + eta * increment, 1.0)


def _p_win_vec(party: np.ndarray, arrays: dict) -> np.ndarray:
    """Return P_win vector given party allocations (with adversarial R if η > 0)."""
    d = np.maximum(arrays["floors"] + party, 1.0)
    r = _reactive_r(party, arrays)
    t = d + r
    ratio = np.clip(d / t, 1e-15, 1 - 1e-15)
    log_ratio = np.log(ratio)
    log_total_pv = np.log(t / arrays["cvap"])
    mu = arrays["mu_const"] + arrays["c_spend"] * log_ratio + arrays["alpha4"] * log_total_pv
    return scipy_norm.cdf(mu / arrays["sigma"])


def _msg_vec(party: np.ndarray, arrays: dict) -> np.ndarray:
    """
    Return MSG vector ∂P_win/∂party_i with adversarial R correction.

    With η > 0 and party_i > party_i_obs:
        ∂R/∂party_i = η  →  ∂t/∂party_i = 1 + η
        ∂log_ratio/∂party_i = 1/d − (1+η)/t        (vs 1/d − 1/t when η=0)

    At η=1, d=r (equal spending): gradient → 0, correctly capturing that
    NRCC dollar-for-dollar matching neutralizes log-ratio improvement.
    """
    eta = arrays["eta"]
    d = np.maximum(arrays["floors"] + party, 1.0)
    r = _reactive_r(party, arrays)
    t = d + r
    ratio = np.clip(d / t, 1e-15, 1 - 1e-15)
    log_ratio = np.log(ratio)
    log_total_pv = np.log(t / arrays["cvap"])
    mu = arrays["mu_const"] + arrays["c_spend"] * log_ratio + arrays["alpha4"] * log_total_pv
    sigma = arrays["sigma"]
    phi = scipy_norm.pdf(mu / sigma)

    # η penalty: only applies where party > party_obs (actual new spending)
    above_obs = (party > arrays["party_obs"]).astype(float)
    eta_eff = eta * above_obs   # 0 below observed, η above observed
    dt_dd = 1.0 + eta_eff      # ∂t/∂D = 1 + η (reactive), 1 (at/below obs)

    d_log_ratio_d_d = 1.0 / d - dt_dd / t          # corrected gradient
    d_log_total_pv_d_d = dt_dd / t                  # ∂log(t/cvap)/∂D = (∂t/∂D)/t
    d_mu_d_d = arrays["c_spend"] * d_log_ratio_d_d + arrays["alpha4"] * d_log_total_pv_d_d
    return (phi / sigma) * d_mu_d_d


def optimize_nonlinear(
    races: list[RaceRecord],
    coef: MarginModelCoefficients,
    sigma_model: SigmaModel,
    budget: float,
    cov_matrix: np.ndarray,
    gamma: float,
    cap_fraction: float,
    party_budget: float | None = None,
    eta: float = 0.0,
) -> OptimizerResult:
    """
    Non-linear portfolio optimizer using direct Φ(μ(D)/σ) evaluation.

    Parameters
    ----------
    races         : full race list with cand_d_total floors and r_total
    coef          : margin model coefficients
    sigma_model   : σᵢ model
    budget        : total D budget (used for shares computation)
    cov_matrix    : (n_races × n_races) factor covariance
    gamma         : risk-aversion coefficient (0.0 for pure E[Seats] max)
    cap_fraction  : max fraction of party_budget per race
    party_budget  : DCCC party budget. Defaults to sum(d_total - cand_floor).
    eta           : adversarial response coefficient (0 ≤ η ≤ 1).
                    NRCC/CLF match fraction of each new DCCC dollar above
                    observed spending. Set to 0 for retrospective analysis
                    or late-cycle deployment where γ ≈ 0 (ad inventory sold).
    """
    n = len(races)
    arrays = _precompute_race_arrays(races, coef, sigma_model, eta=eta)
    floors = arrays["floors"]

    pb = party_budget if party_budget is not None else float(np.sum(
        np.array([r.d_total for r in races]) - floors))
    cap = cap_fraction * pb

    # Initial point: observed party allocation scaled to fit constraints
    d_total_obs = np.array([r.d_total for r in races])
    party_obs = np.maximum(d_total_obs - floors, 0.0)
    # Clip to cap first, then rescale to meet the budget constraint
    party0 = np.minimum(party_obs, cap)
    total0 = party0.sum()
    if total0 > pb:
        party0 = party0 * (pb / total0)
    # party0 is now feasible: all in [0, cap] and sum <= pb

    # Scale party allocations to $M so SLSQP gradients are O(1).
    # Without scaling, MSG values (~1e-7 $/seat) × raw dollar variables (~1e7 $)
    # produce a projected Lagrangian that appears near-zero to SLSQP's ftol check,
    # causing premature convergence at the starting point after 1 iteration.
    SCALE = 1_000_000.0          # 1 dollar = 1e-6 scaled units
    pb_s = pb / SCALE
    cap_s = cap / SCALE
    party0_s = party0 / SCALE
    neg_ones = -np.ones(n)

    def neg_e_seats(xs: np.ndarray) -> float:
        return -float(_p_win_vec(xs * SCALE, arrays).sum())

    def neg_e_seats_grad(xs: np.ndarray) -> np.ndarray:
        msg = _msg_vec(xs * SCALE, arrays) * SCALE   # chain rule: dL/dxs = dL/dp * dp/dxs
        if gamma > 0:
            d = floors + xs * SCALE
            grad_var = 2.0 * (cov_matrix @ d) * SCALE
            return -(msg - gamma * grad_var)
        return -msg

    def budget_slack(xs: np.ndarray) -> float:
        return float(pb_s - xs.sum())

    def budget_slack_jac(xs: np.ndarray) -> np.ndarray:
        return neg_ones.copy()

    constraints = [{"type": "ineq", "fun": budget_slack, "jac": budget_slack_jac}]
    bounds = [(0.0, cap_s)] * n

    result = minimize(
        neg_e_seats,
        x0=party0_s,
        method="SLSQP",
        jac=neg_e_seats_grad,
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 1000 if eta > 0 else 500, "ftol": 1e-10},
    )

    party_opt = np.maximum(result.x * SCALE, 0.0)
    allocs = floors + party_opt  # total D spend
    shares = allocs / budget

    p_win_final = _p_win_vec(party_opt, arrays)
    e_seats = float(p_win_final.sum())
    d_total_arr = allocs
    var_seats = float(d_total_arr @ cov_matrix @ d_total_arr)

    tol = 1e-3 * pb
    n_corner = int(np.sum((party_opt < tol) | (party_opt > cap - tol)))

    status = "optimal" if result.success else f"slsqp:{result.message}"

    return OptimizerResult(
        allocations=allocs,
        shares=shares,
        expected_seats=e_seats,
        var_seats=var_seats,
        objective_value=float(-result.fun),
        budget_used=float(allocs.sum()),
        status=status,
        n_corner_solutions=n_corner,
    )


def optimize(
    race_outputs: list[ModelOutputs],
    budget: float,
    cov_matrix: np.ndarray,
    gamma: float,
    cap_fraction: float,
    floor_allocations: np.ndarray | None = None,
    party_budget: float | None = None,
) -> OptimizerResult:
    """
    LP/QP optimizer using linearized MSG objective (kept for γ>0 QP).

    For γ=0, prefer optimize_nonlinear() which correctly handles diminishing
    returns. This function is retained for the risk-penalized case and for
    the uncertainty propagation inner loop (faster than non-linear).

    Parameters
    ----------
    race_outputs      : list of ModelOutputs with pre-computed MSG and P_win
    budget            : total D budget ($)
    cov_matrix        : (n_races × n_races) covariance
    gamma             : risk-aversion coefficient
    cap_fraction      : max fraction of party_budget per race
    floor_allocations : (n_races,) candidate spending floor
    party_budget      : DCCC party budget. Defaults to budget.
    """
    n = len(race_outputs)
    msg = np.array([o.msg_i for o in race_outputs])
    p_win0 = np.array([o.p_win for o in race_outputs])

    floors = floor_allocations if floor_allocations is not None else np.zeros(n)
    pb = party_budget if party_budget is not None else budget
    cap = cap_fraction * pb

    s = cp.Variable(n)
    party = s - floors

    constraints = [
        cp.sum(party) <= pb,
        party >= 0,
        party <= cap,
    ]

    # If γ × max_var is negligible vs MSG scale, treat as risk-neutral LP.
    _msg_scale = max(float(np.abs(msg).max()), 1e-12)
    _var_scale = float(np.abs(cov_matrix).max()) if cov_matrix.size > 0 else 0.0
    _use_lp = (gamma == 0.0) or (gamma * _var_scale * pb ** 2 < 1e-6 * _msg_scale * pb)

    if _use_lp:
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
        objective = cp.Maximize(msg @ s - gamma * cp.quad_form(s, cov_matrix))
        prob = cp.Problem(objective, constraints)
        solved = False
        for solver in [cp.CLARABEL, cp.SCS]:
            try:
                prob.solve(solver=solver, verbose=False)
                if prob.status in ("optimal", "optimal_inaccurate"):
                    solved = True
                    break
            except Exception:
                continue
        if not solved:
            # QP degenerate (near-zero γ or ill-conditioned cov) — fall back to LP
            logger.warning("QP solver infeasible/failed — falling back to LP (γ≈0 degeneracy)")
            objective = cp.Maximize(msg @ s)
            prob = cp.Problem(objective, constraints)
            for solver in [cp.SCIPY, cp.CLARABEL, cp.SCS]:
                try:
                    prob.solve(solver=solver, verbose=False)
                    if prob.status in ("optimal", "optimal_inaccurate"):
                        break
                except Exception:
                    continue

    if prob.status not in ("optimal", "optimal_inaccurate"):
        logger.warning(f"Optimizer status: {prob.status}")

    allocs = np.maximum(s.value if s.value is not None else floors.copy(), floors)
    shares = allocs / budget

    observed = np.array([p + f for p, f in zip(p_win0 * budget / max(budget, 1), floors)])
    expected_seats = float(np.sum(np.clip(
        p_win0 + msg * (allocs - np.array([0.0] * n)), 0.0, 1.0)))
    var_seats = float(allocs @ cov_matrix @ allocs)

    tol = 1e-3 * pb
    party_allocs = allocs - floors
    n_corner = int(np.sum((party_allocs < tol) | (party_allocs > cap - tol)))

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
    floor_allocations: np.ndarray | None = None,
    party_budget: float | None = None,
    races: list[RaceRecord] | None = None,
    coef: MarginModelCoefficients | None = None,
    sigma_model: SigmaModel | None = None,
    eta: float = 0.0,
) -> dict[tuple[float, float], OptimizerResult]:
    """
    Run the optimizer across all (γ, cap) combinations.

    Uses optimize_nonlinear for γ=0 (if races/coef/sigma_model provided)
    and optimize (LP/QP) for γ>0.

    eta : adversarial response coefficient passed to optimize_nonlinear.
    Returns dict keyed by (gamma, cap_fraction) → OptimizerResult.
    """
    results = {}
    for gamma in gamma_values:
        if gamma is None:
            continue
        for cap in cap_fractions:
            label = f"γ={gamma}, cap={cap:.0%}" + (f", η={eta}" if eta > 0 else "")
            logger.info(f"Running optimizer: {label}")
            if gamma == 0.0 and races is not None and coef is not None and sigma_model is not None:
                results[(gamma, cap)] = optimize_nonlinear(
                    races, coef, sigma_model, budget, cov_matrix, gamma, cap,
                    party_budget=party_budget, eta=eta)
            else:
                results[(gamma, cap)] = optimize(
                    race_outputs, budget, cov_matrix, gamma, cap,
                    floor_allocations=floor_allocations, party_budget=party_budget)
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
