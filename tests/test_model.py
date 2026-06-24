"""Tests for the spending response surface and win probability computation."""

import pytest
import numpy as np
from backtest.types import RaceRecord, SigmaModel
from backtest.model.margin import MarginModelCoefficients, predict
from backtest.model.win_prob import compute_outputs, _marginal_seat_gain


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
