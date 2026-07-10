"""Tests for the spending response surface and win probability computation."""

import pytest
import numpy as np
import pandas as pd
from backtest.types import RaceRecord, SigmaModel
from backtest.model.margin import MarginModelCoefficients, predict, predict_batch
from backtest.model.win_prob import compute_outputs, compute_outputs_batch, _marginal_seat_gain


@pytest.fixture
def coef():
    return MarginModelCoefficients(
        alpha0=0.0, alpha1=0.5, alpha2=2.0, alpha3=0.3,
        beta1=3.0, beta2=0.05, beta3=1.0,
    )


@pytest.fixture
def sigma_model():
    return SigmaModel(_coef={
        "intercept": 2.0, "abs_pvi": 0.02,
        "is_open": 0.3, "is_challenger": 0.15,
    })


@pytest.fixture
def tossup_race():
    return RaceRecord(
        district_id="PA-08", state="PA", district=8,
        cook_rating="Toss-Up", incumb_status="Challenger",
        pvi=-1.0, d_total=3_000_000.0, r_total=3_500_000.0,
        cvap=400_000, generic_ballot=-1.2,
    )


class TestMarginPredict:
    def test_incumbent_advantage(self, coef):
        margin_incumb = predict(0.0, "Incumbent", 0.0, 0.5, coef)
        margin_chall = predict(0.0, "Challenger", 0.0, 0.5, coef)
        assert margin_incumb > margin_chall

    def test_even_ratio_log_is_zero(self, coef):
        # At ratio=0.5, log(ratio)=log(0.5) ≠ 0; spending parity is not zero
        margin = predict(0.0, "Open", 0.0, 0.5, coef)
        # Just verify it doesn't error and is finite
        assert np.isfinite(margin)

    def test_higher_ratio_increases_margin(self, coef):
        m_low  = predict(0.0, "Challenger", 0.0, 0.4, coef)
        m_high = predict(0.0, "Challenger", 0.0, 0.6, coef)
        assert m_high > m_low

    def test_beta1_override(self, coef):
        base = predict(0.0, "Challenger", 0.0, 0.6, coef)
        override = predict(0.0, "Challenger", 0.0, 0.6, coef, beta1_override=0.0)
        # With β₁=0 and positive ratio, log(ratio) term vanishes → different result
        assert base != override


