"""Tests for β_RC uncertainty propagation."""

import pytest
import numpy as np
from backtest import config
from backtest.types import BetaRC, UncertaintyBundle, RaceRecord, SigmaModel, FactorModel
from backtest.estimation.beta_rc import sample_beta_rc
from backtest.model.margin import MarginModelCoefficients
from backtest.comparison.uncertainty import propagate_beta_rc_uncertainty


class TestBetaRCSampling:
    def test_sample_count(self):
        beta_rc = BetaRC(estimate=3.0, se=0.5, n_pairs=60)
        rng = np.random.default_rng(42)
        samples = sample_beta_rc(beta_rc, 1000, rng)
        assert len(samples) == 1000

    def test_sample_mean_close_to_estimate(self):
        beta_rc = BetaRC(estimate=3.0, se=0.5, n_pairs=60)
        rng = np.random.default_rng(42)
        samples = sample_beta_rc(beta_rc, 10_000, rng)
        assert abs(samples.mean() - 3.0) < 0.05

    def test_sample_std_close_to_se(self):
        beta_rc = BetaRC(estimate=3.0, se=0.5, n_pairs=60)
        rng = np.random.default_rng(42)
        samples = sample_beta_rc(beta_rc, 10_000, rng)
        assert abs(samples.std() - 0.5) < 0.02


class TestUncertaintyBundle:
    def _make_bundle(self, K: int = 100, n: int = 5) -> UncertaintyBundle:
        rng = np.random.default_rng(0)
        matrix = rng.uniform(0.0, 0.1, (K, n))
        matrix = matrix / matrix.sum(axis=1, keepdims=True)
        observed = np.full(n, 1.0 / n)
        return UncertaintyBundle(
            district_ids=[f"XX-{i}" for i in range(n)],
            recommended_shares_matrix=matrix,
            observed_shares=observed,
        )

    def test_median_shape(self):
        bundle = self._make_bundle()
        assert bundle.median_share().shape == (5,)

    def test_ci_bounds(self):
        bundle = self._make_bundle(K=1000)
        lo, hi = bundle.credible_interval(0.83)
        assert (lo <= hi).all()
        assert (lo >= 0).all()

    def test_prob_exceeds_between_0_and_1(self):
        bundle = self._make_bundle(K=500)
        probs = bundle.prob_model_exceeds_dccc()
        assert (probs >= 0).all()
        assert (probs <= 1).all()


