"""
Persuasion ceiling: regularizes the margin model's spending response against
inferring an unbounded vote-share shift from a district's current candidate
floor.

Why this exists
----------------
The margin model's log-ratio spending term has an unbounded gradient as
D -> 0 (see model/margin.py's docstring). Before the 2026-07-23b sigma-model
fix, an understated sigma kept every near-zero-floor race's win probability
near 0 regardless of spending, which happened to suppress this blowup by
accident. Once sigma was corrected, the optimizer began recommending large
sums into Safe-tier races with near-zero historical floors -- extrapolating
the spending response far outside the region the historical panel actually
supports. See FINDINGS.md's persuasion-ceiling section for the full
diagnosis, including the empirical evidence that a naive repeat-challenger
swing calibration is itself contaminated by candidate-quality composition
effects (a real repeat challenger becoming a token candidate between
cycles), and the C_max robustness sweep behind the chosen default.

The fix
-------
C_i = c_max * 4*Phi0*(1-Phi0), where Phi0 = Phi(mu_floor/sigma_i) is the
race's win probability at its own candidate-only floor (no party money
added). This is a parabola peaking at C_i = c_max for a true toss-up
(Phi0=0.5) and shrinking to ~0 at either extreme. The interpretation is a
regularization prior, not a behavioral claim: the model should not infer a
systematic spending effect larger than a multiple of the race's own already-
estimated uncertainty, scaled by how close to a toss-up its current state
suggests it is. sigma alone was tested and found insufficient as the sole
scale (its own PVI dependence is far weaker than mu's -- see FINDINGS.md);
Phi0 (driven mostly by mu) is what actually discriminates hopeless races
from competitive ones.

mu'(D) = mu_floor + C_i * (1 - exp(-max(mu_raw(D) - mu_floor, 0) / C_i))

d(mu')/d(mu_raw) = exp(-delta/C_i) is the chain-rule factor used to correct
the analytic MSG gradient without re-deriving the underlying structural
derivative.
"""

from __future__ import annotations
import numpy as np
from scipy.stats import norm

EPS_C = 1e-6  # floor on C_i to avoid division by zero as Phi0 -> {0, 1}


def persuadability(mu_floor, sigma_i):
    """4*Phi0*(1-Phi0): 1.0 at a true toss-up (Phi0=0.5), 0.0 at either extreme."""
    phi0 = norm.cdf(mu_floor / sigma_i)
    return 4.0 * phi0 * (1.0 - phi0)


def ceiling(mu_floor, sigma_i, c_max):
    """C_i = c_max * persuadability(mu_floor, sigma_i), floored at EPS_C."""
    return np.maximum(c_max * persuadability(mu_floor, sigma_i), EPS_C)


def apply(mu_raw, mu_floor, sigma_i, c_max):
    """Cap the achievable shift from mu_floor to mu_raw at C_i.

    Returns (mu_capped, gradient_factor), where gradient_factor =
    d(mu_capped)/d(mu_raw) is the multiplier MSG must be scaled by (chain
    rule) to stay consistent with mu_capped rather than mu_raw.
    """
    C = ceiling(mu_floor, sigma_i, c_max)
    delta = np.maximum(mu_raw - mu_floor, 0.0)
    decay = np.exp(-delta / C)
    mu_capped = mu_floor + C * (1.0 - decay)
    return mu_capped, decay
