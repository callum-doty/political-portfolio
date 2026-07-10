"""Tests for dynamic/state.py — RaceState/CampaignState (paper §3.1)."""

from datetime import date

from backtest.types import RaceRecord
from backtest.dynamic.state import RaceState, CampaignState


def make_base_race(district_id: str = "TX-07") -> RaceRecord:
    return RaceRecord(
        district_id=district_id, state="TX", district=7,
        cook_rating="Toss-Up", incumb_status="Challenger",
        pvi=1.0, d_total=2_000_000.0, r_total=2_500_000.0,
        cvap=400_000, generic_ballot=-1.2, cand_d_total=250_000.0,
    )


def make_race_state(base: RaceRecord, **overrides) -> RaceState:
    defaults = dict(
        base=base, period=0, period_date=date(2024, 3, 1),
        mu_hat=1.0, sigma_hat=5.0, mu_raw=1.0, sigma_raw=5.0,
        d_total_t=base.d_total, r_total_t=base.r_total,
        cand_d_total_t=base.cand_d_total,
    )
    defaults.update(overrides)
    return RaceState(**defaults)


class TestRaceState:
    def test_district_id_matches_base(self):
        base = make_base_race("NY-03")
        rs = make_race_state(base)
        assert rs.district_id == "NY-03"

    def test_to_race_record_uses_period_t_spend(self):
        base = make_base_race()
        rs = make_race_state(base, d_total_t=3_000_000.0, r_total_t=1_500_000.0,
                             cand_d_total_t=400_000.0)
        rr = rs.to_race_record()
        assert rr.d_total == 3_000_000.0
        assert rr.r_total == 1_500_000.0
        assert rr.cand_d_total == 400_000.0

    def test_to_race_record_preserves_static_fields(self):
        base = make_base_race()
        rs = make_race_state(base, d_total_t=9e6)
        rr = rs.to_race_record()
        assert rr.district_id == base.district_id
        assert rr.state == base.state
        assert rr.pvi == base.pvi
        assert rr.cvap == base.cvap
        assert rr.incumb_status == base.incumb_status

    def test_stub_fields_default_none_and_fall_back(self):
        base = make_base_race()
        rs = make_race_state(base)
        assert rs.cash_on_hand_d is None
        assert rs.cook_rating_t is None
        assert rs.generic_ballot_t is None
        rr = rs.to_race_record()
        # falls back to the static base values, not an error or None
        assert rr.cook_rating == base.cook_rating
        assert rr.generic_ballot == base.generic_ballot

    def test_explicit_stub_override_takes_precedence(self):
        base = make_base_race()
        rs = make_race_state(base, cook_rating_t="Lean D", generic_ballot_t=2.0)
        rr = rs.to_race_record()
        assert rr.cook_rating == "Lean D"
        assert rr.generic_ballot == 2.0

    def test_committed_t_not_baked_into_cand_d_total(self):
        """Committed capital enters the optimizer floor via CapitalLedger,
        not via RaceState.to_race_record() — keeps the two floor components
        distinguishable up to the point they're combined (dynamic/ledger.py)."""
        base = make_base_race()
        rs = make_race_state(base, cand_d_total_t=250_000.0, committed_t=1_000_000.0)
        rr = rs.to_race_record()
        assert rr.cand_d_total == 250_000.0


class TestCampaignState:
    def test_to_race_records_returns_all_races(self):
        bases = [make_base_race("TX-07"), make_base_race("NY-03")]
        races = {b.district_id: make_race_state(b) for b in bases}
        state = CampaignState(period=0, period_date=date(2024, 3, 1),
                              races=races, generic_ballot_national=-1.2)
        records = state.to_race_records()
        assert {r.district_id for r in records} == {"TX-07", "NY-03"}
        assert len(records) == 2
