"""Tests for dynamic/simulate.py — one-step-ahead historical harness (paper §6.2)."""

import inspect
from datetime import date

import numpy as np
import pandas as pd
import pytest

from backtest import config
from backtest.data import fec
from backtest.types import RaceRecord, SigmaModel
from backtest.model.margin import MarginModelCoefficients
from backtest.dynamic.ledger import ZeroCommitmentSource
from backtest.dynamic.updates import EMAStateUpdater
from backtest.dynamic.periods import ReportingPeriod
from backtest.dynamic.simulate import one_step_ahead, _reconstruct_races_at


def make_coef() -> MarginModelCoefficients:
    return MarginModelCoefficients(
        alpha0=0.0, alpha1=0.5, alpha2=2.0, alpha3=0.3,
        beta1=3.0, beta2=0.05, beta3=1.0,
    )


def make_sigma() -> SigmaModel:
    return SigmaModel(_coef={
        "intercept": 2.0, "abs_pvi": 0.02, "is_open": 0.3, "is_challenger": 0.15,
    })


def cov_matrix_fn(races: list[RaceRecord]) -> np.ndarray:
    return np.eye(len(races)) * 0.01


class TestNoLookaheadSafeguard:
    """Structural safeguard from paper §6.2: `_reconstruct_races_at` must
    have no way to receive a prior period's model output."""

    def test_reconstruct_races_at_has_no_prior_results_parameter(self):
        sig = inspect.signature(_reconstruct_races_at)
        param_names = set(sig.parameters.keys())
        forbidden = {"prior_results", "prior_result", "results", "period_result", "period_results"}
        assert not (param_names & forbidden), (
            f"_reconstruct_races_at must not accept a prior-results-shaped "
            f"parameter; found {param_names & forbidden}"
        )
        expected = {"period_index", "period_date", "cycle", "base_races", "static_totals"}
        assert param_names == expected


class TestOneStepAheadIndependence:
    """Behavioral test: two runs that produce different model
    recommendations at period 0 must reconstruct IDENTICAL state at period 1
    — real historical data can never depend on what the model recommended
    (paper §6.2)."""

    def test_reconstructed_state_independent_of_model_recommendation(self, monkeypatch, tmp_path):
        cycle = 2024
        # district_id must match the raw file's can_office_state/can_office_dis
        # encoding below ("TX-01", "TX-02"), or every race's reconstructed
        # d_total/r_total silently degenerates to 0 regardless of the
        # synthetic IE data (a real gotcha worth flagging in a comment: the
        # join key is the district_id string, not list position).
        races = [
            RaceRecord(
                district_id="TX-01", state="TX", district=1,
                cook_rating="Toss-Up", incumb_status="Challenger",
                pvi=0.0, d_total=0.0, r_total=0.0,
                cvap=400_000, generic_ballot=-1.2, cand_d_total=200_000.0,
            ),
            RaceRecord(
                district_id="TX-02", state="TX", district=2,
                cook_rating="Toss-Up", incumb_status="Challenger",
                pvi=0.0, d_total=0.0, r_total=0.0,
                cvap=400_000, generic_ballot=-1.2, cand_d_total=200_000.0,
            ),
        ]

        # Both D- and R-aligned IE spend, dated before period 0, so the
        # reconstructed ratio is non-degenerate (real MSG gradient to chase)
        # rather than saturating at ratio ~= 1 with r ~= 0.
        raw_csv = tmp_path / f"independent_expenditure_{cycle}.csv"
        raw_csv.write_text(
            "can_office,ele_type,can_office_state,can_office_dis,cand_pty_aff,sup_opp,exp_amo,exp_date\n"
            "H,G,TX,01,DEMOCRATIC,S,1000000,05-JAN-24\n"
            "H,G,TX,01,REPUBLICAN,S,1000000,05-JAN-24\n"
            "H,G,TX,02,DEMOCRATIC,S,1000000,05-JAN-24\n"
            "H,G,TX,02,REPUBLICAN,S,1000000,05-JAN-24\n"
            # Additional spend after period 0 but before period 1, so period
            # 1's reconstructed state genuinely differs from period 0's —
            # a meaningful check, not just two identical snapshots.
            "H,G,TX,01,DEMOCRATIC,S,500000,15-FEB-24\n"
            "H,G,TX,02,DEMOCRATIC,S,500000,15-FEB-24\n"
        )
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)

        cand_csv = tmp_path / f"candidate_disbursements_{cycle}.csv"
        cand_csv.write_text("district_id,party,candidate_disbursements\n")
        coord_csv = tmp_path / f"coordinated_expenditures_{cycle}.csv"
        coord_csv.write_text("district_id,party,coordinated_expenditures\n")

        periods = [
            ReportingPeriod(index=0, period_date=date(2024, 1, 10), label="P0"),
            ReportingPeriod(index=1, period_date=date(2024, 2, 20), label="P1"),
        ]

        def run_with(total_budget):
            return one_step_ahead(
                periods, cycle, races, make_coef(), make_sigma(),
                ZeroCommitmentSource(), EMAStateUpdater(lam=0.7),
                cov_matrix_fn, gamma=0.0, cap_fraction=0.9,
                total_budget_fn=lambda t: total_budget,
                generic_ballot_national=-1.2,
            )

        # Very different deployable budgets -> mechanically different model
        # recommendations at period 0 (the budget constraint binds
        # differently), regardless of the MSG gradient's shape.
        results_a = run_with(total_budget=9_000_000.0)
        results_b = run_with(total_budget=100_000.0)

        assert results_a[0].optimizer_result.allocations.tolist() != \
            results_b[0].optimizer_result.allocations.tolist()

        # But period 1's reconstructed state must be identical regardless.
        races_1_a = results_a[1].state.to_race_records()
        races_1_b = results_b[1].state.to_race_records()
        for ra, rb in zip(races_1_a, races_1_b):
            assert ra.d_total == pytest.approx(rb.d_total)
            assert ra.r_total == pytest.approx(rb.r_total)


