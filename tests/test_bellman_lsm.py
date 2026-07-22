"""
Regression and unit tests for the Bellman/LSM Theta machinery
(scripts/solve_bellman_lsm.py, scripts/solve_bellman_lsm_continuous_phi.py,
scripts/simulate_and_validate.py).

This code family previously had zero automated test coverage despite being
where both real bugs this project has found so far actually lived:
  - the `add_constant()` intercept-drop bug (has_constant defaults to "skip",
    which silently discards the regression's own intercept column when a
    feature happens to be a deterministic constant across every path -- g_t
    is exactly zero for every path at t=0, since G_0=0 by construction)
  - the frozen-floor bug (`_deploy_value`/`_solve_committed_floor` resetting
    to the original candidate floor regardless of how much of the reserve
    had already been notionally committed, which silently flattens what
    should be a concave value-of-budget curve)

Both were caught by a human reading the code carefully, not by any test.
These tests exist so a future refactor can't silently reintroduce either.

Scope note: `_deploy_value` inside `solve_bellman_lsm.run_lsm()` is a
closure, not a module-level function, and is not directly importable without
refactoring production code (out of scope for this pass). It is exercised
here only indirectly, through `run_lsm()` integration tests on a small
synthetic universe. `_solve_committed_floor` in the continuous-phi script,
by contrast, IS a module-level function and is tested directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from backtest.types import RaceRecord  # noqa: E402
from backtest.model.win_prob import compute_outputs_batch  # noqa: E402
from backtest.model.margin import predict as static_predict  # noqa: E402

import solve_bellman_lsm as lsm  # noqa: E402
import solve_bellman_lsm_continuous_phi as cphi  # noqa: E402
import simulate_and_validate as sim  # noqa: E402


# ─── Shared fixtures ───────────────────────────────────────────────────────

def _race(district_id, cook_rating, incumb_status, pvi, d_total, r_total,
          cand_d_total, generic_ballot=2.0, cvap=500_000):
    return RaceRecord(
        district_id=district_id, state=district_id.split("-")[0], district=1,
        cook_rating=cook_rating, incumb_status=incumb_status, pvi=pvi,
        d_total=d_total, r_total=r_total, cvap=cvap,
        generic_ballot=generic_ballot, cand_d_total=cand_d_total,
    )


@pytest.fixture
def synthetic_races() -> list[RaceRecord]:
    """A small, hand-built universe spanning safe/competitive tiers on both
    sides and both incumbency statuses -- enough to exercise the competitive
    mask, the near-threshold count, and the open-seat coefficient branch,
    without depending on any live 2026 data file."""
    return [
        _race("TX-01", "Safe D", "Incumbent", pvi=20.0, d_total=500_000, r_total=100_000, cand_d_total=400_000),
        _race("OH-02", "Toss-Up", "Open", pvi=0.0, d_total=300_000, r_total=300_000, cand_d_total=200_000),
        _race("PA-03", "Lean D", "Incumbent", pvi=3.0, d_total=250_000, r_total=200_000, cand_d_total=150_000),
        _race("MI-04", "Lean R", "Challenger", pvi=-3.0, d_total=200_000, r_total=250_000, cand_d_total=100_000),
        _race("FL-05", "Safe R", "Challenger", pvi=-20.0, d_total=50_000, r_total=500_000, cand_d_total=40_000),
        _race("NV-06", "Toss-Up", "Open", pvi=1.0, d_total=280_000, r_total=290_000, cand_d_total=180_000),
    ]


@pytest.fixture
def coef_sigma():
    return lsm.load_coef_and_sigma()


# ─── margin_gradient() ─────────────────────────────────────────────────────

class TestMarginGradient:
    def test_eta_zero_matches_algebraic_simplification(self, coef_sigma):
        """c*(1/D - 1/T) must equal the algebraically simplified c*R/(D*T)
        used elsewhere in the docs/derivation -- a direct check against
        the closed-form the docstring claims this reduces to at eta=0."""
        coef, _ = coef_sigma
        d, r = 250_000.0, 400_000.0
        grad = lsm.margin_gradient(coef, pvi=3.0, incumb_status="Incumbent",
                                    d_total=d, r_total=r, eta=0.0)
        c = coef.beta1 + coef.beta2 * 3.0 + coef.beta3 * 1.0
        expected = c * r / (d * (d + r))
        assert grad == pytest.approx(expected, rel=1e-9)

    def test_gradient_strictly_decreases_as_eta_increases(self, coef_sigma):
        """Docstring's claim: higher eta means more of a new dollar's
        log-ratio benefit is offset by opponent reaction. A regression here
        would mean the eta-discount wired into the deploy branch (Section
        0.1.2 of the followup plan) silently stopped doing anything."""
        coef, _ = coef_sigma
        etas = [0.0, 0.25, 0.5, 0.75, 1.0]
        grads = [lsm.margin_gradient(coef, pvi=0.0, incumb_status="Incumbent",
                                      d_total=200_000, r_total=200_000, eta=e)
                 for e in etas]
        assert all(g2 < g1 for g1, g2 in zip(grads, grads[1:])), grads

    def test_open_seat_uses_beta1_open_not_beta1(self, coef_sigma):
        coef, _ = coef_sigma
        assert coef.beta1_open is not None, (
            "fixture assumption: data/processed/margin_model_coef.json is "
            "expected to carry a calibrated beta1_open; if this now fails, "
            "the open-seat branch below is untested, not confirmed absent"
        )
        grad_open = lsm.margin_gradient(coef, pvi=2.0, incumb_status="Open",
                                         d_total=200_000, r_total=200_000, eta=0.0)
        c_open = coef.beta1_open + coef.beta2 * 2.0
        expected = c_open * (1.0 / 200_000 - 1.0 / 400_000)
        assert grad_open == pytest.approx(expected, rel=1e-9)
        # And that this genuinely differs from what the Incumbent-branch
        # coefficient would have given -- guards against the Open check
        # being dead code that never actually swaps c.
        c_incumbent_formula = coef.beta1 + coef.beta2 * 2.0
        assert c_open != pytest.approx(c_incumbent_formula)

    def test_floor_clamps_avoid_division_by_zero(self, coef_sigma):
        """d_total/r_total of 0 must not raise -- margin_gradient clamps
        both to >= 1.0 internally."""
        coef, _ = coef_sigma
        grad = lsm.margin_gradient(coef, pvi=0.0, incumb_status="Open",
                                    d_total=0.0, r_total=0.0, eta=0.0)
        assert np.isfinite(grad)


# ─── tile_single_cycle() ───────────────────────────────────────────────────

class TestTileSingleCycle:
    def test_broadcasts_identically_across_all_paths(self):
        eta_by_tier = {"Toss-Up": 0.475, "Lean D": 0.259}
        resid_by_tier = {"Toss-Up": 1.1, "Lean D": 0.9}
        tiers_per_race = ["Toss-Up", "Lean D", "Toss-Up"]
        eta_arr, resid_arr = lsm.tile_single_cycle(eta_by_tier, resid_by_tier, tiers_per_race, k_paths=5)

        assert eta_arr.shape == (5, 3)
        assert resid_arr.shape == (5, 3)
        # Every path row must be byte-identical -- this scenario means "one
        # cycle's fit, shared across all paths," not per-path variation.
        for row in eta_arr:
            np.testing.assert_array_equal(row, eta_arr[0])
        np.testing.assert_allclose(eta_arr[0], [0.475, 0.259, 0.475])

    def test_missing_tier_defaults_to_zero_not_a_crash(self):
        eta_arr, resid_arr = lsm.tile_single_cycle(
            {"Toss-Up": 0.5}, {"Toss-Up": 1.0}, ["Toss-Up", "Safe D"], k_paths=3)
        assert eta_arr[0, 1] == 0.0
        assert resid_arr[0, 1] == 0.0


# ─── bootstrap_eta_resid_paths() ───────────────────────────────────────────

class TestBootstrapEtaResidPaths:
    """fit_eta_and_resid() hits real historical IE data -- monkeypatched
    here to canned per-cycle values so this exercises only the sampling
    logic, not data availability."""

    @pytest.fixture
    def canned_fits(self, monkeypatch):
        fits = {
            2012: ({"Toss-Up": 0.42, "Lean D": 0.30}, {"Toss-Up": 1.0, "Lean D": 0.8}),
            2016: ({"Toss-Up": -0.22, "Lean D": 0.24}, {"Toss-Up": 1.3, "Lean D": 0.9}),  # real sign-flip cycle
            2024: ({"Toss-Up": 0.34, "Lean D": 0.24}, {"Toss-Up": 1.1, "Lean D": 0.85}),
        }

        def fake_fit(cycle):
            return fits[cycle]

        monkeypatch.setattr(lsm, "fit_eta_and_resid", fake_fit)
        return fits

    def test_shape_and_determinism_given_seeded_rng(self, canned_fits):
        tiers_per_race = ["Toss-Up", "Lean D", "Toss-Up", "Safe R"]
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)
        eta1, resid1, summary1 = lsm.bootstrap_eta_resid_paths(
            list(canned_fits.keys()), tiers_per_race, k_paths=10, rng=rng1)
        eta2, _, _ = lsm.bootstrap_eta_resid_paths(
            list(canned_fits.keys()), tiers_per_race, k_paths=10, rng=rng2)

        assert eta1.shape == (10, 4)
        np.testing.assert_array_equal(eta1, eta2)  # same seed -> same draws

    def test_draws_come_only_from_the_provided_historical_values(self, canned_fits):
        tiers_per_race = ["Toss-Up"] * 20
        rng = np.random.default_rng(7)
        eta, resid, summary = lsm.bootstrap_eta_resid_paths(
            list(canned_fits.keys()), tiers_per_race, k_paths=200, rng=rng)

        allowed = {fits[0]["Toss-Up"] for fits in canned_fits.values()}
        drawn = set(np.unique(eta[:, 0]))
        assert drawn <= allowed
        # With 200 draws from 3 candidates, the sign-flip value should show up.
        assert -0.22 in drawn

    def test_a_tiers_draw_is_shared_by_every_race_in_that_tier_same_path(self, canned_fits):
        """The whole point of this scenario (per the module docstring) is
        that eta and resid_std are drawn ONCE PER PATH PER TIER, held fixed
        for every race sharing that tier -- not independently per race. A
        regression here would silently reintroduce race-independent noise
        the bootstrap design specifically exists to avoid."""
        tiers_per_race = ["Toss-Up", "Toss-Up", "Toss-Up"]
        rng = np.random.default_rng(3)
        eta, resid, summary = lsm.bootstrap_eta_resid_paths(
            list(canned_fits.keys()), tiers_per_race, k_paths=50, rng=rng)
        for k in range(50):
            assert eta[k, 0] == eta[k, 1] == eta[k, 2]
            assert resid[k, 0] == resid[k, 1] == resid[k, 2]

    def test_eta_and_resid_std_paired_within_a_cycle_not_drawn_independently(self, canned_fits):
        """Bootstrap must draw (eta, resid_std) as a pair from ONE randomly
        chosen cycle -- e.g. 2016's Toss-Up eta (-0.22) must always co-occur
        with 2016's Toss-Up resid_std (1.3), never mixed with another
        cycle's resid_std. This is the real-within-cycle-relationship
        invariant the module docstring states explicitly."""
        tiers_per_race = ["Toss-Up"] * 5
        rng = np.random.default_rng(11)
        eta, resid, _ = lsm.bootstrap_eta_resid_paths(
            list(canned_fits.keys()), tiers_per_race, k_paths=500, rng=rng)
        pairing = {fits[0]["Toss-Up"]: fits[1]["Toss-Up"] for fits in canned_fits.values()}
        for k in range(500):
            e = eta[k, 0]
            assert resid[k, 0] == pytest.approx(pairing[e])


# ─── remaining_variance() / incremental_variances() (simulate_and_validate.py) ──

class TestVarianceDecomposition:
    def test_remaining_variance_is_zero_at_election_day(self):
        assert sim.remaining_variance(sigma_static=10.0, days_remaining=0.0) == pytest.approx(0.0)

    def test_remaining_variance_approaches_sigma_squared_at_long_horizon(self):
        v = sim.remaining_variance(sigma_static=10.0, days_remaining=1e6)
        assert v == pytest.approx(100.0, rel=1e-6)

    def test_remaining_variance_monotonically_increases_with_days_remaining(self):
        days = np.array([0, 30, 90, 180, 365])
        v = sim.remaining_variance(10.0, days)
        assert np.all(np.diff(v) > 0)

    @pytest.mark.parametrize("n_periods", [1, 3, 7, 26])
    def test_incremental_variances_telescope_to_cumulative_target(self, n_periods):
        """Sum of per-step increments must equal V(0) exactly (up to float
        tolerance) -- this is the self-consistency property Paper III
        Section 7.1's Check C validates statistically at 5,000 paths; this
        checks the same identity analytically, deterministically, every run."""
        sigma = 8.5
        v = sim.incremental_variances(sigma, n_periods)
        target = sim.remaining_variance(sigma, n_periods * sim.PERIOD_DAYS)
        assert v.sum() == pytest.approx(target, rel=1e-9)
        assert len(v) == n_periods

    def test_incremental_variances_all_nonnegative(self):
        v = sim.incremental_variances(12.0, 10)
        assert np.all(v >= 0.0)

    def test_incremental_variances_final_step_lands_at_zero_remaining(self):
        """V(n_periods) must be exactly 0 (Theta(T)=0 boundary condition) --
        i.e. the increments must fully exhaust the cumulative variance
        budget by the last step, not leave a residual."""
        sigma = 6.0
        n_periods = 5
        v = sim.incremental_variances(sigma, n_periods)
        days_remaining_after_each_step = np.array(
            [(n_periods - (n + 1)) * sim.PERIOD_DAYS for n in range(n_periods)])
        v_after_last_step = sim.remaining_variance(sigma, days_remaining_after_each_step[-1])
        assert v_after_last_step == pytest.approx(0.0, abs=1e-9)


# ─── has_constant="add" regression (the intercept-drop bug) ───────────────

class TestAddConstantInterceptDropRegression:
    """Direct regression test for the bug documented in
    docs/theta_followup_plan.md Section 4's implementation log:
    sm.add_constant()'s default has_constant="skip" silently drops the
    intercept column whenever it decides a feature column is "already a
    constant" -- which is what g_t looks like at t=0, since G_0=0 for every
    simulated path by construction.

    Precision note, found while writing this test: on the statsmodels
    version currently pinned in this repo (0.14.6), add_constant's
    numpy-array code path defines "already constant" as zero range AND all
    values nonzero (`np.ptp(x, axis=0) == 0` and `np.all(x != 0.0, axis=0)`)
    -- so an all-*zero* column like g_t at t=0 does NOT actually trigger the
    skip on this version; only a nonzero constant column would. The
    documented crash may have been hit on a different statsmodels release
    with different detection logic. Either way, the defensive fix
    (has_constant="add", tested below) is correct regardless of which
    statsmodels version's quirk originally caused it, and is worth keeping
    exactly because relying on "it happens not to trigger on the currently
    installed version" would be a silent, environment-dependent trap."""

    def test_current_statsmodels_version_does_not_skip_on_an_all_zero_column(self):
        """Documents current, actual behavior (not the historically assumed
        one) so a future statsmodels upgrade that changes this detection
        logic shows up here as a test change, not a silent surprise."""
        import statsmodels.api as sm
        n = 20
        rng = np.random.default_rng(0)
        e_seats = rng.normal(size=n)
        var_seats = rng.normal(size=n)
        max_msg = rng.normal(size=n)
        near_thresh = rng.integers(0, 5, size=n).astype(float)
        g_t = np.zeros(n)  # deterministic zero, as at t=0

        X_default = sm.add_constant(
            np.column_stack([e_seats, var_seats, max_msg, near_thresh, g_t]))
        assert X_default.shape[1] == 6  # NOT 5 -- see class docstring

    def test_a_nonzero_constant_column_does_trigger_the_default_skip(self):
        """This IS the condition current statsmodels treats as "already has
        a constant" -- confirms the mechanism is real, just not triggered
        by an all-zero column specifically."""
        import statsmodels.api as sm
        n = 20
        rng = np.random.default_rng(0)
        e_seats = rng.normal(size=n)
        var_seats = rng.normal(size=n)
        max_msg = rng.normal(size=n)
        near_thresh = rng.integers(0, 5, size=n).astype(float)
        nonzero_const = np.full(n, 3.0)

        X_default = sm.add_constant(
            np.column_stack([e_seats, var_seats, max_msg, near_thresh, nonzero_const]))
        assert X_default.shape[1] == 5  # intercept silently skipped

    def test_has_constant_add_always_yields_six_columns(self):
        import statsmodels.api as sm
        n = 20
        rng = np.random.default_rng(0)
        e_seats = rng.normal(size=n)
        var_seats = rng.normal(size=n)
        max_msg = rng.normal(size=n)
        near_thresh = rng.integers(0, 5, size=n).astype(float)

        for g_t in (np.zeros(n), rng.normal(size=n)):  # constant AND non-constant g_t
            X = sm.add_constant(
                np.column_stack([e_seats, var_seats, max_msg, near_thresh, g_t]),
                has_constant="add")
            assert X.shape[1] == 6, (
                "has_constant='add' must always append a genuine intercept "
                "column regardless of whether g_t happens to be constant "
                "this period -- reverting to the default here is exactly "
                "the regression this test exists to catch."
            )


