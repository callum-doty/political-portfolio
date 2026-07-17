#!/usr/bin/env python3
"""
Longstaff-Schwartz backward induction for Theta(t) (Paper III Section 7.2),
run only after Section 7.1's simulator self-consistency gate passed.

Setup: 2026 live universe (434 races), "wait" branch simulated forward
(no discretionary deployment -- candidate-committee floors only; R_i,t
moves via residual noise only, since eta fires only in reaction to a
deployment that never happens on this branch), K paths, biweekly periods
from today to Election Day 2026-11-03.

Per (path, period), two values are compared:
  - "Deploy now": close the discretionary reserve immediately via the fast
    LP allocator (optimize(), ~11ms/call -- the full nonlinear optimizer
    was benchmarked and is computationally infeasible at Monte Carlo path
    counts), apply the resulting Delta_mu_i via Paper I's chain-rule
    gradient, then apply the closed-form "let remaining drift resolve"
    widening: Phi((mu_i,t + Delta_mu_i) / sqrt(sigma_i^2 + V_i(t))).
    sigma_i (Paper I's static residual) and V_i(t) (Paper III's remaining-
    drift variance, Section 7.1) are ADDITIVE, not substitutive: mu_i,T =
    mu_i,t + Delta_mu_i + xi, xi ~ N(0, V_i(t)), and
    E[Phi((mu+xi)/sigma)] = Phi(mu / sqrt(sigma^2 + V)) by the standard
    normal-CDF-convolution identity.
  - "Wait": regression-estimated continuation value, basis = Section
    7.2's four compressed features (E[Seats]_t, Var[Seats]_t, max MSG_t,
    near-threshold count), fit on paths' own realized V*_{t+1}.

Var[Seats]_t here is Sum_i p_i(1-p_i) -- an independence approximation,
not Paper I's full factor-covariance model -- stated explicitly as a
simplification of this first pass, not a silent omission.

Run twice -- eta fit on 2022 only, eta fit on 2024 only -- bracketing
Theta per the cycle-instability caveat already on record (Section 5.5).

Output: outputs/theta_schedule.json
"""

from __future__ import annotations
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from backtest import config
from backtest.data.universe import build_universe
from backtest.model.margin import MarginModelCoefficients
from backtest.model.win_prob import compute_outputs_batch
from backtest.optimizer.allocator import optimize
from backtest.types import SigmaModel, ModelOutputs

from estimate_eta_reaction import build_period_panel, build_delta_panel, TIERS
from simulate_and_validate import incremental_variances, remaining_variance, SIGMA_G_PER_SQRT_DAY

ROOT = Path(__file__).parent.parent
RNG = np.random.default_rng(20260716)

# Single source of truth: data/processed/live_2026_state.json, written by
# scripts/plot_2026_live_allocation.py. Previously TODAY/ELECTION_DAY/F0 were
# independent hardcoded literals here -- a stale TODAY already caused a real
# 98-vs-110-days-remaining mismatch against scripts/make_theta_paper_figures.py
# before this fix (Paper III audit, 2026-07-16).
with open(ROOT / "data/processed/live_2026_state.json") as _f:
    _live_state = json.load(_f)

