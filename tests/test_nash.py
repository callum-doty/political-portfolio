"""
Tests for src/backtest/optimizer/nash.py -- the two-sided Nash equilibrium
solver for adversarial NRCC response (FINDINGS.md Section 10.5, replacing
the reduced-form eta scalar).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from backtest.types import RaceRecord  # noqa: E402
from backtest.optimizer import nash  # noqa: E402
from backtest.optimizer.allocator import optimize_nonlinear  # noqa: E402
from backtest.data import fec  # noqa: E402
from backtest.data.universe import build_universe  # noqa: E402

import solve_bellman_lsm as lsm  # noqa: E402 -- reuse its real-coefficient loader, not its logic
import solve_nash_equilibrium as script  # noqa: E402


def _race(district_id, cook_rating, incumb_status, pvi, d_total, r_total,
          cand_d_total, generic_ballot=2.0, cvap=500_000):
    return RaceRecord(
        district_id=district_id, state=district_id.split("-")[0], district=1,
        cook_rating=cook_rating, incumb_status=incumb_status, pvi=pvi,
        d_total=d_total, r_total=r_total, cvap=cvap,
        generic_ballot=generic_ballot, cand_d_total=cand_d_total,
    )


@pytest.fixture
def coef_sigma():
    return lsm.load_coef_and_sigma()


@pytest.fixture
def synthetic_races() -> list[RaceRecord]:
    return [
        _race("TX-01", "Safe D", "Incumbent", pvi=20.0, d_total=500_000, r_total=100_000, cand_d_total=400_000),
        _race("OH-02", "Toss-Up", "Open", pvi=0.0, d_total=300_000, r_total=300_000, cand_d_total=200_000),
        _race("PA-03", "Lean D", "Incumbent", pvi=3.0, d_total=250_000, r_total=200_000, cand_d_total=150_000),
        _race("MI-04", "Lean R", "Challenger", pvi=-3.0, d_total=200_000, r_total=250_000, cand_d_total=100_000),
        _race("FL-05", "Safe R", "Challenger", pvi=-20.0, d_total=50_000, r_total=500_000, cand_d_total=40_000),
    ]


# ─── best_response("D", ...) ────────────────────────────────────────────────

class TestDBestResponseMatchesOptimizeNonlinear:
    def test_d_best_response_reproduces_direct_optimize_nonlinear_call(self, coef_sigma, synthetic_races):
        """best_response("D", ...) is documented as reusing optimize_nonlinear()
        unmodified -- this checks that claim against the real code, not just
        the docstring: same races-with-r_total-overridden construction, same
        result, for both the allocation and the reported expected seats."""
        coef, sigma_model = coef_sigma
        races = synthetic_races
        opp_total_fixed = np.array([r.r_total for r in races]) * 1.3  # some arbitrary R position
        party_budget_d = 400_000.0
        cap_fraction_d = 0.4

        result = nash.best_response(
            "D", races, coef, sigma_model, opp_total_fixed=opp_total_fixed,
            own_party_budget=party_budget_d, own_cap_fraction=cap_fraction_d,
        )

        import dataclasses
        races_t = [dataclasses.replace(r, r_total=float(opp_total_fixed[i])) for i, r in enumerate(races)]
        expected = optimize_nonlinear(
            races_t, coef, sigma_model, budget=party_budget_d,
            cov_matrix=np.eye(len(races)) * 1e-6, gamma=0.0, cap_fraction=cap_fraction_d,
            party_budget=party_budget_d, eta=0.0,
        )
        floors = np.array([r.cand_d_total for r in races])
        expected_party = np.maximum(expected.allocations - floors, 0.0)

        np.testing.assert_allclose(result.party, expected_party, rtol=1e-9)
        assert result.e_seats_own == pytest.approx(expected.expected_seats, rel=1e-9)
        assert result.status == expected.status


# ─── best_response("R", ...) gradient correctness ──────────────────────────

class TestRBestResponseGradient:
    def test_r_gradient_at_symmetric_start_is_negative_of_d_gradient(self, coef_sigma):
        """Exact numerical symmetry between D's and R's optimal ALLOCATIONS
        does not generally hold in this game (the mu formula is not
        antisymmetric under a d<->r swap away from the party=0 point -- see
        nash.py's module docstring on the asymmetry). What DOES hold exactly,
        by construction, is the FIRST-ORDER behavior at a perfectly symmetric
        starting point (identical floor/fixed-total on both sides, identical
        race characteristics): moving D up by an infinitesimal amount must
        help D by exactly the amount moving R up by the same infinitesimal
        hurts D, since both act on the same shared mu formula from the same
        starting point. This is the real invariant to test -- it directly
        validates that _r_mu_and_grad's hand-derived calculus (module
        docstring's d(mu_raw)/d(r) = (alpha4-c_spend)/t derivation) was
        implemented correctly, independent of any downstream optimizer
        behavior."""
        coef, sigma_model = coef_sigma
        X = 300_000.0
        race = _race("XX-01", "Toss-Up", "Open", pvi=0.0, d_total=X, r_total=X, cand_d_total=X)

        # D-side gradient at party_d=0, R fixed at X (mirrors allocator.py's
        # own margin_gradient/_msg_vec construction at eta=0).
        c = coef.beta1_open if coef.beta1_open is not None else coef.beta1
        # (Open-seat race with pvi=0 -> abs_pvi term vanishes regardless.)
        d_mu_d_partyd_at_0 = c * (1.0 / X - 1.0 / (2 * X)) + coef.alpha4 * (1.0 / (2 * X))

        # R-side mirror gradient at party_r=0, D fixed at X, R's own floor = X.
        r_arrays = nash._r_precompute([race], coef, sigma_model,
                                       cand_r_total=np.array([X]), d_current=np.array([X]))
        _, d_mu_d_partyr_at_0 = nash._r_mu_and_grad(np.array([0.0]), r_arrays)

        assert d_mu_d_partyr_at_0[0] == pytest.approx(-d_mu_d_partyd_at_0, rel=1e-6)

    def test_r_mu_floor_matches_direct_formula_at_symmetric_start(self, coef_sigma):
        """mu_floor_r at party_r=0 must equal mu_raw computed directly from
        the shared formula at (d=d_current, r=cand_r_total) -- the defining
        property of _r_precompute's anchor, checked directly rather than
        only indirectly through the gradient test above."""
        coef, sigma_model = coef_sigma
        d_fixed, r_floor = 400_000.0, 150_000.0
        race = _race("XX-01", "Lean D", "Incumbent", pvi=4.0, d_total=1.0, r_total=1.0, cand_d_total=1.0, cvap=600_000)

        arrays = nash._r_precompute([race], coef, sigma_model,
                                     cand_r_total=np.array([r_floor]), d_current=np.array([d_fixed]))
        mu_capped_at_0, _ = nash._r_mu_and_grad(np.array([0.0]), arrays)

        c_spend = coef.beta1 + coef.beta2 * abs(4.0) + coef.beta3 * 1.0
        t = d_fixed + r_floor
        expected_mu_raw = (coef.alpha0 + coef.alpha1 * 4.0 + coef.alpha2 * 1.0 + coef.alpha3 * race.generic_ballot
                            + c_spend * np.log(d_fixed / t) + coef.alpha4 * np.log(t / race.cvap))

        assert mu_capped_at_0[0] == pytest.approx(expected_mu_raw, rel=1e-6)


# ─── solve_best_response_dynamics() ─────────────────────────────────────────

class TestSolveBestResponseDynamics:
    def test_converges_on_a_small_well_behaved_case(self, coef_sigma, synthetic_races):
        coef, sigma_model = coef_sigma
        races = synthetic_races
        cand_r_total = np.array([r.r_total * 0.3 for r in races])  # plausible R floor

        result = nash.solve_best_response_dynamics(
            races, coef, sigma_model, cand_r_total,
            party_budget_d=300_000.0, party_budget_r=300_000.0,
            cap_fraction_d=0.3, cap_fraction_r=0.3, max_rounds=100, tol_dollars=100.0,
        )

        assert result.converged
        assert result.n_iterations <= 100
        assert len(result.history) == result.n_iterations
        # Zero-sum sanity check: E[D seats] + E[R seats] must equal n_races.
        assert result.e_seats_d + result.e_seats_r == pytest.approx(len(races), abs=1e-6)
        assert 0.0 <= result.e_seats_d <= len(races)
        assert np.all(result.party_d >= -1e-6)
        assert np.all(result.party_r >= -1e-6)

    def test_budgets_are_respected(self, coef_sigma, synthetic_races):
        coef, sigma_model = coef_sigma
        races = synthetic_races
        cand_r_total = np.array([r.r_total * 0.3 for r in races])
        party_budget_d, party_budget_r = 250_000.0, 180_000.0

        result = nash.solve_best_response_dynamics(
            races, coef, sigma_model, cand_r_total, party_budget_d, party_budget_r,
            cap_fraction_d=0.5, cap_fraction_r=0.5, max_rounds=100, tol_dollars=100.0,
        )
        assert result.party_d.sum() <= party_budget_d + 1.0  # $1 SLSQP-tolerance slack
        assert result.party_r.sum() <= party_budget_r + 1.0


class TestDampingReachesSameFixedPoint:
    def test_damped_and_undamped_converge_to_the_same_fixed_point_more_slowly(self, coef_sigma):
        """A single race with a large budget and a wide-open cap relative to
        its floor -- each side can swing the whole race in one round. Empirically
        (checked directly, not assumed) this particular game does not exhibit
        classic cobweb-style cycling: undamped (theta=1.0) converges in 3
        rounds after one large corrective overshoot-and-retreat. What damping
        must still guarantee is the more fundamental invariant: it changes
        HOW FAST the dynamics reach a fixed point (monotonically slower, by
        construction -- each round moves only a theta-fraction of the way),
        not WHICH fixed point they reach. theta=1.0 needs only 30 rounds;
        theta=0.3 needs ~40 to reach the same point within a wider tolerance,
        confirming damping doesn't silently redirect the equilibrium itself."""
        coef, sigma_model = coef_sigma
        race = _race("XX-01", "Toss-Up", "Open", pvi=0.0, d_total=100.0, r_total=100.0, cand_d_total=100.0)
        cand_r_total = np.array([100.0])

        undamped = nash.solve_best_response_dynamics(
            [race], coef, sigma_model, cand_r_total,
            party_budget_d=2_000_000.0, party_budget_r=2_000_000.0,
            cap_fraction_d=1.0, cap_fraction_r=1.0,
            damping_theta=1.0, max_rounds=30, tol_dollars=1.0,
        )
        damped = nash.solve_best_response_dynamics(
            [race], coef, sigma_model, cand_r_total,
            party_budget_d=2_000_000.0, party_budget_r=2_000_000.0,
            cap_fraction_d=1.0, cap_fraction_r=1.0,
            damping_theta=0.3, max_rounds=200, tol_dollars=1.0,
        )

        assert undamped.converged and damped.converged
        assert damped.n_iterations > undamped.n_iterations, (
            "damping is supposed to slow convergence down, not speed it up or leave it unchanged"
        )
        np.testing.assert_allclose(damped.party_d, undamped.party_d, atol=50.0)
        np.testing.assert_allclose(damped.party_r, undamped.party_r, atol=50.0)


# ─── find_nash_equilibrium_multi_start() ────────────────────────────────────

class TestMultiStartAgreement:
    def test_reports_agreement_on_a_well_behaved_case(self, coef_sigma, synthetic_races):
        coef, sigma_model = coef_sigma
        races = synthetic_races
        cand_r_total = np.array([r.r_total * 0.3 for r in races])

        result = nash.find_nash_equilibrium_multi_start(
            races, coef, sigma_model, cand_r_total,
            party_budget_d=300_000.0, party_budget_r=300_000.0,
            cap_fraction_d=0.3, cap_fraction_r=0.3, max_rounds=100, tol_dollars=100.0,
        )

        agreement = result.multi_start_agreement
        assert agreement is not None
        assert set(agreement["per_start_converged"].keys()) == {"observed", "uniform", "zero"}
        assert agreement["converged_all"]
        assert agreement["agree_within_tolerance"]

    def test_honestly_reports_disagreement_when_starts_diverge(self, monkeypatch, coef_sigma, synthetic_races):
        """Mocks solve_best_response_dynamics to return a genuinely different
        fixed point for one starting point, and checks
        find_nash_equilibrium_multi_start does NOT silently paper over
        this -- agree_within_tolerance must be False, and the disagreeing
        start must still be visible in per_start_e_seats_d."""
        coef, sigma_model = coef_sigma
        races = synthetic_races
        n = len(races)
        cand_r_total = np.array([r.r_total * 0.3 for r in races])

        real_solve = nash.solve_best_response_dynamics
        call_count = {"n": 0}

        def fake_solve(*args, **kwargs):
            call_count["n"] += 1
            res = real_solve(*args, **kwargs)
            if call_count["n"] == 2:   # perturb exactly one of the three starts
                res.party_d = res.party_d + 1_000_000.0
            return res

        monkeypatch.setattr(nash, "solve_best_response_dynamics", fake_solve)
        result = nash.find_nash_equilibrium_multi_start(
            races, coef, sigma_model, cand_r_total,
            party_budget_d=300_000.0, party_budget_r=300_000.0,
            cap_fraction_d=0.3, cap_fraction_r=0.3, max_rounds=20, tol_dollars=100.0,
        )

        assert result.multi_start_agreement["agree_within_tolerance"] is False
        assert result.multi_start_agreement["max_pairwise_party_d_diff"] >= 1_000_000.0 - 1.0


# ─── NRCC budget construction (solve_nash_equilibrium.py) ──────────────────

class TestNrccBudgetMatchesIndependentComputation:
    def test_load_cand_r_total_matches_direct_fec_groupby(self):
        """Cross-checks solve_nash_equilibrium.load_cand_r_total() (built
        from fec.load_candidate_disbursements(), party='R') against an
        independent computation over the same real 2026-08-07 data, and
        confirms party_budget_r = sum(r_total - cand_r_total) is internally
        consistent with fec.build_total_spend()'s own R_total figures."""
        cycle = 2024
        races = build_universe(cycle=cycle)
        cand_r_total = script.load_cand_r_total(races, cycle)

        disb = fec.load_candidate_disbursements(cycle)
        r_disb = disb[disb["party"] == "R"].set_index("district_id")["candidate_disbursements"]
        expected = np.array([float(r_disb.get(r.district_id, 0.0)) for r in races])
        np.testing.assert_allclose(cand_r_total, expected)

        r0 = np.array([r.r_total for r in races])
        party_budget_r = float(np.sum(r0 - cand_r_total))
        # Sanity: NRCC's party-controlled budget must be a real, bounded
        # positive share of total observed R spend, not degenerate.
        assert 0.0 < party_budget_r < r0.sum()
