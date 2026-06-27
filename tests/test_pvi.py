"""Tests for PVI computation, derive_rating, and data contract consistency."""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

from backtest.data.pvi import (
    _d2party_share,
    derive_rating,
    NATIONAL_D2PARTY,
    CYCLE_TO_PRES_YEARS,
    compute_pvi,
    load_pvi,
)


# ─── _d2party_share ───────────────────────────────────────────────────────────

class TestD2PartyShare:
    def test_basic_60_40_split(self):
        df = pd.DataFrame({"d_votes": [60_000], "r_votes": [40_000]})
        share = _d2party_share(df)
        assert share.iloc[0] == pytest.approx(0.6)

    def test_uncontested_returns_half(self):
        """Uncontested district (zero total votes) must default to 0.5."""
        df = pd.DataFrame({"d_votes": [0], "r_votes": [0]})
        share = _d2party_share(df)
        assert share.iloc[0] == pytest.approx(0.5)

    def test_all_d_votes(self):
        df = pd.DataFrame({"d_votes": [100_000], "r_votes": [0]})
        share = _d2party_share(df)
        assert share.iloc[0] == pytest.approx(1.0)

    def test_all_r_votes(self):
        df = pd.DataFrame({"d_votes": [0], "r_votes": [100_000]})
        share = _d2party_share(df)
        assert share.iloc[0] == pytest.approx(0.0)

    def test_multiple_districts(self):
        df = pd.DataFrame({
            "d_votes": [50_000, 70_000],
            "r_votes": [50_000, 30_000],
        })
        shares = _d2party_share(df)
        assert shares.iloc[0] == pytest.approx(0.5)
        assert shares.iloc[1] == pytest.approx(0.7)


# ─── derive_rating ────────────────────────────────────────────────────────────

class TestDeriveRating:
    """
    Thresholds (on eff = pvi + bonus):
      ≥ +10 → Safe D  |  +5 to +10 → Likely D  |  +1 to +5 → Lean D
      −3 to +1 → Toss-Up  |  −5 to −3 → Lean R
      −10 to −5 → Likely R  |  ≤ −10 → Safe R
    Bonus: Incumbent +2, Challenger −2, Open 0.
    """

    def test_safe_d(self):
        assert derive_rating(15.0, "Open") == "Safe D"

    def test_likely_d(self):
        # eff = 7.0 + 0 = 7.0
        assert derive_rating(7.0, "Open") == "Likely D"

    def test_lean_d(self):
        # eff = 3.0 + 0 = 3.0
        assert derive_rating(3.0, "Open") == "Lean D"

    def test_tossup(self):
        # eff = 0.0 + 0 = 0.0
        assert derive_rating(0.0, "Open") == "Toss-Up"

    def test_lean_r(self):
        # eff = -4.0 + 0 = -4.0
        assert derive_rating(-4.0, "Open") == "Lean R"

    def test_likely_r(self):
        # eff = -7.0 + 0 = -7.0
        assert derive_rating(-7.0, "Open") == "Likely R"

    def test_safe_r(self):
        # eff = -15.0 + 0 = -15.0
        assert derive_rating(-15.0, "Open") == "Safe R"

    def test_incumbent_bonus_positive(self):
        # pvi=0, Incumbent → eff=+2 → Lean D
        assert derive_rating(0.0, "Incumbent") == "Lean D"

    def test_challenger_penalty_negative(self):
        # pvi=0, Challenger → eff=-2 → Toss-Up (−3 ≤ −2 < +1)
        assert derive_rating(0.0, "Challenger") == "Toss-Up"

    def test_boundary_10_is_safe_d(self):
        # eff = 10.0 exactly → Safe D
        assert derive_rating(10.0, "Open") == "Safe D"

    def test_boundary_just_below_10(self):
        # eff = 9.99 → Likely D
        assert derive_rating(9.99, "Open") == "Likely D"

    def test_boundary_minus_10_is_likely_r(self):
        # eff = -10.0: the code checks `if eff >= -10: return "Likely R"`,
        # so -10 exactly is still "Likely R".
        assert derive_rating(-10.0, "Open") == "Likely R"

    def test_boundary_just_below_minus_10_is_safe_r(self):
        # eff = -10.001 → falls through all ≥ checks → Safe R
        assert derive_rating(-10.001, "Open") == "Safe R"

    def test_incumbent_in_r_leaning_district(self):
        # Incumbent D, pvi=-3 → eff=-1 → Toss-Up
        assert derive_rating(-3.0, "Incumbent") == "Toss-Up"

    def test_challenger_in_d_leaning_district(self):
        # Challenger D, pvi=+6 → eff=+4 → Lean D
        assert derive_rating(6.0, "Challenger") == "Lean D"

    def test_all_seven_ratings_reachable(self):
        """All seven Cook categories should be reachable via the function."""
        expected = {
            "Safe D", "Likely D", "Lean D", "Toss-Up",
            "Lean R", "Likely R", "Safe R",
        }
        produced = {derive_rating(pvi, "Open") for pvi in [-20, -8, -4, 0, 3, 7, 15]}
        assert produced == expected