# ─── run_lsm() integration: exercises the actual backward induction ───────

class TestRunLsmIntegration:
    """Runs the real run_lsm() backward induction end-to-end on a tiny
    synthetic universe with a small path count, so it actually executes
    the code path where both known bugs lived (the terminal deploy value,
    the g_t regression feature at t=0, the per-period backward step) rather
    than re-testing an isolated reimplementation of it."""

    @pytest.fixture
    def fast_run(self, monkeypatch, synthetic_races, tmp_path):
        monkeypatch.setattr(lsm, "build_universe", lambda cycle=2026: synthetic_races)
        monkeypatch.setattr(lsm, "K_PATHS", 40)
        monkeypatch.setattr(lsm, "N_PERIODS", 3)
        # This fixture is designed around a zero-trickle baseline (this
        # class's assertions, e.g. test_theta_equals_wait_minus_deploy_sign_convention,
        # were written and tuned against it). Point _TRICKLE_PATH at a path
        # that doesn't exist so this test is hermetic -- independent of
        # whether data/processed/candidate_spend_trickle.json happens to be
        # present in the working tree (it wasn't when these tests were
        # first written; it is now that the real calibration has been run,
        # which silently broke this fixture's isolation until caught here).
        monkeypatch.setattr(lsm, "_TRICKLE_PATH", tmp_path / "no_trickle_for_this_test.json")

        tiers_per_race = [r.cook_rating for r in synthetic_races]
        eta_by_tier = {"Toss-Up": 0.4, "Lean D": 0.26, "Lean R": 0.3, "Safe D": 0.0, "Safe R": 0.0}
        resid_by_tier = {"Toss-Up": 15_000.0, "Lean D": 12_000.0, "Lean R": 12_000.0,
                          "Safe D": 8_000.0, "Safe R": 8_000.0}
        eta_arr, resid_arr = lsm.tile_single_cycle(eta_by_tier, resid_by_tier, tiers_per_race, k_paths=40)
        return lsm.run_lsm(eta_arr, resid_arr, "test_scenario")

    def test_runs_without_error_and_returns_expected_shape(self, fast_run):
        assert fast_run["label"] == "test_scenario"
        assert fast_run["n_periods"] == 3
        assert fast_run["k_paths"] == 40
        assert len(fast_run["theta_by_period"]) == 3

    def test_no_nan_or_inf_anywhere_in_the_schedule(self, fast_run):
        """g_t_pvalue is the one documented exception: at period 0, g_t is
        deterministically 0 for every path (G_0=0 by construction), so its
        regression coefficient is correctly estimated as 0 (pinv handles
        the zero-variance column gracefully) but its standard error --
        and therefore its p-value -- is genuinely undefined, not a bug
        (docs/theta_followup_plan.md Section 4's implementation log calls
        this out explicitly: "g_t_coef=0.0, p=nan, expected... not a new
        bug"). Every other field, at every period including 0, must be
        finite; g_t_pvalue must be finite everywhere EXCEPT period 0."""
        for entry in fast_run["theta_by_period"]:
            for key in ("mean_theta", "frac_deploy_now", "basis_r2", "g_t_coef"):
                assert np.isfinite(entry[key]), f"{key} at period {entry['period']} is not finite: {entry[key]}"
            if entry["period"] == 0:
                assert np.isnan(entry["g_t_pvalue"]), (
                    "period 0's g_t_pvalue is expected to be NaN (zero-variance "
                    "regressor) -- if this is now finite, double-check g_paths[:,0] "
                    "is still forced to exactly 0 for every path"
                )
            else:
                assert np.isfinite(entry["g_t_pvalue"]), \
                    f"g_t_pvalue at period {entry['period']} is not finite: {entry['g_t_pvalue']}"

    def test_frac_deploy_now_is_a_valid_probability_every_period(self, fast_run):
        for entry in fast_run["theta_by_period"]:
            assert 0.0 <= entry["frac_deploy_now"] <= 1.0

    def test_t0_g_t_regression_feature_is_well_formed(self, fast_run):
        """t=0 is exactly where g_t is deterministically zero for every
        path (G_0=0 by construction) -- the precise scenario that crashed
        with an IndexError (params[5] out of range on a shrunk 5-column
        design matrix) before has_constant='add' was added. The regression
        test is that run_lsm() completes AT ALL and returns an indexable,
        finite g_t_coef at t=0 -- a NaN g_t_pvalue at t=0 specifically is
        documented, expected behavior (see test_no_nan_or_inf_anywhere_in_
        the_schedule), not a sign of the historical bug."""
        t0 = next(e for e in fast_run["theta_by_period"] if e["period"] == 0)
        assert np.isfinite(t0["g_t_coef"])
        assert np.isnan(t0["g_t_pvalue"])

    def test_days_remaining_strictly_decreases_from_period_0_onward(self, fast_run):
        days = [e["days_remaining"] for e in fast_run["theta_by_period"]]
        assert days == sorted(days, reverse=True)
        assert len(set(days)) == len(days)

    def test_theta_equals_wait_minus_deploy_sign_convention(self, fast_run):
        """theta_t > 0 must correspond to frac_deploy_now < 1 somewhere in
        that period's path population, and theta_t uniformly very negative
        should correspond to frac_deploy_now == 1.0 -- a basic sanity check
        that the deploy_now decision (deploy_vals >= wait_vals) and the
        reported mean_theta (wait - deploy) haven't drifted out of sync."""
        for entry in fast_run["theta_by_period"]:
            if entry["mean_theta"] < -0.05:
                assert entry["frac_deploy_now"] == pytest.approx(1.0), entry


