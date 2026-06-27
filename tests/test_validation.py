"""Tests for validation gates (run_all_gates and individual gate logic)."""

import pytest
import numpy as np
from backtest.types import RaceRecord, ModelOutputs, SigmaModel
from backtest.validation.gates import run_all_gates, ValidationError, GateResult


# ─── Fixtures / helpers ───────────────────────────────────────────────────────

def _make_race(
    district_id="TX-07",
    cook_rating="Toss-Up",
    d_total=2_000_000.0,
    r_total=2_000_000.0,
    outcome="D",
) -> RaceRecord:
    state, num = district_id.split("-")
    return RaceRecord(
        district_id=district_id, state=state, district=int(num),
        cook_rating=cook_rating, incumb_status="Challenger",
        pvi=-1.0, d_total=d_total, r_total=r_total,
        cvap=350_000, generic_ballot=-1.2, outcome=outcome,
    )


def _make_output(
    district_id="TX-07",
    p_win=0.55,
    msg_i=1e-7,
) -> ModelOutputs:
    return ModelOutputs(
        district_id=district_id, ratio=0.5,
        mu_hat=1.0, sigma_i=5.0,
        p_win=p_win, msg_i=msg_i,
    )


def _good_sigma() -> SigmaModel:
    """Sigma model that satisfies the ordering check (open > challenger > incumbent)."""
    return SigmaModel(_coef={
        "intercept": 2.0, "abs_pvi": 0.02,
        "is_open": 0.3, "is_challenger": 0.15,
    })


def _run_gates(races, outputs, **overrides):
    """Run all gates with sane defaults; override any keyword to trigger failures."""
    kwargs = dict(
        races=races,
        outputs=outputs,
        sigma_model=_good_sigma(),
        margin_r2_competitive=0.45,
        optimizer_status="optimal",
        n_corner_solutions=0,
        brier_model=0.10,
        brier_cook=0.20,
        budget=sum(r.d_total for r in races) or 4_000_000.0,
    )
    kwargs.update(overrides)
    return run_all_gates(**kwargs)


# ─── All-gates-pass scenarios ─────────────────────────────────────────────────

class TestAllGatesPass:
    def test_returns_six_gate_results(self):
        races = [_make_race()]
        results = _run_gates(races, [_make_output()])
        assert len(results) == 6

    def test_all_passed_flag_true(self):
        races = [_make_race()]
        results = _run_gates(races, [_make_output()])
        assert all(g.passed for g in results)

    def test_each_result_has_name_and_threshold(self):
        races = [_make_race()]
        results = _run_gates(races, [_make_output()])
        for g in results:
            assert isinstance(g, GateResult)
            assert g.name
            assert g.threshold

    def test_stretch_r2_also_passes(self):
        """R² above the stretch goal (0.60) must still pass gate 2."""
        races = [_make_race()]
        results = _run_gates(races, [_make_output()], margin_r2_competitive=0.65)
        assert results[1].passed

    def test_optimal_inaccurate_passes_gate_5(self):
        races = [_make_race()]
        results = _run_gates(races, [_make_output()], optimizer_status="optimal_inaccurate")
        assert results[4].passed


# ─── Gate 1: spending completeness ────────────────────────────────────────────

class TestGate1SpendingCompleteness:
    def test_fails_when_two_thirds_one_sided(self):
        """2 of 3 races with missing one side → completeness 33% < 80%."""
        races = [
            _make_race("TX-01", d_total=1e6, r_total=0.0),
            _make_race("TX-02", d_total=0.0, r_total=1e6),
            _make_race("TX-03", d_total=1e6, r_total=1e6),
        ]
        outputs = [_make_output(r.district_id) for r in races]
        with pytest.raises(ValidationError, match="Spending data completeness"):
            _run_gates(races, outputs)

    def test_passes_when_all_two_sided(self):
        races = [
            _make_race("TX-01", d_total=1e6, r_total=1e6),
            _make_race("TX-02", d_total=2e6, r_total=1.5e6),
        ]
        outputs = [_make_output(r.district_id) for r in races]
        results = _run_gates(races, outputs)
        assert results[0].passed


# ─── Gate 2: margin model R² ──────────────────────────────────────────────────

