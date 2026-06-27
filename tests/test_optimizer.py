"""Tests for the portfolio optimizer."""

import pytest
import numpy as np
from backtest.types import ModelOutputs, RaceRecord, SigmaModel
from backtest.model.margin import MarginModelCoefficients
from backtest.optimizer.allocator import optimize, optimize_nonlinear, build_allocation_results, OptimizerResult


def make_outputs(n: int, msg_vals: list[float], p_wins: list[float]) -> list[ModelOutputs]:
    return [
        ModelOutputs(
            district_id=f"XX-{i:02d}",
            ratio=0.5,
            mu_hat=0.0,
            sigma_i=5.0,
            p_win=p_wins[i],
            msg_i=msg_vals[i],
        )
        for i in range(n)
    ]


class TestOptimizer:
    """Basic optimizer behavior tests (require cvxpy to be installed)."""

    def test_budget_constraint_binds(self):
        n = 5
        outputs = make_outputs(
            n, msg_vals=[0.1, 0.2, 0.15, 0.05, 0.3],
            p_wins=[0.5] * n,
        )
        budget = 10_000_000.0
        cov = np.eye(n) * 0.01
        result = optimize(outputs, budget, cov, gamma=0.0, cap_fraction=0.5)
        assert result.budget_used == pytest.approx(budget, rel=1e-3)

    def test_high_msg_gets_more(self):
        """Race with highest MSG should receive the most allocation (γ=0, no risk penalty).

        cap_fraction=0.7 so the per-race cap (6.3M) exceeds budget/2 (4.5M).
        The LP fills race 1 first (highest MSG) to cap, then allocates the
        remaining budget to race 2.  Race 1 ends up strictly larger than race 2.
        With cap=0.5 the budget fills exactly two races at cap (tie); use 0.7.
        """
        n = 3
        outputs = make_outputs(
            n, msg_vals=[0.01, 0.50, 0.02], p_wins=[0.5, 0.5, 0.5]
        )
        budget = 9_000_000.0
        cov = np.eye(n) * 1e-8   # near-zero covariance
        result = optimize(outputs, budget, cov, gamma=0.0, cap_fraction=0.7)
        assert result.shares[1] > result.shares[0]
        assert result.shares[1] > result.shares[2]

    def test_cap_respected(self):
        n = 4
        outputs = make_outputs(
            n, msg_vals=[0.9, 0.1, 0.1, 0.1], p_wins=[0.5] * n
        )
        budget = 10_000_000.0
        cov = np.eye(n) * 1e-8
        cap = 0.30
        result = optimize(outputs, budget, cov, gamma=0.0, cap_fraction=cap)
        assert result.shares.max() <= cap + 1e-4

    def test_shares_sum_to_at_most_one(self):
        n = 6
        rng = np.random.default_rng(0)
        outputs = make_outputs(n, msg_vals=rng.uniform(0.01, 0.5, n).tolist(),
                               p_wins=[0.5] * n)
        budget = 5_000_000.0
        cov = np.eye(n) * 0.01
        result = optimize(outputs, budget, cov, gamma=0.0, cap_fraction=0.20)
        assert result.shares.sum() <= 1.0 + 1e-4

    def test_risk_aversion_reduces_concentration(self):
        """With higher γ the optimizer should spread more relative to γ=0."""
        n = 5
        msg_vals = [0.1, 0.5, 0.05, 0.05, 0.05]
        p_wins = [0.5] * n
        outputs = make_outputs(n, msg_vals, p_wins)
        budget = 10_000_000.0
        cov = np.eye(n) * 0.05
        result_risk_neutral = optimize(outputs, budget, cov, gamma=0.0, cap_fraction=1.0)
        result_risk_averse  = optimize(outputs, budget, cov, gamma=100.0, cap_fraction=1.0)
        # The max share should be lower (less concentrated) under high γ
        assert result_risk_averse.shares.max() <= result_risk_neutral.shares.max() + 1e-3

    def test_floor_allocations_respected(self):
        """Allocations must be >= floors (candidate spending floors)."""
        n = 3
        floors = np.array([500_000.0, 750_000.0, 300_000.0])
        outputs = make_outputs(n, msg_vals=[0.1, 0.3, 0.2], p_wins=[0.5] * n)
        budget = 6_000_000.0
        cov = np.eye(n) * 1e-8
        result = optimize(outputs, budget, cov, gamma=0.0, cap_fraction=0.5,
                          floor_allocations=floors)
        assert (result.allocations >= floors - 1.0).all()

    def test_party_budget_cap_applies(self):
        """party_budget separates total from controllable budget."""
        n = 4
        outputs = make_outputs(n, msg_vals=[0.2] * n, p_wins=[0.5] * n)
        total_budget = 10_000_000.0
        party_budget = 4_000_000.0   # only 40% is discretionary
        cov = np.eye(n) * 1e-8
        result = optimize(outputs, total_budget, cov, gamma=0.0, cap_fraction=0.5,
                          party_budget=party_budget)
        # Total allocations should not exceed total_budget
        assert result.budget_used <= total_budget + 1.0