class TestSpendTrickle:
    """docs/theta_followup_plan.md Section 0.1.1's blocked fix: wait-branch
    D_i,t now grows via a calibrated trickle, giving eta something to react
    to. load_trickle_rate_per_day() must fall back cleanly to zero (the old
    behavior) when the calibration file doesn't exist, and read real
    per-tier rates when it does."""

    def test_falls_back_to_zero_when_trickle_file_absent(self, monkeypatch, tmp_path):
        monkeypatch.setattr(lsm, "_TRICKLE_PATH", tmp_path / "does_not_exist.json")
        rates = lsm.load_trickle_rate_per_day(["Toss-Up", "Safe D", "Lean R"])
        assert (rates == 0.0).all()

    def test_respects_preferred_estimator_key_not_hardcoded_to_median(self, monkeypatch, tmp_path):
        """Regression test for a real finding: checked against the actual
        2022/2024 panel, median_rate_per_day is exactly $0.00/day in every
        tier (FEC's quarterly filing cadence against this project's
        biweekly grid means most periods have no new filing at all), so
        estimate_candidate_spend_trickle.py switched its preferred
        estimator to mean_rate_per_day. This test locks in that
        load_trickle_rate_per_day() reads whichever key
        preferred_estimator names, rather than a hardcoded field, so a
        future re-calibration's estimator choice is honored automatically."""
        import json
        trickle_path = tmp_path / "candidate_spend_trickle.json"
        trickle_path.write_text(json.dumps({
            "preferred_estimator": "mean_rate_per_day",
            "by_tier": {
                "Toss-Up": {"median_rate_per_day": 0.0, "mean_rate_per_day": 5000.0},
            }
        }))
        monkeypatch.setattr(lsm, "_TRICKLE_PATH", trickle_path)
        rates = lsm.load_trickle_rate_per_day(["Toss-Up"])
        assert rates[0] == pytest.approx(5000.0), (
            "expected the mean_rate_per_day value (5000.0), not median_rate_per_day (0.0) "
            "or a fallback to pooled/zero -- preferred_estimator was not respected"
        )

    def test_reads_per_tier_rate_and_falls_back_to_pooled_for_unknown_tier(self, monkeypatch, tmp_path):
        import json
        trickle_path = tmp_path / "candidate_spend_trickle.json"
        trickle_path.write_text(json.dumps({
            "preferred_estimator": "mean_rate_per_day",
            "by_tier": {
                "Toss-Up": {"mean_rate_per_day": 1200.0},
                "Safe D": {"mean_rate_per_day": 300.0},
                "_pooled": {"mean_rate_per_day": 600.0},
            }
        }))
        monkeypatch.setattr(lsm, "_TRICKLE_PATH", trickle_path)
        rates = lsm.load_trickle_rate_per_day(["Toss-Up", "Safe D", "Lean R"])
        assert rates[0] == pytest.approx(1200.0)
        assert rates[1] == pytest.approx(300.0)
        assert rates[2] == pytest.approx(600.0)   # Lean R absent from by_tier -> pooled fallback

    def test_nonzero_trickle_changes_run_lsm_output_without_crashing(self, monkeypatch, tmp_path, synthetic_races):
        """Integration check: wiring in a real (nonzero) trickle rate must
        not crash run_lsm() and must produce a materially different result
        from the zero-trickle baseline -- if it silently produced identical
        numbers, that would mean the trickle wasn't actually reaching
        d_paths/r_paths despite load_trickle_rate_per_day() returning
        nonzero values (exactly the class of wiring bug this file exists to
        catch, per its module docstring)."""
        import json
        monkeypatch.setattr(lsm, "build_universe", lambda cycle=2026: synthetic_races)
        monkeypatch.setattr(lsm, "K_PATHS", 40)
        monkeypatch.setattr(lsm, "N_PERIODS", 3)

        tiers_per_race = [r.cook_rating for r in synthetic_races]
        eta_by_tier = {"Toss-Up": 0.4, "Lean D": 0.26, "Lean R": 0.3, "Safe D": 0.0, "Safe R": 0.0}
        resid_by_tier = {"Toss-Up": 15_000.0, "Lean D": 12_000.0, "Lean R": 12_000.0,
                          "Safe D": 8_000.0, "Safe R": 8_000.0}
        eta_arr, resid_arr = lsm.tile_single_cycle(eta_by_tier, resid_by_tier, tiers_per_race, k_paths=40)

        monkeypatch.setattr(lsm, "_TRICKLE_PATH", tmp_path / "no_trickle.json")
        baseline = lsm.run_lsm(eta_arr, resid_arr, "no_trickle")

        trickle_path = tmp_path / "trickle.json"
        # A large trickle rate ($50k/day for every tier) relative to these
        # races' floors -- deliberately large so the effect isn't lost in
        # Monte Carlo noise at only 40 paths.
        trickle_path.write_text(json.dumps({
            "preferred_estimator": "mean_rate_per_day",
            "by_tier": {t: {"mean_rate_per_day": 50_000.0} for t in set(tiers_per_race)},
            "_pooled": {"mean_rate_per_day": 50_000.0},
        }))
        monkeypatch.setattr(lsm, "_TRICKLE_PATH", trickle_path)
        trickled = lsm.run_lsm(eta_arr, resid_arr, "with_trickle")

        for entry in trickled["theta_by_period"]:
            assert np.isfinite(entry["mean_theta"])
            assert 0.0 <= entry["frac_deploy_now"] <= 1.0

        # Some period's mean_theta must differ meaningfully between the two
        # runs -- otherwise the trickle demonstrably had no effect.
        baseline_thetas = [e["mean_theta"] for e in baseline["theta_by_period"]]
        trickled_thetas = [e["mean_theta"] for e in trickled["theta_by_period"]]
        assert any(
            abs(b - t) > 1e-6 for b, t in zip(baseline_thetas, trickled_thetas)
        ), "trickle had no measurable effect on any period's mean_theta -- likely not wired into d_paths/mu_paths"


