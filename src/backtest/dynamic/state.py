"""
Time-indexed campaign state X_t (paper §3.1, docs/paper2_draft.md).

RaceState/CampaignState are Paper II concepts with no Paper I equivalent.
The only dependency direction is dynamic/ -> types.py (read-only); nothing
in types.py is modified.
"""

from __future__ import annotations
import dataclasses
from dataclasses import dataclass
from datetime import date

from ..types import RaceRecord


@dataclass
class RaceState:
    """Per-race, per-period slice of the campaign state X_t.

    `base` carries every field that doesn't vary by period in this
    implementation (state, district, pvi, cvap, incumb_status, indiv_share,
    redistricting_flagged) — it is the static RaceRecord template this
    race's period-t snapshot is derived from. `mu_hat`/`sigma_hat` are the
    *smoothed* (post state-update-operator) estimates; `mu_raw`/`sigma_raw`
    are the pre-smoothing re-estimates from this period's spend snapshot,
    retained for diagnostics (paper §3.3). `committed_t` is this race's
    share of locked capital L_t (paper §3.2) — kept separate from
    `cand_d_total_t` so the two floor components (candidate spend vs.
    committed party spend) stay distinguishable for diagnostics, even
    though both enter the optimizer's floor identically (see dynamic/ledger.py).

    cash_on_hand_d / cook_rating_t / generic_ballot_t are explicit stub
    fields (paper §3.1's state vector includes these, but no historical or
    live data source for them exists in this repo yet — see
    docs/paper2_draft.md §8 and the implementation plan's data-gap table).
    They default to None; to_race_record() falls back to `base`'s static
    values when a stub field is unset, rather than silently failing.
    """

    base: RaceRecord
    period: int
    period_date: date
    mu_hat: float
    sigma_hat: float
    mu_raw: float
    sigma_raw: float
    d_total_t: float
    r_total_t: float
    cand_d_total_t: float
    committed_t: float = 0.0
    cash_on_hand_d: float | None = None
    cook_rating_t: str | None = None
    generic_ballot_t: float | None = None

    @property
    def district_id(self) -> str:
        return self.base.district_id

    def to_race_record(self) -> RaceRecord:
        """Project this race's period-t state onto Paper I's RaceRecord
        schema, unmodified. This is the seam that lets every downstream
        call (compute_outputs_batch, optimize_nonlinear, SigmaModel.predict,
        ...) reuse Paper I's code exactly as written.

        Note: committed_t is NOT added to cand_d_total here. Committed
        capital enters the optimizer's floor via CapitalLedger.apply_to_races
        (dynamic/ledger.py), one step closer to the optimizer call, so that
        "candidate-committee floor" and "committed party capital" remain two
        clearly distinguishable inputs up to the point where they are
        mechanically combined.
        """
        return dataclasses.replace(
            self.base,
            d_total=self.d_total_t,
            r_total=self.r_total_t,
            cand_d_total=self.cand_d_total_t,
            cook_rating=self.cook_rating_t if self.cook_rating_t is not None else self.base.cook_rating,
            generic_ballot=(
                self.generic_ballot_t if self.generic_ballot_t is not None else self.base.generic_ballot
            ),
        )


@dataclass
class CampaignState:
    """X_t across all races at reporting period t (paper §3.1)."""

    period: int
    period_date: date
    races: dict[str, RaceState]   # district_id -> RaceState
    generic_ballot_national: float

    def to_race_records(self) -> list[RaceRecord]:
        """Adapter: project X_t -> list[RaceRecord] for Paper I's frozen
        pipeline. See RaceState.to_race_record() for what "projection" means
        field by field."""
        return [rs.to_race_record() for rs in self.races.values()]
