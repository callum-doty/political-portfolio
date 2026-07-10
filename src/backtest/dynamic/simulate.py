"""
One-step-ahead historical simulation harness (paper §6, docs/paper2_draft.md).

**Never a closed-loop autoregressive rollout** — this is paper §6.2's
explicit methodological constraint, and the reason this module exists
separately from `dynamic/horizon.py`'s live receding-horizon loop. At each
historical reporting period, the campaign state is reconstructed from real
historical data only — never from a prior period's model recommendation —
and the single-period receding-horizon solve is compared against DCCC's
actual behavior. The model's own recommendation for period t is discarded
before moving to period t+1; nothing about it is ever fed into period
t+1's reconstructed state.

Why this matters: historical polling, fundraising, and spending data
available as of any date t+1 are themselves a function of what DCCC
*actually* spent through date t — not of what this architecture would have
recommended spending. Feeding a hypothetical model-driven spending path
back into a reconstruction of "what the world looked like next" would
optimize against a state contaminated by a counterfactual that never
happened. `_reconstruct_races_at`'s signature is the structural safeguard
against this: it takes no `PeriodResult`/`prior_results` argument, so there
is no way — even by mistake — to pass a past period's model output into a
later period's reconstructed state.
"""

from __future__ import annotations
import dataclasses
import logging
from datetime import date
from typing import Callable

import numpy as np
import pandas as pd

from ..types import RaceRecord, SigmaModel
from ..model.margin import MarginModelCoefficients
from ..data import fec
from .ledger import CapitalLedger, CommitmentSource
from .updates import StateUpdater, compute_raw_snapshot
from .horizon import PeriodResult, _solve_one_period
from .periods import ReportingPeriod
from .state import CampaignState

logger = logging.getLogger(__name__)


def _static_floor_totals(cycle: int) -> pd.DataFrame:
    """Candidate-committee + coordinated-expenditure spend per
    (district_id, party), held fixed across every period of the historical
    harness.

    This repo has no per-filing date source for either component (Phase 3
    documented gap — see docs/paper2_draft.md §6.2's data-availability
    table): `candidate_disbursements_{cycle}.csv` and
    `coordinated_expenditures_{cycle}.csv` are both cycle-cumulative FEC
    snapshots with no filing-date granularity. Only independent-expenditure
    spend (`fec.cumulative_ie_as_of`) can be genuinely date-bucketed from
    data already in this repo.

    Returns DataFrame with columns: district_id, party, cand_plus_coord.
    """
    cand = fec.load_candidate_disbursements(cycle)[
        ["district_id", "party", "candidate_disbursements"]
    ]
    coord = fec.load_coordinated_expenditures(cycle)[
        ["district_id", "party", "coordinated_expenditures"]
    ]
    merged = cand.merge(coord, on=["district_id", "party"], how="outer")
    merged["candidate_disbursements"] = merged["candidate_disbursements"].fillna(0.0)
    merged["coordinated_expenditures"] = merged["coordinated_expenditures"].fillna(0.0)
    merged["cand_plus_coord"] = (
        merged["candidate_disbursements"] + merged["coordinated_expenditures"]
    )
    return merged[["district_id", "party", "cand_plus_coord"]]