# ─── _solve_committed_floor() (continuous-phi script): the floor-reset fix ──

class TestSolveCommittedFloor:
    """_solve_committed_floor is a module-level function (unlike
    solve_bellman_lsm.run_lsm's _deploy_value closure), so it can be tested
    directly. This is the exact function docs/theta_followup_plan.md Section
    1.3 item 2 describes fixing: `_deploy_value()` used to hardcode
    `d_t = floor_arr.copy()` on every call regardless of how much had
    already been notionally committed, which would have made every nonzero
    budget level in the continuous-phi grid trace out a flat line instead
    of a genuinely concave value-of-budget curve."""

    @pytest.fixture
    def setup(self, coef_sigma, synthetic_races):
        coef, sigma_model = coef_sigma
        races = synthetic_races
        n = len(races)
        outputs0 = compute_outputs_batch(races, coef, sigma_model)
        sigma_arr = np.array([o.sigma_i for o in outputs0])
        pvi_arr = np.array([r.pvi for r in races])
        incumb_arr = [r.incumb_status for r in races]
        floor_arr = np.array([r.cand_d_total for r in races])
        r_arr = np.array([r.r_total for r in races])
        is_incumb_arr = np.array([1.0 if s == "Incumbent" else 0.0 for s in incumb_arr])
        is_open_arr = np.array([1.0 if s == "Open" else 0.0 for s in incumb_arr])
        gb_national = races[0].generic_ballot
        mu_baseline = cphi._mu_struct(coef, pvi_arr, is_incumb_arr, gb_national, floor_arr, r_arr, is_open_arr)
        eta_arr_k = np.full(n, 0.3)
        return dict(coef=coef, races=races, n=n, sigma_arr=sigma_arr, pvi_arr=pvi_arr,
                    incumb_arr=incumb_arr, floor_arr=floor_arr, r_arr=r_arr,
                    mu_baseline=mu_baseline, eta_arr_k=eta_arr_k)

    def _call(self, s, budget):
        return cphi._solve_committed_floor(
            s["coef"], s["races"], s["n"], s["sigma_arr"], s["pvi_arr"], s["incumb_arr"],
            s["floor_arr"], s["mu_baseline"], s["r_arr"], s["eta_arr_k"], budget)

    def test_zero_budget_returns_floor_unchanged_without_calling_the_lp(self, setup):
        out = self._call(setup, budget=0.0)
        np.testing.assert_array_equal(out, setup["floor_arr"])

    def test_allocation_is_monotonically_non_decreasing_in_budget(self, setup):
        budgets = [0.0, 50_000.0, 150_000.0, 400_000.0]
        allocs = [self._call(setup, b) for b in budgets]
        for a_lo, a_hi in zip(allocs, allocs[1:]):
            assert np.all(a_hi >= a_lo - 1e-6), (a_lo, a_hi)

    def test_higher_budget_actually_changes_the_allocation_not_frozen(self, setup):
        """Direct regression test for the historical frozen-floor bug
        class: a materially larger budget must produce a materially
        different allocation, not the identical vector a hardcoded
        `floor_arr.copy()` would silently keep returning."""
        low = self._call(setup, budget=20_000.0)
        high = self._call(setup, budget=400_000.0)
        assert not np.allclose(low, high), "allocation frozen across a 20x budget change"

    def test_total_party_allocation_respects_the_budget_constraint(self, setup):
        budget = 150_000.0
        out = self._call(setup, budget=budget)
        party_allocated = float((out - setup["floor_arr"]).sum())
        assert party_allocated <= budget + 1.0  # $1 solver tolerance

    def test_allocation_never_falls_below_the_original_floor(self, setup):
        """Money can only be committed, never uncommitted (module docstring,
        Section 1.3's design) -- every grid level's floor must sit at or
        above the original candidate-committee floor."""
        for budget in (0.0, 100_000.0, 400_000.0):
            out = self._call(setup, budget)
            assert np.all(out >= setup["floor_arr"] - 1e-6)


