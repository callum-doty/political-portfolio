"""Tests for benchmark comparison (Brier, allocators) and efficiency (Spearman ρ)."""

import pytest
import numpy as np
import pandas as pd
from backtest.types import RaceRecord, ModelOutputs
from backtest.comparison.benchmark import (
    brier_score,
    null_equal_weight_shares,
    cook_proportional_shares,
    expected_seats,
    compare_allocators,
)
from backtest.comparison.efficiency import (
    spearman_efficiency_test, characterize_misallocation,
    spearman_by_cook_category, matched_group_efficiency_test,
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
