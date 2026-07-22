"""Tests for scripts/fetch_polling.py's district-level polling summary logic
(data_catalog.md §4.4) — pure-function tests only, no live network calls."""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from fetch_polling import house_district_poll_summary  # noqa: E402


def _polls(rows):
    df = pd.DataFrame(rows)
    df["end_date"] = pd.to_datetime(df["end_date"])
    return df


class TestHouseDistrictPollSummary:
    def test_empty_input_returns_empty_dict(self):
        assert house_district_poll_summary(pd.DataFrame(), date(2026, 7, 20)) == {}

    def test_single_poll_district_has_none_sigma_and_none_trend(self):
        polls = _polls([
            {"district_id": "PA-07", "end_date": "2026-06-01", "margin": 5.0},
        ])
        summary = house_district_poll_summary(polls, date(2026, 7, 20))
        assert summary["PA-07"]["poll_n"] == 1
        assert summary["PA-07"]["poll_mean"] == pytest.approx(5.0)
        assert summary["PA-07"]["poll_sigma"] is None
        assert summary["PA-07"]["poll_trend"] is None

    def test_multiple_polls_computes_mean_sigma_and_positive_trend(self):
        polls = _polls([
            {"district_id": "PA-07", "end_date": "2026-05-01", "margin": 2.0},
            {"district_id": "PA-07", "end_date": "2026-06-01", "margin": 6.0},
            {"district_id": "PA-07", "end_date": "2026-07-01", "margin": 10.0},
        ])
        summary = house_district_poll_summary(polls, date(2026, 7, 20))
        entry = summary["PA-07"]
        assert entry["poll_n"] == 3
        assert entry["poll_mean"] == pytest.approx(6.0)
        assert entry["poll_sigma"] == pytest.approx(polls["margin"].std())
        assert entry["poll_trend"] > 0   # margin rising over time -> positive slope

    def test_same_day_polls_do_not_crash_polyfit_and_trend_is_none(self):
        """Regression test: two polls sharing an end_date give polyfit a
        zero-variance x column (days-since-first-poll is 0 for both), which
        crashes numpy's SVD-based lstsq (LinAlgError) rather than returning
        a sensible answer -- caught via a live smoke test against the real
        VoteHub feed, not written from a hypothetical."""
        polls = _polls([
            {"district_id": "AK-01", "end_date": "2026-06-01", "margin": 3.0},
            {"district_id": "AK-01", "end_date": "2026-06-01", "margin": 7.0},
        ])
        summary = house_district_poll_summary(polls, date(2026, 7, 20))
        entry = summary["AK-01"]
        assert entry["poll_n"] == 2
        assert entry["poll_trend"] is None
        assert entry["poll_mean"] == pytest.approx(5.0)

    def test_respects_as_of_cutoff(self):
        polls = _polls([
            {"district_id": "PA-07", "end_date": "2026-05-01", "margin": 2.0},
            {"district_id": "PA-07", "end_date": "2026-08-01", "margin": 20.0},   # after cutoff
        ])
        summary = house_district_poll_summary(polls, date(2026, 7, 20))
        assert summary["PA-07"]["poll_n"] == 1
        assert summary["PA-07"]["poll_mean"] == pytest.approx(2.0)

    def test_multiple_districts_are_independent(self):
        polls = _polls([
            {"district_id": "PA-07", "end_date": "2026-06-01", "margin": 2.0},
            {"district_id": "MI-07", "end_date": "2026-06-01", "margin": 8.0},
        ])
        summary = house_district_poll_summary(polls, date(2026, 7, 20))
        assert set(summary.keys()) == {"PA-07", "MI-07"}
        assert summary["PA-07"]["poll_mean"] == pytest.approx(2.0)
        assert summary["MI-07"]["poll_mean"] == pytest.approx(8.0)