class TestNonlinearOptimizer:
    """Tests for optimize_nonlinear() — the SLSQP-based direct Φ optimizer."""

    def _make_races(self, n: int) -> list[RaceRecord]:
        return [
            RaceRecord(
                district_id=f"XX-{i:02d}", state="TX", district=i + 1,
                cook_rating="Toss-Up", incumb_status="Challenger",
                pvi=0.0, d_total=3_000_000.0, r_total=3_000_000.0,
                cvap=400_000, generic_ballot=-1.2, cand_d_total=0.0,
            )
            for i in range(n)
        ]

    def _coef(self):
        return MarginModelCoefficients(
            alpha0=0.0, alpha1=0.5, alpha2=2.0, alpha3=0.3,
            beta1=3.0, beta2=0.05, beta3=1.0,
        )

    def _sigma(self):
        return SigmaModel(_coef={
            "intercept": 2.0, "abs_pvi": 0.02,
            "is_open": 0.3, "is_challenger": 0.15,
        })

    def test_party_budget_not_exceeded(self):
        n = 4
        races = self._make_races(n)
        result = optimize_nonlinear(
            races, self._coef(), self._sigma(),
            budget=12_000_000.0,
            cov_matrix=np.eye(n) * 0.01,
            gamma=0.0, cap_fraction=0.5,
        )
        party_budget = sum(r.d_total - r.cand_d_total for r in races)
        party_used = result.budget_used - sum(r.cand_d_total for r in races)
        assert party_used <= party_budget * 1.01

    def test_expected_seats_positive(self):
        n = 3
        races = self._make_races(n)
        result = optimize_nonlinear(
            races, self._coef(), self._sigma(),
            budget=9_000_000.0,
            cov_matrix=np.eye(n) * 0.01,
            gamma=0.0, cap_fraction=0.5,
        )
        assert result.expected_seats > 0.0

    def test_cap_fraction_respected(self):
        n = 4
        races = self._make_races(n)
        cap = 0.30
        party_budget = sum(r.d_total - r.cand_d_total for r in races)
        result = optimize_nonlinear(
            races, self._coef(), self._sigma(),
            budget=sum(r.d_total for r in races),
            cov_matrix=np.eye(n) * 0.01,
            gamma=0.0, cap_fraction=cap,
            party_budget=party_budget,
        )
        max_party_per_race = max(
            r.d_total - r.cand_d_total for r in races
        ) * cap / party_budget  # cap as fraction of total
        # Every allocation minus its floor must not exceed cap * party_budget
        for i, r in enumerate(races):
            party_alloc = result.allocations[i] - r.cand_d_total
            assert party_alloc <= cap * party_budget + 1.0


class TestBuildAllocationResults:
    def test_length_matches_races(self):
        races = [
            RaceRecord("TX-01", "TX", 1, "Toss-Up", "Challenger",
                       0.0, 2e6, 2e6, 350_000, -1.2),
            RaceRecord("TX-02", "TX", 2, "Lean R", "Incumbent",
                       -3.0, 1e6, 3e6, 300_000, -1.2),
        ]
        outputs = [
            ModelOutputs("TX-01", 0.5, 0.0, 5.0, 0.5, 1e-7),
            ModelOutputs("TX-02", 0.25, -5.0, 5.0, 0.2, 5e-8),
        ]
        allocs = np.array([3e6, 1.5e6])
        budget = 6e6
        opt_result = OptimizerResult(
            allocations=allocs, shares=allocs / budget,
            expected_seats=0.7, var_seats=0.1,
            objective_value=0.7, budget_used=4.5e6,
            status="optimal", n_corner_solutions=1,
        )
        results = build_allocation_results(races, outputs, opt_result, budget)
        assert len(results) == 2

    def test_difference_is_recommended_minus_observed(self):
        races = [
            RaceRecord("TX-01", "TX", 1, "Toss-Up", "Challenger",
                       0.0, 2e6, 2e6, 350_000, -1.2),
        ]
        outputs = [ModelOutputs("TX-01", 0.5, 0.0, 5.0, 0.5, 1e-7)]
        budget = 4e6
        recommended_share = 0.75
        allocs = np.array([budget * recommended_share])
        opt_result = OptimizerResult(
            allocations=allocs, shares=allocs / budget,
            expected_seats=0.5, var_seats=0.05,
            objective_value=0.5, budget_used=float(allocs.sum()),
            status="optimal", n_corner_solutions=0,
        )
        results = build_allocation_results(races, outputs, opt_result, budget)
        expected_diff = recommended_share - (2e6 / budget)
        assert results[0].difference == pytest.approx(expected_diff, rel=1e-5)
