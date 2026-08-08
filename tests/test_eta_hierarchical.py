"""
Tests for src/backtest/estimation/eta_hierarchical.py -- the two-stage
(fit-per-cell, then partial-pool via statsmodels MixedLM) hierarchical eta
model. See that module's own docstring for why this replaced the originally
planned PyMC observation-level model (PyMC's numba/llvmlite dependency could
not be installed in this environment).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.estimation import eta_hierarchical as eh


# ─── fit_per_cell_eta() ──────────────────────────────────────────────────────

class TestFitPerCellEta:
    def _fake_panel_builders(self, cell_data: dict):
        """cell_data: {cycle: DataFrame with tier, d_ie_delta_lag_dm, r_ie_delta_dm}.
        build_period_panel/build_delta_panel are stubbed to hand back
        cell_data[cycle] directly from build_delta_panel, since
        fit_per_cell_eta only ever calls build_delta_panel(build_period_panel(cycle))."""
        def fake_build_period_panel(cycle):
            return cycle   # opaque passthrough

        def fake_build_delta_panel(panel):
            return cell_data[panel]

        return fake_build_period_panel, fake_build_delta_panel

    def test_fits_one_row_per_cell_meeting_min_obs(self):
        rng = np.random.default_rng(0)
        n = 20
        x = rng.normal(0, 1, n)
        y = 0.5 * x + rng.normal(0, 0.1, n)
        cell_data = {
            2024: pd.DataFrame({"tier": ["Toss-Up"] * n, "d_ie_delta_lag_dm": x, "r_ie_delta_dm": y}),
        }
        bp, bd = self._fake_panel_builders(cell_data)
        result = eh.fit_per_cell_eta([2024], bp, bd, ["Toss-Up", "Safe D"], min_obs=10)

        assert len(result) == 1
        row = result.iloc[0]
        assert row["cycle"] == 2024
        assert row["tier"] == "Toss-Up"
        assert row["eta_hat"] == pytest.approx(0.5, abs=0.1)
        assert row["n_obs"] == n

    def test_below_min_obs_cell_is_skipped(self):
        cell_data = {
            2024: pd.DataFrame({"tier": ["Toss-Up"] * 3,
                                 "d_ie_delta_lag_dm": [1.0, 2.0, 3.0],
                                 "r_ie_delta_dm": [0.5, 1.0, 1.5]}),
        }
        bp, bd = self._fake_panel_builders(cell_data)
        result = eh.fit_per_cell_eta([2024], bp, bd, ["Toss-Up"], min_obs=10)
        assert result.empty

    def test_eta_se_is_populated_not_nan_with_enough_variation(self):
        rng = np.random.default_rng(1)
        n = 30
        x = rng.normal(0, 1, n)
        y = 0.3 * x + rng.normal(0, 1, n)
        cell_data = {2024: pd.DataFrame({"tier": ["Safe R"] * n, "d_ie_delta_lag_dm": x, "r_ie_delta_dm": y})}
        bp, bd = self._fake_panel_builders(cell_data)
        result = eh.fit_per_cell_eta([2024], bp, bd, ["Safe R"], min_obs=10)
        assert np.isfinite(result.iloc[0]["eta_se"])
        assert result.iloc[0]["eta_se"] > 0


# ─── fit_hierarchical_eta() / posterior_predictive_eta_draws() ─────────────

class TestFitHierarchicalEta:
    def _synthetic_per_cell(self, rng, n_tiers=5, n_cycles=6, tier_sd=0.1, cycle_sd=0.05, resid_sd=0.02):
        tiers = [f"T{i}" for i in range(n_tiers)]
        cycles = list(range(2012, 2012 + 2 * n_cycles, 2))
        tier_effects = {t: rng.normal(0, tier_sd) for t in tiers}
        cycle_effects = {c: rng.normal(0, cycle_sd) for c in cycles}
        rows = []
        for t in tiers:
            for c in cycles:
                eta = 0.4 + tier_effects[t] + cycle_effects[c] + rng.normal(0, resid_sd)
                rows.append(dict(cycle=c, tier=t, eta_hat=eta, eta_se=resid_sd, resid_std=1.0, n_obs=50))
        return pd.DataFrame(rows), tier_effects, cycle_effects

    def test_fit_runs_and_returns_expected_keys(self):
        rng = np.random.default_rng(42)
        per_cell, _, _ = self._synthetic_per_cell(rng)
        fit = eh.fit_hierarchical_eta(per_cell)
        for key in ("mu_global", "tier_effects", "cycle_effects", "tier_var", "cycle_var", "resid_var"):
            assert key in fit
        assert set(fit["tier_effects"].keys()) == set(per_cell["tier"].unique())
        assert set(fit["cycle_effects"].keys()) == set(per_cell["cycle"].unique())

    def test_mu_global_recovers_the_true_grand_mean(self):
        """Positive-control check: the synthetic DGP's grand mean is 0.4 --
        REML's fixed-effect intercept should recover it closely."""
        rng = np.random.default_rng(7)
        per_cell, _, _ = self._synthetic_per_cell(rng, tier_sd=0.15, cycle_sd=0.1, resid_sd=0.02)
        fit = eh.fit_hierarchical_eta(per_cell)
        assert fit["mu_global"] == pytest.approx(0.4, abs=0.1)

    def test_variance_components_are_nonnegative(self):
        rng = np.random.default_rng(3)
        per_cell, _, _ = self._synthetic_per_cell(rng)
        fit = eh.fit_hierarchical_eta(per_cell)
        assert fit["tier_var"] >= 0
        assert fit["cycle_var"] >= 0
        assert fit["resid_var"] >= 0


