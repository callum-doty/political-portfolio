"""Tests for dynamic/ledger.py — CapitalLedger and CommitmentSource impls (paper §3.2)."""

from datetime import date

import pytest

from backtest import config
from backtest.types import RaceRecord
from backtest.dynamic.ledger import (
    CapitalLedger, ZeroCommitmentSource, OperationalLedgerSource, AdReservationProxySource,
    RealizedSpendCommitmentSource,
)


def make_races(n: int) -> list[RaceRecord]:
    return [
        RaceRecord(
            district_id=f"XX-{i:02d}", state="XX", district=i + 1,
            cook_rating="Toss-Up", incumb_status="Challenger",
            pvi=0.0, d_total=2_000_000.0, r_total=2_000_000.0,
            cvap=400_000, generic_ballot=-1.2, cand_d_total=200_000.0,
        )
        for i in range(n)
    ]


class TestZeroCommitmentSource:
    def test_returns_zero_for_all_races(self):
        races = make_races(3)
        source = ZeroCommitmentSource()
        committed = source.committed_capital(0, date(2024, 3, 1), races)
        assert all(v == 0.0 for v in committed.values())
        assert set(committed.keys()) == {r.district_id for r in races}


class TestOperationalLedgerSource:
    def test_reads_committed_capital_for_period(self, tmp_path):
        races = make_races(2)
        ledger_csv = tmp_path / "ledger.csv"
        ledger_csv.write_text(
            "period,district_id,committed\n"
            "0,XX-00,100000\n"
            "0,XX-01,50000\n"
            "1,XX-00,300000\n"
        )
        source = OperationalLedgerSource(ledger_csv)
        committed_0 = source.committed_capital(0, date(2024, 3, 1), races)
        assert committed_0["XX-00"] == 100_000.0
        assert committed_0["XX-01"] == 50_000.0

        committed_1 = source.committed_capital(1, date(2024, 4, 1), races)
        assert committed_1["XX-00"] == 300_000.0
        assert "XX-01" not in committed_1

    def test_missing_column_raises(self, tmp_path):
        bad_csv = tmp_path / "bad_ledger.csv"
        bad_csv.write_text("period,district_id\n0,XX-00\n")
        with pytest.raises(ValueError, match="missing columns"):
            OperationalLedgerSource(bad_csv)


class TestAdReservationProxySource:
    def test_strict_raises(self):
        races = make_races(1)
        source = AdReservationProxySource(strict=True)
        with pytest.raises(NotImplementedError):
            source.committed_capital(0, date(2024, 3, 1), races)

    def test_non_strict_returns_zero_with_warning(self, caplog):
        races = make_races(2)
        source = AdReservationProxySource(strict=False)
        with caplog.at_level("WARNING"):
            committed = source.committed_capital(0, date(2024, 3, 1), races)
        assert all(v == 0.0 for v in committed.values())
        assert any("no real ad-reservation data source" in r.message for r in caplog.records)