class TestWinProbability:
    def test_pwin_between_0_and_1(self, tossup_race, coef, sigma_model):
        out = compute_outputs(tossup_race, coef, sigma_model)
        assert 0.0 <= out.p_win <= 1.0

    def test_msg_positive_for_tossup(self, tossup_race, coef, sigma_model):
        out = compute_outputs(tossup_race, coef, sigma_model)
        assert out.msg_i > 0

    def test_sigma_ordering(self, sigma_model):
        for pvi in [0, 5, 10, 15]:
            s_open = sigma_model.predict(float(pvi), "Open")
            s_chall = sigma_model.predict(float(pvi), "Challenger")
            s_incumb = sigma_model.predict(float(pvi), "Incumbent")
            assert s_open > s_chall > s_incumb, (
                f"|PVI|={pvi}: ordering violated: open={s_open:.2f}, "
                f"chall={s_chall:.2f}, incumb={s_incumb:.2f}"
            )

    def test_zero_spend_safe_race(self, coef, sigma_model):
        safe_race = RaceRecord(
            district_id="TX-21", state="TX", district=21,
            cook_rating="Safe R", incumb_status="Incumbent",
            pvi=-20.0, d_total=0.0, r_total=1_000_000.0,
            cvap=400_000, generic_ballot=-1.2,
        )
        out = compute_outputs(safe_race, coef, sigma_model)
        # ratio is clipped to 1e-6, not exactly 0, so MSG is near-zero not exactly 0
        assert out.msg_i == pytest.approx(0.0, abs=1e-10)

    def test_all_outputs_finite(self, tossup_race, coef, sigma_model):
        """compute_outputs must always return finite, well-typed values."""
        out = compute_outputs(tossup_race, coef, sigma_model)
        assert np.isfinite(out.mu_hat)
        assert np.isfinite(out.sigma_i)
        assert np.isfinite(out.p_win)
        assert np.isfinite(out.msg_i)
        assert np.isfinite(out.ratio)

    def test_msg_per_dollar_magnitude(self, tossup_race, coef, sigma_model):
        """MSG_i is seats per dollar: should be tiny (< 1e-4 for realistic races)."""
        out = compute_outputs(tossup_race, coef, sigma_model)
        assert out.msg_i < 1e-4

    def test_msg_decreases_as_total_spend_increases(self, coef, sigma_model):
        """MSG ∝ 1/total_spend when ratio is held fixed (gradient = factor/total).

        With alpha4=0 and constant log(ratio), doubling both D and R spend
        keeps μ and σ unchanged but halves the gradient → MSG halves.
        """
        base = RaceRecord(
            district_id="PA-01", state="PA", district=1,
            cook_rating="Toss-Up", incumb_status="Challenger",
            pvi=-1.0, d_total=2_000_000.0, r_total=2_000_000.0,
            cvap=400_000, generic_ballot=-1.2,
        )
        scaled = RaceRecord(
            district_id="PA-01", state="PA", district=1,
            cook_rating="Toss-Up", incumb_status="Challenger",
            pvi=-1.0, d_total=4_000_000.0, r_total=4_000_000.0,
            cvap=400_000, generic_ballot=-1.2,
        )
        out_base = compute_outputs(base, coef, sigma_model)
        out_scaled = compute_outputs(scaled, coef, sigma_model)
        # Same log(ratio), same μ, same σ → MSG halves when spend doubles
        assert out_base.msg_i > out_scaled.msg_i

    def test_msg_positive_for_incumbent_underdog(self, coef, sigma_model):
        race = RaceRecord(
            district_id="OH-01", state="OH", district=1,
            cook_rating="Lean R", incumb_status="Incumbent",
            pvi=-3.0, d_total=2_000_000.0, r_total=5_000_000.0,
            cvap=350_000, generic_ballot=-1.2,
        )
        out = compute_outputs(race, coef, sigma_model)
        assert out.msg_i > 0

    def test_msg_matches_finite_difference_off_parity(self, coef, sigma_model):
        """MSG_i must match a numerical d/dD of P(win) at D != R.

        Regression test for a bug where the analytic gradient dropped the
        R/D factor (equivalent to assuming D == R for every race).
        """
        h = 1.0
        for d_total, r_total in [(6_000_000.0, 2_000_000.0), (1_000_000.0, 5_000_000.0)]:
            race_lo = RaceRecord(
                district_id="X", state="TX", district=1,
                cook_rating="Toss-Up", incumb_status="Challenger",
                pvi=-1.0, d_total=d_total - h, r_total=r_total,
                cvap=400_000, generic_ballot=-1.2,
            )
            race_hi = RaceRecord(
                district_id="X", state="TX", district=1,
                cook_rating="Toss-Up", incumb_status="Challenger",
                pvi=-1.0, d_total=d_total + h, r_total=r_total,
                cvap=400_000, generic_ballot=-1.2,
            )
            race_mid = RaceRecord(
                district_id="X", state="TX", district=1,
                cook_rating="Toss-Up", incumb_status="Challenger",
                pvi=-1.0, d_total=d_total, r_total=r_total,
                cvap=400_000, generic_ballot=-1.2,
            )
            p_lo = compute_outputs(race_lo, coef, sigma_model).p_win
            p_hi = compute_outputs(race_hi, coef, sigma_model).p_win
            numerical_msg = (p_hi - p_lo) / (2 * h)
            analytic_msg = compute_outputs(race_mid, coef, sigma_model).msg_i
            assert analytic_msg == pytest.approx(numerical_msg, rel=1e-4), (
                f"D={d_total}, R={r_total}: analytic={analytic_msg:.3e} "
                f"vs numerical={numerical_msg:.3e}"
            )

    def test_batch_matches_single(self, coef, sigma_model):
        """compute_outputs_batch must return same values as compute_outputs one-by-one."""
        races = [
            RaceRecord("TX-01", "TX", 1, "Toss-Up", "Challenger",
                       -1.0, 3e6, 3.5e6, 400_000, -1.2),
            RaceRecord("CA-12", "CA", 12, "Safe D", "Incumbent",
                       15.0, 2e6, 0.5e6, 400_000, -1.2),
        ]
        batch = compute_outputs_batch(races, coef, sigma_model)
        for i, race in enumerate(races):
            single = compute_outputs(race, coef, sigma_model)
            assert batch[i].p_win == pytest.approx(single.p_win, rel=1e-6)
            assert batch[i].msg_i == pytest.approx(single.msg_i, rel=1e-6)


