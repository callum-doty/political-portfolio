"""Tests for β_RC uncertainty propagation."""

import pytest
import numpy as np
from backtest.types import BetaRC, UncertaintyBundle
from backtest.estimation.beta_rc import sample_beta_rc


class TestBetaRCSampling:
    def test_sample_count(self):
        beta_rc = BetaRC(estimate=3.0, se=0.5, n_pairs=60)
        rng = np.random.default_rng(42)
        samples = sample_beta_rc(beta_rc, 1000, rng)
        assert len(samples) == 1000

    def test_sample_mean_close_to_estimate(self):
        beta_rc = BetaRC(estimate=3.0, se=0.5, n_pairs=60)
        rng = np.random.default_rng(42)
        samples = sample_beta_rc(beta_rc, 10_000, rng)
        assert abs(samples.mean() - 3.0) < 0.05

    def test_sample_std_close_to_se(self):
        beta_rc = BetaRC(estimate=3.0, se=0.5, n_pairs=60)
        rng = np.random.default_rng(42)
        samples = sample_beta_rc(beta_rc, 10_000, rng)
        assert abs(samples.std() - 0.5) < 0.02


class TestUncertaintyBundle:
    def _make_bundle(self, K: int = 100, n: int = 5) -> UncertaintyBundle:
        rng = np.random.default_rng(0)
        matrix = rng.uniform(0.0, 0.1, (K, n))
        matrix = matrix / matrix.sum(axis=1, keepdims=True)
        observed = np.full(n, 1.0 / n)
        return UncertaintyBundle(
            district_ids=[f"XX-{i}" for i in range(n)],
            recommended_shares_matrix=matrix,
            observed_shares=observed,
        )

    def test_median_shape(self):
        bundle = self._make_bundle()
        assert bundle.median_share().shape == (5,)

    def test_ci_bounds(self):
        bundle = self._make_bundle(K=1000)
        lo, hi = bundle.credible_interval(0.83)
        assert (lo <= hi).all()
        assert (lo >= 0).all()

    def test_prob_exceeds_between_0_and_1(self):
        bundle = self._make_bundle(K=500)
        probs = bundle.prob_model_exceeds_dccc()
        assert (probs >= 0).all()
        assert (probs <= 1).all()