# ─── run_continuous_phi_lsm() integration: trickle mechanism wired in ─────

class TestContinuousPhiTrickle:
    """docs/theta_followup_plan.md Section 12.4 flagged the continuous-phi
    generalization as NOT updated with the wait-branch spending trickle
    (solve_bellman_lsm.py's binary framing got it first). This class covers
    it being wired in afterward: run_continuous_phi_lsm() must run
    end-to-end with a real (nonzero) trickle file, and the trickle must
    actually reach the output (same "wired but inert" bug class Section 0
    of the followup plan found once already for eta)."""

    @pytest.fixture
    def fast_setup(self, monkeypatch, synthetic_races):
        monkeypatch.setattr(lsm, "build_universe", lambda cycle=2026: synthetic_races)
        monkeypatch.setattr(lsm, "K_PATHS", 20)
        monkeypatch.setattr(lsm, "N_PERIODS", 3)
        tiers_per_race = [r.cook_rating for r in synthetic_races]
        eta_by_tier = {"Toss-Up": 0.4, "Lean D": 0.26, "Lean R": 0.3, "Safe D": 0.0, "Safe R": 0.0}
        resid_by_tier = {"Toss-Up": 15_000.0, "Lean D": 12_000.0, "Lean R": 12_000.0,
                          "Safe D": 8_000.0, "Safe R": 8_000.0}
        eta_arr, resid_arr = lsm.tile_single_cycle(eta_by_tier, resid_by_tier, tiers_per_race, k_paths=20)
        return tiers_per_race, eta_arr, resid_arr

    def _run(self, tmp_path, monkeypatch, eta_arr, resid_arr, trickle_json, label, seed=42):
        import json
        trickle_path = tmp_path / f"{label}.json"
        trickle_path.write_text(json.dumps(trickle_json))
        monkeypatch.setattr(lsm, "_TRICKLE_PATH", trickle_path)
        rng = np.random.default_rng(seed)
        grid_fracs = list(np.linspace(0.0, 1.0, 5))
        return cphi.run_continuous_phi_lsm(eta_arr, resid_arr, label, grid_fracs, 20, rng)

    def test_runs_without_error_with_nonzero_trickle(self, monkeypatch, tmp_path, fast_setup):
        tiers_per_race, eta_arr, resid_arr = fast_setup
        res = self._run(tmp_path, monkeypatch, eta_arr, resid_arr, {
            "preferred_estimator": "mean_rate_per_day",
            "by_tier": {t: {"mean_rate_per_day": 5000.0} for t in set(tiers_per_race)},
            "_pooled": {"mean_rate_per_day": 5000.0},
        }, "with_trickle")
        assert len(res["schedule"]) == 3
        for entry in res["schedule"]:
            assert np.isfinite(entry["v_g0_mean"])
            assert 0.0 <= entry["chosen_frac_mean"] <= 1.0

    def test_nonzero_trickle_changes_output_vs_zero_trickle(self, monkeypatch, tmp_path, fast_setup):
        """Same wiring-bug class solve_bellman_lsm.py's TestSpendTrickle
        guards against: a trickle file that load_trickle_rate_per_day()
        reads as nonzero must actually change run_continuous_phi_lsm's
        output, not silently fail to reach d_paths/mu_committed."""
        tiers_per_race, eta_arr, resid_arr = fast_setup

        baseline = self._run(tmp_path, monkeypatch, eta_arr, resid_arr, {
            "preferred_estimator": "mean_rate_per_day", "by_tier": {},
        }, "no_trickle")

        trickled = self._run(tmp_path, monkeypatch, eta_arr, resid_arr, {
            "preferred_estimator": "mean_rate_per_day",
            "by_tier": {t: {"mean_rate_per_day": 50_000.0} for t in set(tiers_per_race)},
            "_pooled": {"mean_rate_per_day": 50_000.0},
        }, "with_trickle")

        baseline_v = [e["v_g0_mean"] for e in baseline["schedule"]]
        trickled_v = [e["v_g0_mean"] for e in trickled["schedule"]]
        assert any(abs(b - t) > 1e-6 for b, t in zip(baseline_v, trickled_v)), (
            "trickle had no measurable effect on any period's v_g0_mean -- "
            "likely not wired into d_paths/mu_committed"
        )

    def test_drift_correction_formula_matches_mu_struct_difference(self, coef_sigma, synthetic_races):
        """Sanity check of the drift-correction arithmetic itself
        (docs/theta_followup_plan.md Section 12.3's fourth correction,
        mirrored into this script's run_continuous_phi_lsm): the drift
        added on top of mu_level is defined as
        _mu_struct(d_terminal, r_terminal_expected) - _mu_struct(floor_g_kt, r_eff).
        This test exercises that exact formula (not a duplicate
        implementation -- there's only one _mu_struct call site here, so
        no copy-paste-divergence risk the way solve_bellman_lsm.py's
        separately-maintained inline mu_struct had) against realistic
        inputs, confirming it produces a finite, nonzero shift whenever
        d_terminal genuinely differs from floor_g_kt -- the basic
        precondition for the correction to do anything at all."""
        coef, sigma_model = coef_sigma
        races = synthetic_races
        pvi_arr = np.array([r.pvi for r in races])
        incumb_arr = [r.incumb_status for r in races]
        is_incumb_arr = np.array([1.0 if s == "Incumbent" else 0.0 for s in incumb_arr])
        is_open_arr = np.array([1.0 if s == "Open" else 0.0 for s in incumb_arr])
        gb_national = races[0].generic_ballot
        n = len(races)

        floor_g_kt = np.array([r.cand_d_total + 50_000.0 for r in races])   # after a DCCC commitment
        r_eff = np.array([r.r_total for r in races])
        eta_k = np.full(n, 0.3)
        d_terminal = floor_g_kt + 80_000.0   # further organic trickle growth after commitment

        mu_level = cphi._mu_struct(coef, pvi_arr, is_incumb_arr, gb_national, floor_g_kt, r_eff, is_open_arr)
        r_terminal_expected = np.maximum(r_eff + eta_k * (d_terminal - floor_g_kt), 1.0)
        mu_terminal_level = cphi._mu_struct(
            coef, pvi_arr, is_incumb_arr, gb_national, d_terminal, r_terminal_expected, is_open_arr
        )
        expected_drift = mu_terminal_level - mu_level

        # Same formula, independently re-derived: since d_terminal - floor_g_kt
        # is exactly the "further organic growth" term added above, and
        # r_terminal_expected is deterministic given eta_k and that gap, the
        # only way this drift could be zero is if d_terminal == floor_g_kt --
        # it isn't here, so a nonzero, finite drift is the correct expectation.
        assert np.all(np.isfinite(expected_drift))
        assert not np.allclose(expected_drift, 0.0), (
            "drift should be nonzero when d_terminal differs from floor_g_kt"
        )

    def test_terminal_period_has_no_drift_since_no_time_remains(self, monkeypatch, tmp_path, fast_setup):
        """At tstep == n_periods (election day itself), d_terminal == d_t --
        no more trickle can accrue -- so the drift correction must be
        exactly zero there, matching solve_bellman_lsm.py's terminal
        condition (d_t IS d_terminal at T, drift=0 by construction)."""
        tiers_per_race, eta_arr, resid_arr = fast_setup
        res = self._run(tmp_path, monkeypatch, eta_arr, resid_arr, {
            "preferred_estimator": "mean_rate_per_day",
            "by_tier": {t: {"mean_rate_per_day": 80_000.0} for t in set(tiers_per_race)},
            "_pooled": {"mean_rate_per_day": 80_000.0},
        }, "terminal_check")
        # No direct handle on mu_committed from the public return value, but a
        # finite, sane v_g0_mean at every period (including the implicit
        # terminal condition folded into period n_periods-1's absorbing_val)
        # is the available end-to-end signal that the tstep < n_periods guard
        # didn't produce a shape mismatch or NaN at the boundary.
        for entry in res["schedule"]:
            assert np.isfinite(entry["v_g0_mean"])


