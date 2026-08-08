"""
Tests for src/backtest/optimizer/robust.py -- robust/max-min-over-eta
optimization (docs/theta_followup_plan.md Section 6), reduced to a single
optimize_nonlinear() call at the per-race worst-case eta, verified post-hoc
for the monotonicity assumption that reduction depends on.
"""

from __future__ import annotations

import numpy as np
import pytest

from backtest.types import RaceRecord
from backtest.optimizer import robust
from backtest.optimizer.allocator import optimize_nonlinear


def _race(district_id, cook_rating, incumb_status, pvi, d_total, r_total,
          cand_d_total, generic_ballot=2.0, cvap=500_000):
    return RaceRecord(
        district_id=district_id, state=district_id.split("-")[0], district=1,
        cook_rating=cook_rating, incumb_status=incumb_status, pvi=pvi,
        d_total=d_total, r_total=r_total, cvap=cvap,
        generic_ballot=generic_ballot, cand_d_total=cand_d_total,
    )


@pytest.fixture
def synthetic_races():
    return [
        _race("TX-01", "Safe D", "Incumbent", pvi=20.0, d_total=500_000, r_total=100_000, cand_d_total=400_000),
        _race("OH-02", "Toss-Up", "Open", pvi=0.0, d_total=300_000, r_total=300_000, cand_d_total=200_000),
        _race("PA-03", "Lean D", "Incumbent", pvi=3.0, d_total=250_000, r_total=200_000, cand_d_total=150_000),
        _race("MI-04", "Lean R", "Challenger", pvi=-3.0, d_total=200_000, r_total=250_000, cand_d_total=100_000),
        _race("FL-05", "Safe R", "Challenger", pvi=-20.0, d_total=50_000, r_total=500_000, cand_d_total=40_000),
    ]


@pytest.fixture
def coef_sigma():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import solve_bellman_lsm as lsm
    return lsm.load_coef_and_sigma()


@pytest.fixture
def eta_uncertainty_by_tier():
    return {
        "Safe D": {"bootstrap": {"p95": 0.6}},
        "Toss-Up": {"bootstrap": {"p95": 0.9}},
        "Lean D": {"bootstrap": {"p95": 0.5}},
        "Lean R": {"bootstrap": {"p95": 0.4}},
        "Safe R": {"bootstrap": {"p95": 0.3}},
    }


class TestEtaHighByRace:
    def test_maps_each_race_to_its_own_tiers_p95(self, synthetic_races, eta_uncertainty_by_tier):
        result = robust.eta_high_by_race(synthetic_races, eta_uncertainty_by_tier)
        assert result[0] == pytest.approx(0.6)   # Safe D
        assert result[1] == pytest.approx(0.9)   # Toss-Up
        assert result[4] == pytest.approx(0.3)   # Safe R

    def test_missing_tier_falls_back_to_zero_not_a_crash(self, synthetic_races):
        result = robust.eta_high_by_race(synthetic_races, {})
        np.testing.assert_array_equal(result, np.zeros(len(synthetic_races)))

    def test_never_returns_negative(self, synthetic_races):
        result = robust.eta_high_by_race(
            synthetic_races, {"Safe D": {"bootstrap": {"p95": -0.2}}}
        )
        assert result[0] == 0.0