PERIOD_DAYS = config.period_days()
TODAY = date.fromisoformat(_live_state["as_of"])
ELECTION_DAY = date.fromisoformat(_live_state["election_day"])
N_PERIODS = max(1, (ELECTION_DAY - TODAY).days // PERIOD_DAYS)
K_PATHS = 2000
COMPETITIVE = {"Toss-Up", "Lean D", "Lean R"}
NEAR_THRESHOLD_MARGIN_PP = 3.0   # points, matching Section 7.2's stated "e.g. 2 points" spec (widened slightly for path-count stability)
F0 = _live_state["f0"]          # deployable capital, single source of truth (Paper II Section 7.1's live figure)


def load_coef_and_sigma():
    with open(ROOT / "data/processed/margin_model_coef.json") as f:
        d = json.load(f)
    coef = MarginModelCoefficients(
        **{k: d[k] for k in ["alpha0", "alpha1", "alpha2", "alpha3", "alpha4",
                              "beta1", "beta2", "beta3"]},
        alpha5=d.get("alpha5", 0.0), beta1_open=d.get("beta1_open"),
    )
    with open(ROOT / "data/processed/sigma_model.json") as f:
        sigma_coef = json.load(f)
    return coef, SigmaModel(_coef=sigma_coef)


def fit_eta_and_resid(fit_cycle: int) -> tuple[dict, dict]:
    panel = build_period_panel(fit_cycle)
    delta = build_delta_panel(panel)
    eta_by_tier, resid_std_by_tier = {}, {}
    for tier in TIERS:
        mask = delta["tier"] == tier
        if mask.sum() < 10:
            continue
        X = sm.add_constant(delta.loc[mask, "d_ie_delta_lag_dm"])
        y = delta.loc[mask, "r_ie_delta_dm"]
        fit = sm.OLS(y, X).fit()
        eta_by_tier[tier] = float(fit.params.get("d_ie_delta_lag_dm", 0.0))
        resid_std_by_tier[tier] = float(fit.resid.std())
    return eta_by_tier, resid_std_by_tier


def margin_gradient(coef, pvi, incumb_status, d_total, r_total, eta: float = 0.0) -> float:
    """d(mu_i)/d(D_i), Part I Section I.5's chain rule.

    eta=0 (default): holds R fixed, c*(1/D - 1/T) [algebraically c*R/(D*T)].
    eta>0: R reacts dollar-for-dollar at rate eta to new D spend (dT/dD=1+eta),
    matching allocator.py's _msg_vec eta-adjusted gradient (docs/theta_followup_plan.md
    Section 0.1.2) -- the entire deploy-branch increment is "new" spend from a
    d_total floor baseline, so unlike _reactive_r's party_obs threshold there is
    no "already-observed" spend to gate the reaction on here.
    """
    c = coef.beta1 + coef.beta2 * abs(pvi) + coef.beta3 * (1.0 if incumb_status == "Incumbent" else 0.0)
    if incumb_status == "Open" and coef.beta1_open is not None:
        c = coef.beta1_open + coef.beta2 * abs(pvi)
    d = max(d_total, 1.0)
    t = max(d_total + r_total, 1.0)
    return c * (1.0 / d - (1.0 + eta) / t)


def run_lsm(eta_by_tier: dict, resid_std_by_tier: dict, label: str) -> dict:
    coef, sigma_model = load_coef_and_sigma()
    races = build_universe(cycle=2026)
    n = len(races)
    outputs0 = compute_outputs_batch(races, coef, sigma_model)
    sigma_arr = np.array([o.sigma_i for o in outputs0])
    pvi_arr = np.array([r.pvi for r in races])
    incumb_arr = [r.incumb_status for r in races]
    floor_arr = np.array([r.cand_d_total for r in races])
    r0_arr = np.array([r.r_total for r in races])
    tiers = [r.cook_rating for r in races]
    is_comp = np.array([t in COMPETITIVE for t in tiers])
    gb_national = races[0].generic_ballot
    is_incumb_arr = np.array([1.0 if s == "Incumbent" else 0.0 for s in incumb_arr])
    resid_std_arr = np.array([resid_std_by_tier.get(t, 0.0) for t in tiers])
    eta_arr = np.array([eta_by_tier.get(t, 0.0) for t in tiers])

    # --- Simulate the "wait" branch forward: R moves via residual noise only ---
    # NOTE (docs/theta_followup_plan.md Section 0.1.1): eta_arr is NOT applied here.
    # Giving eta something to react to on this branch requires a non-discretionary
    # baseline spending trickle (e.g. candidate-committee floor growth); that
    # requires a dated candidate-committee disbursement panel, which does not
    # exist in this repository -- `candidate_disbursements_{cycle}.csv` is
    # cycle-cumulative-final only (TTL_DISB), the same permanent gap
    # `dynamic/ledger.py`'s RealizedSpendCommitmentSource docstring already
    # documents for coordinated expenditures. D_i,t is therefore still held
    # exactly fixed while waiting, so eta still cannot fire on this branch --
    # not a bug, a real, reported data constraint. eta IS wired into the
    # deploy branch below (Section 0.1.2), where the full deployed amount is
    # unambiguously "new" spend and no dated panel is needed.
    r_paths = np.zeros((K_PATHS, N_PERIODS + 1, n))
    r_paths[:, 0, :] = r0_arr
    for tstep in range(N_PERIODS):
        r_paths[:, tstep + 1, :] = r_paths[:, tstep, :] + RNG.normal(0, resid_std_arr, size=(K_PATHS, n))
    r_paths = np.maximum(r_paths, 1.0)

    # --- Simulate G_t (Section 0.1.3): standalone zero-drift random walk, matching
    # simulate_and_validate.py's construction. NOT fed into mu_i's structural
    # formula -- alpha3 was estimated entirely from between-cycle variation
    # (paper3_draft.md Section 5.5's scope boundary) -- only tracked as a state
    # variable and added below as a fifth continuation-value regression feature,
    # so the LSM step can pick up a G_t-dependent effect empirically if one
    # exists, without applying alpha3 to an estimand it was never fit against.
    # scripts/estimate_gb_ou_drift.py fit an OU-with-drift model on the pooled
    # 4-cycle series and found the drift term statistically indistinguishable
    # from zero (p=0.37) and numerically negligible over the ~110 remaining days
    # to Election Day (implied E[delta_G] = -0.02 points, vs sigma_G~2 points at
    # that horizon) -- consistent with Section 5.3's finding that RW is a good
    # approximation at this horizon, so a zero-drift walk is used here.
    g_step_std = SIGMA_G_PER_SQRT_DAY * np.sqrt(PERIOD_DAYS)
    g_paths = np.cumsum(RNG.normal(0, g_step_std, size=(K_PATHS, N_PERIODS)), axis=1)
    g_paths = np.concatenate([np.zeros((K_PATHS, 1)), g_paths], axis=1)   # G_0 = 0 (relative to today)

    eps_cum = np.zeros((K_PATHS, N_PERIODS + 1, n))
    for i in range(n):
        v = incremental_variances(sigma_arr[i], N_PERIODS)
        incr = RNG.normal(0, np.sqrt(v), size=(K_PATHS, N_PERIODS))
        eps_cum[:, 1:, i] = np.cumsum(incr, axis=1)

    # mu_i,t = structural(floor D fixed, simulated R_t, static GB) + accumulated epsilon
    mu_paths = np.zeros((K_PATHS, N_PERIODS + 1, n))
    for tstep in range(N_PERIODS + 1):
        d_t = floor_arr[None, :]
        t_t = d_t + r_paths[:, tstep, :]
        ratio = np.clip(d_t / t_t, 1e-6, 1 - 1e-6)
        log_ratio = np.log(ratio)
        c_arr = coef.beta1 + coef.beta2 * np.abs(pvi_arr)[None, :] + coef.beta3 * is_incumb_arr[None, :]
        mu_struct = (coef.alpha0 + coef.alpha1 * pvi_arr[None, :] + coef.alpha2 * is_incumb_arr[None, :]
                     + coef.alpha3 * gb_national + c_arr * log_ratio)
        mu_paths[:, tstep, :] = mu_struct + eps_cum[:, tstep, :]

    def _deploy_value(mu_t, r_t, widened_sigma):
        """Close the reserve now via the LP allocator, apply the resulting
        Delta_mu via the chain-rule gradient, then evaluate expected seats
        against widened_sigma (sigma_i, or sqrt(sigma_i^2+V_i(t)) if time
        remains). Shared by the terminal condition and every backward step
        so both use identical mechanics -- this is the fix for a bug this
        session found via a smoke test: the terminal value must ALSO
        deploy, or it is not a valid anchor for the recursion.

        grad now uses eta_arr (Section 0.1.2): the LP's linearized gradient
        is discounted by each race's tier-specific opponent-reaction rate,
        since the entire deploy_now increment is new spend against which R
        reacts at eta -- previously eta_by_tier was computed and reported
        but never multiplied into anything in this function."""
        d_t = floor_arr.copy()
        p_win0 = norm.cdf(mu_t / sigma_arr)
        phi0 = norm.pdf(mu_t / sigma_arr)
        grad = np.array([margin_gradient(coef, pvi_arr[i], incumb_arr[i], d_t[i], r_t[i], eta_arr[i])
                          for i in range(n)])
        msg = phi0 / sigma_arr * grad
        outs = [ModelOutputs(district_id=races[i].district_id, ratio=d_t[i] / (d_t[i] + r_t[i]),
                              mu_hat=mu_t[i], sigma_i=sigma_arr[i], p_win=p_win0[i], msg_i=msg[i])
                for i in range(n)]
        res = optimize(outs, budget=F0, cov_matrix=np.eye(n) * 1e-6,
                        gamma=0.0, cap_fraction=0.15, floor_allocations=d_t, party_budget=F0)
        delta_s = np.maximum(res.allocations - d_t, 0.0)
        delta_mu = grad * delta_s
        deployed_mu = mu_t + delta_mu
        return norm.cdf(deployed_mu / widened_sigma).sum()

    # --- Backward induction ---
    remaining_days = np.array([(N_PERIODS - t) * PERIOD_DAYS for t in range(N_PERIODS + 1)])

    print(f"  [{label}] computing terminal condition (forced deploy, {K_PATHS} paths)...")
    V_star = np.array([
        _deploy_value(mu_paths[k, -1, :], r_paths[k, -1, :], sigma_arr)   # V=0 at T: no widening
        for k in range(K_PATHS)
    ])

    theta_by_period = []
    for tstep in range(N_PERIODS - 1, -1, -1):
        v_remaining = remaining_variance(sigma_arr, remaining_days[tstep])   # vectorized over races
        widened_sigma = np.sqrt(sigma_arr ** 2 + v_remaining)

        deploy_vals = np.array([
            _deploy_value(mu_paths[k, tstep, :], r_paths[k, tstep, :], widened_sigma)
            for k in range(K_PATHS)
        ])

        # Compressed basis, evaluated at period t (unwidened -- standard convention, matches Section 5.5's Validation A)
        p_win_t = norm.cdf(mu_paths[:, tstep, :] / sigma_arr[None, :])
        phi_t = norm.pdf(mu_paths[:, tstep, :] / sigma_arr[None, :])
        e_seats_t = p_win_t.sum(axis=1)
        var_seats_t = (p_win_t * (1 - p_win_t))[:, is_comp].sum(axis=1)   # independence approximation, stated explicitly
        max_msg_t = (phi_t / sigma_arr[None, :])[:, is_comp].max(axis=1)
        near_thresh_t = (np.abs(mu_paths[:, tstep, :][:, is_comp]) < NEAR_THRESHOLD_MARGIN_PP).sum(axis=1)
        g_t = g_paths[:, tstep]   # 5th feature (Section 0.1.3) -- G_t as a state descriptor only,
                                  # never fed into mu_i's structural formula (Section 5.5's scope boundary)

        # has_constant="add" (not the default "skip"): g_t is deterministically 0 for every
        # path at tstep=0 (G_0=0), which add_constant's default treats as an already-present
        # constant column and skips adding its own intercept -- silently shrinking X from 6
        # columns to 5 rather than raising, first caught via an IndexError on cont_fit.params[5].
        X = sm.add_constant(np.column_stack([e_seats_t, var_seats_t, max_msg_t, near_thresh_t, g_t]),
                             has_constant="add")
        cont_fit = sm.OLS(V_star, X).fit()
        wait_vals = cont_fit.predict(X)

        theta_t = wait_vals - deploy_vals
        deploy_now = deploy_vals >= wait_vals
        V_star = np.where(deploy_now, deploy_vals, wait_vals)

        theta_by_period.append({
            "period": tstep, "days_remaining": int(remaining_days[tstep]),
            "mean_theta": float(np.mean(theta_t)), "frac_deploy_now": float(np.mean(deploy_now)),
            "basis_r2": float(cont_fit.rsquared),
            "g_t_coef": float(cont_fit.params[5]), "g_t_pvalue": float(cont_fit.pvalues[5]),
        })
        print(f"  [{label}] t={tstep} ({remaining_days[tstep]}d left): "
              f"mean Theta={np.mean(theta_t):+.4f} seats, frac(deploy now)={np.mean(deploy_now):.3f}, "
              f"basis R2={cont_fit.rsquared:.3f}, g_t_coef={cont_fit.params[5]:+.5f} (p={cont_fit.pvalues[5]:.3f})")

    theta_by_period = list(reversed(theta_by_period))
    return {"label": label, "eta_by_tier": eta_by_tier, "n_periods": N_PERIODS, "k_paths": K_PATHS,
            "theta_by_period": theta_by_period}


def main():
    print(f"N_PERIODS={N_PERIODS} ({N_PERIODS*PERIOD_DAYS} days), K_PATHS={K_PATHS}\n")
    results = {}
    for label, fit_cycle in [("eta_fit_2022", 2022), ("eta_fit_2024", 2024)]:
        print(f"=== {label} ===")
        eta_by_tier, resid_std_by_tier = fit_eta_and_resid(fit_cycle)
        print(f"  eta(tier): {eta_by_tier}")
        res = run_lsm(eta_by_tier, resid_std_by_tier, label)
        results[label] = res

    out_path = ROOT / "outputs/theta_schedule.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
