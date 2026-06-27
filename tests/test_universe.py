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
