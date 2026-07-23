"""Tests for benchmark comparison (Brier, allocators) and efficiency (Spearman ρ)."""

import pytest
import numpy as np
import pandas as pd
from itertools import permutations
from backtest.types import RaceRecord, ModelOutputs
from backtest.model.margin import MarginModelCoefficients
from backtest.types import SigmaModel
from backtest.optimizer.allocator import nonlinear_expected_seats_at_party_dollars, optimize_nonlinear
from backtest.comparison.benchmark import (
    brier_score,
    null_equal_weight_shares,
    cook_proportional_shares,
    expected_seats,
    compare_allocators,
    permutation_test_allocation_efficiency,
)
from backtest.comparison.efficiency import (
    spearman_efficiency_test, characterize_misallocation,
    spearman_by_cook_category, matched_group_efficiency_test,
    permutation_test_spearman_efficiency,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_race(
    district_id: str,
    cook_rating: str = "Toss-Up",
    d_total: float = 2_000_000.0,
    outcome: str | None = None,
    pvi: float = 0.0,
) -> RaceRecord:
    state, num = district_id.split("-")
    return RaceRecord(
        district_id=district_id, state=state, district=int(num),
        cook_rating=cook_rating, incumb_status="Challenger",
        pvi=pvi, d_total=d_total, r_total=d_total,
        cvap=350_000, generic_ballot=-1.2, outcome=outcome,
    )


def _make_output(
    district_id: str,
    p_win: float = 0.5,
    msg_i: float = 1e-7,
) -> ModelOutputs:
    return ModelOutputs(
        district_id=district_id, ratio=0.5,
        mu_hat=0.0, sigma_i=5.0,
        p_win=p_win, msg_i=msg_i,
    )


# ─── brier_score ──────────────────────────────────────────────────────────────

class TestBrierScore:
    def test_perfect_predictor_is_zero(self):
        p = np.array([1.0, 1.0, 0.0, 0.0])
        outcomes = np.array([1.0, 1.0, 0.0, 0.0])
        assert brier_score(p, outcomes) == pytest.approx(0.0)

    def test_worst_predictor_is_one(self):
        p = np.array([0.0, 0.0, 1.0, 1.0])
        outcomes = np.array([1.0, 1.0, 0.0, 0.0])
        assert brier_score(p, outcomes) == pytest.approx(1.0)

    def test_uniform_half_is_0_25(self):
        p = np.full(4, 0.5)
        outcomes = np.array([1.0, 0.0, 1.0, 0.0])
        assert brier_score(p, outcomes) == pytest.approx(0.25)

    def test_always_nonnegative(self):
        rng = np.random.default_rng(0)
        p = rng.uniform(0.0, 1.0, 50)
        outcomes = rng.integers(0, 2, 50).astype(float)
        assert brier_score(p, outcomes) >= 0.0

    def test_single_race(self):
        assert brier_score(np.array([0.8]), np.array([1.0])) == pytest.approx(0.04)

    def test_symmetric_in_p_and_1_minus_p_for_balanced_outcomes(self):
        """Swapping p=0.3→0.7 for symmetric outcomes should give same Brier."""
        outcomes = np.array([1.0, 0.0])
        assert brier_score(np.array([0.3, 0.7]), outcomes) == pytest.approx(
            brier_score(np.array([0.7, 0.3]), outcomes[::-1])
        )


# ─── null_equal_weight_shares ─────────────────────────────────────────────────

class TestNullEqualWeightShares:
    def test_uniform_over_competitive(self):
        races = [
            _make_race("TX-01", cook_rating="Toss-Up"),
            _make_race("TX-02", cook_rating="Lean D"),
            _make_race("TX-03", cook_rating="Safe R"),  # non-competitive → 0
        ]
        shares = null_equal_weight_shares(races)
        assert shares[0] == pytest.approx(0.5)
        assert shares[1] == pytest.approx(0.5)
        assert shares[2] == pytest.approx(0.0)

    def test_shares_sum_to_one(self):
        races = [_make_race(f"TX-{i:02d}", cook_rating="Toss-Up") for i in range(1, 6)]
        shares = null_equal_weight_shares(races)
        assert shares.sum() == pytest.approx(1.0)

    def test_no_competitive_races_raises(self):
        races = [_make_race("TX-01", cook_rating="Safe R")]
        with pytest.raises(ValueError, match="No competitive"):
            null_equal_weight_shares(races)

    def test_single_competitive_race_gets_all(self):
        races = [
            _make_race("TX-01", cook_rating="Toss-Up"),
            _make_race("TX-02", cook_rating="Safe D"),
        ]
        shares = null_equal_weight_shares(races)
        assert shares[0] == pytest.approx(1.0)
        assert shares[1] == pytest.approx(0.0)

    def test_all_ratings_that_are_competitive(self):
        """Lean D, Toss-Up, and Lean R are all competitive in config."""
        races = [
            _make_race("TX-01", cook_rating="Lean D"),
            _make_race("TX-02", cook_rating="Toss-Up"),
            _make_race("TX-03", cook_rating="Lean R"),
        ]
        shares = null_equal_weight_shares(races)
        assert shares.sum() == pytest.approx(1.0)
        assert (shares > 0).sum() == 3


# ─── cook_proportional_shares ─────────────────────────────────────────────────

class TestCookProportionalShares:
    def test_sums_to_one_over_competitive(self):
        races = [
            _make_race("TX-01", cook_rating="Toss-Up"),
            _make_race("TX-02", cook_rating="Lean D"),
            _make_race("TX-03", cook_rating="Lean R"),
        ]
        shares = cook_proportional_shares(races)
        assert shares.sum() == pytest.approx(1.0)

    def test_lean_d_gets_more_than_lean_r(self):
        """Cook win prob for Lean D (0.70) > Lean R (0.30)."""
        races = [
            _make_race("TX-01", cook_rating="Lean D"),
            _make_race("TX-02", cook_rating="Lean R"),
        ]
        shares = cook_proportional_shares(races)
        assert shares[0] > shares[1]

    def test_safe_r_gets_zero(self):
        races = [
            _make_race("TX-01", cook_rating="Toss-Up"),
            _make_race("TX-02", cook_rating="Safe R"),
        ]
        shares = cook_proportional_shares(races)
        assert shares[1] == pytest.approx(0.0)

    def test_tossup_gets_half_of_equal_weight_pair(self):
        """Two Toss-Up races should receive equal shares (both p=0.50)."""
        races = [
            _make_race("TX-01", cook_rating="Toss-Up"),
            _make_race("TX-02", cook_rating="Toss-Up"),
        ]
        shares = cook_proportional_shares(races)
        assert shares[0] == pytest.approx(shares[1])


# ─── expected_seats ───────────────────────────────────────────────────────────

class TestExpectedSeats:
    def test_sum_of_probabilities(self):
        p_win = np.array([0.2, 0.5, 0.8, 0.9])
        assert expected_seats(p_win) == pytest.approx(2.4)

    def test_all_wins(self):
        assert expected_seats(np.ones(5)) == pytest.approx(5.0)

    def test_all_losses(self):
        assert expected_seats(np.zeros(5)) == pytest.approx(0.0)

    def test_single_race(self):
        assert expected_seats(np.array([0.7])) == pytest.approx(0.7)


# ─── compare_allocators ─────────────────────────────────────────────────────────

class TestCompareAllocators:
    """
    Had zero test coverage (imported, never called) until 2026-07-22 --
    closed the same day compare_allocators() was rewritten twice, both
    prompted by scripts/investigate_null_benchmark_bias.py finding an
    anomalous 2022 OOS result (Null appeared to edge out the model
    optimizer): first to use the true nonlinear evaluation for every row
    (not just the Model row), then to constrain Null/Cook to the same
    DCCC-controllable party_budget the Model optimizer is constrained to,
    rather than the entire two-party spending pool including candidate
    money DCCC never controls.

    Races carry a nonzero cand_d_total floor deliberately -- with floors at
    zero, "scale to total budget" and "scale to party budget, floors fixed"
    are much harder to tell apart in a test; a real floor exercises the
    actual bug this fixture is meant to catch.
    """

    def _coef(self):
        return MarginModelCoefficients(
            alpha0=0.0, alpha1=0.5, alpha2=2.0, alpha3=0.3,
            beta1=3.0, beta2=0.05, beta3=1.0,
        )

    def _sigma(self):
        return SigmaModel(_coef={
            "intercept": 2.0, "abs_pvi": 0.02,
            "is_open": 0.3, "is_challenger": 0.15,
        })

    def _races(self, n: int = 6):
        return [
            RaceRecord(
                district_id=f"XX-{i:02d}", state="TX", district=i + 1,
                cook_rating="Toss-Up", incumb_status="Challenger",
                pvi=float(i * 5), d_total=float(i + 1) * 2e6, r_total=float(i + 1) * 1e6,
                cvap=400_000, generic_ballot=-1.2, cand_d_total=float(i + 1) * 1e6,
            )
            for i in range(n)
        ]

    def test_returns_four_rows(self):
        races = self._races()
        coef, sigma = self._coef(), self._sigma()
        outputs = [
            ModelOutputs(r.district_id, 0.5, 0.0, 5.0, 0.5, 1e-7) for r in races
        ]
        budget = sum(r.d_total for r in races)
        party_budget = sum(r.d_total - r.cand_d_total for r in races)
        null_shares = null_equal_weight_shares(races)
        cook_shares = cook_proportional_shares(races)
        model_shares = null_shares  # arbitrary valid shares vector for this test
        table = compare_allocators(races, outputs, coef, sigma, model_shares,
                                   null_shares, cook_shares, budget, party_budget)
        assert len(table) == 4
        assert set(table["allocator"]) == {
            "DCCC observed", "Null (equal-weight)", "Cook-implied", "Model optimizer",
        }

    def test_every_row_matches_direct_party_dollar_evaluation(self):
        """Each hypothetical row should equal a direct call to the same
        nonlinear evaluator on party dollars scaled to party_budget, not
        total budget -- i.e. no row is still using the retired linearized
        approximation or the retired total-budget scope."""
        races = self._races()
        coef, sigma = self._coef(), self._sigma()
        outputs = [
            ModelOutputs(r.district_id, 0.5, 0.0, 5.0, 0.5, 1e-7) for r in races
        ]
        budget = sum(r.d_total for r in races)
        party_budget = sum(r.d_total - r.cand_d_total for r in races)
        floors = np.array([r.cand_d_total for r in races])
        null_shares = null_equal_weight_shares(races)
        cook_shares = cook_proportional_shares(races)
        observed_party = np.array([r.d_total for r in races]) - floors

        table = compare_allocators(races, outputs, coef, sigma, cook_shares,
                                   null_shares, cook_shares, budget, party_budget)

        expected = {
            "DCCC observed": nonlinear_expected_seats_at_party_dollars(races, coef, sigma, observed_party),
            "Null (equal-weight)": nonlinear_expected_seats_at_party_dollars(
                races, coef, sigma, null_shares * party_budget),
            "Cook-implied": nonlinear_expected_seats_at_party_dollars(
                races, coef, sigma, cook_shares * party_budget),
            # model_shares uses the OptimizerResult.shares convention (fraction of
            # TOTAL budget, allocs = floor + party), not the null/cook weight-vector
            # convention (fraction of party_budget directly) -- compare_allocators()
            # converts it via model_shares*budget - floors, not model_shares*party_budget.
            "Model optimizer": nonlinear_expected_seats_at_party_dollars(
                races, coef, sigma, np.maximum(cook_shares * budget - floors, 0.0)),
        }
        for _, row in table.iterrows():
            assert row["expected_seats"] == pytest.approx(expected[row["allocator"]], abs=1e-9)

    def test_null_and_cook_never_exceed_party_budget(self):
        """Regression test for the exact bug found 2026-07-22: Null/Cook
        should never be credited with reallocating candidate money in
        races DCCC doesn't control. Their implied party spend, summed
        across races, must not exceed party_budget."""
        races = self._races()
        coef, sigma = self._coef(), self._sigma()
        party_budget = sum(r.d_total - r.cand_d_total for r in races)
        null_shares = null_equal_weight_shares(races)
        cook_shares = cook_proportional_shares(races)
        assert (null_shares * party_budget).sum() == pytest.approx(party_budget, rel=1e-6)
        assert (cook_shares * party_budget).sum() <= party_budget + 1.0

    def test_model_row_matches_optimizer_own_result_exactly(self):
        """The historical reason compare_allocators() needed a post-hoc
        override: its Model row didn't match optimize_nonlinear()'s own
        answer. It now should, to high precision, with no override."""
        races = self._races()
        coef, sigma = self._coef(), self._sigma()
        outputs = [
            ModelOutputs(r.district_id, 0.5, 0.0, 5.0, 0.5, 1e-7) for r in races
        ]
        budget = sum(r.d_total for r in races)
        party_budget = sum(r.d_total - r.cand_d_total for r in races)
        cov = np.eye(len(races)) * 0.01
        result = optimize_nonlinear(races, coef, sigma, budget, cov, gamma=0.0, cap_fraction=0.5,
                                     party_budget=party_budget)

        table = compare_allocators(
            races, outputs, coef, sigma, result.shares,
            null_equal_weight_shares(races), cook_proportional_shares(races), budget, party_budget,
        )
        model_row = table[table["allocator"] == "Model optimizer"].iloc[0]
        assert model_row["expected_seats"] == pytest.approx(result.expected_seats, abs=1e-6)


# ─── permutation_test_allocation_efficiency ────────────────────────────────────

class TestPermutationAllocationEfficiency:
    """
    Uses the true nonlinear Φ(μ/σ) evaluation (nonlinear_expected_seats_at_shares),
    not a linearized MSG-delta approximation -- an earlier version of this
    function used the linear approximation throughout and was found
    (2026-07-22, scripts/investigate_null_benchmark_bias.py) to substantially
    overstate P(random reshuffle >= DCCC) on real data (100% vs. a true 35.6%
    in 2024). Fixture below establishes "worst" and "best" allocations by
    exhaustive search over all permutations of a small (n=6) dollar multiset,
    not by guessing a direction from intuition -- with the real nonlinear
    model, which reallocation is best is not obvious by inspection.
    """

    def _coef(self):
        return MarginModelCoefficients(
            alpha0=0.0, alpha1=0.5, alpha2=2.0, alpha3=0.3,
            beta1=3.0, beta2=0.05, beta3=1.0,
        )

    def _sigma(self):
        return SigmaModel(_coef={
            "intercept": 2.0, "abs_pvi": 0.02,
            "is_open": 0.3, "is_challenger": 0.15,
        })

    def _worst_and_best_fixture(self, n: int = 6):
        races = [
            RaceRecord(
                district_id=f"XX-{i:02d}", state="TX", district=i + 1,
                cook_rating="Toss-Up", incumb_status="Challenger",
                pvi=float(i * 5), d_total=float(i + 1) * 1e6, r_total=float(i + 1) * 1e6,
                cvap=400_000, generic_ballot=-1.2, cand_d_total=0.0,
            )
            for i in range(n)
        ]
        coef, sigma = self._coef(), self._sigma()
        amounts = np.array([r.d_total for r in races])  # floors are 0.0, so amounts == party dollars
        total_budget = amounts.sum()

        best_val, best_perm = -1.0, None
        worst_val, worst_perm = float("inf"), None
        for perm in permutations(amounts):
            val = nonlinear_expected_seats_at_party_dollars(races, coef, sigma, np.array(perm))
            if val > best_val:
                best_val, best_perm = val, perm
            if val < worst_val:
                worst_val, worst_perm = val, perm

        # DCCC "observed" IS the exhaustively-verified worst permutation of
        # this multiset (set directly on the race records); model_shares IS
        # the exhaustively-verified best.
        for r, amt in zip(races, worst_perm):
            r.d_total = float(amt)
        model_shares = np.array(best_perm) / total_budget

        return races, coef, sigma, model_shares

    def test_returns_all_required_keys(self):
        races, coef, sigma, model_shares = self._worst_and_best_fixture()
        result = permutation_test_allocation_efficiency(
            races, coef, sigma, model_shares, n_permutations=200, rng=np.random.default_rng(0))
        for key in ["dccc_expected_seats", "model_expected_seats", "null_mean_expected_seats",
                    "null_ci_95", "n_permutations", "n_competitive",
                    "p_value_dccc_below_null", "p_value_model_exceeds_null"]:
            assert key in result

    def test_worst_possible_dccc_allocation_sits_at_bottom_of_null(self):
        races, coef, sigma, model_shares = self._worst_and_best_fixture()
        result = permutation_test_allocation_efficiency(
            races, coef, sigma, model_shares, n_permutations=2000, rng=np.random.default_rng(1))
        # observed_d is the exhaustively-verified global-worst permutation of
        # its own multiset, so literally every random reshuffle does at
        # least as well: p == 1.0 exactly, not just close to it.
        assert result["p_value_dccc_below_null"] == 1.0

    def test_best_possible_model_allocation_sits_at_top_of_null(self):
        races, coef, sigma, model_shares = self._worst_and_best_fixture()
        result = permutation_test_allocation_efficiency(
            races, coef, sigma, model_shares, n_permutations=2000, rng=np.random.default_rng(1))
        # model_shares is the exhaustively-verified global-best permutation,
        # so no random reshuffle can exceed it: p == 0.0 exactly.
        assert result["p_value_model_exceeds_null"] == 0.0
        assert result["model_expected_seats"] > result["dccc_expected_seats"]

    def test_no_competitive_races_raises(self):
        races = [_make_race("TX-01", cook_rating="Safe R")]
        with pytest.raises(ValueError, match="No competitive"):
            permutation_test_allocation_efficiency(
                races, self._coef(), self._sigma(), np.array([1.0]))

    def test_deterministic_with_seeded_rng(self):
        races, coef, sigma, model_shares = self._worst_and_best_fixture()
        result_a = permutation_test_allocation_efficiency(
            races, coef, sigma, model_shares, n_permutations=300, rng=np.random.default_rng(7))
        result_b = permutation_test_allocation_efficiency(
            races, coef, sigma, model_shares, n_permutations=300, rng=np.random.default_rng(7))
        assert result_a["null_mean_expected_seats"] == result_b["null_mean_expected_seats"]


# ─── spearman_efficiency_test ─────────────────────────────────────────────────

class TestSpearmanEfficiency:
    def _aligned(self, n: int = 10):
        """Spending and MSG rank-aligned → ρ ≈ +1."""
        races = [
            _make_race(f"TX-{i:02d}", cook_rating="Toss-Up", d_total=float(i + 1) * 1e6)
            for i in range(n)
        ]
        outputs = [_make_output(f"TX-{i:02d}", msg_i=float(i + 1) * 1e-7) for i in range(n)]
        return races, outputs

    def _anti_aligned(self, n: int = 10):
        """Spending and MSG rank anti-aligned → ρ ≈ −1."""
        races = [
            _make_race(f"TX-{i:02d}", cook_rating="Toss-Up", d_total=float(i + 1) * 1e6)
            for i in range(n)
        ]
        outputs = [_make_output(f"TX-{i:02d}", msg_i=float(n - i) * 1e-7) for i in range(n)]
        return races, outputs

    def test_positive_rho_when_aligned(self):
        races, outputs = self._aligned()
        result = spearman_efficiency_test(races, outputs, n_bootstrap=100,
                                          rng=np.random.default_rng(0))
        assert result["rho"] > 0.8

    def test_negative_rho_when_anti_aligned(self):
        races, outputs = self._anti_aligned()
        result = spearman_efficiency_test(races, outputs, n_bootstrap=100,
                                          rng=np.random.default_rng(0))
        assert result["rho"] < -0.8

    def test_returns_all_required_keys(self):
        races, outputs = self._aligned()
        result = spearman_efficiency_test(races, outputs, n_bootstrap=50,
                                          rng=np.random.default_rng(0))
        for key in ["rho", "p_value", "ci_low", "ci_high", "n_competitive"]:
            assert key in result

    def test_n_competitive_is_correct(self):
        n = 8
        races, outputs = self._aligned(n)
        result = spearman_efficiency_test(races, outputs, n_bootstrap=50,
                                          rng=np.random.default_rng(0))
        assert result["n_competitive"] == n

    def test_ci_brackets_rho(self):
        races, outputs = self._aligned(n=15)
        result = spearman_efficiency_test(races, outputs, n_bootstrap=500,
                                          rng=np.random.default_rng(0))
        assert result["ci_low"] <= result["rho"] <= result["ci_high"]

    def test_p_value_in_unit_interval(self):
        races, outputs = self._aligned()
        result = spearman_efficiency_test(races, outputs, n_bootstrap=50,
                                          rng=np.random.default_rng(0))
        assert 0.0 <= result["p_value"] <= 1.0

    def test_no_competitive_races_raises(self):
        races = [_make_race("TX-01", cook_rating="Safe R")]
        outputs = [_make_output("TX-01")]
        with pytest.raises(ValueError, match="No competitive"):
            spearman_efficiency_test(races, outputs)


# ─── permutation_test_spearman_efficiency ──────────────────────────────────────

class TestPermutationSpearmanEfficiency:
    def _aligned(self, n: int = 15):
        races = [
            _make_race(f"TX-{i:02d}", cook_rating="Toss-Up", d_total=float(i + 1) * 1e6)
            for i in range(n)
        ]
        outputs = [_make_output(f"TX-{i:02d}", msg_i=float(i + 1) * 1e-7) for i in range(n)]
        return races, outputs

    def _anti_aligned(self, n: int = 15):
        races = [
            _make_race(f"TX-{i:02d}", cook_rating="Toss-Up", d_total=float(i + 1) * 1e6)
            for i in range(n)
        ]
        outputs = [_make_output(f"TX-{i:02d}", msg_i=float(n - i) * 1e-7) for i in range(n)]
        return races, outputs

    def test_returns_all_required_keys(self):
        races, outputs = self._aligned()
        result = permutation_test_spearman_efficiency(
            races, outputs, n_permutations=200, rng=np.random.default_rng(0))
        for key in ["rho", "p_value_asymptotic", "p_value_permutation",
                    "n_permutations", "n_competitive"]:
            assert key in result

    def test_rho_matches_direct_spearman(self):
        """The reported rho should be the same statistic spearman_efficiency_test reports."""
        races, outputs = self._anti_aligned()
        direct = spearman_efficiency_test(races, outputs, n_bootstrap=10,
                                          rng=np.random.default_rng(0))
        perm = permutation_test_spearman_efficiency(
            races, outputs, n_permutations=200, rng=np.random.default_rng(0))
        assert perm["rho"] == pytest.approx(direct["rho"])

    def test_permutation_p_value_near_zero_when_strongly_anti_aligned(self):
        """A near-perfect -1 rank correlation should almost never occur by
        chance among 15! random reassignments -- permutation p should be ~0."""
        races, outputs = self._anti_aligned(n=15)
        result = permutation_test_spearman_efficiency(
            races, outputs, n_permutations=2000, rng=np.random.default_rng(1))
        assert result["rho"] < -0.9
        assert result["p_value_permutation"] < 0.01

    def test_permutation_p_value_in_unit_interval(self):
        races, outputs = self._aligned()
        result = permutation_test_spearman_efficiency(
            races, outputs, n_permutations=200, rng=np.random.default_rng(0))
        assert 0.0 <= result["p_value_permutation"] <= 1.0

    def test_no_competitive_races_raises(self):
        races = [_make_race("TX-01", cook_rating="Safe R")]
        outputs = [_make_output("TX-01")]
        with pytest.raises(ValueError, match="No competitive"):
            permutation_test_spearman_efficiency(races, outputs)

    def test_deterministic_with_seeded_rng(self):
        races, outputs = self._anti_aligned()
        result_a = permutation_test_spearman_efficiency(
            races, outputs, n_permutations=300, rng=np.random.default_rng(7))
        result_b = permutation_test_spearman_efficiency(
            races, outputs, n_permutations=300, rng=np.random.default_rng(7))
        assert result_a["p_value_permutation"] == result_b["p_value_permutation"]


# ─── spearman_by_cook_category ─────────────────────────────────────────────────

class TestSpearmanByCookCategory:
    def test_returns_row_per_category_present(self):
        races, outputs = [], []
        for cat in ["Lean D", "Toss-Up"]:
            for i in range(5):
                rid = f"{cat[:2]}-{i:02d}"
                races.append(_make_race(rid, cook_rating=cat, d_total=float(i + 1) * 1e6))
                outputs.append(_make_output(rid, msg_i=float(i + 1) * 1e-7))
        df = spearman_by_cook_category(races, outputs, categories=("Lean D", "Toss-Up", "Lean R"))
        assert set(df["cook_category"]) == {"Lean D", "Toss-Up"}   # Lean R absent -> dropped
        assert (df["n"] == 5).all()

    def test_skips_categories_with_too_few_races(self):
        races = [_make_race("AA-01", cook_rating="Lean R", d_total=1e6),
                 _make_race("AA-02", cook_rating="Lean R", d_total=2e6)]
        outputs = [_make_output("AA-01", msg_i=1e-7), _make_output("AA-02", msg_i=2e-7)]
        df = spearman_by_cook_category(races, outputs, categories=("Lean R",))
        assert df.empty   # n=2 < minimum of 3

    def test_rho_sign_within_category(self):
        races, outputs = [], []
        for i in range(6):
            rid = f"TU-{i:02d}"
            races.append(_make_race(rid, cook_rating="Toss-Up", d_total=float(i + 1) * 1e6))
            outputs.append(_make_output(rid, msg_i=float(6 - i) * 1e-7))   # anti-aligned
        df = spearman_by_cook_category(races, outputs, categories=("Toss-Up",))
        assert df.iloc[0]["rho"] < -0.8


# ─── matched_group_efficiency_test ─────────────────────────────────────────────

class TestMatchedGroupEfficiency:
    def test_filters_by_category_and_pvi(self):
        races, outputs = [], []
        # In-scope: Lean D, |PVI| <= 5
        for i in range(5):
            rid = f"IN-{i:02d}"
            races.append(_make_race(rid, cook_rating="Lean D", pvi=3.0, d_total=float(i + 1) * 1e6))
            outputs.append(_make_output(rid, msg_i=float(i + 1) * 1e-7))
        # Out of scope: PVI too large
        races.append(_make_race("OT-01", cook_rating="Lean D", pvi=9.0, d_total=1e6))
        outputs.append(_make_output("OT-01", msg_i=1e-7))
        # Out of scope: wrong category
        races.append(_make_race("OT-02", cook_rating="Likely D", pvi=1.0, d_total=1e6))
        outputs.append(_make_output("OT-02", msg_i=1e-7))

        result = matched_group_efficiency_test(races, outputs)
        assert result["n"] == 5

    def test_raises_when_no_races_match(self):
        races = [_make_race("AA-01", cook_rating="Safe R", pvi=20.0, d_total=1e6)]
        outputs = [_make_output("AA-01", msg_i=1e-7)]
        with pytest.raises(ValueError, match="No races"):
            matched_group_efficiency_test(races, outputs)


# ─── characterize_misallocation ───────────────────────────────────────────────

class TestCharacterizeMisallocation:
    def _run(self, races, outputs, diffs, budget=10_000_000.0):
        return characterize_misallocation(races, outputs, diffs, budget)

    def test_identifies_overfunded_race(self):
        """diff < 0 means model recommends less than observed → observed overfunded."""
        budget = 10_000_000.0
        races = [_make_race("TX-01", cook_rating="Toss-Up", d_total=5e6)]
        outputs = [_make_output("TX-01")]
        # model recommends 3M, observed 5M → diff = -2M < -threshold
        result = self._run(races, outputs, diffs=[-2_000_000.0], budget=budget)
        assert result["overfunded"]["count"] == 1

    def test_identifies_underfunded_race(self):
        """diff > 0 means model recommends more than observed → observed underfunded."""
        budget = 10_000_000.0
        races = [_make_race("TX-02", cook_rating="Lean D", d_total=1e6)]
        outputs = [_make_output("TX-02")]
        # model recommends 4M, observed 1M → diff = +3M > threshold
        result = self._run(races, outputs, diffs=[3_000_000.0], budget=budget)
        assert result["underfunded"]["count"] == 1

    def test_small_diff_not_material(self):
        """Difference below 1% of budget (100K for 10M budget) is not reported."""
        budget = 10_000_000.0
        races = [_make_race("TX-01", cook_rating="Toss-Up", d_total=2e6)]
        outputs = [_make_output("TX-01")]
        result = self._run(races, outputs, diffs=[50_000.0], budget=budget)
        # 50K < 1% of 10M = 100K → immaterial
        assert result["overfunded"]["count"] == 0
        assert result["underfunded"]["count"] == 0

    def test_returns_both_summary_keys(self):
        races = [_make_race("TX-01")]
        outputs = [_make_output("TX-01")]
        result = self._run(races, outputs, diffs=[0.0])
        assert "overfunded" in result
        assert "underfunded" in result

    def test_mixed_over_and_under(self):
        budget = 10_000_000.0
        races = [
            _make_race("TX-01", cook_rating="Toss-Up",  d_total=5e6),
            _make_race("TX-02", cook_rating="Lean D",   d_total=2e6),
            _make_race("TX-03", cook_rating="Lean R",   d_total=3e6),
        ]
        outputs = [_make_output(r.district_id) for r in races]
        # TX-01: over-observed by 2M → overfunded
        # TX-02: under-observed by 3M → underfunded
        # TX-03: tiny diff → immaterial
        diffs = [-2_000_000.0, 3_000_000.0, 10_000.0]
        result = self._run(races, outputs, diffs, budget)
        assert result["overfunded"]["count"] == 1
        assert result["underfunded"]["count"] == 1

    def test_by_rating_breakdown_present(self):
        budget = 10_000_000.0
        races = [_make_race("TX-01", cook_rating="Toss-Up", d_total=5e6)]
        outputs = [_make_output("TX-01")]
        result = self._run(races, outputs, diffs=[-2_000_000.0], budget=budget)
        assert "by_rating" in result["overfunded"]
        assert "by_incumb" in result["overfunded"]
        assert "by_pvi_bin" in result["overfunded"]
