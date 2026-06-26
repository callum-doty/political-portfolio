"""
β_RC uncertainty propagation.

For each of K draws from β_RC ~ N(β̂, SE²):
  1. Recompute MSG_i for all races
  2. Re-run the optimizer to produce recommended_share_i^(k)
  3. Collect distribution of recommended shares and Spearman ρ

Produces an UncertaintyBundle with median, 83% CI, and
P(model recommends more than DCCC) per race.
"""

from __future__ import annotations
import logging
import numpy as np
from tqdm import tqdm
from ..types import RaceRecord, BetaRC, SigmaModel, FactorModel, UncertaintyBundle
from ..model.margin import MarginModelCoefficients
from ..model.win_prob import compute_outputs_batch
from ..optimizer.allocator import optimize
from .. import config

logger = logging.getLogger(__name__)


def propagate_beta_rc_uncertainty(
    races: list[RaceRecord],
    beta_rc: BetaRC,
    coef: MarginModelCoefficients,
    sigma_model: SigmaModel,
    factor_model: FactorModel,
    budget: float,
    gamma: float,
    cap_fraction: float,
    rng: np.random.Generator | None = None,
    party_budget: float | None = None,
) -> UncertaintyBundle:
    """
    Run K optimizer iterations, each with a different β_RC draw.

    Parameters
    ----------
    gamma, cap_fraction : use the primary (baseline) optimizer settings

    Returns
    -------
    UncertaintyBundle with matrix of recommended shares (K × n_races)
    """
    ucfg = config.uncertainty_cfg()
    K = ucfg["n_draws"]
    rng = rng or np.random.default_rng(42)

    beta_draws = rng.normal(loc=beta_rc.estimate, scale=beta_rc.se, size=K)
    cov_matrix = factor_model.race_covariance()
    n_races = len(races)
    observed_shares = np.array([r.d_total / budget for r in races])

    cand_floors = np.array([r.cand_d_total for r in races])
    recommended_matrix = np.zeros((K, n_races))

    for k, beta_draw in enumerate(tqdm(beta_draws, desc="β_RC draws", leave=False)):
        outputs_k = compute_outputs_batch(races, coef, sigma_model, beta1_override=float(beta_draw))
        result_k = optimize(outputs_k, budget, cov_matrix, gamma, cap_fraction,
                            floor_allocations=cand_floors, party_budget=party_budget)
        recommended_matrix[k] = result_k.shares

    return UncertaintyBundle(
        district_ids=[r.district_id for r in races],
        recommended_shares_matrix=recommended_matrix,
        observed_shares=observed_shares,
    )


def spearman_distribution(
    races: list[RaceRecord],
    beta_rc: BetaRC,
    coef: MarginModelCoefficients,
    sigma_model: SigmaModel,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """
    Return distribution of Spearman ρ across β_RC draws (K values).

    Used to report ρ as a distribution rather than a point estimate.
    """
    from scipy import stats as scipy_stats
    ucfg = config.uncertainty_cfg()
    K = ucfg["n_draws"]
    rng = rng or np.random.default_rng(42)
    beta_draws = rng.normal(loc=beta_rc.estimate, scale=beta_rc.se, size=K)

    competitive = set(config.competitive_ratings())
    comp_races = [(i, r) for i, r in enumerate(races) if r.cook_rating in competitive]
    observed_spend = np.array([r.d_total for _, r in comp_races])

    rhos = []
    for beta_draw in beta_draws:
        outputs_k = compute_outputs_batch(
            [r for _, r in comp_races], coef, sigma_model, beta1_override=float(beta_draw)
        )
        msg_k = np.array([o.msg_i for o in outputs_k])
        rho, _ = scipy_stats.spearmanr(observed_spend, msg_k)
        rhos.append(rho)

    return np.array(rhos)