class TestOptimizeNonlinearRobust:
    def test_reduces_to_direct_optimize_nonlinear_call_at_worst_case_eta(
        self, synthetic_races, coef_sigma, eta_uncertainty_by_tier
    ):
        coef, sigma_model = coef_sigma
        n = len(synthetic_races)
        budget = 300_000.0
        cov = np.eye(n) * 1e-6

        result = robust.optimize_nonlinear_robust(
            synthetic_races, coef, sigma_model, budget=budget, cov_matrix=cov,
            gamma=0.0, cap_fraction=0.3, eta_uncertainty_by_tier=eta_uncertainty_by_tier,
            party_budget=budget,
        )

        eta_high = robust.eta_high_by_race(synthetic_races, eta_uncertainty_by_tier)
        expected = optimize_nonlinear(
            synthetic_races, coef, sigma_model, budget=budget, cov_matrix=cov,
            gamma=0.0, cap_fraction=0.3, party_budget=budget, eta=eta_high,
        )
        np.testing.assert_allclose(result.allocations, expected.allocations, rtol=1e-9)
        assert result.expected_seats == pytest.approx(expected.expected_seats, rel=1e-9)

    def test_robust_allocation_is_more_conservative_than_point_estimate(
        self, synthetic_races, coef_sigma, eta_uncertainty_by_tier
    ):
        """Standard robust-optimization sanity check ("price of robustness"):
        evaluating the ROBUST allocation at the TRUE (point-estimate, eta=0)
        world should give E[Seats] no better than the point-estimate
        optimizer's own allocation evaluated in that same eta=0 world --
        the robust allocation is deliberately hedged against a worse
        scenario, so it cannot outperform the allocation optimized
        specifically for the eta=0 case, evaluated in that exact case."""
        coef, sigma_model = coef_sigma
        n = len(synthetic_races)
        budget = 300_000.0
        cov = np.eye(n) * 1e-6

        robust_result = robust.optimize_nonlinear_robust(
            synthetic_races, coef, sigma_model, budget=budget, cov_matrix=cov,
            gamma=0.0, cap_fraction=0.3, eta_uncertainty_by_tier=eta_uncertainty_by_tier,
            party_budget=budget,
        )
        point_result = optimize_nonlinear(
            synthetic_races, coef, sigma_model, budget=budget, cov_matrix=cov,
            gamma=0.0, cap_fraction=0.3, party_budget=budget, eta=0.0,
        )

        from backtest.optimizer.allocator import nonlinear_expected_seats_at_party_dollars
        robust_party = np.maximum(
            robust_result.allocations - np.array([r.cand_d_total for r in synthetic_races]), 0.0)
        point_party = np.maximum(
            point_result.allocations - np.array([r.cand_d_total for r in synthetic_races]), 0.0)

        e_seats_robust_at_truth = nonlinear_expected_seats_at_party_dollars(
            synthetic_races, coef, sigma_model, robust_party, eta=0.0)
        e_seats_point_at_truth = nonlinear_expected_seats_at_party_dollars(
            synthetic_races, coef, sigma_model, point_party, eta=0.0)

        assert e_seats_robust_at_truth <= e_seats_point_at_truth + 1e-6

    def test_monotonicity_violation_raises_rather_than_returning_silently_wrong_result(self, coef_sigma):
        """Calls _verify_monotonicity() directly (rather than going through
        the full optimize_nonlinear_robust() -> SLSQP solve) with a
        deliberately broken coefficient set and a controlled, hand-picked
        allocation -- routing this through the real solver was tried first
        and found unreliable at triggering a clean violation (extreme
        alpha4 values push the persuasion ceiling into saturation, which
        can mask or reverse the violation depending on exactly which
        allocation SLSQP converges to); direct, controlled inputs give a
        deterministic test of the verification logic itself instead.

        alpha4=50 (with this race's real c_spend, beta1~5.5) empirically
        confirmed (not guessed) to produce msg_high > msg_0 at eta=1 for a
        controlled allocation with party clearly above party_obs -- i.e. a
        genuine violation of d(mu_raw)/d(eta) = (alpha4-c_spend)/t <= 0."""
        import dataclasses
        coef, sigma_model = coef_sigma
        broken_coef = dataclasses.replace(coef, alpha4=50.0)
        race = [_race("OH-02", "Toss-Up", "Open", pvi=0.0, d_total=300_000, r_total=300_000, cand_d_total=200_000)]
        eta_high = np.array([1.0])
        allocation = np.array([320_000.0])   # party=120,000 > party_obs=100,000 -- reaction gates active

        with pytest.raises(RuntimeError, match="monotonicity assumption violated"):
            robust._verify_monotonicity(race, broken_coef, sigma_model, eta_high, allocation)
