"""Tests for dynamic/horizon.py — receding-horizon loop (paper §4)."""

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from backtest import config
from backtest.data.universe import build_universe
from backtest.types import RaceRecord, SigmaModel
from backtest.model.margin import MarginModelCoefficients
from backtest.dynamic.ledger import ZeroCommitmentSource
from backtest.dynamic.updates import EMAStateUpdater
from backtest.dynamic.periods import ReportingPeriod
from backtest.dynamic.horizon import run_receding_horizon

# scripts/ isn't an importable package; load_processed_artifacts() and
# build_dummy_factor_model() live in scripts/run_backtest.py and are the
# exact loaders Phase 2 is meant to reuse (see the implementation plan).
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def make_races(n: int) -> list[RaceRecord]:
    return [
        RaceRecord(
            district_id=f"XX-{i:02d}", state="TX", district=i + 1,
            cook_rating="Toss-Up", incumb_status="Challenger",
            pvi=0.0, d_total=3_000_000.0, r_total=3_000_000.0,
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


class GrowingCommitmentSource:
    """Test double: commits a growing fixed amount per race each period,
    so F_t shrinks period over period even with B_t held constant."""

    def __init__(self, per_period_per_race: float):
        self.per_period_per_race = per_period_per_race

    def committed_capital(self, period, period_date, races) -> dict[str, float]:
        amount = self.per_period_per_race * (period + 1)
        return {r.district_id: amount for r in races}


def cov_matrix_fn(races: list[RaceRecord]) -> np.ndarray:
    return np.eye(len(races)) * 0.01


class TestRunRecedingHorizon:
    def test_produces_one_result_per_period(self):
        races = make_races(3)
        periods = make_periods(3)
        results = run_receding_horizon(
            periods, races, make_coef(), make_sigma(),
            ZeroCommitmentSource(), EMAStateUpdater(lam=0.7),
            cov_matrix_fn, gamma=0.0, cap_fraction=0.5,
            total_budget_fn=lambda t: 9_000_000.0,
            generic_ballot_national=-1.2,
        )
        assert len(results) == 3
        assert [r.period for r in results] == [0, 1, 2]

    def test_floor_always_respected(self):
        races = make_races(3)
        periods = make_periods(2)
        results = run_receding_horizon(
            periods, races, make_coef(), make_sigma(),
            ZeroCommitmentSource(), EMAStateUpdater(lam=0.7),
            cov_matrix_fn, gamma=0.0, cap_fraction=0.5,
            total_budget_fn=lambda t: 9_000_000.0,
            generic_ballot_national=-1.2,
        )
        for res in results:
            floor = res.ledger.deployable_floor_for(races)
            assert (res.optimizer_result.allocations >= floor - 1.0).all()

    def test_deployable_total_shrinks_as_commitments_grow(self):
        races = make_races(3)
        periods = make_periods(3)
        commitment_source = GrowingCommitmentSource(per_period_per_race=500_000.0)
        results = run_receding_horizon(
            periods, races, make_coef(), make_sigma(),
            commitment_source, EMAStateUpdater(lam=0.7),
            cov_matrix_fn, gamma=0.0, cap_fraction=0.5,
            total_budget_fn=lambda t: 9_000_000.0,   # constant B_t
            generic_ballot_national=-1.2,
        )
        deployable = [r.ledger.deployable_total for r in results]
        assert deployable == sorted(deployable, reverse=True)
        assert deployable[0] > deployable[-1]

    def test_lower_deployable_capital_constrains_allocation(self):
        """F_t < B_t should produce a lower total allocation than the
        equivalent uncommitted case — proves the ledger's floor/budget
        substitution actually constrains the optimizer (paper §4)."""
        races = make_races(3)
        one_period = make_periods(1)

        uncommitted = run_receding_horizon(
            one_period, races, make_coef(), make_sigma(),
            ZeroCommitmentSource(), EMAStateUpdater(lam=0.7),
            cov_matrix_fn, gamma=0.0, cap_fraction=0.9,
            total_budget_fn=lambda t: 9_000_000.0,
            generic_ballot_national=-1.2,
        )
        constrained_source = GrowingCommitmentSource(per_period_per_race=2_500_000.0)
        constrained = run_receding_horizon(
            one_period, races, make_coef(), make_sigma(),
            constrained_source, EMAStateUpdater(lam=0.7),
            cov_matrix_fn, gamma=0.0, cap_fraction=0.9,
            total_budget_fn=lambda t: 9_000_000.0,
            generic_ballot_national=-1.2,
        )
        assert constrained[0].ledger.deployable_total < uncommitted[0].ledger.deployable_total
        assert (constrained[0].optimizer_result.budget_used
                <= uncommitted[0].optimizer_result.budget_used + 1.0)


class TestRealArtifactIntegration:
    """Phase 2 milestone (implementation plan): wire the receding-horizon
    loop to real 2024 estimation artifacts and a real race universe, with
    the universe held fixed across periods (no point-in-time
    reconstruction yet — that's Phase 3, gated on the dated-IE derivation).
    This validates real-data wiring in isolation from the harder historical
    reconstruction problem.

    Skipped if run_estimation.py hasn't been run, matching run_backtest.py's
    own existing assumption that data/processed/ artifacts already exist.
    """

    REQUIRED_ARTIFACTS = ("beta_rc.json", "margin_model_coef.json", "sigma_model.json")

    def _artifacts_available(self) -> bool:
        processed = config.processed_path()
        return all((processed / f).exists() for f in self.REQUIRED_ARTIFACTS)

    def test_receding_horizon_with_real_2024_coefficients(self):
        if not self._artifacts_available():
            pytest.skip(
                "data/processed/*.json not found — run scripts/run_estimation.py first"
            )
        from run_backtest import load_processed_artifacts, build_dummy_factor_model

        _, coef, sigma_model = load_processed_artifacts(config.processed_path())
        all_races = build_universe(cycle=2024)
        # Keep the test fast: a handful of competitive races, not all 433.
        races = [r for r in all_races if r.cook_rating in
                ("Toss-Up", "Lean D", "Lean R")][:8]
        assert len(races) > 0, "expected at least one competitive race in the 2024 universe"

        gb = config.generic_ballot_for_cycle(2024)
        factor_model = build_dummy_factor_model(races, gb)
        cov_matrix = factor_model.race_covariance()

        periods = [
            ReportingPeriod(index=i, period_date=date(2024, 1 + 3 * i, 1), label=f"Q{i + 1}")
            for i in range(4)
        ]
        # DCCC's own controllable money for this race subset (mirrors
        # run_backtest.py's party_budget: sum of d_total minus each race's
        # non-DCCC-controllable candidate-committee floor).
        party_budget = sum(max(r.d_total - r.cand_d_total, 0.0) for r in races)

        dyn_cfg = config.dynamic_cfg()
        results = run_receding_horizon(
            periods, races, coef, sigma_model,
            ZeroCommitmentSource(), EMAStateUpdater(lam=dyn_cfg["ema_lambda"]),
            cov_matrix_fn=lambda rs: cov_matrix,
            gamma=0.0, cap_fraction=0.5,
            total_budget_fn=lambda t: party_budget,
            generic_ballot_national=gb,
        )

        assert len(results) == 4
        for res in results:
            assert res.optimizer_result.status == "optimal"
            assert res.optimizer_result.expected_seats > 0.0
            assert res.optimizer_result.budget_used <= party_budget * 1.01 + sum(
                r.cand_d_total for r in races
            )
