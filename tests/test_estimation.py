"""Tests for estimation pipeline: beta_rc, sigma, open_seat calibration."""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch

from backtest.estimation.beta_rc import (
    _normalize_name, identify_repeat_pairs, estimate_beta_rc, sample_beta_rc,
)
from backtest.estimation.sigma import estimate_sigma, compute_residuals_from_panel
from backtest.estimation.open_seat import calibrate_open_seat, _covariate_overlap_tau
from backtest.types import BetaRC, SigmaModel


# ─── _normalize_name ──────────────────────────────────────────────────────────

class TestNormalizeName:
    def test_uppercases(self):
        assert _normalize_name("john doe") == "JOHN DOE"

    def test_strips_jr_suffix(self):
        result = _normalize_name("Smith Jr.")
        assert "JR" not in result
        assert "SMITH" in result

    def test_strips_iii_suffix(self):
        result = _normalize_name("Jones III")
        assert "III" not in result

    def test_strips_esq_suffix(self):
        result = _normalize_name("Clark Esq.")
        assert "ESQ" not in result

    def test_collapses_whitespace(self):
        result = _normalize_name("John  Doe")
        assert "  " not in result

    def test_normalizes_em_dash_to_hyphen(self):
        result = _normalize_name("O—Brien")
        assert "—" not in result
        assert "-" in result

    def test_same_name_after_double_normalization(self):
        name = "Jane  Smith-Jones Jr."
        assert _normalize_name(name) == _normalize_name(_normalize_name(name))


# ─── identify_repeat_pairs ────────────────────────────────────────────────────

def _repeat_pair_frames():
    """
    Two cycles: 2018, 2020.
    TX-07: same challenger ("Jones D.") both cycles → repeat pair.
    CA-01: different challengers ("Lee D." vs "Chen D.") → excluded.
    """
    results = pd.DataFrame([
        {"district_id": "TX-07", "cycle": 2018, "margin_pp": -5.0},
        {"district_id": "TX-07", "cycle": 2020, "margin_pp": -2.0},
        {"district_id": "CA-01", "cycle": 2018, "margin_pp": 10.0},
        {"district_id": "CA-01", "cycle": 2020, "margin_pp": 12.0},
    ])
    spend = pd.DataFrame([
        {"district_id": "TX-07", "cycle": 2018, "d_total": 1e6, "r_total": 2e6},
        {"district_id": "TX-07", "cycle": 2020, "d_total": 1.5e6, "r_total": 2e6},
        {"district_id": "CA-01", "cycle": 2018, "d_total": 3e6, "r_total": 1e6},
        {"district_id": "CA-01", "cycle": 2020, "d_total": 3.5e6, "r_total": 1e6},
    ])
    incumb = pd.DataFrame([
        {"district_id": "TX-07", "cycle": 2018, "incumb_status": "Challenger",
         "incumbent_name": "Smith R.", "challenger_name": "Jones D."},
        {"district_id": "TX-07", "cycle": 2020, "incumb_status": "Challenger",
         "incumbent_name": "Smith R.", "challenger_name": "Jones D."},
        {"district_id": "CA-01", "cycle": 2018, "incumb_status": "Challenger",
         "incumbent_name": "Brown R.", "challenger_name": "Lee D."},
        {"district_id": "CA-01", "cycle": 2020, "incumb_status": "Challenger",
         "incumbent_name": "Brown R.", "challenger_name": "Chen D."},
    ])
    return results, spend, incumb


class TestIdentifyRepeatPairs:
    def _run(self, results, spend, incumb, cycles=(2018, 2020)):
        with patch("backtest.estimation.beta_rc.config") as mock_cfg:
            mock_cfg.panel_cycles.return_value = list(cycles)
            return identify_repeat_pairs(results, spend, incumb)

    def test_finds_same_challenger_pair(self):
        results, spend, incumb = _repeat_pair_frames()
        pairs = self._run(results, spend, incumb)
        assert len(pairs) == 1
        assert pairs.iloc[0]["district_id"] == "TX-07"

    def test_different_challenger_excluded(self):
        results, spend, incumb = _repeat_pair_frames()
        pairs = self._run(results, spend, incumb)
        assert "CA-01" not in pairs["district_id"].values

    def test_single_cycle_returns_empty(self):
        results, spend, incumb = _repeat_pair_frames()
        pairs = self._run(results, spend, incumb, cycles=(2020,))
        assert len(pairs) == 0

    def test_required_columns_present(self):
        results, spend, incumb = _repeat_pair_frames()
        pairs = self._run(results, spend, incumb)
        for col in ["district_id", "cycle_t", "cycle_tm1", "delta_margin", "delta_log_ratio"]:
            assert col in pairs.columns

    def test_delta_log_ratio_sign(self):
        """delta_log_ratio > 0 when D share improves across cycles."""
        results, spend, incumb = _repeat_pair_frames()
        # TX-07: ratio_prev = 1/(1+2) ≈ 0.333, ratio_curr = 1.5/(1.5+2) ≈ 0.429
        # → log(0.429) − log(0.333) > 0
        pairs = self._run(results, spend, incumb)
        assert pairs.iloc[0]["delta_log_ratio"] > 0


