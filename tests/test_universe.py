"""Tests for race universe construction logic."""

import pytest
import pandas as pd
from unittest.mock import patch
from backtest.types import RaceRecord
from backtest.data.cook import _parse_pvi


class TestParsePVI:
    def test_democratic_lean(self):
        assert _parse_pvi("D+3") == pytest.approx(3.0)

    def test_republican_lean(self):
        assert _parse_pvi("R+8") == pytest.approx(-8.0)

    def test_even(self):
        assert _parse_pvi("EVEN") == pytest.approx(0.0)

    def test_large_lean(self):
        assert _parse_pvi("D+15") == pytest.approx(15.0)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            _parse_pvi("X+5")


class TestParsePVIEdgeCases:
    def test_zero_numeric_string(self):
        assert _parse_pvi("0") == pytest.approx(0.0)

    def test_empty_string(self):
        assert _parse_pvi("") == pytest.approx(0.0)

    def test_decimal_pvi(self):
        assert _parse_pvi("D+2.5") == pytest.approx(2.5)

    def test_case_insensitive(self):
        assert _parse_pvi("d+3") == pytest.approx(3.0)
        assert _parse_pvi("r+4") == pytest.approx(-4.0)

    def test_r_invalid_prefix_raises(self):
        with pytest.raises(ValueError):
            _parse_pvi("X+5")


class TestUniverseFilters:
    """Test inclusion/exclusion logic without hitting disk."""

    def _make_race(self, **kwargs) -> RaceRecord:
        defaults = dict(
            district_id="TX-07", state="TX", district=7,
            cook_rating="Toss-Up", incumb_status="Challenger",
            pvi=-2.0, d_total=500_000.0, r_total=600_000.0,
            cvap=350_000, generic_ballot=-1.2,
        )
        defaults.update(kwargs)
        return RaceRecord(**defaults)

    def test_alaska_excluded_by_config(self):
        from backtest import config
        assert "AK" in config.universe_cfg().get("exclude_states", [])

    def test_competitive_subset(self):
        from backtest.data.universe import competitive_subset
        races = [
            self._make_race(cook_rating="Safe D"),
            self._make_race(cook_rating="Toss-Up"),
            self._make_race(cook_rating="Lean R"),
            self._make_race(cook_rating="Safe R"),
        ]
        comp = competitive_subset(races)
        assert len(comp) == 2
        assert all(r.cook_rating in {"Toss-Up", "Lean R"} for r in comp)

    def test_lean_d_is_competitive(self):
        from backtest.data.universe import competitive_subset
        race = self._make_race(cook_rating="Lean D")
        assert len(competitive_subset([race])) == 1

    def test_likely_d_not_competitive(self):
        from backtest.data.universe import competitive_subset
        race = self._make_race(cook_rating="Likely D")
        assert len(competitive_subset([race])) == 0

    def test_empty_input_returns_empty(self):
        from backtest.data.universe import competitive_subset
        assert competitive_subset([]) == []

    def test_safe_d_not_competitive(self):
        from backtest.data.universe import competitive_subset
        race = self._make_race(cook_rating="Safe D")
        assert len(competitive_subset([race])) == 0

    def test_competitive_ratings_from_config(self):
        """competitive_subset must honour the config — not a hard-coded set."""
        from backtest import config
        from backtest.data.universe import competitive_subset
        competitive = set(config.competitive_ratings())
        races = [
            self._make_race(district_id=f"TX-{i:02d}", cook_rating=rating)
            for i, rating in enumerate(
                ["Safe D", "Likely D", "Lean D", "Toss-Up", "Lean R", "Likely R", "Safe R"]
            )
        ]
        comp = competitive_subset(races)
        for r in comp:
            assert r.cook_rating in competitive


