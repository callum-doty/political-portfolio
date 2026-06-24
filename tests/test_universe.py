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
