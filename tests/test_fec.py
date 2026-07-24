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


# ─── Paper I core spend-aggregation functions ─────────────────────────────────
# (load_candidate_disbursements, load_coordinated_expenditures,
# load_independent_expenditures, build_total_spend) — the functions that feed
# d_total/r_total for the entire historical panel and every backtest cycle,
# previously untested despite being the most consequential loaders in the module.

def _write_candidate_disbursements(tmp_path, cycle, rows):
    df = pd.DataFrame(rows, columns=[
        "district_id", "fec_candidate_id", "candidate_name", "party", "cycle",
        "candidate_disbursements", "incumbent_challenge_full",
        "ttl_receipts", "ttl_indiv_contrib", "indiv_share",
    ])
    df.to_csv(tmp_path / f"candidate_disbursements_{cycle}.csv", index=False)


def _write_mit_house_file(tmp_path, rows):
    """rows: list of dicts with year, stage, state_po, district, party, candidate."""
    df = pd.DataFrame(rows)
    (tmp_path / "mit").mkdir(exist_ok=True)
    df.to_csv(tmp_path / "mit" / "1976-2024-house.tab", index=False)


class TestLoadCandidateDisbursements:
    def test_selects_top_spender_per_party_as_nominee_proxy(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path / source if source == "mit" else tmp_path)
        _write_candidate_disbursements(tmp_path, 2024, [
            dict(district_id="TX-01", fec_candidate_id="D1", candidate_name="WINNER, D",
                 party="D", cycle=2024, candidate_disbursements=2_000_000,
                 incumbent_challenge_full="Open seat", ttl_receipts=2_200_000,
                 ttl_indiv_contrib=1_100_000, indiv_share=0.5),
            # primary loser: same district/party, lower spend -- must NOT be selected
            dict(district_id="TX-01", fec_candidate_id="D2", candidate_name="LOSER, D",
                 party="D", cycle=2024, candidate_disbursements=500_000,
                 incumbent_challenge_full="Open seat", ttl_receipts=550_000,
                 ttl_indiv_contrib=200_000, indiv_share=0.36),
            dict(district_id="TX-01", fec_candidate_id="R1", candidate_name="NOMINEE, R",
                 party="R", cycle=2024, candidate_disbursements=1_800_000,
                 incumbent_challenge_full="Open seat", ttl_receipts=1_900_000,
                 ttl_indiv_contrib=900_000, indiv_share=0.47),
        ])
        result = fec.load_candidate_disbursements(2024)
        assert len(result) == 2   # one row per party, primary loser dropped
        d_row = result[(result.district_id == "TX-01") & (result.party == "D")].iloc[0]
        assert d_row["candidate_disbursements"] == 2_000_000
        assert d_row["indiv_share"] == pytest.approx(0.5)

    def test_indiv_share_defaults_to_zero_when_column_absent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path / source if source == "mit" else tmp_path)
        df = pd.DataFrame([
            dict(district_id="TX-01", fec_candidate_id="D1", candidate_name="A, B",
                 party="D", cycle=2024, candidate_disbursements=1_000_000,
                 incumbent_challenge_full="Open seat"),
        ])
        df.to_csv(tmp_path / "candidate_disbursements_2024.csv", index=False)
        result = fec.load_candidate_disbursements(2024)
        assert result.iloc[0]["indiv_share"] == 0.0

    def test_large_spender_not_on_ballot_is_excluded(self, tmp_path, monkeypatch):
        """Regression for the Gallego/Schiff-style artifact: a House member's
        committee that disbursed >$10M while actually running for a different
        office must not inflate their old House district's totals."""
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path / source if source == "mit" else tmp_path)
        _write_candidate_disbursements(tmp_path, 2024, [
            # $59M spender NOT on the MIT House general-election ballot (ran for Senate instead)
            dict(district_id="AZ-03", fec_candidate_id="D1", candidate_name="RANFORSENATE, GALLEGO",
                 party="D", cycle=2024, candidate_disbursements=59_000_000,
                 incumbent_challenge_full="Incumbent", ttl_receipts=60_000_000,
                 ttl_indiv_contrib=30_000_000, indiv_share=0.5),
            # legitimate on-ballot D nominee, low spend
            dict(district_id="AZ-03", fec_candidate_id="D2", candidate_name="REALNOMINEE, SMITH",
                 party="D", cycle=2024, candidate_disbursements=800_000,
                 incumbent_challenge_full="Open seat", ttl_receipts=850_000,
                 ttl_indiv_contrib=400_000, indiv_share=0.47),
            dict(district_id="AZ-03", fec_candidate_id="R1", candidate_name="NOMINEE, JONES",
                 party="R", cycle=2024, candidate_disbursements=700_000,
                 incumbent_challenge_full="Open seat", ttl_receipts=750_000,
                 ttl_indiv_contrib=300_000, indiv_share=0.4),
        ])
        _write_mit_house_file(tmp_path, [
            dict(year=2024, stage="GEN", state_po="AZ", district="03",
                 party="DEMOCRAT", candidate="JOHN SMITH"),
            dict(year=2024, stage="GEN", state_po="AZ", district="03",
                 party="REPUBLICAN", candidate="ROBERT JONES"),
        ])
        result = fec.load_candidate_disbursements(2024)
        d_row = result[(result.district_id == "AZ-03") & (result.party == "D")].iloc[0]
        # the $59M off-ballot spender must have been filtered before top-spender
        # selection, leaving the legitimate $800K on-ballot nominee
        assert d_row["candidate_disbursements"] == 800_000

    def test_small_spender_passes_through_without_ballot_match(self, tmp_path, monkeypatch):
        """Candidates under the $10M threshold pass through regardless of MIT
        name-matching, to avoid false exclusions from name-format mismatches
        (JR/SR suffixes, compound names) -- per the code's documented rationale."""
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path / source if source == "mit" else tmp_path)
        _write_candidate_disbursements(tmp_path, 2024, [
            dict(district_id="OH-05", fec_candidate_id="D1", candidate_name="NOMATCH, NAME",
                 party="D", cycle=2024, candidate_disbursements=300_000,
                 incumbent_challenge_full="Open seat", ttl_receipts=310_000,
                 ttl_indiv_contrib=150_000, indiv_share=0.48),
        ])
        # MIT file has GEN rows for 2024 but none matching this candidate's name
        _write_mit_house_file(tmp_path, [
            dict(year=2024, stage="GEN", state_po="OH", district="05",
                 party="DEMOCRAT", candidate="SOMEONE ELSE"),
        ])
        result = fec.load_candidate_disbursements(2024)
        assert len(result) == 1
        assert result.iloc[0]["candidate_disbursements"] == 300_000

    def test_manual_live_cycle_exclusion_applied_without_mit_data(self, tmp_path, monkeypatch):
        """When no MIT ballot data exists yet (a live, in-progress cycle),
        config.yaml's live_cycle_ballot_exclusions is the documented fallback
        for excluding a specific known off-ballot large spender, while other
        large spenders honestly pass through (no MIT data, not manually
        excluded)."""
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        monkeypatch.setattr(config, "live_cycle_ballot_exclusions",
                             lambda cycle: [{"district_id": "CA-30", "party": "D", "last_name": "SCHIFF"}])
        _write_candidate_disbursements(tmp_path, 2026, [
            dict(district_id="CA-30", fec_candidate_id="D1", candidate_name="SCHIFF, ADAM",
                 party="D", cycle=2026, candidate_disbursements=45_000_000,
                 incumbent_challenge_full="Incumbent", ttl_receipts=46_000_000,
                 ttl_indiv_contrib=20_000_000, indiv_share=0.43),
            dict(district_id="CA-30", fec_candidate_id="D2", candidate_name="NOMINEE, REAL",
                 party="D", cycle=2026, candidate_disbursements=900_000,
                 incumbent_challenge_full="Open seat", ttl_receipts=950_000,
                 ttl_indiv_contrib=450_000, indiv_share=0.47),
            # a different large spender, NOT manually excluded, no MIT data -> passes through
            dict(district_id="NY-10", fec_candidate_id="D3", candidate_name="BIGSPENDER, UNLISTED",
                 party="D", cycle=2026, candidate_disbursements=15_000_000,
                 incumbent_challenge_full="Incumbent", ttl_receipts=15_500_000,
                 ttl_indiv_contrib=7_000_000, indiv_share=0.45),
        ])
        result = fec.load_candidate_disbursements(2026)
        ca30 = result[(result.district_id == "CA-30") & (result.party == "D")].iloc[0]
        assert ca30["candidate_disbursements"] == 900_000   # Schiff excluded
        ny10 = result[(result.district_id == "NY-10") & (result.party == "D")].iloc[0]
        assert ny10["candidate_disbursements"] == 15_000_000   # honest pass-through