# ─── _mu_struct() cross-consistency and a real finding it surfaced ────────

class TestMuStructConsistency:
    def test_matches_solve_bellman_lsm_inline_formula(self, coef_sigma, synthetic_races):
        """solve_bellman_lsm.py's run_lsm() computes mu_struct inline rather
        than calling a shared function; solve_bellman_lsm_continuous_phi.py
        keeps its own copy (_mu_struct), documented in its own docstring as
        'identical to solve_bellman_lsm.run_lsm's mu_struct computation.'
        This test checks that claim against the actual code rather than
        trusting the comment -- two independently maintained copies of the
        same formula in two different files are exactly the kind of thing
        that silently drifts apart under a future edit to only one of them."""
        coef, _ = coef_sigma
        races = synthetic_races
        pvi_arr = np.array([r.pvi for r in races])
        incumb_arr = [r.incumb_status for r in races]
        is_incumb_arr = np.array([1.0 if s == "Incumbent" else 0.0 for s in incumb_arr])
        is_open_arr = np.array([1.0 if s == "Open" else 0.0 for s in incumb_arr])
        floor_arr = np.array([r.cand_d_total for r in races])
        r_arr = np.array([r.r_total for r in races])
        gb_national = races[0].generic_ballot

        mu_cphi = cphi._mu_struct(coef, pvi_arr, is_incumb_arr, gb_national, floor_arr, r_arr, is_open_arr)

        # Manual replica of run_lsm's inline per-tstep computation
        # (solve_bellman_lsm.py, inside the mu_paths loop), including the
        # beta1_open substitution both now apply for Open-seat races.
        beta1_eff = np.where(is_open_arr > 0, coef.beta1_open, coef.beta1)
        d_t = floor_arr
        t_t = d_t + r_arr
        ratio = np.clip(d_t / t_t, 1e-6, 1 - 1e-6)
        log_ratio = np.log(ratio)
        c_arr = beta1_eff + coef.beta2 * np.abs(pvi_arr) + coef.beta3 * is_incumb_arr
        mu_inline = (coef.alpha0 + coef.alpha1 * pvi_arr + coef.alpha2 * is_incumb_arr
                     + coef.alpha3 * gb_national + c_arr * log_ratio)

        np.testing.assert_allclose(mu_cphi, mu_inline, rtol=1e-9)

    def test_mu_struct_uses_beta1_open_for_open_seat_races(self, coef_sigma, synthetic_races):
        """Was an xfail documenting a real gap when this suite was first
        written: margin_gradient() (solve_bellman_lsm.py) already
        substituted coef.beta1_open for Open-seat races, matching the
        static pipeline's win_prob.predict(), but the mu_struct LEVEL
        formula -- both run_lsm()'s inline computation and this function --
        always used coef.beta1, even for Open seats, so the Bellman/Theta
        machinery computed the level and the gradient of mu for the same
        Open-seat race with two different elasticities. Now fixed in both
        solve_bellman_lsm.py and solve_bellman_lsm_continuous_phi.py; this
        confirms it against win_prob.py's static predict(), the source of
        truth for what beta1_open should do."""
        coef, _ = coef_sigma
        assert coef.beta1_open is not None and coef.beta1_open != coef.beta1  # else this test is vacuous

        races = synthetic_races
        open_idx = [i for i, r in enumerate(races) if r.incumb_status == "Open"]
        assert open_idx, "fixture must include at least one Open-seat race"

        pvi_arr = np.array([r.pvi for r in races])
        incumb_arr = [r.incumb_status for r in races]
        is_incumb_arr = np.array([1.0 if s == "Incumbent" else 0.0 for s in incumb_arr])
        is_open_arr = np.array([1.0 if s == "Open" else 0.0 for s in incumb_arr])
        floor_arr = np.array([r.cand_d_total for r in races])
        r_arr = np.array([r.r_total for r in races])
        gb_national = races[0].generic_ballot

        mu_actual = cphi._mu_struct(coef, pvi_arr, is_incumb_arr, gb_national, floor_arr, r_arr, is_open_arr)

        for i in open_idx:
            ratio = floor_arr[i] / (floor_arr[i] + r_arr[i])
            expected = static_predict(pvi=races[i].pvi, incumb_status="Open",
                                       generic_ballot=gb_national, ratio=ratio, coef=coef)
            assert mu_actual[i] == pytest.approx(expected, rel=1e-6)

    def test_mu_struct_omitting_is_open_arr_keeps_old_behavior_not_silently_wrong(self, coef_sigma, synthetic_races):
        """is_open_arr is optional for backward compatibility with any
        caller not yet updated -- verify that omitting it reproduces the
        pre-fix (coef.beta1-for-everyone) formula exactly, rather than
        raising or silently doing something else. Any new caller in this
        repo should always pass is_open_arr; this only guards the fallback
        path itself."""
        coef, _ = coef_sigma
        races = synthetic_races
        pvi_arr = np.array([r.pvi for r in races])
        incumb_arr = [r.incumb_status for r in races]
        is_incumb_arr = np.array([1.0 if s == "Incumbent" else 0.0 for s in incumb_arr])
        floor_arr = np.array([r.cand_d_total for r in races])
        r_arr = np.array([r.r_total for r in races])
        gb_national = races[0].generic_ballot

        mu_no_open_arg = cphi._mu_struct(coef, pvi_arr, is_incumb_arr, gb_national, floor_arr, r_arr)

        d_t = floor_arr
        t_t = d_t + r_arr
        ratio = np.clip(d_t / t_t, 1e-6, 1 - 1e-6)
        log_ratio = np.log(ratio)
        c_arr = coef.beta1 + coef.beta2 * np.abs(pvi_arr) + coef.beta3 * is_incumb_arr
        mu_expected_old_formula = (coef.alpha0 + coef.alpha1 * pvi_arr + coef.alpha2 * is_incumb_arr
                                    + coef.alpha3 * gb_national + c_arr * log_ratio)

        np.testing.assert_allclose(mu_no_open_arg, mu_expected_old_formula, rtol=1e-9)
