"""Tests for elections.py — MIT MEDSL House results loader."""

from unittest.mock import patch

import pandas as pd
import pytest

from backtest.data import elections


def _raw_row(state, district, party, votes, year=2022):
    return {
        "year": year, "state_po": state, "district": district,
        "stage": "gen", "mode": "total", "party": party,
        "candidatevotes": votes, "runoff": False, "special": False, "writein": False,
    }


class TestPartyLabelVariants:
    """Regression: MEDSL records state-affiliate labels literally (MN's
    Democratic-Farmer-Labor, ND's Democratic-NPL), not normalized to
    "DEMOCRAT" -- an exact match alone silently coded every MN/ND Democratic
    candidate as 0 votes (100%-R landslide) in every panel cycle."""

    def test_minnesota_dfl_counted_as_democrat(self):
        raw = pd.DataFrame([
            _raw_row("MN", "01", "democratic-farmer-labor", 125_457),
            _raw_row("MN", "01", "republican", 159_621),
        ])
        with patch.object(elections, "_load_raw", return_value=raw):
            df = elections.load_results(2022)
        row = df[df.district_id == "MN-01"].iloc[0]
        assert row["d_votes"] == 125_457
        assert row["r_votes"] == 159_621
        assert row["winner"] == "R"

    def test_north_dakota_npl_variants_counted_as_democrat(self):
        for label in ["democratic-npl", "democratic-nonpartisan league"]:
            raw = pd.DataFrame([
                _raw_row("ND", "00", label, 100_000),
                _raw_row("ND", "00", "republican", 50_000),
            ])
            with patch.object(elections, "_load_raw", return_value=raw):
                df = elections.load_results(2022)
            row = df[df.district_id == "ND-00"].iloc[0]
            assert row["d_votes"] == 100_000, f"label {label!r} not counted as Democrat"
            assert row["winner"] == "D"

    def test_plain_democrat_republican_still_work(self):
        raw = pd.DataFrame([
            _raw_row("CA", "12", "democrat", 80_000),
            _raw_row("CA", "12", "republican", 20_000),
        ])
        with patch.object(elections, "_load_raw", return_value=raw):
            df = elections.load_results(2022)
        row = df[df.district_id == "CA-12"].iloc[0]
        assert row["d_votes"] == 80_000
        assert row["r_votes"] == 20_000