class TestLoadCoordinatedExpenditures:
    def test_reads_and_coerces_numeric(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        pd.DataFrame([
            dict(district_id="PA-07", party="D", cycle=2024, coordinated_expenditures=190_000),
            dict(district_id="PA-07", party="R", cycle=2024, coordinated_expenditures="not_a_number"),
        ]).to_csv(tmp_path / "coordinated_expenditures_2024.csv", index=False)
        result = fec.load_coordinated_expenditures(2024)
        d_row = result[(result.district_id == "PA-07") & (result.party == "D")].iloc[0]
        r_row = result[(result.district_id == "PA-07") & (result.party == "R")].iloc[0]
        assert d_row["coordinated_expenditures"] == 190_000
        assert r_row["coordinated_expenditures"] == 0   # malformed value coerced to 0, not NaN/crash


class TestLoadIndependentExpenditures:
    def test_aggregates_multiple_rows_by_district_and_party(self, tmp_path, monkeypatch):
        """Comprehensive format: district_id, party [D/R-aligned], cycle, amount."""
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        pd.DataFrame([
            dict(district_id="PA-07", party="D", cycle=2024, amount=500_000),
            dict(district_id="PA-07", party="D", cycle=2024, amount=250_000),
            dict(district_id="PA-07", party="R", cycle=2024, amount=300_000),
        ]).to_csv(tmp_path / "independent_expenditures_2024.csv", index=False)
        result = fec.load_independent_expenditures(2024)
        d_row = result[(result.district_id == "PA-07") & (result.party == "D")].iloc[0]
        r_row = result[(result.district_id == "PA-07") & (result.party == "R")].iloc[0]
        assert d_row["ie_net"] == 750_000
        assert r_row["ie_net"] == 300_000

    def test_legacy_format_with_support_oppose_column_also_aggregates(self, tmp_path, monkeypatch):
        """Legacy DCCC/NRCC-only format carries an extra support_oppose column;
        amounts are still unsigned with party alignment already reflected in
        `party`, so aggregation must behave identically to the comprehensive format."""
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        pd.DataFrame([
            dict(district_id="PA-07", party="D", cycle=2024, support_oppose="S", amount=400_000),
            dict(district_id="PA-07", party="D", cycle=2024, support_oppose="O", amount=100_000),
        ]).to_csv(tmp_path / "independent_expenditures_2024.csv", index=False)
        result = fec.load_independent_expenditures(2024)
        d_row = result[(result.district_id == "PA-07") & (result.party == "D")].iloc[0]
        assert d_row["ie_net"] == 500_000


class TestBuildTotalSpend:
    def test_combines_all_three_components_per_party(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        _write_candidate_disbursements(tmp_path, 2024, [
            dict(district_id="PA-07", fec_candidate_id="D1", candidate_name="A, B", party="D",
                 cycle=2024, candidate_disbursements=1_000_000, incumbent_challenge_full="Open seat",
                 ttl_receipts=1_100_000, ttl_indiv_contrib=500_000, indiv_share=0.45),
            dict(district_id="PA-07", fec_candidate_id="R1", candidate_name="C, D", party="R",
                 cycle=2024, candidate_disbursements=900_000, incumbent_challenge_full="Open seat",
                 ttl_receipts=950_000, ttl_indiv_contrib=400_000, indiv_share=0.42),
        ])
        pd.DataFrame([
            dict(district_id="PA-07", party="D", cycle=2024, coordinated_expenditures=190_000),
            dict(district_id="PA-07", party="R", cycle=2024, coordinated_expenditures=150_000),
        ]).to_csv(tmp_path / "coordinated_expenditures_2024.csv", index=False)
        pd.DataFrame([
            dict(district_id="PA-07", party="D", cycle=2024, amount=300_000),
            dict(district_id="PA-07", party="R", cycle=2024, amount=250_000),
        ]).to_csv(tmp_path / "independent_expenditures_2024.csv", index=False)

        result = fec.build_total_spend(2024)
        row = result[result.district_id == "PA-07"].iloc[0]
        assert row["d_total"] == pytest.approx(1_000_000 + 190_000 + 300_000)
        assert row["r_total"] == pytest.approx(900_000 + 150_000 + 250_000)

    def test_missing_coordinated_and_ie_components_fill_with_zero(self, tmp_path, monkeypatch):
        """A district with candidate spend but no coordinated/IE rows at all
        must still produce a finite d_total/r_total equal to candidate spend
        alone, not NaN -- both coordinated_expenditures_2024.csv and
        independent_expenditures_2024.csv exist (schema-only) but have no
        rows for this district."""
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        _write_candidate_disbursements(tmp_path, 2024, [
            dict(district_id="PA-07", fec_candidate_id="D1", candidate_name="A, B", party="D",
                 cycle=2024, candidate_disbursements=500_000, incumbent_challenge_full="Open seat",
                 ttl_receipts=520_000, ttl_indiv_contrib=250_000, indiv_share=0.48),
        ])
        pd.DataFrame(columns=["district_id", "party", "cycle", "coordinated_expenditures"]).to_csv(
            tmp_path / "coordinated_expenditures_2024.csv", index=False)
        pd.DataFrame(columns=["district_id", "party", "cycle", "amount"]).to_csv(
            tmp_path / "independent_expenditures_2024.csv", index=False)

        result = fec.build_total_spend(2024)
        row = result[result.district_id == "PA-07"].iloc[0]
        assert row["d_total"] == pytest.approx(500_000)
        assert not pd.isna(row["d_total"])
