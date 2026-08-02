#!/usr/bin/env python3
"""
Item (5) of Section 8.9's investigation plan: a validated fast surrogate
for optimize_nonlinear() that preserves diminishing returns, unlike the LP
allocator, but runs at LP speed rather than SLSQP speed (40s-3,600s/call).

Key structural fact this exploits, confirmed by reading _reactive_r()
before assuming it: R_i(party_i) depends ONLY on race i's own party
spending, not on any other race's allocation. This means the TRUE
objective sum_i Phi(mu_i'(party_i)/sigma_i) -- even with opponent reaction
and the persuasion ceiling both included -- is fully SEPARABLE across
races, subject only to the budget and per-race cap constraints. A
separable-concave resource-allocation problem of this form has a classic,
exactly-optimal solution once each race's payoff function is replaced by
its piecewise-linear concave envelope: sort every (race, segment) pair by
marginal slope, descending, and allocate greedily until the budget is
exhausted (a discrete water-filling algorithm). This is NOT a heuristic
approximation to the piecewise-linear relaxation -- it is the exact
optimum of that relaxation -- and it runs in O(n_races * n_grid_points *
log(...)) time (a sort), not an iterative nonlinear solve.

Validation (not assumed, checked): compare the surrogate's allocation,
objective value, funded-race count, and concentration against the TRUE
optimize_nonlinear() at the same states already used for the period
decomposition (scripts/theta_lp_vs_nonlinear_period_decomposition.py),
before this surrogate is trusted for anything.

Output: outputs/theta_concave_surrogate_validation.json
"""

from __future__ import annotations
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import solve_bellman_lsm as lsm
from backtest.optimizer.allocator import (
    optimize_nonlinear, _precompute_race_arrays, _reactive_r, _apply_ceiling,
)
import theta_lp_vs_nonlinear_period_decomposition as pd

N_GRID = 40   # per-race breakpoints from 0 to cap


def race_payoff_at_party(party: np.ndarray, arrays: dict) -> np.ndarray:
    """f_i(party_i) = Phi(mu_i'(party_i)/sigma_i), vectorized over races at
    a SHARED party vector -- used here only to evaluate a grid, race by
    race, with all OTHER races' party held at whatever `party` specifies
    (irrelevant to race i's own value, by separability, but computing all
    races at once per grid point is far cheaper than a python loop)."""
    d = np.maximum(arrays["floors"] + party, 1.0)
    r = _reactive_r(party, arrays)
    t_ = d + r
    ratio = np.clip(d / t_, 1e-15, 1 - 1e-15)
    log_ratio = np.log(ratio)
    log_total_pv = np.log(t_ / arrays["cvap"])
    mu_raw = arrays["mu_const"] + arrays["c_spend"] * log_ratio + arrays["alpha4"] * log_total_pv
    mu_capped, _ = _apply_ceiling(mu_raw, arrays)
    return norm.cdf(mu_capped / arrays["sigma"])


def build_concave_segments(arrays: dict, cap: np.ndarray, n_grid: int = N_GRID):
    """For each race, evaluate f_i on a grid of party$ from 0 to cap_i,
    then take the concave (upper) envelope of the resulting breakpoints so
    segment slopes are guaranteed non-increasing -- required for the greedy
    algorithm's optimality guarantee to hold exactly, not approximately.
    Returns arrays of (race_idx, width, slope, x_start) for every segment
    surviving the envelope step."""
    n = len(cap)
    grid_fracs = np.linspace(0.0, 1.0, n_grid + 1)
    xs = grid_fracs[None, :] * cap[:, None]              # (n, n_grid+1)
    fs = np.zeros_like(xs)
    for k in range(n_grid + 1):
        party_k = xs[:, k]
        fs[:, k] = race_payoff_at_party(party_k, arrays)

    race_idx_list, width_list, slope_list, xstart_list = [], [], [], []
    for i in range(n):
        x_i, f_i = xs[i], fs[i]
        # Upper concave envelope via a monotone stack (classic "convex hull
        # trick" applied to a maximization/concave problem): process
        # breakpoints left to right, popping any preceding segment whose
        # slope is EXCEEDED by the new one (that would violate concavity --
        # a later segment steeper than an earlier one is impossible for a
        # genuinely concave function, so its presence means an earlier
        # breakpoint was on the "wrong side" of the true concave envelope).
        pts_x = [x_i[0]]
        pts_f = [f_i[0]]
        for k in range(1, len(x_i)):
            while len(pts_x) >= 2:
                slope_prev = (pts_f[-1] - pts_f[-2]) / (pts_x[-1] - pts_x[-2])
                slope_new = (f_i[k] - pts_f[-1]) / (x_i[k] - pts_x[-1])
                if slope_new >= slope_prev - 1e-15:
                    pts_x.pop(); pts_f.pop()
                else:
                    break
            pts_x.append(x_i[k]); pts_f.append(f_i[k])
        for k in range(len(pts_x) - 1):
            w = pts_x[k + 1] - pts_x[k]
            if w <= 0:
                continue
            slope = (pts_f[k + 1] - pts_f[k]) / w
            race_idx_list.append(i); width_list.append(w)
            slope_list.append(slope); xstart_list.append(pts_x[k])

    return (np.array(race_idx_list), np.array(width_list),
            np.array(slope_list), np.array(xstart_list))