# ─── NATIONAL_D2PARTY / CYCLE_TO_PRES_YEARS ──────────────────────────────────

class TestKnownConstants:
    def test_known_cycles_in_national_d2party(self):
        for year in [2016, 2020, 2024]:
            assert year in NATIONAL_D2PARTY, f"{year} missing from NATIONAL_D2PARTY"

    def test_national_shares_in_reasonable_range(self):
        for year, share in NATIONAL_D2PARTY.items():
            assert 0.40 <= share <= 0.60, f"{year}: D2party share={share} looks wrong"

    def test_panel_cycles_covered(self):
        from backtest import config
        for cycle in config.panel_cycles():
            assert cycle in CYCLE_TO_PRES_YEARS, f"Cycle {cycle} missing from CYCLE_TO_PRES_YEARS"

    def test_2024_in_cycle_mapping(self):
        assert 2024 in CYCLE_TO_PRES_YEARS


# ─── load_pvi (error paths only — no disk I/O) ───────────────────────────────

class TestLoadPVIErrors:
    def test_invalid_cycle_raises_value_error(self):
        with pytest.raises(ValueError, match="No presidential year mapping"):
            load_pvi(1990)

    def test_invalid_cycle_message_mentions_cycle(self):
        with pytest.raises(ValueError, match="1899"):
            load_pvi(1899)


# ─── compute_pvi (unit test with mocked file reads) ──────────────────────────

class TestComputePVI:
    """Verify the PVI formula using synthetic per-district presidential results."""

    def _make_pres_df(self, district_id: str, d_votes: int, r_votes: int) -> pd.DataFrame:
        return pd.DataFrame({
            "district_id": [district_id],
            "d_votes": [d_votes],
            "r_votes": [r_votes],
        })

    def test_equal_national_share_gives_zero_pvi(self):
        """A district that matches the national D2party share has PVI ≈ 0."""
        # For year1=2016: national share = 0.5111
        # If district also has D2party=0.5111, lean1=0 → PVI=0
        national_2016 = NATIONAL_D2PARTY[2016]
        national_2020 = NATIONAL_D2PARTY[2020]

        d16 = int(national_2016 * 100_000)
        r16 = 100_000 - d16
        d20 = int(national_2020 * 100_000)
        r20 = 100_000 - d20

        p16 = self._make_pres_df("XX-01", d16, r16).set_index("district_id")
        p20 = self._make_pres_df("XX-01", d20, r20).set_index("district_id")

        with patch("backtest.data.pvi.load_presidential") as mock_load:
            mock_load.side_effect = lambda year: (
                self._make_pres_df("XX-01", d16, r16) if year == 2016
                else self._make_pres_df("XX-01", d20, r20)
            )
            df = compute_pvi(2016, 2020)

        assert df.loc[df["district_id"] == "XX-01", "pvi"].iloc[0] == pytest.approx(0.0, abs=0.5)

    def test_pure_d_district_has_positive_pvi(self):
        """A strongly Dem district should have positive PVI."""
        with patch("backtest.data.pvi.load_presidential") as mock_load:
            mock_load.return_value = self._make_pres_df("XX-01", 90_000, 10_000)
            df = compute_pvi(2016, 2020)

        pvi = df.loc[df["district_id"] == "XX-01", "pvi"].iloc[0]
        assert pvi > 0

    def test_pure_r_district_has_negative_pvi(self):
        """A strongly Rep district should have negative PVI."""
        with patch("backtest.data.pvi.load_presidential") as mock_load:
            mock_load.return_value = self._make_pres_df("XX-01", 10_000, 90_000)
            df = compute_pvi(2016, 2020)

        pvi = df.loc[df["district_id"] == "XX-01", "pvi"].iloc[0]
        assert pvi < 0

    def test_missing_national_year_raises(self):
        with pytest.raises(ValueError, match="No known national D2party share"):
            with patch("backtest.data.pvi.load_presidential"):
                compute_pvi(1850, 1854)  # not in NATIONAL_D2PARTY

    def test_output_columns(self):
        with patch("backtest.data.pvi.load_presidential") as mock_load:
            mock_load.return_value = self._make_pres_df("XX-01", 60_000, 40_000)
            df = compute_pvi(2016, 2020)
        assert "district_id" in df.columns
        assert "pvi" in df.columns