class TestBuildUniverse:
    """End-to-end test of build_universe()'s merge/filter pipeline: every
    loader mocked, real config-driven filtering logic exercised. Previously
    untested despite being the single seam every downstream RaceRecord
    passes through (only its helpers, _parse_pvi and competitive_subset,
    had coverage)."""

    def _install_mocks(self, monkeypatch, spend_df, cand_df, results_df,
                        pvi_df, ratings_df, cvap_df, incumb_df,
                        universe_cfg, generic_ballot=-1.2):
        from backtest.data import universe
        monkeypatch.setattr(universe.fec, "build_total_spend", lambda cycle: spend_df)
        monkeypatch.setattr(universe.fec, "load_candidate_disbursements", lambda cycle: cand_df)
        monkeypatch.setattr(universe.elections, "load_results", lambda cycle: results_df)
        monkeypatch.setattr(universe.cook, "load_pvi", lambda cycle: pvi_df)
        monkeypatch.setattr(universe.cook, "load_ratings", lambda cycle: ratings_df)
        monkeypatch.setattr(universe.census, "load_cvap", lambda: cvap_df)
        monkeypatch.setattr(universe.incumbency, "load_incumbency", lambda cycle: incumb_df)
        monkeypatch.setattr(universe.config, "universe_cfg", lambda: universe_cfg)
        monkeypatch.setattr(universe.config, "generic_ballot_for_cycle", lambda cycle: generic_ballot)

    def _base_frames(self, district_ids):
        """One well-formed row per district_id across all six loader outputs,
        so a test only needs to override the specific field(s) under test."""
        spend = pd.DataFrame({
            "district_id": district_ids, "cycle": 2024,
            "d_total": [1_000_000.0] * len(district_ids),
            "r_total": [900_000.0] * len(district_ids),
        })
        cand = pd.DataFrame({
            "district_id": district_ids * 2,
            "party": ["D"] * len(district_ids) + ["R"] * len(district_ids),
            "candidate_disbursements": [400_000.0] * len(district_ids) * 2,
            "indiv_share": [0.45] * len(district_ids) * 2,
        })
        results = pd.DataFrame({"district_id": district_ids, "winner": ["D"] * len(district_ids)})
        pvi = pd.DataFrame({"district_id": district_ids, "pvi": [2.0] * len(district_ids)})
        ratings = pd.DataFrame({"district_id": district_ids, "cook_rating": ["Toss-Up"] * len(district_ids)})
        cvap = pd.DataFrame({"district_id": district_ids, "cvap": [400_000] * len(district_ids)})
        incumb = pd.DataFrame({
            "district_id": district_ids, "cycle": 2024,
            "incumb_status": ["Challenger"] * len(district_ids),
        })
        return spend, cand, results, pvi, ratings, cvap, incumb

    def test_full_pipeline_merges_and_filters_correctly(self, monkeypatch):
        district_ids = ["TX-01", "TX-02", "TX-03", "AK-01", "TX-04", "TX-05"]
        spend, cand, results, pvi, ratings, cvap, incumb = self._base_frames(district_ids)

        # TX-02: below min_total_spend on both sides -> excluded
        spend.loc[spend.district_id == "TX-02", ["d_total", "r_total"]] = [10_000.0, 5_000.0]
        # AK-01: excluded by exclude_states regardless of spend
        # TX-03: missing PVI -> excluded
        pvi.loc[pvi.district_id == "TX-03", "pvi"] = float("nan")
        # TX-04: missing incumbency -> excluded
        incumb = incumb[incumb.district_id != "TX-04"]
        # TX-05: redistricting-flagged, included but flagged=True

        universe_cfg = {
            "min_total_spend": 100_000,
            "exclude_states": ["AK"],
            "redistricting_flag_districts": ["TX-05"],
        }
        self._install_mocks(monkeypatch, spend, cand, results, pvi, ratings, cvap, incumb, universe_cfg)

        from backtest.data.universe import build_universe
        races = build_universe(cycle=2024)
        race_ids = {r.district_id for r in races}

        assert race_ids == {"TX-01", "TX-05"}

        tx01 = next(r for r in races if r.district_id == "TX-01")
        assert tx01.d_total == pytest.approx(1_000_000.0)
        assert tx01.r_total == pytest.approx(900_000.0)
        assert tx01.cand_d_total == pytest.approx(400_000.0)   # D-party candidate disbursement only
        assert tx01.indiv_share == pytest.approx(0.45)
        assert tx01.pvi == pytest.approx(2.0)
        assert tx01.incumb_status == "Challenger"
        assert tx01.generic_ballot == pytest.approx(-1.2)
        assert tx01.redistricting_flagged is False
        assert tx01.outcome == "D"

        tx05 = next(r for r in races if r.district_id == "TX-05")
        assert tx05.redistricting_flagged is True

    def test_missing_candidate_disbursement_row_fills_zero(self, monkeypatch):
        """A district with no D-party row in load_candidate_disbursements()
        (left-merge miss) must get cand_d_total=0.0, not crash or leave NaN."""
        district_ids = ["TX-01"]
        spend, cand, results, pvi, ratings, cvap, incumb = self._base_frames(district_ids)
        cand = cand[cand.party != "D"]   # drop the only D-party row

        universe_cfg = {"min_total_spend": 100_000, "exclude_states": [], "redistricting_flag_districts": []}
        self._install_mocks(monkeypatch, spend, cand, results, pvi, ratings, cvap, incumb, universe_cfg)

        from backtest.data.universe import build_universe
        races = build_universe(cycle=2024)
        assert len(races) == 1
        assert races[0].cand_d_total == 0.0
        assert not pd.isna(races[0].cand_d_total)
