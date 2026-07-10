"""
Win probability and marginal seat gain computation.

P_win_i = Φ(μᵢ / σᵢ)

where Φ is the standard normal CDF, μᵢ is the fitted expected margin, and
σᵢ is the estimated margin uncertainty from the heteroskedastic model.
"""

from __future__ import annotations
import numpy as np
from scipy.stats import norm
from ..types import RaceRecord, ModelOutputs, SigmaModel
from ..model.margin import MarginModelCoefficients, predict


def compute_outputs(
    race: RaceRecord,
    coef: MarginModelCoefficients,
    sigma_model: SigmaModel,
    beta1_override: float | None = None,
) -> ModelOutputs:
    """
    Compute all model quantities for a single race.

    Parameters
    ----------
    beta1_override : used during β_RC uncertainty propagation draws
    """
    d_total = race.d_total
    r_total = race.r_total
    total = d_total + r_total

    if total <= 0:
        ratio = 0.5
    else:
        ratio = d_total / total

    ratio = np.clip(ratio, 1e-6, 1 - 1e-6)

    mu = predict(
        pvi=race.pvi,
        incumb_status=race.incumb_status,
        generic_ballot=race.generic_ballot,
        ratio=ratio,
        coef=coef,
        beta1_override=beta1_override,
        total_spend=total,
        cvap=race.cvap,
        indiv_share=race.indiv_share,
    )

    sigma = sigma_model.predict(abs(race.pvi), race.incumb_status, race.generic_ballot)
    p_win = float(norm.cdf(mu / sigma))

    msg = _marginal_seat_gain(
        mu=mu,
        sigma=sigma,
        pvi=race.pvi,
        incumb_status=race.incumb_status,
        d_total=d_total,
        r_total=r_total,
        coef=coef,
        beta1_override=beta1_override,
    )

    return ModelOutputs(
        district_id=race.district_id,
        ratio=ratio,
        mu_hat=mu,
        sigma_i=sigma,
        p_win=p_win,
        msg_i=msg,
    )


def _marginal_seat_gain(
    mu: float,
    sigma: float,
    pvi: float,
    incumb_status: str,
    d_total: float,
    r_total: float,
    coef: MarginModelCoefficients,
    beta1_override: float | None = None,
) -> float:
    """
    MSG_i = φ(μᵢ/σᵢ) · (1/σᵢ) · (∂μᵢ/∂Dᵢ)

    ∂μᵢ/∂Dᵢ = [β₁ + β₂·|PVI_i| + β₃·incumb_i] · Rᵢ/(Dᵢ·(Dᵢ+Rᵢ))
              + α₄ · 1/(Dᵢ+Rᵢ)

    The α₄ term captures how adding a dollar increases total spending
    intensity log((D+R)/CVAP). Its contribution to MSG is small relative
    to the log-ratio term but ensures the gradient is exact.

    D and R must be passed separately (not just D+R): the log-ratio
    gradient is R/(D·(D+R)), not 1/(D+R) — these coincide only at D=R
    (spending parity) and diverge for any lopsided spending ratio.

    b1 mirrors predict()'s open-seat substitution: β₁ is replaced by
    coef.beta1_open for Open races when set, so MSG differentiates the
    same effective β that predict() used to produce mu.

    Returns MSG per dollar. Multiply by 1e6 externally for per-$1M.
    """
    total_spend = d_total + r_total
    if total_spend <= 0 or d_total <= 0:
        return 0.0

    if beta1_override is not None:
        b1 = beta1_override
    elif coef.beta1_open is not None and incumb_status == "Open":
        b1 = coef.beta1_open
    else:
        b1 = coef.beta1
    is_incumb = 1.0 if incumb_status == "Incumbent" else 0.0
    abs_pvi = abs(pvi)

    d_log_ratio_dd = r_total / (d_total * total_spend)
    d_mu_d_s = (b1 + coef.beta2 * abs_pvi + coef.beta3 * is_incumb) * d_log_ratio_dd
    # α₄ gradient: ∂log((D+R)/CVAP)/∂D = 1/(D+R)
    d_mu_d_s += coef.alpha4 / total_spend

    phi = float(norm.pdf(mu / sigma))
    return phi * (1.0 / sigma) * d_mu_d_s


def compute_outputs_batch(
    races: list[RaceRecord],
    coef: MarginModelCoefficients,
    sigma_model: SigmaModel,
    beta1_override: float | None = None,
) -> list[ModelOutputs]:
    """Apply compute_outputs to every race in the list."""
    return [compute_outputs(r, coef, sigma_model, beta1_override) for r in races]
