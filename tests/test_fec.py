"""Tests for src/backtest/data/fec.py's dated candidate-committee periodic
reports (data_catalog.md §2.7) — the panel that unblocks
docs/theta_followup_plan.md §0.1.1's previously-blocked wait-branch fix."""

from datetime import date

import pandas as pd
import pytest

from backtest import config
from backtest.data import fec


def _write_periodic_reports(tmp_path, cycle, rows):
    df = pd.DataFrame(rows, columns=[
        "district_id", "party", "cycle", "fec_candidate_id", "committee_id",
        "coverage_start_date", "coverage_end_date", "receipts_period",
        "disbursements_period", "cash_on_hand_end_period", "report_type_full",
        "beginning_image_number",
    ])
    df.to_csv(tmp_path / f"candidate_periodic_reports_{cycle}.csv", index=False)


class TestLoadCandidatePeriodicReports:
    def test_missing_file_raises_with_actionable_message(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        with pytest.raises(FileNotFoundError, match="fetch_data.py"):
            fec.load_candidate_periodic_reports(2024)

    def test_amendment_resolution_keeps_highest_image_number(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        _write_periodic_reports(tmp_path, 2024, [
            dict(district_id="PA-07", party="D", cycle=2024, fec_candidate_id="H1", committee_id="C1",
                 coverage_start_date="2024-01-01", coverage_end_date="2024-03-31",
                 receipts_period=10000, disbursements_period=5000, cash_on_hand_end_period=20000,
                 report_type_full="Q1", beginning_image_number="202404010001"),
            # amendment to the SAME coverage window, filed later (higher image number)
            dict(district_id="PA-07", party="D", cycle=2024, fec_candidate_id="H1", committee_id="C1",
                 coverage_start_date="2024-01-01", coverage_end_date="2024-03-31",
                 receipts_period=11000, disbursements_period=5500, cash_on_hand_end_period=20500,
                 report_type_full="Q1 AMENDED", beginning_image_number="202405010001"),
            dict(district_id="PA-07", party="D", cycle=2024, fec_candidate_id="H1", committee_id="C1",
                 coverage_start_date="2024-04-01", coverage_end_date="2024-06-30",
                 receipts_period=15000, disbursements_period=8000, cash_on_hand_end_period=27000,
                 report_type_full="Q2", beginning_image_number="202407010001"),
        ])
        reports = fec.load_candidate_periodic_reports(2024)
        assert len(reports) == 2   # amendment resolved down to one row per period
        q1 = reports[reports["coverage_end_date"] == pd.Timestamp("2024-03-31")].iloc[0]
        assert q1["disbursements_period"] == 5500   # the amended value, not the original 5000
        assert q1["cash_on_hand_end_period"] == 20500

    def test_unparseable_coverage_end_date_is_dropped_not_crashed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        _write_periodic_reports(tmp_path, 2024, [
            dict(district_id="PA-07", party="D", cycle=2024, fec_candidate_id="H1", committee_id="C1",
                 coverage_start_date="2024-01-01", coverage_end_date="",
                 receipts_period=10000, disbursements_period=5000, cash_on_hand_end_period=20000,
                 report_type_full="Q1", beginning_image_number="202404010001"),
            dict(district_id="PA-07", party="D", cycle=2024, fec_candidate_id="H1", committee_id="C1",
                 coverage_start_date="2024-04-01", coverage_end_date="2024-06-30",
                 receipts_period=15000, disbursements_period=8000, cash_on_hand_end_period=27000,
                 report_type_full="Q2", beginning_image_number="202407010001"),
        ])
        reports = fec.load_candidate_periodic_reports(2024)
        assert len(reports) == 1


class TestCumulativeCandidateSpendAsOf:
    def test_date_bounded_and_party_separated(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        _write_periodic_reports(tmp_path, 2024, [
            dict(district_id="PA-07", party="D", cycle=2024, fec_candidate_id="H1", committee_id="C1",
                 coverage_start_date="2024-01-01", coverage_end_date="2024-03-31",
                 receipts_period=10000, disbursements_period=5000, cash_on_hand_end_period=20000,
                 report_type_full="Q1", beginning_image_number="202404010001"),
            dict(district_id="PA-07", party="D", cycle=2024, fec_candidate_id="H1", committee_id="C1",
                 coverage_start_date="2024-04-01", coverage_end_date="2024-06-30",
                 receipts_period=15000, disbursements_period=8000, cash_on_hand_end_period=27000,
                 report_type_full="Q2", beginning_image_number="202407010001"),
            dict(district_id="PA-07", party="R", cycle=2024, fec_candidate_id="H2", committee_id="C2",
                 coverage_start_date="2024-01-01", coverage_end_date="2024-03-31",
                 receipts_period=8000, disbursements_period=4000, cash_on_hand_end_period=15000,
                 report_type_full="Q1", beginning_image_number="202404020001"),
        ])
        early = fec.cumulative_candidate_spend_as_of(2024, date(2024, 5, 1))
        d_early = early[(early.district_id == "PA-07") & (early.party == "D")].iloc[0]
        assert d_early["disb_cum"] == 5000
        r_early = early[(early.district_id == "PA-07") & (early.party == "R")].iloc[0]
        assert r_early["disb_cum"] == 4000

        late = fec.cumulative_candidate_spend_as_of(2024, date(2024, 7, 1))
        d_late = late[(late.district_id == "PA-07") & (late.party == "D")].iloc[0]
        assert d_late["disb_cum"] == 5000 + 8000

    def test_before_any_report_gives_zero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        _write_periodic_reports(tmp_path, 2024, [
            dict(district_id="PA-07", party="D", cycle=2024, fec_candidate_id="H1", committee_id="C1",
                 coverage_start_date="2024-01-01", coverage_end_date="2024-03-31",
                 receipts_period=10000, disbursements_period=5000, cash_on_hand_end_period=20000,
                 report_type_full="Q1", beginning_image_number="202404010001"),
        ])
        early = fec.cumulative_candidate_spend_as_of(2024, date(2024, 1, 15))
        assert not len(early[early.district_id == "PA-07"])   # no rows -> caller treats as 0.0


class TestCumulativeCandidateReceiptsAsOf:
    def test_tracks_receipts_not_disbursements(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        _write_periodic_reports(tmp_path, 2024, [
            dict(district_id="PA-07", party="D", cycle=2024, fec_candidate_id="H1", committee_id="C1",
                 coverage_start_date="2024-01-01", coverage_end_date="2024-03-31",
                 receipts_period=10000, disbursements_period=5000, cash_on_hand_end_period=20000,
                 report_type_full="Q1", beginning_image_number="202404010001"),
        ])
        cum = fec.cumulative_candidate_receipts_as_of(2024, date(2024, 5, 1))
        row = cum[cum.district_id == "PA-07"].iloc[0]
        assert row["receipts_cum"] == 10000


class TestCashOnHandAsOf:
    def test_returns_most_recent_report_as_of_date(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        _write_periodic_reports(tmp_path, 2024, [
            dict(district_id="PA-07", party="D", cycle=2024, fec_candidate_id="H1", committee_id="C1",
                 coverage_start_date="2024-01-01", coverage_end_date="2024-03-31",
                 receipts_period=10000, disbursements_period=5000, cash_on_hand_end_period=20000,
                 report_type_full="Q1", beginning_image_number="202404010001"),
            dict(district_id="PA-07", party="D", cycle=2024, fec_candidate_id="H1", committee_id="C1",
                 coverage_start_date="2024-04-01", coverage_end_date="2024-06-30",
                 receipts_period=15000, disbursements_period=8000, cash_on_hand_end_period=27000,
                 report_type_full="Q2", beginning_image_number="202407010001"),
        ])
        coh_mid = fec.cash_on_hand_as_of(2024, date(2024, 5, 1))
        assert coh_mid[coh_mid.district_id == "PA-07"].iloc[0]["cash_on_hand"] == 20000
        coh_late = fec.cash_on_hand_as_of(2024, date(2024, 7, 1))
        assert coh_late[coh_late.district_id == "PA-07"].iloc[0]["cash_on_hand"] == 27000

    def test_district_with_no_report_yet_is_absent_not_zero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        _write_periodic_reports(tmp_path, 2024, [
            dict(district_id="PA-07", party="D", cycle=2024, fec_candidate_id="H1", committee_id="C1",
                 coverage_start_date="2024-04-01", coverage_end_date="2024-06-30",
                 receipts_period=15000, disbursements_period=8000, cash_on_hand_end_period=27000,
                 report_type_full="Q2", beginning_image_number="202407010001"),
        ])
        coh = fec.cash_on_hand_as_of(2024, date(2024, 1, 15))
        assert not len(coh[coh.district_id == "PA-07"])


class TestSpendAndReceiptsVelocity:
    def test_window_excludes_reports_outside_trailing_window(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        _write_periodic_reports(tmp_path, 2024, [
            # far outside the 30-day window ending 2024-07-01
            dict(district_id="PA-07", party="D", cycle=2024, fec_candidate_id="H1", committee_id="C1",
                 coverage_start_date="2024-01-01", coverage_end_date="2024-01-31",
                 receipts_period=10000, disbursements_period=5000, cash_on_hand_end_period=20000,
                 report_type_full="Q1", beginning_image_number="202402010001"),
            # inside the window
            dict(district_id="PA-07", party="D", cycle=2024, fec_candidate_id="H1", committee_id="C1",
                 coverage_start_date="2024-06-01", coverage_end_date="2024-06-20",
                 receipts_period=6000, disbursements_period=3000, cash_on_hand_end_period=23000,
                 report_type_full="pre-general", beginning_image_number="202406210001"),
        ])
        vel = fec.spend_velocity(2024, date(2024, 7, 1), window_days=30)
        row = vel[vel.district_id == "PA-07"].iloc[0]
        assert row["disb_velocity_per_day"] == pytest.approx(3000 / 30)

        rvel = fec.receipts_velocity(2024, date(2024, 7, 1), window_days=30)
        rrow = rvel[rvel.district_id == "PA-07"].iloc[0]
        assert rrow["receipts_velocity_per_day"] == pytest.approx(6000 / 30)
