"""Tests for the portfolio optimizer."""

import pytest
import numpy as np
from backtest.types import ModelOutputs
from backtest.optimizer.allocator import optimize, OptimizerResult


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
        """Race with highest MSG should receive the most allocation (γ=0, no risk penalty)."""
        n = 3
        outputs = make_outputs(
            n, msg_vals=[0.01, 0.50, 0.02], p_wins=[0.5, 0.5, 0.5]
        )
        budget = 9_000_000.0
        cov = np.eye(n) * 1e-8   # near-zero covariance
        result = optimize(outputs, budget, cov, gamma=0.0, cap_fraction=0.5)
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
