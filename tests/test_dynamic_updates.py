"""Tests for dynamic/updates.py — f_baseline (EMA) and compute_raw_snapshot (paper §3.3)."""

from datetime import date

import pytest

from backtest.types import RaceRecord, SigmaModel
from backtest.model.margin import MarginModelCoefficients
from backtest.model.win_prob import compute_outputs_batch
from backtest.dynamic.updates import EMAStateUpdater, compute_raw_snapshot
from backtest.dynamic.state import CampaignState, RaceState


def make_races(n: int) -> list[RaceRecord]:
    return [
        RaceRecord(
            district_id=f"XX-{i:02d}", state="TX", district=i + 1,
            cook_rating="Toss-Up", incumb_status="Challenger",
            pvi=0.0, d_total=3_000_000.0, r_total=3_000_000.0,
            cvap=400_000, generic_ballot=-1.2, cand_d_total=0.0,
        )
        for i in range(n)
    ]


def make_coef() -> MarginModelCoefficients:
    return MarginModelCoefficients(
        alpha0=0.0, alpha1=0.5, alpha2=2.0, alpha3=0.3,
        beta1=3.0, beta2=0.05, beta3=1.0,
    )


def make_sigma() -> SigmaModel:
    return SigmaModel(_coef={
        "intercept": 2.0, "abs_pvi": 0.02, "is_open": 0.3, "is_challenger": 0.15,
    })


def campaign_state_from(races, period=0, period_date=date(2024, 3, 1), mu=1.0, sigma=5.0) -> CampaignState:
    race_states = {
        r.district_id: RaceState(
            base=r, period=period, period_date=period_date,
            mu_hat=mu, sigma_hat=sigma, mu_raw=mu, sigma_raw=sigma,
            d_total_t=r.d_total, r_total_t=r.r_total, cand_d_total_t=r.cand_d_total,
        )
        for r in races
    }
    return CampaignState(period=period, period_date=period_date, races=race_states,
                         generic_ballot_national=-1.2)


class TestComputeRawSnapshot:
    def test_matches_compute_outputs_batch(self):
        races = make_races(3)
        coef, sigma_model = make_coef(), make_sigma()
        snapshot = compute_raw_snapshot(races, coef, sigma_model, 0, date(2024, 3, 1), -1.2)
        expected = compute_outputs_batch(races, coef, sigma_model)
        for out in expected:
            rs = snapshot.races[out.district_id]
            assert rs.mu_raw == pytest.approx(out.mu_hat)
            assert rs.sigma_raw == pytest.approx(out.sigma_i)
            # mu_hat/sigma_hat are initialized to the raw values pre-smoothing
            assert rs.mu_hat == pytest.approx(out.mu_hat)
            assert rs.sigma_hat == pytest.approx(out.sigma_i)

    def test_cash_on_hand_defaults_to_none_when_not_supplied(self):
        races = make_races(2)
        coef, sigma_model = make_coef(), make_sigma()
        snapshot = compute_raw_snapshot(races, coef, sigma_model, 0, date(2024, 3, 1), -1.2)
        for rs in snapshot.races.values():
            assert rs.cash_on_hand_d is None

    def test_cash_on_hand_populated_when_dict_supplied(self):
        races = make_races(2)   # district_ids XX-00, XX-01
        coef, sigma_model = make_coef(), make_sigma()
        snapshot = compute_raw_snapshot(
            races, coef, sigma_model, 0, date(2024, 3, 1), -1.2,
            cash_on_hand_by_district={"XX-00": 123456.0},
        )
        assert snapshot.races["XX-00"].cash_on_hand_d == pytest.approx(123456.0)
        # a district absent from the dict still falls back to None, not $0
        assert snapshot.races["XX-01"].cash_on_hand_d is None


class TestEMAStateUpdater:
    def test_rejects_lambda_out_of_range(self):
        with pytest.raises(ValueError):
            EMAStateUpdater(lam=0.0)
        with pytest.raises(ValueError):
            EMAStateUpdater(lam=1.0)
        with pytest.raises(ValueError):
            EMAStateUpdater(lam=1.5)

    def test_first_period_no_prior_uses_raw(self):
        races = make_races(2)
        raw = campaign_state_from(races, mu=7.0, sigma=6.0)
        updater = EMAStateUpdater(lam=0.7)
        result = updater.update(prev=None, raw_snapshot=raw)
        for rs in result.races.values():
            assert rs.mu_hat == pytest.approx(7.0)
            assert rs.sigma_hat == pytest.approx(6.0)

    def test_second_period_blends_prior_and_raw(self):
        races = make_races(1)
        prev = campaign_state_from(races, period=0, mu=2.0, sigma=4.0)
        raw = campaign_state_from(races, period=1, mu=10.0, sigma=8.0)
        # raw_snapshot must carry mu_raw for the new value
        for rs in raw.races.values():
            rs.mu_raw, rs.sigma_raw = 10.0, 8.0
        updater = EMAStateUpdater(lam=0.7)
        result = updater.update(prev=prev, raw_snapshot=raw)
        rs = next(iter(result.races.values()))
        expected_mu = 0.7 * 2.0 + 0.3 * 10.0
        expected_sigma = 0.7 * 4.0 + 0.3 * 8.0
        assert rs.mu_hat == pytest.approx(expected_mu)
        assert rs.sigma_hat == pytest.approx(expected_sigma)

    def test_higher_lambda_stays_closer_to_prior(self):
        races = make_races(1)
        prev = campaign_state_from(races, period=0, mu=0.0, sigma=5.0)
        raw = campaign_state_from(races, period=1, mu=20.0, sigma=5.0)

        low_lambda = EMAStateUpdater(lam=0.3).update(prev, raw)
        high_lambda = EMAStateUpdater(lam=0.9).update(prev, raw)

        low_mu = next(iter(low_lambda.races.values())).mu_hat
        high_mu = next(iter(high_lambda.races.values())).mu_hat
        # higher lambda = more inertia = stays closer to the prior (0.0)
        assert high_mu < low_mu
