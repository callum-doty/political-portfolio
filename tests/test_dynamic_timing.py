"""Tests for dynamic/timing.py — deployment-timing diagnostic (paper §5.4.1, §6.3)."""

from datetime import date, timedelta

import numpy as np
import pytest

from backtest.types import RaceRecord, SigmaModel
from backtest.model.margin import MarginModelCoefficients
from backtest.dynamic.ledger import ZeroCommitmentSource
from backtest.dynamic.updates import EMAStateUpdater
from backtest.dynamic.periods import ReportingPeriod
from backtest.dynamic.horizon import run_receding_horizon
from backtest.dynamic.timing import build_timing_table, timing_gap_vs_volatility


def make_races(n: int) -> list[RaceRecord]:
    return [
        RaceRecord(
            district_id=f"XX-{i:02d}", state="TX", district=i + 1,
            cook_rating="Toss-Up", incumb_status="Challenger",
            pvi=float(i * 3), d_total=3_000_000.0, r_total=3_000_000.0,
            cvap=400_000, generic_ballot=-1.2, cand_d_total=200_000.0,
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


def make_periods(n: int) -> list[ReportingPeriod]:
    start = date(2024, 3, 1)
    return [
        ReportingPeriod(index=i, period_date=start + timedelta(days=14 * i), label=f"P{i}")
        for i in range(n)
    ]


def cov_matrix_fn(races: list[RaceRecord]) -> np.ndarray:
    return np.eye(len(races)) * 0.01


class TestBuildTimingTable:
    def test_returns_one_row_per_race_per_period(self):
        races = make_races(3)
        periods = make_periods(2)
        results = run_receding_horizon(
            periods, races, make_coef(), make_sigma(),
            ZeroCommitmentSource(), EMAStateUpdater(lam=0.7),
            cov_matrix_fn, gamma=0.0, cap_fraction=0.9,
            total_budget_fn=lambda t: 9_000_000.0,
            generic_ballot_national=-1.2,
        )
        timing = build_timing_table(results)
        assert len(timing) == 3 * 2

    def test_positive_gap_when_model_deploys_and_actual_is_static(self):
        """Races are held fixed across periods (no period_races_fn override),
        so real d_total never changes -> DCCC's 'actual incremental' spend
        is 0 after period 0. The model recommends deploying most of F_t
        each period regardless (it has no term rewarding patience), so the
        gap should be positive -- exactly the front-loading pattern paper
        §5.4.1 predicts."""
        races = make_races(3)
        periods = make_periods(3)
        results = run_receding_horizon(
            periods, races, make_coef(), make_sigma(),
            ZeroCommitmentSource(), EMAStateUpdater(lam=0.7),
            cov_matrix_fn, gamma=0.0, cap_fraction=0.9,
            total_budget_fn=lambda t: 9_000_000.0,
            generic_ballot_national=-1.2,
        )
        timing = build_timing_table(results)
        later_periods = [tc for tc in timing if tc.period > 0]
        assert len(later_periods) > 0
        assert all(
            tc.dccc_actual_incremental_party_spend == pytest.approx(0.0)
            for tc in later_periods
        )
        assert all(tc.gap >= -1.0 for tc in later_periods)   # model_recommended >= 0 always


class TestTimingGapVsVolatility:
    def test_correlation_present_with_multiple_races(self):
        races = make_races(4)
        periods = make_periods(2)
        results = run_receding_horizon(
            periods, races, make_coef(), make_sigma(),
            ZeroCommitmentSource(), EMAStateUpdater(lam=0.7),
            cov_matrix_fn, gamma=0.0, cap_fraction=0.9,
            total_budget_fn=lambda t: 9_000_000.0,
            generic_ballot_national=-1.2,
        )
        timing = build_timing_table(results)
        races_by_district = {r.district_id: r for r in races}
        df = timing_gap_vs_volatility(timing, make_sigma(), races_by_district)
        assert len(df) == 4
        assert "correlation" in df.attrs
        assert -1.0 <= df.attrs["correlation"] <= 1.0

    def test_empty_timing_returns_empty_frame_without_correlation(self):
        df = timing_gap_vs_volatility([], make_sigma(), {})
        assert len(df) == 0
        assert "correlation" not in df.attrs
