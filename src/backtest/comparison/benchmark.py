"""
Benchmark comparisons: Brier score and four-way allocator comparison.

Compares model-implied win probabilities against:
  1. Cook Political Report converted probabilities
  2. FiveThirtyEight final pre-election probabilities (where available)

Also implements the null (equal-weight) allocator benchmark.
"""

from __future__ import annotations
import logging
import numpy as np
import pandas as pd
from ..types import RaceRecord, ModelOutputs
from .. import config

logger = logging.getLogger(__name__)


# ─── Brier score ──────────────────────────────────────────────────────────────

def brier_score(p_win: np.ndarray, outcomes: np.ndarray) -> float:
    """
    Brier score = mean((p − outcome)²).
    outcomes: 1 if Democrat won, 0 if Republican won.
    """
    return float(np.mean((p_win - outcomes) ** 2))


def compute_brier_comparison(
    races: list[RaceRecord],
    model_outputs: list[ModelOutputs],
    fte_probs: dict[str, float] | None = None,
) -> dict:
    """
    Compute Brier scores for model, Cook, and (optionally) FiveThirtyEight.

    Parameters
    ----------
    fte_probs : district_id → D win probability, from FTE (where available)

    Returns dict: {model, cook, fte (if available), n_races}
    """
    cook_map = config.cook_win_probs()
    races_with_outcomes = [r for r in races if r.outcome is not None]
    outputs_with_outcomes = [o for r, o in zip(races, model_outputs) if r.outcome is not None]

    if not races_with_outcomes:
        logger.warning("No outcome data available — skipping Brier score computation")
        return {}

    outcomes = np.array([1.0 if r.outcome == "D" else 0.0 for r in races_with_outcomes])
    model_p = np.array([o.p_win for o in outputs_with_outcomes])
    cook_p = np.array([cook_map.get(r.cook_rating, 0.5) for r in races_with_outcomes])

    result = {
        "model": brier_score(model_p, outcomes),
        "cook": brier_score(cook_p, outcomes),
        "n_races": len(races_with_outcomes),
    }

    if fte_probs:
        fte_p = np.array([fte_probs.get(r.district_id, 0.5) for r in races_with_outcomes])
        result["fte"] = brier_score(fte_p, outcomes)

    for source, score in result.items():
        if source != "n_races":
            logger.info(f"Brier score ({source}): {score:.4f}")

    return result


# ─── Null allocator ───────────────────────────────────────────────────────────

def null_equal_weight_shares(races: list[RaceRecord]) -> np.ndarray:
    """
    Null benchmark: uniform allocation across competitive races, zero elsewhere.

    Returns array of length len(races) with shares summing to 1.
    """
    competitive = set(config.competitive_ratings())
    n_comp = sum(1 for r in races if r.cook_rating in competitive)
    if n_comp == 0:
        raise ValueError("No competitive races for null allocator")

    shares = np.array([
        1.0 / n_comp if r.cook_rating in competitive else 0.0
        for r in races
    ])
    return shares


def cook_proportional_shares(races: list[RaceRecord]) -> np.ndarray:
    """
    Cook-implied allocation: proportional to Cook win probability.
    Only allocates to competitive races.

    Returns array of length len(races) with shares summing to ≤ 1.
    """
    cook_map = config.cook_win_probs()
    competitive = set(config.competitive_ratings())

    raw = np.array([
        cook_map.get(r.cook_rating, 0.0) if r.cook_rating in competitive else 0.0
        for r in races
    ])
    total = raw.sum()
    return raw / total if total > 0 else raw


def expected_seats(p_win: np.ndarray) -> float:
    """E[Seats] = Σ P_win_i."""
    return float(np.sum(p_win))


def compare_allocators(
    races: list[RaceRecord],
    model_outputs: list[ModelOutputs],
    model_shares: np.ndarray,
    null_shares: np.ndarray,
    cook_shares: np.ndarray,
    budget: float,
    model_label: str = "Model optimizer",
) -> pd.DataFrame:
    """
    Four-way E[Seats] comparison table.

    Returns DataFrame with columns: allocator, expected_seats, description
    """
    cook_map = config.cook_win_probs()
    p_win_model = np.array([o.p_win for o in model_outputs])

    # E[Seats] under DCCC observed (evaluated at model win probs)
    observed_shares = np.array([r.d_total / budget for r in races])

    rows = [
        {"allocator": "DCCC observed",     "expected_seats": expected_seats(p_win_model),
         "description": "Actual 2024 DCCC spending shares, model P_win"},
        {"allocator": "Null (equal-weight)", "expected_seats": _expected_seats_at_shares(
            races, model_outputs, null_shares),
         "description": "Uniform across competitive races"},
        {"allocator": "Cook-implied",        "expected_seats": _expected_seats_at_shares(
            races, model_outputs, cook_shares),
         "description": "Proportional to Cook win probability"},
        {"allocator": model_label,           "expected_seats": _expected_seats_at_shares(
            races, model_outputs, model_shares),
         "description": "Marginal seat gain optimization"},
    ]

    return pd.DataFrame(rows)