class TestPropagateBetaRCUncertainty:
    """Tests for propagate_beta_rc_uncertainty() itself, not just its
    downstream UncertaintyBundle/sample_beta_rc consumers — previously
    untested despite this module's filename."""

    def _make_races(self, n: int = 4) -> list[RaceRecord]:
        return [
            RaceRecord(
                district_id=f"XX-{i:02d}", state="XX", district=i + 1,
                cook_rating="Toss-Up", incumb_status="Challenger",
                pvi=0.0, d_total=2_000_000.0 + i * 100_000.0, r_total=1_800_000.0,
                cvap=400_000, generic_ballot=-1.2, cand_d_total=200_000.0,
            )
            for i in range(n)
        ]

    def _make_varied_races(self) -> list[RaceRecord]:
        """Deliberately non-symmetric across pvi/incumbency/spend so the MSG
        ranking actually flips at different beta1 values (verified directly
        against compute_outputs_batch before writing this fixture) -- unlike
        _make_races()'s uniform fixture, where every race shares the same
        pvi/incumbency and only d_total varies, so beta1 scales every race's
        msg by the same monotonic factor and the LP corner solution is
        invariant to beta1 regardless of whether beta1_override is wired
        through correctly or not (a false-negative trap for this test)."""
        # cand_d_total set to 30% of d_total per race (not a uniform 200k):
        # the persuasion ceiling (model/ceiling.py) scales achievable MSG by
        # Phi0 = Phi(mu_floor/sigma), and a floor too small relative to
        # d_total collapses Phi0 (and therefore msg_i) toward 0 for every
        # beta1 draw alike, which would make this test pass for the wrong
        # reason -- verified numerically against compute_outputs_batch that
        # 30% keeps msg_i responsive to beta1_override across all four races.
        return [
            RaceRecord(district_id="XX-00", state="XX", district=1, cook_rating="Toss-Up",
                       incumb_status="Challenger", pvi=8.0, d_total=1_200_000.0, r_total=3_000_000.0,
                       cvap=400_000, generic_ballot=-1.2, cand_d_total=360_000.0),
            RaceRecord(district_id="XX-01", state="XX", district=2, cook_rating="Toss-Up",
                       incumb_status="Incumbent", pvi=-3.0, d_total=2_800_000.0, r_total=1_000_000.0,
                       cvap=400_000, generic_ballot=-1.2, cand_d_total=840_000.0),
            RaceRecord(district_id="XX-02", state="XX", district=3, cook_rating="Toss-Up",
                       incumb_status="Open", pvi=1.0, d_total=2_000_000.0, r_total=2_000_000.0,
                       cvap=400_000, generic_ballot=-1.2, cand_d_total=600_000.0),
            RaceRecord(district_id="XX-03", state="XX", district=4, cook_rating="Toss-Up",
                       incumb_status="Challenger", pvi=-6.0, d_total=500_000.0, r_total=4_000_000.0,
                       cvap=400_000, generic_ballot=-1.2, cand_d_total=150_000.0),
        ]

    def _make_coef(self) -> MarginModelCoefficients:
        return MarginModelCoefficients(
            alpha0=0.0, alpha1=0.5, alpha2=2.0, alpha3=0.3,
            beta1=3.0, beta2=0.05, beta3=1.0,
        )

    def _make_sigma(self) -> SigmaModel:
        return SigmaModel(_coef={
            "intercept": 2.0, "abs_pvi": 0.02, "is_open": 0.3, "is_challenger": 0.15,
        })

    def _make_factor_model(self, n: int, variance: float = 0.01) -> FactorModel:
        return FactorModel(
            loadings=np.eye(n), factor_cov=np.eye(n) * variance,
            district_ids=[f"XX-{i:02d}" for i in range(n)],
        )

    def test_output_shape_and_district_alignment(self, monkeypatch):
        monkeypatch.setattr(config, "uncertainty_cfg", lambda: {"n_draws": 5})
        n = 4
        races = self._make_races(n)
        budget = 10_000_000.0
        bundle = propagate_beta_rc_uncertainty(
            races, BetaRC(estimate=3.0, se=1.0, n_pairs=60),
            self._make_coef(), self._make_sigma(), self._make_factor_model(n),
            budget, gamma=0.0, cap_fraction=0.9, rng=np.random.default_rng(0),
        )
        assert bundle.recommended_shares_matrix.shape == (5, n)
        assert bundle.district_ids == [r.district_id for r in races]
        expected_observed = np.array([r.d_total / budget for r in races])
        np.testing.assert_allclose(bundle.observed_shares, expected_observed)

    def test_nonzero_se_produces_varying_recommendations_across_draws(self, monkeypatch):
        """Regression for a class of bug this codebase has hit before
        (an estimated quantity computed but never actually multiplied/wired
        into the thing it's supposed to affect): if beta1_override weren't
        actually threaded through to compute_outputs_batch, every draw would
        produce an identical recommendation regardless of se."""
        monkeypatch.setattr(config, "uncertainty_cfg", lambda: {"n_draws": 20})
        races = self._make_varied_races()
        n = len(races)
        bundle = propagate_beta_rc_uncertainty(
            races, BetaRC(estimate=3.0, se=1.5, n_pairs=60),
            self._make_coef(), self._make_sigma(), self._make_factor_model(n),
            budget=10_000_000.0, gamma=0.0, cap_fraction=0.9,
            rng=np.random.default_rng(1),
        )
        # at least one district's recommended share must vary meaningfully
        # across draws -- a degenerate (beta1_override ignored) implementation
        # would produce zero variance in every column.
        per_district_std = bundle.recommended_shares_matrix.std(axis=0)
        assert (per_district_std > 1e-6).any()

    def test_zero_se_produces_identical_draws(self, monkeypatch):
        """Degenerate case: se=0 collapses every beta_rc draw to the same
        point estimate, so every row of the recommendation matrix must be
        identical (not just close -- the RNG draws are literally constant)."""
        monkeypatch.setattr(config, "uncertainty_cfg", lambda: {"n_draws": 5})
        n = 3
        races = self._make_races(n)
        bundle = propagate_beta_rc_uncertainty(
            races, BetaRC(estimate=3.0, se=0.0, n_pairs=60),
            self._make_coef(), self._make_sigma(), self._make_factor_model(n),
            budget=10_000_000.0, gamma=0.0, cap_fraction=0.9,
            rng=np.random.default_rng(2),
        )
        first_row = bundle.recommended_shares_matrix[0]
        for row in bundle.recommended_shares_matrix[1:]:
            np.testing.assert_allclose(row, first_row, atol=1e-9)