class TestCapitalLedger:
    def test_build_with_zero_commitment(self):
        races = make_races(3)
        ledger = CapitalLedger.build(0, 10_000_000.0, ZeroCommitmentSource(), date(2024, 3, 1), races)
        assert ledger.committed_total == 0.0
        assert ledger.deployable_total == 10_000_000.0

    def test_build_raises_if_committed_exceeds_budget(self, tmp_path):
        races = make_races(1)
        ledger_csv = tmp_path / "ledger.csv"
        ledger_csv.write_text("period,district_id,committed\n0,XX-00,20000000\n")
        source = OperationalLedgerSource(ledger_csv)
        with pytest.raises(ValueError, match="exceeds total budget"):
            CapitalLedger.build(0, 10_000_000.0, source, date(2024, 3, 1), races)

    def test_deployable_floor_for_adds_committed_to_cand_floor(self, tmp_path):
        races = make_races(2)
        ledger_csv = tmp_path / "ledger.csv"
        ledger_csv.write_text(
            "period,district_id,committed\n0,XX-00,100000\n0,XX-01,0\n"
        )
        source = OperationalLedgerSource(ledger_csv)
        ledger = CapitalLedger.build(0, 5_000_000.0, source, date(2024, 3, 1), races)
        floor = ledger.deployable_floor_for(races)
        assert floor[0] == pytest.approx(300_000.0)   # cand_d_total 200k + committed 100k
        assert floor[1] == pytest.approx(200_000.0)   # cand_d_total 200k + committed 0

    def test_apply_to_races_bakes_floor_into_cand_d_total(self, tmp_path):
        races = make_races(1)
        ledger_csv = tmp_path / "ledger.csv"
        ledger_csv.write_text("period,district_id,committed\n0,XX-00,150000\n")
        source = OperationalLedgerSource(ledger_csv)
        ledger = CapitalLedger.build(0, 5_000_000.0, source, date(2024, 3, 1), races)
        adjusted = ledger.apply_to_races(races)
        assert adjusted[0].cand_d_total == pytest.approx(350_000.0)
        # original races list is untouched
        assert races[0].cand_d_total == 200_000.0


class TestRealizedSpendCommitmentSource:
    """L_t = already-disbursed coordinated + independent expenditure spend
    (real, lower-bound alternative to AdReservationProxySource)."""

    def _write_synthetic_fec_files(self, tmp_path, monkeypatch, cycle: int):
        (tmp_path / f"coordinated_expenditures_{cycle}.csv").write_text(
            "district_id,party,cycle,coordinated_expenditures\n"
            "XX-00,D,{c},50000\n"
            "XX-01,D,{c},0\n"
            "XX-00,R,{c},20000\n".format(c=cycle)
        )
        (tmp_path / f"independent_expenditure_{cycle}.csv").write_text(
            "can_office,ele_type,can_office_state,can_office_dis,cand_pty_aff,sup_opp,exp_amo,exp_date\n"
            "H,G,XX,00,DEMOCRATIC,S,30000,01-JAN-24\n"   # -> D-aligned, XX-00, before period_date
            "H,G,XX,00,DEMOCRATIC,S,90000,01-DEC-24\n"   # -> D-aligned, XX-00, AFTER period_date
        )
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)

    def test_combines_coordinated_and_dated_ie(self, tmp_path, monkeypatch):
        cycle = 2024
        self._write_synthetic_fec_files(tmp_path, monkeypatch, cycle)
        races = make_races(2)
        source = RealizedSpendCommitmentSource(cycle=cycle, party="D")

        committed = source.committed_capital(0, date(2024, 3, 1), races)
        # XX-00: 50000 coordinated + 30000 IE (only the pre-March-1 transaction) = 80000
        assert committed["XX-00"] == pytest.approx(80_000.0)
        # XX-01: no coordinated, no IE
        assert committed["XX-01"] == pytest.approx(0.0)

    def test_ie_component_grows_with_later_period_date(self, tmp_path, monkeypatch):
        cycle = 2024
        self._write_synthetic_fec_files(tmp_path, monkeypatch, cycle)
        races = make_races(2)
        source = RealizedSpendCommitmentSource(cycle=cycle, party="D")

        early = source.committed_capital(0, date(2024, 3, 1), races)
        late = source.committed_capital(1, date(2024, 12, 31), races)
        # Late period includes both IE transactions -> 50000 coordinated + 120000 IE
        assert late["XX-00"] == pytest.approx(170_000.0)
        assert late["XX-00"] > early["XX-00"]

    def test_republican_spend_excluded_by_default_party_filter(self, tmp_path, monkeypatch):
        cycle = 2024
        self._write_synthetic_fec_files(tmp_path, monkeypatch, cycle)
        races = make_races(2)
        source = RealizedSpendCommitmentSource(cycle=cycle, party="D")
        committed = source.committed_capital(0, date(2024, 3, 1), races)
        # The 20000 R-aligned coordinated expenditure in XX-00 must not leak into D's L_t
        assert committed["XX-00"] == pytest.approx(80_000.0)