# ─── estimate_beta_rc ─────────────────────────────────────────────────────────

class TestEstimateBetaRC:
    def _make_pairs(self, true_beta: float, n: int = 200, seed: int = 0) -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        delta_log_ratio = rng.normal(0.0, 0.3, n)
        noise = rng.normal(0.0, 1.0, n)
        return pd.DataFrame({
            "district_id": [f"XX-{i:03d}" for i in range(n)],
            "cycle_t":  [2020] * n,
            "cycle_tm1": [2018] * n,
            "delta_margin": true_beta * delta_log_ratio + noise,
            "delta_log_ratio": delta_log_ratio,
        })

    def _run(self, pairs, min_pairs=10):
        with patch("backtest.estimation.beta_rc.config") as mock_cfg:
            mock_cfg.min_repeat_pairs.return_value = min_pairs
            return estimate_beta_rc(pairs)

    def test_recovers_true_beta(self):
        pairs = self._make_pairs(true_beta=3.5, n=300)
        beta_rc = self._run(pairs)
        assert abs(beta_rc.estimate - 3.5) < 0.5

    def test_positive_se(self):
        pairs = self._make_pairs(true_beta=3.0, n=100)
        beta_rc = self._run(pairs)
        assert beta_rc.se > 0

    def test_n_pairs_recorded(self):
        pairs = self._make_pairs(3.0, n=75)
        beta_rc = self._run(pairs)
        assert beta_rc.n_pairs == 75

    def test_returns_betarc_type(self):
        pairs = self._make_pairs(3.0, n=50)
        beta_rc = self._run(pairs)
        assert isinstance(beta_rc, BetaRC)


# ─── estimate_sigma ───────────────────────────────────────────────────────────

def _make_sigma_residuals(n: int = 400, seed: int = 42) -> pd.DataFrame:
    """Synthetic residuals with known ordering: open > challenger > incumbent."""
    rng = np.random.default_rng(seed)
    statuses = rng.choice(["Open", "Challenger", "Incumbent"], n)
    abs_pvi = rng.uniform(0, 20, n)
    base_sigma = np.where(statuses == "Open", 8.0,
                 np.where(statuses == "Challenger", 6.0, 4.0))
    residuals = rng.normal(0, base_sigma, n)
    return pd.DataFrame({
        "district_id": [f"XX-{i}" for i in range(n)],
        "cycle": 2020, "abs_pvi": abs_pvi,
        "incumb_status": statuses, "margin_residual": residuals, "gb": 0.0,
    })


class TestEstimateSigma:
    def test_returns_sigma_model(self):
        model = estimate_sigma(_make_sigma_residuals())
        assert isinstance(model, SigmaModel)

    def test_ordering_open_gt_challenger_gt_incumbent(self):
        """With clearly separated true sigmas, fitted model should honour ordering."""
        model = estimate_sigma(_make_sigma_residuals(n=600))
        for pvi in [0.0, 5.0, 10.0]:
            s_open = model.predict(pvi, "Open")
            s_chall = model.predict(pvi, "Challenger")
            s_incumb = model.predict(pvi, "Incumbent")
            assert s_open > s_chall > s_incumb, (
                f"|PVI|={pvi}: open={s_open:.2f}, chall={s_chall:.2f}, incumb={s_incumb:.2f}"
            )

    def test_sigma_positive_everywhere(self):
        model = estimate_sigma(_make_sigma_residuals())
        for pvi in [0.0, 10.0, 20.0]:
            for status in ["Open", "Challenger", "Incumbent"]:
                assert model.predict(pvi, status) > 0

    def test_filters_near_zero_residuals(self):
        """Rows with |residual| <= 0.01 must not cause a crash."""
        df = _make_sigma_residuals(n=200)
        df.loc[:5, "margin_residual"] = 0.001   # near-zero rows
        model = estimate_sigma(df)
        assert isinstance(model, SigmaModel)


# ─── compute_residuals_from_panel ─────────────────────────────────────────────