class TestDatedIEReconstruction:
    """Correctness of the point-in-time IE derivation against a small
    synthetic transaction list with known dates."""

    def _write_synthetic_ie_file(self, tmp_path, monkeypatch):
        raw_csv = tmp_path / "independent_expenditure_2024.csv"
        raw_csv.write_text(
            "can_office,ele_type,can_office_state,can_office_dis,cand_pty_aff,sup_opp,exp_amo,exp_date\n"
            # D-aligned: DEM candidate + support
            "H,G,TX,07,DEMOCRATIC,S,1000,01-JAN-24\n"
            # R-aligned: DEM candidate + oppose
            "H,G,TX,07,DEMOCRATIC,O,500,15-FEB-24\n"
            # R-aligned: REP candidate + support
            "H,G,TX,07,REPUBLICAN,S,2000,01-MAR-24\n"
            # D-aligned: REP candidate + oppose
            "H,G,TX,07,REPUBLICAN,O,300,10-JAN-24\n"
            # Dropped: blank exp_date
            "H,G,TX,07,DEMOCRATIC,S,999,\n"
            # Filtered: primary, not general
            "H,P,TX,07,DEMOCRATIC,S,999,01-JAN-24\n"
            # Filtered: not House
            "S,G,TX,07,DEMOCRATIC,S,999,01-JAN-24\n"
        )
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)

    def test_load_ie_transactions_dated_filters_and_aligns_correctly(self, tmp_path, monkeypatch):
        self._write_synthetic_ie_file(tmp_path, monkeypatch)
        txns = fec.load_ie_transactions_dated(2024)
        assert len(txns) == 4
        assert set(txns["district_id"]) == {"TX-07"}
        d_total = txns[txns["party"] == "D"]["amount"].sum()
        r_total = txns[txns["party"] == "R"]["amount"].sum()
        assert d_total == pytest.approx(1300.0)   # 1000 (S,DEM) + 300 (O,REP)
        assert r_total == pytest.approx(2500.0)   # 500 (O,DEM) + 2000 (S,REP)

    def test_cumulative_ie_as_of_is_monotonic_and_date_bounded(self, tmp_path, monkeypatch):
        self._write_synthetic_ie_file(tmp_path, monkeypatch)

        early = fec.cumulative_ie_as_of(2024, date(2024, 1, 20))
        late = fec.cumulative_ie_as_of(2024, date(2024, 3, 1))

        early_d = early[early["party"] == "D"]["ie_net"].sum()
        early_r = early[early["party"] == "R"]["ie_net"].sum() if (early["party"] == "R").any() else 0.0
        assert early_d == pytest.approx(1300.0)   # both D-aligned txns are <= Jan 20
        assert early_r == pytest.approx(0.0)      # both R-aligned txns are after Jan 20

        late_d = late[late["party"] == "D"]["ie_net"].sum()
        late_r = late[late["party"] == "R"]["ie_net"].sum()
        assert late_d == pytest.approx(1300.0)
        assert late_r == pytest.approx(2500.0)
