"""
FEC disbursement and expenditure loader.

Raw data contract (files produced by scripts/fetch_data.py)
───────────────────────────────────────────────────────────
  candidate_disbursements_{cycle}.csv
    Columns: district_id, fec_candidate_id, candidate_name, party, cycle,
             candidate_disbursements
    One row per candidate. Multiple candidates per party per district are
    possible (primary losers); load_candidate_disbursements selects the
    top spender per party per district as the general-election nominee proxy.

  coordinated_expenditures_{cycle}.csv
    Columns: district_id, party, cycle, coordinated_expenditures
    One row per (district, party) — pre-aggregated by fetch_data.py.

  independent_expenditures_{cycle}.csv
    Columns: district_id, party, cycle, support_oppose, amount
    One row per IE transaction. support_oppose ∈ {"S", "O"}.
"""

from __future__ import annotations
import logging
import pandas as pd
from .. import config

logger = logging.getLogger(__name__)


def _ballot_last_names(cycle: int) -> set[tuple[str, str, str]]:
    """
    Return the set of (district_id, party_initial, last_name) tuples for
    candidates who actually appeared on the general-election ballot, sourced
    from the MIT MEDSL elections file.

    Used to filter out weball entries for members who ran for a different
    federal office (e.g., Senate) while their House committee was still active.
    MIT name format is "FIRSTNAME LASTNAME"; FEC format is "LASTNAME, FIRSTNAME".
    We match on upper-cased last name token only.
    """
    mit_path = config.raw_path("mit") / "1976-2024-house.tab"
    if not mit_path.exists():
        return set()
    raw = pd.read_csv(mit_path, sep=",", dtype={"district": str}, low_memory=False)
    gen = raw[
        (raw["year"] == cycle)
        & (raw["stage"].str.upper() == "GEN")
        & (~raw["candidate"].isna())
    ]
    result: set[tuple[str, str, str]] = set()
    for _, row in gen.iterrows():
        dist = str(row["state_po"]) + "-" + str(row["district"]).zfill(2)
        party = str(row["party"]).upper()
        party_initial = "D" if "DEMOCRAT" in party else ("R" if "REPUBLICAN" in party else "X")
        # MIT name: "FIRSTNAME LASTNAME" or "FIRSTNAME MIDDLE LASTNAME"
        name_parts = str(row["candidate"]).upper().split()
        last = name_parts[-1] if name_parts else ""
        result.add((dist, party_initial, last))
    return result


def load_candidate_disbursements(cycle: int) -> pd.DataFrame:
    """
    Return total principal-committee disbursements per district per party.

    Selects the top-spending candidate per party per district as the
    general-election nominee proxy.  Candidates are filtered against the MIT
    MEDSL ballot list so that House members who ran for a different federal
    office in the same cycle (e.g., Gallego/AZ-03, Schiff/CA-30 running for
    Senate in 2024) are excluded — their committee disbursements would otherwise
    inflate the district's apparent candidate spending by $40–60M.

    Returns DataFrame with columns:
        district_id, party, cycle, candidate_disbursements (float)
    """
    path = config.raw_path("fec") / f"candidate_disbursements_{cycle}.csv"
    df = pd.read_csv(path, dtype={"district_id": str, "party": str})
    df["cycle"] = cycle
    df["candidate_disbursements"] = pd.to_numeric(
        df["candidate_disbursements"], errors="coerce"
    ).fillna(0)

    df = df[df["party"].isin(["D", "R"])].copy()

    # Cross-reference against actual ballot candidates from MIT elections data.
    # Only exclude HIGH-SPENDING candidates (>$10M) who do NOT appear on the
    # House general-election ballot.  This targets the specific artifact where a
    # House member running for Senate (e.g., Gallego/AZ-03 $59M, Schiff/CA-30 $45M)
    # has their committee spending attributed to their old House district.
    # Low-spending candidates (<$10M) pass through regardless of name matching,
    # because name-format mismatches (JR/SR suffixes, compound names) cause false
    # exclusions and drop legitimate R candidates from safe-D districts.
    _LARGE_SPEND_THRESHOLD = 10_000_000
    ballot = _ballot_last_names(cycle)
    if ballot:
        def _on_ballot(row: pd.Series) -> bool:
            if row["candidate_disbursements"] < _LARGE_SPEND_THRESHOLD:
                return True
            last = str(row["candidate_name"]).split(",")[0].strip().upper()
            return (row["district_id"], row["party"], last) in ballot

        before = len(df)
        df = df[df.apply(_on_ballot, axis=1)]
        excluded = before - len(df)
        if excluded:
            logger.info(
                f"Candidate disbursements {cycle}: excluded {excluded} large-spending "
                "candidates not on the House ballot (likely ran for Senate/President)"
            )

    top = (
        df.sort_values("candidate_disbursements", ascending=False)
        .groupby(["district_id", "party"], sort=False)
        .first()
        .reset_index()
    )
    return top[["district_id", "party", "cycle", "candidate_disbursements"]]