def _reconstruct_races_at(
    period_index: int,
    period_date: date,
    cycle: int,
    base_races: list[RaceRecord],
    static_totals: pd.DataFrame,
) -> list[RaceRecord]:
    """
    Reconstruct one historical period's RaceRecord snapshot from real data
    only.

    Structural no-lookahead safeguard: this function's parameters are
    exactly (period_index, period_date, cycle, base_races, static_totals).
    There is no `PeriodResult`/`prior_results` argument — a prior period's
    *model recommendation* cannot be passed into this call even by
    mistake. `d_total`/`r_total` are built entirely from DCCC's real,
    actual historical spend as of `period_date`.

    Held fixed for every period (documented Phase 3 gaps): candidate
    committee and coordinated-expenditure spend (`static_totals` — see
    `_static_floor_totals`; no per-filing date source in this repo), Cook
    rating (carried unchanged from `base_races` — no historical revision
    time series exists here), and cash on hand (no data source at all;
    stays unset downstream). The only period-varying component is
    independent-expenditure spend, from `fec.cumulative_ie_as_of`, which
    has real per-transaction dates.

    Generic ballot is held fixed too, but for a different and more
    fundamental reason than "no data source exists" — see the
    implementation plan's Phase 4A note. `coef.alpha3` (this margin
    model's generic-ballot coefficient) is estimated in
    `model.margin.estimate_from_panel()` from a design matrix with exactly
    one GB value per election cycle (`generic_ballot_by_cycle`), identical
    across every race in that cycle. Its identifying variation is
    therefore entirely *between* cycles (six cycles, six GB values), never
    *within* a cycle. Even where a genuine within-cycle historical GB time
    series is available, applying alpha3 to day-to-day movement in that
    series would be substituting an estimand the model was never fit
    against — a modeling decision, not a data-acquisition one — and this
    function does not make that substitution.
    """
    ie_asof = fec.cumulative_ie_as_of(cycle, period_date)
    ie_by_key = {(r.district_id, r.party): r.ie_net for r in ie_asof.itertuples()}
    static_by_key = {(r.district_id, r.party): r.cand_plus_coord for r in static_totals.itertuples()}

    snapshot: list[RaceRecord] = []
    for race in base_races:
        d_static = static_by_key.get((race.district_id, "D"), 0.0)
        r_static = static_by_key.get((race.district_id, "R"), 0.0)
        d_ie = ie_by_key.get((race.district_id, "D"), 0.0)
        r_ie = ie_by_key.get((race.district_id, "R"), 0.0)
        snapshot.append(dataclasses.replace(
            race, d_total=d_static + d_ie, r_total=r_static + r_ie,
        ))
    return snapshot


def one_step_ahead(
    periods: list[ReportingPeriod],
    cycle: int,
    base_races: list[RaceRecord],
    coef: MarginModelCoefficients,
    sigma_model: SigmaModel,
    commitment_source: CommitmentSource,
    state_updater: StateUpdater,
    cov_matrix_fn: Callable[[list[RaceRecord]], np.ndarray],
    gamma: float,
    cap_fraction: float,
    total_budget_fn: Callable[[int], float],
    generic_ballot_national: float,
) -> list[PeriodResult]:
    """
    Evaluate the architecture one historical reporting period at a time
    (paper §6.2) — never a closed-loop rollout.

    For each period t: reconstruct RaceRecords from real historical data
    only (`_reconstruct_races_at`, which cannot receive any prior period's
    model output by construction); re-run Paper I's pipeline on that real
    snapshot (`compute_raw_snapshot`); apply the state-update operator
    (`state_updater`) — carrying forward only the EMA's `mu_hat`/`sigma_hat`
    summary, itself computed purely from real past data, never from a past
    model *recommendation* (paper §5.3 draws this distinction explicitly);
    solve exactly one period via `horizon._solve_one_period`, the identical
    single-period logic the live receding-horizon loop uses (paper §6.1).
    Each period's `PeriodResult` is appended and the loop moves on — no
    `PeriodResult` is ever read back by a later iteration.

    Compare the returned results against DCCC's actual behavior and
    against Paper I's static recommendation using `dynamic/timing.py`
    (paper §6.3): `PeriodResult.state` already carries the real
    reconstructed `d_total_t`/`cand_d_total_t` at each period, so the
    "actual" comparison series does not need to be threaded through
    separately.
    """
    static_totals = _static_floor_totals(cycle)
    results: list[PeriodResult] = []
    prev_state: CampaignState | None = None

    for rp in periods:
        races_t = _reconstruct_races_at(rp.index, rp.period_date, cycle, base_races, static_totals)

        raw_snapshot = compute_raw_snapshot(
            races_t, coef, sigma_model, rp.index, rp.period_date, generic_ballot_national,
        )
        state_t = state_updater.update(prev_state, raw_snapshot)
        prev_state = state_t

        total_budget_t = total_budget_fn(rp.index)
        ledger_t = CapitalLedger.build(
            rp.index, total_budget_t, commitment_source, rp.period_date, races_t,
        )

        cov_matrix = cov_matrix_fn(races_t)
        optimizer_result, allocation = _solve_one_period(
            races_t, coef, sigma_model, ledger_t, cov_matrix, gamma, cap_fraction,
        )

        results.append(PeriodResult(
            period=rp.index,
            period_date=rp.period_date,
            state=state_t,
            ledger=ledger_t,
            optimizer_result=optimizer_result,
            recommended_allocation=allocation,
        ))

    return results