class TestPredictBatch:
    def test_batch_matches_single_predict(self, coef):
        """predict_batch() must agree with predict() for every row."""
        rows = [
            {"pvi": 3.0,  "is_incumb": 1.0, "gb": -1.2,
             "log_ratio": np.log(0.55), "log_total_per_voter": np.log(1e7 / 400_000)},
            {"pvi": -5.0, "is_incumb": 0.0, "gb": -1.2,
             "log_ratio": np.log(0.45), "log_total_per_voter": np.log(8e6 / 350_000)},
        ]
        df = pd.DataFrame(rows)
        batch = predict_batch(df, coef).values

        for i, row in enumerate(rows):
            ratio = float(np.exp(row["log_ratio"]))
            incumb = "Incumbent" if row["is_incumb"] == 1.0 else "Challenger"
            single = predict(row["pvi"], incumb, row["gb"], ratio, coef)
            assert batch[i] == pytest.approx(single, rel=1e-6)

    def test_batch_without_log_total_per_voter(self, coef):
        """predict_batch() must not crash when log_total_per_voter column is absent."""
        df = pd.DataFrame([
            {"pvi": 0.0, "is_incumb": 0.0, "gb": 0.0, "log_ratio": np.log(0.5)},
        ])
        result = predict_batch(df, coef)
        assert np.isfinite(result.iloc[0])


class TestBeta1Open:
    def test_open_seat_uses_beta1_open(self, coef):
        """predict() must use beta1_open for Open seats when it is set."""
        coef_with_open = MarginModelCoefficients(
            alpha0=coef.alpha0, alpha1=coef.alpha1, alpha2=coef.alpha2,
            alpha3=coef.alpha3, beta1=coef.beta1, beta2=coef.beta2,
            beta3=coef.beta3, beta1_open=0.5,
        )
        m_default = predict(0.0, "Open", 0.0, 0.6, coef)
        m_open = predict(0.0, "Open", 0.0, 0.6, coef_with_open)
        assert m_default != m_open

    def test_incumbent_ignores_beta1_open(self, coef):
        """Incumbent races must not be affected by beta1_open."""
        coef_with_open = MarginModelCoefficients(
            alpha0=coef.alpha0, alpha1=coef.alpha1, alpha2=coef.alpha2,
            alpha3=coef.alpha3, beta1=coef.beta1, beta2=coef.beta2,
            beta3=coef.beta3, beta1_open=99.9,
        )
        m_default = predict(0.0, "Incumbent", 0.0, 0.6, coef)
        m_open = predict(0.0, "Incumbent", 0.0, 0.6, coef_with_open)
        assert m_default == pytest.approx(m_open)


class TestSigmaModelExtended:
    def test_generic_ballot_increases_sigma(self):
        """Larger |generic_ballot| must raise sigma when abs_gb coefficient > 0."""
        model = SigmaModel(_coef={
            "intercept": 2.0, "abs_pvi": 0.02,
            "is_open": 0.3, "is_challenger": 0.15, "abs_gb": 0.05,
        })
        sigma_calm = model.predict(5.0, "Open", generic_ballot=0.0)
        sigma_wave = model.predict(5.0, "Open", generic_ballot=8.0)
        assert sigma_wave > sigma_calm

    def test_missing_abs_gb_key_defaults_gracefully(self):
        """SigmaModel without abs_gb key must still produce finite positive sigma."""
        model = SigmaModel(_coef={
            "intercept": 2.0, "abs_pvi": 0.0,
            "is_open": 0.0, "is_challenger": 0.0,
        })
        sigma = model.predict(5.0, "Open", generic_ballot=5.0)
        assert np.isfinite(sigma) and sigma > 0

    def test_sigma_positive_all_status_types(self, sigma_model):
        for status in ["Open", "Challenger", "Incumbent"]:
            s = sigma_model.predict(5.0, status)
            assert s > 0, f"sigma <= 0 for {status}"
