"""
Tests for scripts/fetch_data.py's state-party 24K coordinated-expenditure
functions (FINDINGS.md Section 10.7, Gap 3): _load_committee_master(),
identify_state_dem_party_committees(), _itoth_file_year_range(),
_scan_itoth_file_for_24k(), parse_state_party_coordinated_24k().
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from backtest import config  # noqa: E402

import fetch_data as fd  # noqa: E402


def _write_cm(tmp_path, rows, filename="cm.txt"):
    """rows: list of dicts with keys cmte_id, cmte_nm, cmte_st, cmte_dsgn,
    cmte_tp, cmte_pty_affiliation -- other cm.txt fields filled with ''."""
    lines = []
    for r in rows:
        fields = [
            r["cmte_id"], r["cmte_nm"], "", "", "", "", r.get("cmte_st", ""), "",
            r.get("cmte_dsgn", "U"), r.get("cmte_tp", "Y"), r.get("cmte_pty_affiliation", "DEM"),
            "M", "", "", "",
        ]
        lines.append("|".join(fields))
    (tmp_path / filename).write_text("\n".join(lines) + "\n")


def _write_cn(tmp_path, rows, filename="cn.txt"):
    """rows: list of dicts with keys cand_id, cand_office_st, cand_office_district."""
    lines = []
    for r in rows:
        fields = [
            r["cand_id"], r.get("cand_name", "TEST CANDIDATE"), "DEM", "2024",
            r["cand_office_st"], "H", r["cand_office_district"], "C", "C", "",
            "", "", "", "", "",
        ]
        lines.append("|".join(fields))
    (tmp_path / filename).write_text("\n".join(lines) + "\n")


def _write_ccl(tmp_path, rows, filename="ccl.txt"):
    """rows: list of dicts with keys cand_id, fec_election_yr, cmte_id."""
    lines = []
    for r in rows:
        fields = [r["cand_id"], r.get("cand_election_yr", "2024"), str(r["fec_election_yr"]),
                  r["cmte_id"], "H", "P", "1"]
        lines.append("|".join(fields))
    (tmp_path / filename).write_text("\n".join(lines) + "\n")


def _write_itoth(tmp_path, rows, filename="itoth.txt"):
    """rows: list of dicts with keys cmte_id, transaction_tp, entity_tp,
    transaction_dt (MMDDYYYY), transaction_amt, other_id, sub_id."""
    lines = []
    for r in rows:
        fields = [
            r.get("cmte_id", "C1"), "N", "M6", "", "", r.get("transaction_tp", "24K"),
            r.get("entity_tp", "CCM"), "SOME NAME", "", "", "", "", "",
            r.get("transaction_dt", "01152024"), str(r.get("transaction_amt", 1000.0)),
            r.get("other_id", ""), "TRAN1", "1", "", "", str(r.get("sub_id", "1")),
        ]
        lines.append("|".join(fields))
    (tmp_path / filename).write_text("\n".join(lines) + "\n")


@pytest.fixture
def single_raw_dir(tmp_path, monkeypatch):
    """Route every config.raw_path() source used by these functions to the
    same tmp_path -- the real filename patterns (cm*.txt, cn*.txt, ccl*.txt,
    itoth*.txt) don't collide, mirroring how the real multi-source layout
    could in principle share one directory."""
    monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
    return tmp_path


# ─── _load_committee_master() ───────────────────────────────────────────────

class TestLoadCommitteeMaster:
    def test_reads_all_numbered_siblings_and_dedupes(self, single_raw_dir):
        _write_cm(single_raw_dir, [{"cmte_id": "C001", "cmte_nm": "NAME A", "cmte_st": "TX"}], "cm.txt")
        _write_cm(single_raw_dir, [{"cmte_id": "C001", "cmte_nm": "NAME B", "cmte_st": "TX"},
                                    {"cmte_id": "C002", "cmte_nm": "OTHER", "cmte_st": "OH"}], "cm 2.txt")
        cm = fd._load_committee_master()
        # Every numbered sibling is read (not just cm.txt), and duplicate
        # cmte_ids across files collapse to exactly one row each -- which
        # file's row is kept is an accepted, documented looseness (matches
        # _load_candidate_committee_crosswalk's own "keep last as an
        # approximation" precedent), not asserted here.
        assert set(cm["cmte_id"]) == {"C001", "C002"}
        assert len(cm) == 2
        assert cm.set_index("cmte_id").loc["C001", "cmte_nm"] in {"NAME A", "NAME B"}

    def test_missing_directory_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path / "does_not_exist")
        with pytest.raises(FileNotFoundError):
            fd._load_committee_master()


# ─── identify_state_dem_party_committees() ──────────────────────────────────

class TestIdentifyStateDemPartyCommittees:
    def test_admits_real_state_party_pattern(self, single_raw_dir):
        _write_cm(single_raw_dir, [
            {"cmte_id": "C100", "cmte_nm": "NEBRASKA DEMOCRATIC PARTY", "cmte_st": "NE"},
        ])
        result = fd.identify_state_dem_party_committees()
        assert "C100" in set(result["committee_id"])

    def test_excludes_national_committees(self, single_raw_dir):
        _write_cm(single_raw_dir, [
            {"cmte_id": fd.DCCC_COMMITTEE_ID, "cmte_nm": "DCCC", "cmte_st": "DC"},
            {"cmte_id": fd.DNC_COMMITTEE_ID, "cmte_nm": "DNC SERVICES CORP / DEMOCRATIC NATIONAL COMMITTEE", "cmte_st": "DC"},
        ])
        result = fd.identify_state_dem_party_committees()
        assert result.empty

    def test_excludes_town_and_county_committees(self, single_raw_dir):
        _write_cm(single_raw_dir, [
            {"cmte_id": "C200", "cmte_nm": "KENNEBUNKPORT DEMOCRATIC COMMITTEE", "cmte_st": "ME"},
            {"cmte_id": "C201", "cmte_nm": "MONTGOMERY COUNTY DEMOCRATIC CENTRAL COMMITTEE", "cmte_st": "MD"},
        ])
        result = fd.identify_state_dem_party_committees()
        assert result.empty

    def test_excludes_congressional_and_legislative_district_committees(self, single_raw_dir):
        _write_cm(single_raw_dir, [
            {"cmte_id": "C300", "cmte_nm": "MICHIGAN FIRST CONGRESSIONAL DISTRICT DEMOCRATS", "cmte_st": "MI"},
            {"cmte_id": "C301", "cmte_nm": "SIXTH DISTRICT DEMOCRATIC PARTY OF WISCONSIN", "cmte_st": "WI"},
        ])
        result = fd.identify_state_dem_party_committees()
        assert result.empty

    def test_excludes_clubs_caucuses_and_trusts(self, single_raw_dir):
        _write_cm(single_raw_dir, [
            {"cmte_id": "C400", "cmte_nm": "INLAND VALLEY DEMOCRATIC CLUB", "cmte_st": "CA"},
            {"cmte_id": "C401", "cmte_nm": "AFRICAN AMERICAN CAUCUS OF THE NORTH CAROLINA DEMOCRATIC PARTY", "cmte_st": "NC"},
            {"cmte_id": "C402", "cmte_nm": "CALIFORNIA STATE OF THE UNION DEMOCRATIC PARTY TRUST", "cmte_st": "CA"},
        ])
        result = fd.identify_state_dem_party_committees()
        assert result.empty

    def test_excludes_non_dem_and_non_party_designations(self, single_raw_dir):
        _write_cm(single_raw_dir, [
            {"cmte_id": "C500", "cmte_nm": "TEXAS REPUBLICAN PARTY", "cmte_st": "TX", "cmte_pty_affiliation": "REP"},
            {"cmte_id": "C501", "cmte_nm": "TEXAS DEMOCRATIC PARTY PAC", "cmte_st": "TX", "cmte_tp": "N"},
            {"cmte_id": "C502", "cmte_nm": "TEXAS DEMOCRATIC CANDIDATE COMMITTEE", "cmte_st": "TX", "cmte_dsgn": "P"},
        ])
        result = fd.identify_state_dem_party_committees()
        assert result.empty

    def test_manual_override_ids_are_included_even_without_a_structural_match(self, single_raw_dir):
        _write_cm(single_raw_dir, [
            {"cmte_id": "C00041269", "cmte_nm": "GEORGIA FEDERAL ELECTIONS COMMITTEE", "cmte_st": "GA"},
        ])
        result = fd.identify_state_dem_party_committees()
        assert "C00041269" in set(result["committee_id"])

    def test_handles_hyphenated_and_reordered_suffix_variants(self, single_raw_dir):
        """Regression guard for two real-data patterns found during
        development: DEMOCRATIC-NONPARTISAN LEAGUE PARTY (hyphen, not
        space) and STATE DEMOCRATIC COMMITTEE (STATE before DEMOCRATIC,
        not after)."""
        _write_cm(single_raw_dir, [
            {"cmte_id": "C600", "cmte_nm": "NORTH DAKOTA DEMOCRATIC-NONPARTISAN LEAGUE PARTY", "cmte_st": "ND"},
            {"cmte_id": "C601", "cmte_nm": "NEW YORK STATE DEMOCRATIC COMMITTEE", "cmte_st": "NY"},
        ])
        result = fd.identify_state_dem_party_committees()
        assert {"C600", "C601"} <= set(result["committee_id"])


# ─── _itoth_file_year_range() ────────────────────────────────────────────────

class TestItothFileYearRange:
    def test_extracts_year_from_transaction_dt_field(self, tmp_path):
        rows = [{"transaction_dt": "01152023", "sub_id": i} for i in range(50)]
        rows += [{"transaction_dt": "11302024", "sub_id": i} for i in range(50, 100)]
        _write_itoth(tmp_path, rows, "small.txt")
        lo, hi = fd._itoth_file_year_range(tmp_path / "small.txt")
        assert lo <= 2023 and hi >= 2024

    def test_empty_file_returns_zero_range(self, tmp_path):
        (tmp_path / "empty.txt").write_text("")
        assert fd._itoth_file_year_range(tmp_path / "empty.txt") == (0, 0)


# ─── _scan_itoth_file_for_24k() ──────────────────────────────────────────────

class TestScanItothFileFor24k:
    def test_filters_transaction_type_and_entity_type_and_year(self, tmp_path):
        _write_itoth(tmp_path, [
            {"cmte_id": "C1", "transaction_tp": "24K", "entity_tp": "CCM",
             "transaction_dt": "01152024", "other_id": "CAND1", "sub_id": "1"},
            {"cmte_id": "C1", "transaction_tp": "24K", "entity_tp": "PTY",   # wrong entity_tp
             "transaction_dt": "01152024", "other_id": "CAND2", "sub_id": "2"},
            {"cmte_id": "C1", "transaction_tp": "24E", "entity_tp": "CCM",   # wrong transaction_tp
             "transaction_dt": "01152024", "other_id": "CAND3", "sub_id": "3"},
            {"cmte_id": "C1", "transaction_tp": "24K", "entity_tp": "CCM",   # wrong year
             "transaction_dt": "01152010", "other_id": "CAND4", "sub_id": "4"},
        ], "scan.txt")
        result = fd._scan_itoth_file_for_24k(tmp_path / "scan.txt", cycle_years={2023, 2024})
        assert list(result["sub_id"]) == ["1"]
        assert result.iloc[0]["other_id"] == "CAND1"


# ─── parse_state_party_coordinated_24k() ────────────────────────────────────

class TestParseStatePartyCoordinated24k:
    def test_end_to_end_aggregation_excludes_dccc_and_resolves_district(self, single_raw_dir):
        # A state Dem party committee (passes identify_state_dem_party_committees)
        _write_cm(single_raw_dir, [
            {"cmte_id": "C900", "cmte_nm": "NEBRASKA DEMOCRATIC PARTY", "cmte_st": "NE"},
        ])
        # Candidate + crosswalk to a principal committee
        _write_cn(single_raw_dir, [
            {"cand_id": "H4NE01001", "cand_office_st": "NE", "cand_office_district": "01"},
        ])
        _write_ccl(single_raw_dir, [
            {"cand_id": "H4NE01001", "fec_election_yr": 2024, "cmte_id": "CCAND1"},
        ])
        # 24K rows: one from the identified state party to the candidate committee
        # (should count), one from DCCC itself to the same candidate (should be
        # excluded -- already captured by the existing DCCC-only pipeline), one
        # from an unidentified committee (should be excluded).
        _write_itoth(single_raw_dir, [
            {"cmte_id": "C900", "transaction_tp": "24K", "entity_tp": "CCM",
             "transaction_dt": "03012024", "transaction_amt": 5000.0, "other_id": "CCAND1", "sub_id": "1"},
            {"cmte_id": fd.DCCC_COMMITTEE_ID, "transaction_tp": "24K", "entity_tp": "CCM",
             "transaction_dt": "03012024", "transaction_amt": 9999.0, "other_id": "CCAND1", "sub_id": "2"},
            {"cmte_id": "C999_UNKNOWN", "transaction_tp": "24K", "entity_tp": "CCM",
             "transaction_dt": "03012024", "transaction_amt": 7777.0, "other_id": "CCAND1", "sub_id": "3"},
        ], "itoth.txt")

        out = fd.parse_state_party_coordinated_24k(2024)

        assert list(out.columns) == ["district_id", "party", "cycle", "coordinated_expenditures"]
        assert len(out) == 1
        row = out.iloc[0]
        assert row["district_id"] == "NE-01"
        assert row["party"] == "D"
        assert row["cycle"] == 2024
        assert row["coordinated_expenditures"] == pytest.approx(5000.0)

    def test_deduplicates_across_overlapping_vintage_files_on_sub_id(self, single_raw_dir):
        """Two itoth*.txt files can carry the SAME transaction (different
        bulk-data vintage snapshots of the same underlying filing) --
        summing both without deduping on sub_id would double-count."""
        _write_cm(single_raw_dir, [{"cmte_id": "C900", "cmte_nm": "NEBRASKA DEMOCRATIC PARTY", "cmte_st": "NE"}])
        _write_cn(single_raw_dir, [{"cand_id": "H4NE01001", "cand_office_st": "NE", "cand_office_district": "01"}])
        _write_ccl(single_raw_dir, [{"cand_id": "H4NE01001", "fec_election_yr": 2024, "cmte_id": "CCAND1"}])
        row = {"cmte_id": "C900", "transaction_tp": "24K", "entity_tp": "CCM",
               "transaction_dt": "03012024", "transaction_amt": 5000.0, "other_id": "CCAND1", "sub_id": "1"}
        _write_itoth(single_raw_dir, [row], "itoth.txt")
        _write_itoth(single_raw_dir, [row], "itoth 2.txt")   # identical row, different "vintage" file

        out = fd.parse_state_party_coordinated_24k(2024)
        assert len(out) == 1
        assert out.iloc[0]["coordinated_expenditures"] == pytest.approx(5000.0)

    def test_missing_directory_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path / "nope")
        with pytest.raises(FileNotFoundError):
            fd.parse_state_party_coordinated_24k(2024)


# ─── consolidate_fec_files()'s kinds= scoping ───────────────────────────────
#
# Regression guard for a real incident: the first live run of
# parse_state_party_coordinated_24k() called
# consolidate_fec_files(cycle, force=True) to merge the new coordinated
# source in, and force=True's blast radius silently also re-ran the "ie"
# branch -- overwriting the existing, richer build_comprehensive_ie() output
# (independent_expenditures_2024.csv, ~350 rows covering many outside
# groups) with a much narrower DCCC/NRCC-API-only concatenation (ie_dccc +
# ie_nrcc, 1500+1 rows but only two committees' own IE spending), corrupting
# real data. Caught immediately via a before/after d_total sanity diff, not
# by any test -- these tests exist so a future caller can't reintroduce it.

class TestConsolidateFecFilesKindsScoping:
    def test_kinds_coordinated_only_does_not_touch_the_ie_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        # A pre-existing, "richer" IE file that must survive untouched.
        (tmp_path / "independent_expenditures_2024.csv").write_text(
            "district_id,party,cycle,amount\nPA-07,D,2024,999999\n"
        )
        (tmp_path / "coordinated_dccc_2024.csv").write_text(
            "district_id,party,cycle,coordinated_expenditures\nPA-07,D,2024,190000\n"
        )
        (tmp_path / "coordinated_state_party_dem_2024.csv").write_text(
            "district_id,party,cycle,coordinated_expenditures\nPA-07,D,2024,8500\n"
        )
        # Narrower per-committee IE files that WOULD clobber the richer file
        # above if the "ie" branch were touched -- deliberately different
        # content so the test can tell if they were used.
        (tmp_path / "ie_dccc_2024.csv").write_text(
            "district_id,party,cycle,amount\nPA-07,D,2024,111\n"
        )

        fd.consolidate_fec_files(2024, force=True, kinds=["coordinated"])

        ie_after = pd.read_csv(tmp_path / "independent_expenditures_2024.csv")
        assert ie_after["amount"].iloc[0] == 999999   # untouched

        coord_after = pd.read_csv(tmp_path / "coordinated_expenditures_2024.csv")
        assert coord_after["coordinated_expenditures"].sum() == pytest.approx(190000 + 8500)

    def test_kinds_none_preserves_original_both_kinds_behavior(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "raw_path", lambda source: tmp_path)
        (tmp_path / "coordinated_dccc_2024.csv").write_text(
            "district_id,party,cycle,coordinated_expenditures\nPA-07,D,2024,190000\n"
        )
        (tmp_path / "ie_dccc_2024.csv").write_text(
            "district_id,party,cycle,amount\nPA-07,D,2024,111\n"
        )
        fd.consolidate_fec_files(2024)   # kinds=None -> both, matching the pre-2026-08 default
        assert (tmp_path / "coordinated_expenditures_2024.csv").exists()
        assert (tmp_path / "independent_expenditures_2024.csv").exists()