def greedy_allocate(race_idx, width, slope, xstart, n_races, budget) -> np.ndarray:
    """Exact optimum of the piecewise-linear-concave relaxation: sort all
    segments by slope descending, fill greedily until budget exhausted."""
    order = np.argsort(-slope)
    party = np.zeros(n_races)
    remaining = budget
    for k in order:
        if remaining <= 0:
            break
        take = min(width[k], remaining)
        party[race_idx[k]] += take
        remaining -= take
    return party


def surrogate_allocate(races, coef, sigma_model, budget, cap_fraction, eta, n_grid=N_GRID):
    arrays = _precompute_race_arrays(races, coef, sigma_model, eta=eta)
    n = len(races)
    cap = cap_fraction * budget * np.ones(n)
    t0 = time.time()
    race_idx, width, slope, xstart = build_concave_segments(arrays, cap, n_grid)
    party = greedy_allocate(race_idx, width, slope, xstart, n, budget)
    elapsed = time.time() - t0
    return party, elapsed


def validate_at_period(tstep: int):
    state = pd.build_state()
    d_t, r_t, mu_t = pd.state_at_period(state, tstep)
    n = state["n"]
    races, coef, sigma_model = state["races"], state["coef"], state["sigma_model"]
    eta_arr = state["eta_arr"]

    import dataclasses
    races_t = [dataclasses.replace(r, cand_d_total=float(d_t[i]), r_total=float(r_t[i]),
                                    d_total=float(d_t[i])) for i, r in enumerate(races)]

    t0 = time.time()
    res_nl = optimize_nonlinear(races_t, coef, sigma_model, budget=lsm.F0, cov_matrix=np.eye(n) * 1e-6,
                                 gamma=0.0, cap_fraction=0.15, party_budget=lsm.F0, eta=eta_arr)
    nl_elapsed = time.time() - t0
    arrays_nl = _precompute_race_arrays(races_t, coef, sigma_model, eta=eta_arr)
    party_nl = np.maximum(res_nl.allocations - d_t, 0.0)
    nl_value = float(race_payoff_at_party(party_nl, arrays_nl).sum())

    arrays_sur = _precompute_race_arrays(races_t, coef, sigma_model, eta=eta_arr)
    party_sur, sur_elapsed = surrogate_allocate(races_t, coef, sigma_model, lsm.F0, 0.15, eta_arr)
    sur_value = float(race_payoff_at_party(party_sur, arrays_sur).sum())

    def stats(party):
        n_funded = int(np.sum(party > 1.0))
        top5 = np.sort(party)[::-1][:5].sum()
        total = party.sum()
        return n_funded, float(top5 / total) if total > 0 else 0.0

    nl_funded, nl_conc = stats(party_nl)
    sur_funded, sur_conc = stats(party_sur)

    result = {
        "period": tstep, "days_remaining": (lsm.N_PERIODS - tstep) * lsm.PERIOD_DAYS,
        "nonlinear_value": nl_value, "surrogate_value": sur_value,
        "value_diff_surrogate_minus_nonlinear": sur_value - nl_value,
        "nonlinear_elapsed_s": nl_elapsed, "surrogate_elapsed_s": sur_elapsed,
        "nonlinear_n_funded": nl_funded, "nonlinear_top5_share": nl_conc,
        "surrogate_n_funded": sur_funded, "surrogate_top5_share": sur_conc,
    }
    print(f"  t={tstep} ({result['days_remaining']}d left): "
          f"nonlinear={nl_value:.4f} ({nl_elapsed:.1f}s, n_funded={nl_funded}, top5={nl_conc:.2%})  "
          f"surrogate={sur_value:.4f} ({sur_elapsed:.3f}s, n_funded={sur_funded}, top5={sur_conc:.2%})  "
          f"diff={sur_value - nl_value:+.4f}")
    return result


def main():
    print("Validating concave-envelope greedy surrogate against optimize_nonlinear()...")
    results = [validate_at_period(t) for t in [0, 2, 4, 6]]
    out_path = Path(__file__).parent.parent / "outputs/theta_concave_surrogate_validation.json"
    with open(out_path, "w") as f:
        json.dump({"n_grid": N_GRID, "results": results}, f, indent=2, default=str)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