def _expected_seats_at_shares(
    races: list[RaceRecord],
    outputs: list[ModelOutputs],
    shares: np.ndarray,
) -> float:
    """
    Approximate E[Seats] by re-evaluating P_win at the scaled spending implied
    by the new shares.  Uses the linearized MSG approximation:
        P_win_i(new) ≈ P_win_i⁰ + MSG_i · (new_spend_i − observed_spend_i)
    """
    p_win0 = np.array([o.p_win for o in outputs])
    msg = np.array([o.msg_i for o in outputs])
    budget = sum(r.d_total for r in races)
    observed = np.array([r.d_total for r in races])
    new_spend = shares * budget
    delta = new_spend - observed
    p_win_new = np.clip(p_win0 + msg * delta, 0.0, 1.0)
    return float(p_win_new.sum())


def permutation_test_allocation_efficiency(
    races: list[RaceRecord],
    outputs: list[ModelOutputs],
    model_shares: np.ndarray,
    n_permutations: int = 2000,
    rng: np.random.Generator | None = None,
) -> dict:
    """
    Permutation null distribution for DCCC's spending-to-race assignment.

    Randomly reassigns DCCC's observed per-race dollar amounts across
    competitive races (same multiset of dollars, no relationship to MSG) and
    evaluates E[Seats] under each shuffled allocation with the same
    linearized approximation _expected_seats_at_shares() already uses for
    the Null and Cook-implied benchmark rows. This is a direct robustness
    check on two distinct claims:

      1. Is DCCC's *actual* choice of which race gets which dollar amount
         worse than a random shuffle of its own dollars? This is a stronger,
         assumption-lighter claim than the rank-correlation test — it
         doesn't require interpreting a Spearman ρ, just comparing one real
         number against an empirical null.
      2. Is the model optimizer's seat gain over DCCC bigger than what a
         random reshuffle alone would produce? If most of the "+X seats"
         headline is achievable by literally any reshuffle of the same
         dollars (a consequence of the win-probability curve's concavity,
         not of MSG-based targeting), that is a real problem for the
         targeting claim, not just a footnote.

    Returns dict with: dccc_expected_seats, model_expected_seats,
    null_mean_expected_seats, null_ci_95, n_permutations, n_competitive,
    p_value_dccc_below_null (fraction of null ≥ DCCC's actual E[Seats]),
    p_value_model_exceeds_null (fraction of null ≥ the optimizer's E[Seats])
    """
    rng = rng or np.random.default_rng(42)
    competitive = set(config.competitive_ratings())
    comp_idx = np.array([i for i, r in enumerate(races) if r.cook_rating in competitive])
    if len(comp_idx) == 0:
        raise ValueError("No competitive races for permutation test")

    observed_d = np.array([r.d_total for r in races])
    total_budget = observed_d.sum()

    dccc_expected_seats = _expected_seats_at_shares(races, outputs, observed_d / total_budget)
    model_expected_seats = _expected_seats_at_shares(races, outputs, model_shares)

    null_seats = np.empty(n_permutations)
    permuted_d = observed_d.copy()
    for i in range(n_permutations):
        permuted_d[comp_idx] = rng.permutation(observed_d[comp_idx])
        null_seats[i] = _expected_seats_at_shares(races, outputs, permuted_d / total_budget)

    p_dccc_below_null = float(np.mean(null_seats >= dccc_expected_seats))
    p_model_exceeds_null = float(np.mean(null_seats >= model_expected_seats))

    logger.info(
        f"Allocation permutation test (n={n_permutations}, {len(comp_idx)} competitive races): "
        f"DCCC E[Seats]={dccc_expected_seats:.2f}, model E[Seats]={model_expected_seats:.2f}, "
        f"null mean={null_seats.mean():.2f}; "
        f"P(random reshuffle ≥ DCCC)={p_dccc_below_null:.3f}, "
        f"P(random reshuffle ≥ model)={p_model_exceeds_null:.3f}"
    )

    return {
        "dccc_expected_seats": dccc_expected_seats,
        "model_expected_seats": model_expected_seats,
        "null_mean_expected_seats": float(null_seats.mean()),
        "null_ci_95": [float(np.percentile(null_seats, 2.5)), float(np.percentile(null_seats, 97.5))],
        "n_permutations": n_permutations,
        "n_competitive": int(len(comp_idx)),
        "p_value_dccc_below_null": p_dccc_below_null,
        "p_value_model_exceeds_null": p_model_exceeds_null,
    }