class TestPosteriorPredictiveEtaDraws:
    def test_output_shape_matches_bootstrap_eta_resid_paths_convention(self):
        fit = dict(mu_global=0.3, tier_effects={"Toss-Up": 0.05, "Safe D": -0.02},
                   cycle_effects={2024: 0.01}, tier_var=0.01, cycle_var=0.005, resid_var=0.02)
        rng = np.random.default_rng(5)
        tiers_per_race = ["Toss-Up", "Safe D", "Toss-Up", "Toss-Up"]
        draws = eh.posterior_predictive_eta_draws(fit, tiers_per_race, k_paths=100, rng=rng)
        assert draws.shape == (100, 4)

    def test_races_sharing_a_tier_get_the_same_draw_per_path(self):
        """Matches bootstrap_eta_resid_paths()'s own established convention
        (tests/test_bellman_lsm.py::TestBootstrapEtaResidPaths::
        test_a_tiers_draw_is_shared_by_every_race_in_that_tier_same_path):
        eta(tier) is ONE per-path draw representing that simulated
        election's realized opponent-reaction coefficient for the whole
        tier, applied identically to every race sharing that tier -- not
        independent per-race noise. Checked directly here since this
        function's whole purpose is being a drop-in replacement for that
        one's output shape AND semantics."""
        fit = dict(mu_global=0.3, tier_effects={"Toss-Up": 0.0}, cycle_effects={},
                   tier_var=0.01, cycle_var=0.01, resid_var=0.05)
        rng = np.random.default_rng(9)
        draws = eh.posterior_predictive_eta_draws(fit, ["Toss-Up", "Toss-Up"], k_paths=500, rng=rng)
        np.testing.assert_array_equal(draws[:, 0], draws[:, 1])
        assert draws[:, 0].std() > 0   # genuine path-to-path variation exists, just shared across races
        assert draws[:, 0].mean() == pytest.approx(0.3, abs=0.05)

    def test_zero_variance_components_collapse_to_a_point_mass_at_the_mean(self):
        fit = dict(mu_global=0.25, tier_effects={"Safe R": 0.1}, cycle_effects={},
                   tier_var=0.0, cycle_var=0.0, resid_var=0.0)
        rng = np.random.default_rng(2)
        draws = eh.posterior_predictive_eta_draws(fit, ["Safe R"] * 10, k_paths=50, rng=rng)
        np.testing.assert_allclose(draws, 0.35)   # mu_global + tier_effect, no noise
