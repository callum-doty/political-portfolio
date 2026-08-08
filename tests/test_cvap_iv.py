"""
Tests for src/backtest/estimation/cvap_iv.py (FINDINGS.md Section 10.7,
Gap 1) -- within-district fixed-effects estimation of alpha4
(CVAP spending-intensity). NOT an instrumental-variable estimate -- see the
module's own docstring for the stated scope boundary (no redistricting-jump
instrument is implemented; a real GIS crosswalk would be required).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.estimation import cvap_iv


# ─── nearest_vintage_for_cycle() ────────────────────────────────────────────

class TestNearestVintageForCycle:
    def test_picks_exact_match_when_available(self):
        available = [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]
        is_post = {v: v >= 2022 for v in available}
        assert cvap_iv.nearest_vintage_for_cycle(2018, available, is_post) == 2018

    def test_picks_closest_same_era_vintage(self):
        available = [2016, 2020, 2022, 2024]
        is_post = {v: v >= 2022 for v in available}
        # 2018 is pre-redistricting; nearest pre-era vintage is 2020 (|20-18|=2 < |16-18|=2 -- tie,
        # min() keeps the first encountered in iteration order for exact ties, so use a case with
        # a clear winner instead)
        assert cvap_iv.nearest_vintage_for_cycle(2019, available, is_post) == 2020

    def test_never_crosses_the_redistricting_boundary(self):
        """A pre-2022 cycle must never be matched to a post-redistricting
        vintage even if it's numerically closer -- boundary consistency
        takes priority over raw year distance."""
        available = [2016, 2023]   # 2023 is numerically much closer to e.g. 2020
        is_post = {2016: False, 2023: True}
        assert cvap_iv.nearest_vintage_for_cycle(2020, available, is_post) == 2016

        available2 = [2016, 2022]
        is_post2 = {2016: False, 2022: True}
        assert cvap_iv.nearest_vintage_for_cycle(2022, available2, is_post2) == 2022

    def test_returns_none_when_no_same_era_vintage_exists(self):
        available = [2022, 2023, 2024]   # all post-redistricting
        is_post = {v: True for v in available}
        assert cvap_iv.nearest_vintage_for_cycle(2012, available, is_post) is None


# ─── build_fe_estimation_panel() ────────────────────────────────────────────

class TestBuildFeEstimationPanel:
    def _historical_panel(self):
        return pd.DataFrame([
            dict(district_id="AZ-01", cycle=2018, margin_pp=5.0, d_total=500_000, r_total=400_000,
                 pvi=2.0, incumb_status="Incumbent", gb=1.0),
            dict(district_id="AZ-01", cycle=2020, margin_pp=6.0, d_total=600_000, r_total=450_000,
                 pvi=2.0, incumb_status="Incumbent", gb=2.0),
            dict(district_id="AZ-01", cycle=2012, margin_pp=3.0, d_total=300_000, r_total=280_000,
                 pvi=2.0, incumb_status="Incumbent", gb=0.5),
        ])

    def _cvap_panel(self):
        return pd.DataFrame([
            dict(district_id="AZ-01", vintage_end_year=2018, cvap=400_000, is_post_redistricting=False),
            dict(district_id="AZ-01", vintage_end_year=2020, cvap=420_000, is_post_redistricting=False),
            # No 2012-or-earlier vintage -- but 2012 is still the SAME era (pre-redistricting)
            # as 2018/2020, so nearest_vintage_for_cycle() maps it to the nearest available
            # same-era vintage (2018) rather than dropping it; this mirrors the real run
            # (cycles 2012/2014 mapped to the 2016 vintage, the earliest one that exists at
            # all -- CD.csv only starts at the 2016 vintage). Dropping is tested separately
            # below with a cvap_panel that has NO pre-redistricting vintage at all.
        ])

    def test_merges_on_contemporaneous_vintage_and_computes_intensity(self):
        result = cvap_iv.build_fe_estimation_panel(self._historical_panel(), self._cvap_panel())
        assert set(result["cycle"]) == {2012, 2018, 2020}
        row_2018 = result[result["cycle"] == 2018].iloc[0]
        assert row_2018["cvap"] == 400_000
        expected_log = np.log((500_000 + 400_000) / 400_000)
        assert row_2018["log_total_per_voter"] == pytest.approx(expected_log)
        # 2012 has no exact-year vintage -- must fall back to the nearest same-era one (2018).
        row_2012 = result[result["cycle"] == 2012].iloc[0]
        assert row_2012["cvap"] == 400_000

    def test_drops_cycles_with_no_same_era_vintage_at_all_rather_than_imputing(self):
        """Unlike the fixture above (which has SOME pre-redistricting vintage
        for 2012 to fall back to), this uses a cvap_panel with ONLY
        post-redistricting vintages -- no pre-2022 cycle has anywhere to
        map to, and all three historical rows (2012, 2018, 2020) must be
        dropped, not silently imputed."""
        post_only_cvap = pd.DataFrame([
            dict(district_id="AZ-01", vintage_end_year=2022, cvap=430_000, is_post_redistricting=True),
        ])
        result = cvap_iv.build_fe_estimation_panel(self._historical_panel(), post_only_cvap)
        assert len(result) == 0


# ─── estimate_alpha4_fe() ───────────────────────────────────────────────────

class TestEstimateAlpha4Fe:
    def test_insufficient_data_reports_status_not_a_crash(self):
        panel = pd.DataFrame([
            dict(district_id="AZ-01", cycle=2018, margin_pp=5.0, log_total_per_voter=-0.5,
                 log_ratio=0.1, gb=1.0),
        ])
        result = cvap_iv.estimate_alpha4_fe(panel)
        assert result["status"] == "insufficient_data"

    def test_recovers_a_known_true_alpha4_from_a_synthetic_dgp(self):
        """Positive-control test, standard practice before trusting an FE/IV
        implementation on real data: simulate a panel from a KNOWN
        data-generating process (a real district fixed effect, a known
        alpha4, and independent noise -- no endogeneity by construction,
        since this DGP does not route spending decisions through
        competitiveness) and confirm estimate_alpha4_fe() recovers the true
        alpha4 within simulation noise. This does NOT validate that the
        REAL data's within-district variation is strong enough (that's a
        separate, empirical question -- see FINDINGS.md's honest report of
        the actual result) -- it validates only that the estimator itself
        is implemented correctly."""
        rng = np.random.default_rng(20260807)
        n_districts = 60
        n_cycles = 6
        true_alpha4 = -1.5
        true_beta_ratio = 8.0
        true_gb_coef = 0.4

        district_fe = rng.normal(0, 5, size=n_districts)
        rows = []
        for d in range(n_districts):
            for t in range(n_cycles):
                log_tpv = rng.normal(-1.0, 0.3)   # independent of margin -- no endogeneity by construction
                log_ratio = rng.normal(0.0, 0.2)
                gb = rng.normal(0.0, 2.0)
                margin = (
                    district_fe[d] + true_alpha4 * log_tpv + true_beta_ratio * log_ratio
                    + true_gb_coef * gb + rng.normal(0, 1.0)
                )
                rows.append(dict(district_id=f"D{d}", cycle=2000 + 2 * t, margin_pp=margin,
                                  log_total_per_voter=log_tpv, log_ratio=log_ratio, gb=gb))
        panel = pd.DataFrame(rows)

        result = cvap_iv.estimate_alpha4_fe(panel)
        assert result["status"] == "ok"
        assert result["alpha4_fe"] == pytest.approx(true_alpha4, abs=0.3)
        assert result["pvalue"] < 0.01   # strong signal by construction -- should be highly significant

    def test_min_periods_filter_drops_single_observation_districts(self):
        rows = []
        rng = np.random.default_rng(1)
        for d in range(30):
            for t in range(4):
                rows.append(dict(district_id=f"D{d}", cycle=2000 + t, margin_pp=rng.normal(0, 5),
                                  log_total_per_voter=rng.normal(-1, 0.3), log_ratio=rng.normal(0, 0.2),
                                  gb=rng.normal(0, 1)))
        # One district with only a single observation -- must be excluded from the fit.
        rows.append(dict(district_id="SINGLETON", cycle=2000, margin_pp=1.0,
                          log_total_per_voter=-1.0, log_ratio=0.0, gb=0.0))
        panel = pd.DataFrame(rows)

        result = cvap_iv.estimate_alpha4_fe(panel, min_periods_per_district=2)
        assert result["status"] == "ok"
        assert result["n_districts"] == 30   # SINGLETON excluded
