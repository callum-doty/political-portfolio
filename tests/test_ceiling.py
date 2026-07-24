"""Tests for the persuasion ceiling (src/backtest/model/ceiling.py).

See FINDINGS.md's persuasion-ceiling section and config.yaml's
persuasion_ceiling block for the full diagnosis and C_max calibration.
"""

import numpy as np
import pytest
from scipy.stats import norm
from backtest.model import ceiling


class TestPersuadability:
    def test_peaks_at_toss_up(self):
        """4*Phi0*(1-Phi0) is maximized (=1.0) exactly at Phi0=0.5, i.e. mu_floor=0."""
        assert ceiling.persuadability(0.0, 10.0) == pytest.approx(1.0)

    def test_vanishes_at_extremes(self):
        """A hopeless floor (very negative mu) or a lock (very positive mu)
        both drive persuadability toward 0."""
        assert ceiling.persuadability(-1000.0, 10.0) == pytest.approx(0.0, abs=1e-9)
        assert ceiling.persuadability(1000.0, 10.0) == pytest.approx(0.0, abs=1e-9)

    def test_symmetric_around_toss_up(self):
        p_below = ceiling.persuadability(-5.0, 10.0)
        p_above = ceiling.persuadability(5.0, 10.0)
        assert p_below == pytest.approx(p_above)

    def test_bounded_between_0_and_1(self):
        for mu_floor in np.linspace(-50, 50, 21):
            p = ceiling.persuadability(mu_floor, 10.0)
            assert 0.0 <= p <= 1.0


class TestCeiling:
    def test_equals_c_max_at_toss_up(self):
        assert ceiling.ceiling(0.0, 10.0, c_max=10.0) == pytest.approx(10.0)

    def test_floored_at_eps_c_for_hopeless_race(self):
        c = ceiling.ceiling(-1000.0, 10.0, c_max=10.0)
        assert c == pytest.approx(ceiling.EPS_C)

    def test_scales_linearly_with_c_max(self):
        c1 = ceiling.ceiling(0.0, 10.0, c_max=5.0)
        c2 = ceiling.ceiling(0.0, 10.0, c_max=10.0)
        assert c2 == pytest.approx(2.0 * c1)


class TestApply:
    def test_no_shift_returns_floor(self):
        """mu_raw == mu_floor (delta=0) => mu_capped == mu_floor, gradient_factor == 1."""
        mu_capped, grad = ceiling.apply(mu_raw=5.0, mu_floor=5.0, sigma_i=10.0, c_max=10.0)
        assert mu_capped == pytest.approx(5.0)
        assert grad == pytest.approx(1.0)

    def test_never_exceeds_floor_plus_ceiling(self):
        """mu_capped must be bounded above by mu_floor + C, for any mu_raw however large."""
        mu_floor, sigma_i, c_max = 0.0, 10.0, 10.0
        C = ceiling.ceiling(mu_floor, sigma_i, c_max)
        for mu_raw in [0.0, 10.0, 100.0, 1e6]:
            mu_capped, _ = ceiling.apply(mu_raw, mu_floor, sigma_i, c_max)
            assert mu_capped <= mu_floor + C + 1e-9

    def test_saturates_for_extreme_mu_raw(self):
        mu_floor, sigma_i, c_max = 0.0, 10.0, 10.0
        C = ceiling.ceiling(mu_floor, sigma_i, c_max)
        mu_capped, grad = ceiling.apply(mu_raw=1e6, mu_floor=mu_floor, sigma_i=sigma_i, c_max=c_max)
        assert mu_capped == pytest.approx(mu_floor + C, abs=1e-6)
        assert grad == pytest.approx(0.0, abs=1e-6)

    def test_below_floor_is_not_further_suppressed(self):
        """mu_raw < mu_floor (delta clipped to 0) => passes through as mu_floor
        itself, gradient_factor == 1 (the ceiling only regularizes upside)."""
        mu_capped, grad = ceiling.apply(mu_raw=-5.0, mu_floor=0.0, sigma_i=10.0, c_max=10.0)
        assert mu_capped == pytest.approx(0.0)
        assert grad == pytest.approx(1.0)

    def test_gradient_factor_matches_finite_difference(self):
        """grad = d(mu_capped)/d(mu_raw) must match a numerical derivative.

        mu_raw == mu_floor is deliberately excluded: apply()'s max(delta, 0)
        clip creates a kink there (left-gradient 0, right-gradient 1), so a
        central difference straddling it converges to neither one-sided
        analytic value -- not a bug, just not a valid finite-difference point.
        """
        mu_floor, sigma_i, c_max = 2.0, 8.0, 10.0
        h = 1e-4
        for mu_raw in [5.0, 10.0, 20.0]:
            lo, _ = ceiling.apply(mu_raw - h, mu_floor, sigma_i, c_max)
            hi, _ = ceiling.apply(mu_raw + h, mu_floor, sigma_i, c_max)
            numerical_grad = (hi - lo) / (2 * h)
            _, analytic_grad = ceiling.apply(mu_raw, mu_floor, sigma_i, c_max)
            assert analytic_grad == pytest.approx(numerical_grad, abs=1e-6)

    def test_array_inputs(self):
        """apply() must broadcast over numpy arrays (the optimizer's hot path)."""
        mu_raw = np.array([0.0, 10.0, 50.0])
        mu_floor = np.array([0.0, 0.0, 0.0])
        sigma_i = np.array([10.0, 10.0, 10.0])
        mu_capped, grad = ceiling.apply(mu_raw, mu_floor, sigma_i, c_max=10.0)
        assert mu_capped.shape == (3,)
        assert grad.shape == (3,)
        # monotonic: larger raw shift -> larger capped shift, smaller gradient
        assert mu_capped[0] < mu_capped[1] < mu_capped[2]
        assert grad[0] > grad[1] > grad[2]

    def test_win_prob_capped_below_uncapped(self):
        """A sanity check on the actual purpose of the ceiling: Phi(mu_capped/sigma)
        must never exceed Phi(mu_raw/sigma) for an extrapolation past the floor."""
        mu_floor, sigma_i, c_max = -20.0, 8.0, 10.0
        mu_raw = 50.0  # far past any historically-supported shift
        mu_capped, _ = ceiling.apply(mu_raw, mu_floor, sigma_i, c_max)
        assert norm.cdf(mu_capped / sigma_i) < norm.cdf(mu_raw / sigma_i)