class TestComputeResiduals:
    def _base_frames(self):
        results = pd.DataFrame([
            {"district_id": "TX-07", "cycle": 2020, "margin_pp": 5.0},
        ])
        spend = pd.DataFrame([
            {"district_id": "TX-07", "cycle": 2020, "d_total": 2e6, "r_total": 2e6},
        ])
        incumb = pd.DataFrame([
            {"district_id": "TX-07", "cycle": 2020, "incumb_status": "Challenger"},
        ])
        pvi = pd.DataFrame([
            {"district_id": "TX-07", "cycle": 2020, "pvi": 0.0},
        ])
        return results, spend, incumb, pvi

    def test_output_columns(self):
        results, spend, incumb, pvi = self._base_frames()
        df = compute_residuals_from_panel(
            results, spend, incumb, pvi,
            alpha_coef={"intercept": 0.0, "pvi": 0.0, "incumb": 0.0, "gb": 0.0},
            beta_coef={"b1": 0.0, "b2": 0.0, "b3": 0.0},
            generic_ballot_by_cycle={2020: 0.0},
        )
        for col in ["district_id", "cycle", "abs_pvi", "incumb_status", "margin_residual"]:
            assert col in df.columns

    def test_zero_coefficients_gives_raw_margin(self):
        """With all-zero model, residual equals the actual margin."""
        results, spend, incumb, pvi = self._base_frames()
        df = compute_residuals_from_panel(
            results, spend, incumb, pvi,
            alpha_coef={"intercept": 0.0, "pvi": 0.0, "incumb": 0.0, "gb": 0.0},
            beta_coef={"b1": 0.0, "b2": 0.0, "b3": 0.0},
            generic_ballot_by_cycle={2020: 0.0},
        )
        # margin_pp=5.0, all coefs=0 → mu_hat=0 → residual=5.0
        assert df.iloc[0]["margin_residual"] == pytest.approx(5.0)

    def test_filters_zero_spend_rows(self):
        """Rows with zero total spend must be dropped."""
        results = pd.DataFrame([
            {"district_id": "TX-07", "cycle": 2020, "margin_pp": 5.0},
            {"district_id": "TX-08", "cycle": 2020, "margin_pp": 2.0},
        ])
        spend = pd.DataFrame([
            {"district_id": "TX-07", "cycle": 2020, "d_total": 2e6, "r_total": 2e6},
            {"district_id": "TX-08", "cycle": 2020, "d_total": 0.0, "r_total": 0.0},  # zero → filtered
        ])
        incumb = pd.DataFrame([
            {"district_id": "TX-07", "cycle": 2020, "incumb_status": "Challenger"},
            {"district_id": "TX-08", "cycle": 2020, "incumb_status": "Challenger"},
        ])
        pvi = pd.DataFrame([
            {"district_id": "TX-07", "cycle": 2020, "pvi": 0.0},
            {"district_id": "TX-08", "cycle": 2020, "pvi": 0.0},
        ])
        df = compute_residuals_from_panel(
            results, spend, incumb, pvi,
            alpha_coef={"intercept": 0.0, "pvi": 0.0, "incumb": 0.0, "gb": 0.0},
            beta_coef={"b1": 0.0, "b2": 0.0, "b3": 0.0},
            generic_ballot_by_cycle={2020: 0.0},
        )
        assert len(df) == 1
        assert df.iloc[0]["district_id"] == "TX-07"


# ─── _covariate_overlap_tau ───────────────────────────────────────────────────

class TestCovariateOverlapTau:
    def test_positive(self):
        assert _covariate_overlap_tau(0.5, 30) > 0

    def test_fewer_seats_increases_tau(self):
        tau_few = _covariate_overlap_tau(0.5, 10)
        tau_many = _covariate_overlap_tau(0.5, 100)
        assert tau_few > tau_many

    def test_higher_se_increases_tau(self):
        tau_low = _covariate_overlap_tau(0.2, 50)
        tau_high = _covariate_overlap_tau(0.8, 50)
        assert tau_high > tau_low

    def test_formula_check(self):
        """Verify the formula: τ = 2 × SE × sqrt(max(50, n) / n)."""
        se, n = 0.5, 30
        expected = 2.0 * se * (max(50, n) / n) ** 0.5
        assert _covariate_overlap_tau(se, n) == pytest.approx(expected)


# ─── calibrate_open_seat ─────────────────────────────────────────────────────

class TestOpenSeatCalibration:
    def _run(self, beta_rc=3.0, beta_rc_se=0.5, beta_panel_os=4.0,
             beta4_se=0.8, n_open=50):
        return calibrate_open_seat(beta_rc, beta_rc_se, beta_panel_os, beta4_se, n_open)

    def test_calib_between_prior_and_panel(self):
        result = self._run()
        lo, hi = min(3.0, 4.0), max(3.0, 4.0)
        assert lo < result.beta_os_calib < hi

    def test_kappa_in_unit_interval(self):
        result = self._run()
        assert 0.0 <= result.kappa <= 1.0

    def test_lb_below_calib(self):
        result = self._run()
        assert result.beta_os_lb < result.beta_os_calib

    def test_high_uncertainty_shrinks_toward_prior(self):
        """Very high beta4_se → posterior collapses toward prior (β_RC)."""
        result_high_se = self._run(beta4_se=50.0)
        result_low_se = self._run(beta4_se=0.2)
        # Higher SE → more shrinkage toward prior (3.0)
        assert abs(result_high_se.beta_os_calib - 3.0) < abs(result_low_se.beta_os_calib - 3.0)

    def test_posterior_se_positive(self):
        result = self._run()
        assert result.posterior_se > 0

    def test_degenerate_zero_beta4_se_uses_tau(self):
        """beta4_se=0 must not crash — falls back to tau as likelihood uncertainty."""
        result = self._run(beta4_se=0.0)
        assert np.isfinite(result.beta_os_calib)
        assert result.posterior_se > 0

    def test_fields_all_finite(self):
        result = self._run()
        for field in ["beta_os_calib", "posterior_se", "beta_os_lb", "tau", "kappa"]:
            assert np.isfinite(getattr(result, field)), f"{field} not finite"