def load_coordinated_expenditures(cycle: int) -> pd.DataFrame:
    """
    Return DCCC / NRCC coordinated expenditures per race.

    Returns DataFrame with columns:
        district_id, party, cycle, coordinated_expenditures (float)
    """
    path = config.raw_path("fec") / f"coordinated_expenditures_{cycle}.csv"
    df = pd.read_csv(path, dtype={"district_id": str, "party": str})
    df["cycle"] = cycle
    df["coordinated_expenditures"] = pd.to_numeric(
        df["coordinated_expenditures"], errors="coerce"
    ).fillna(0)
    return df[["district_id", "party", "cycle", "coordinated_expenditures"]]


def load_independent_expenditures(cycle: int) -> pd.DataFrame:
    """
    Return net DCCC / NRCC independent expenditures per race.

    Net support = (support transactions) − (opposition transactions from
    the same party committee). A party that spends against the opponent
    is credited on the same sign as spending for its own candidate.

    Returns DataFrame with columns:
        district_id, party, cycle, ie_net (float)
    """
    path = config.raw_path("fec") / f"independent_expenditures_{cycle}.csv"
    df = pd.read_csv(path, dtype={"district_id": str, "support_oppose": str, "party": str})
    df["cycle"] = cycle
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    # Both "Support" own candidate and "Oppose" opponent count as positive
    # spending for the party committee. O:-1 would subtract opposition ads,
    # giving negative totals in heavy-opposition districts like AZ-01.
    df["signed_amount"] = df["amount"].abs()

    ie = (
        df.groupby(["district_id", "party", "cycle"])["signed_amount"]
        .sum()
        .reset_index()
        .rename(columns={"signed_amount": "ie_net"})
    )
    return ie


def build_total_spend(cycle: int) -> pd.DataFrame:
    """
    Construct D_total and R_total per race for a given cycle.

    D_total_i = candidate_D_i + DCCC_coordinated_i + DCCC_IE_i
    R_total_i = candidate_R_i + NRCC_coordinated_i + NRCC_IE_i

    Returns DataFrame with columns:
        district_id, cycle, d_total, r_total
    """
    cand = load_candidate_disbursements(cycle)
    coord = load_coordinated_expenditures(cycle)
    ie = load_independent_expenditures(cycle)

    def _party_total(party: str) -> pd.Series:
        c = (
            cand[cand["party"] == party]
            .set_index("district_id")["candidate_disbursements"]
        )
        co = (
            coord[coord["party"] == party]
            .set_index("district_id")["coordinated_expenditures"]
        )
        i = (
            ie[ie["party"] == party]
            .set_index("district_id")["ie_net"]
        )
        return c.add(co, fill_value=0).add(i, fill_value=0).fillna(0)

    d = _party_total("D").rename("d_total")
    r = _party_total("R").rename("r_total")
    combined = pd.concat([d, r], axis=1).fillna(0).reset_index()
    combined["cycle"] = cycle
    return combined[["district_id", "cycle", "d_total", "r_total"]]