class TestGate2MarginR2:
    def test_fails_when_r2_below_threshold(self):
        races = [_make_race()]
        with pytest.raises(ValidationError, match="Margin model R"):
            _run_gates(races, [_make_output()], margin_r2_competitive=0.10)

    def test_passes_at_exact_threshold(self):
        races = [_make_race()]
        # 0.40 is the pass threshold from config
        results = _run_gates(races, [_make_output()], margin_r2_competitive=0.40)
        assert results[1].passed

    def test_gate_value_is_the_r2(self):
        races = [_make_race()]
        results = _run_gates(races, [_make_output()], margin_r2_competitive=0.50)
        assert results[1].value == pytest.approx(0.50)


# ─── Gate 3: σᵢ ordering ─────────────────────────────────────────────────────

class TestGate3SigmaOrdering:
    def test_well_ordered_sigma_gate_passes(self):
        races = [_make_race()]
        results = _run_gates(races, [_make_output()], sigma_model=_good_sigma())
        assert results[2].passed

    def test_fraction_value_between_0_and_1(self):
        races = [_make_race()]
        results = _run_gates(races, [_make_output()])
        assert 0.0 <= results[2].value <= 1.0


# ─── Gate 4: MSG sign ────────────────────────────────────────────────────────

class TestGate4MSGSign:
    def test_fails_when_competitive_race_has_negative_msg(self):
        races = [_make_race(cook_rating="Toss-Up")]
        outputs = [_make_output(msg_i=-1e-8)]
        with pytest.raises(ValidationError, match="MSG sign"):
            _run_gates(races, outputs)

    def test_fails_when_lean_r_race_has_zero_msg(self):
        races = [_make_race(cook_rating="Lean R")]
        outputs = [_make_output(msg_i=0.0)]
        with pytest.raises(ValidationError, match="MSG sign"):
            _run_gates(races, outputs)

    def test_non_competitive_negative_msg_does_not_fail_gate(self):
        """Safe D races are outside the competitive set — their MSG doesn't trigger gate 4."""
        races = [_make_race(cook_rating="Safe D")]
        outputs = [_make_output(msg_i=-999.0)]  # doesn't matter for non-competitive
        results = _run_gates(races, outputs)
        assert results[3].passed


# ─── Gate 5: optimizer convergence ────────────────────────────────────────────

class TestGate5OptimizerConvergence:
    def test_fails_for_infeasible_status(self):
        races = [_make_race()]
        with pytest.raises(ValidationError, match="Optimizer convergence"):
            _run_gates(races, [_make_output()], optimizer_status="infeasible")

    def test_fails_for_unknown_status(self):
        races = [_make_race()]
        with pytest.raises(ValidationError, match="Optimizer convergence"):
            _run_gates(races, [_make_output()], optimizer_status="solver_error")

    def test_slsqp_success_string_passes(self):
        """The SLSQP success message string must be recognised as convergence."""
        races = [_make_race()]
        results = _run_gates(
            races, [_make_output()],
            optimizer_status="slsqp:Optimization terminated successfully.",
        )
        assert results[4].passed


# ─── Gate 6: Brier score ──────────────────────────────────────────────────────

class TestGate6BrierScore:
    def test_fails_when_model_brier_much_worse_than_cook(self):
        races = [_make_race()]
        with pytest.raises(ValidationError, match="Brier score"):
            _run_gates(
                races, [_make_output()],
                brier_model=0.40,
                brier_cook=0.20,  # tolerance = 0.05 → threshold = 0.25; 0.40 > 0.25
            )

    def test_passes_when_model_beats_cook(self):
        races = [_make_race()]
        results = _run_gates(
            races, [_make_output()],
            brier_model=0.15,
            brier_cook=0.25,
        )
        assert results[5].passed

    def test_passes_at_tolerance_boundary(self):
        """Model Brier = Cook Brier + tolerance exactly → should pass."""
        races = [_make_race()]
        # tolerance from config = 0.05
        results = _run_gates(
            races, [_make_output()],
            brier_model=0.25 + 0.05,  # exactly at boundary
            brier_cook=0.25,
        )
        assert results[5].passed
