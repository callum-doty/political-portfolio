"""
Construct and filter the 2024 backtest race universe.

Applies inclusion/exclusion criteria from Section 2 of the spec and returns
a list of RaceRecord objects ready for the model.
"""

from __future__ import annotations
import logging
import pandas as pd
from ..types import RaceRecord
from .. import config
from . import fec, elections, cook, census, incumbency

logger = logging.getLogger(__name__)


def build_universe() -> list[RaceRecord]:
    """
    Assemble the 2024 race universe and apply all inclusion/exclusion filters.

    Returns a list of RaceRecord objects, one per included district.
    Logs each exclusion decision and redistricting flags.
    """
    ucfg = config.universe_cfg()
    gb = config.generic_ballot_2024()

    # ── Load all 2024 data ────────────────────────────────────────────────────
    spend = fec.build_total_spend(2024)
    results = elections.load_results(2024)
    pvi = cook.load_pvi(2024)
    ratings = cook.load_ratings_2024()
    cvap = census.load_cvap()
    incumb = incumbency.load_incumbency(2024)

    # ── Merge ─────────────────────────────────────────────────────────────────
    df = (
        spend
        .merge(results[["district_id", "winner"]], on="district_id", how="left")
        .merge(pvi, on="district_id", how="left")
        .merge(ratings, on="district_id", how="left")
        .merge(cvap, on="district_id", how="left")
        .merge(incumb[["district_id", "incumb_status"]], on="district_id", how="left")
    )

    df["state"] = df["district_id"].str.split("-").str[0]
    df["district"] = df["district_id"].str.split("-").str[1].astype(int, errors="ignore")

    n_start = len(df)
    logger.info(f"Starting universe: {n_start} districts")

    # ── Exclusion 1: uncontested / no spend ───────────────────────────────────
    min_spend = ucfg["min_total_spend"]
    mask_spend = (df["d_total"] > min_spend) | (df["r_total"] > min_spend)
    df = df[mask_spend]
    logger.info(f"After spend filter (>{min_spend:,}): {len(df)} races")

    # ── Exclusion 2: states excluded by rule ─────────────────────────────────
    exclude_states = ucfg.get("exclude_states", [])
    if exclude_states:
        df = df[~df["state"].isin(exclude_states)]
        logger.info(f"After state exclusions {exclude_states}: {len(df)} races")

    # ── Exclusion 3: missing PVI (at-large without assignment) ───────────────
    missing_pvi = df["pvi"].isna()
    if missing_pvi.any():
        logger.warning(f"Dropping {missing_pvi.sum()} races with no PVI: "
                       f"{df.loc[missing_pvi, 'district_id'].tolist()}")
    df = df[~missing_pvi]

    # ── Exclusion 4: missing incumbency ──────────────────────────────────────
    missing_incumb = df["incumb_status"].isna()
    if missing_incumb.any():
        logger.warning(f"Dropping {missing_incumb.sum()} races with no incumbency data")
    df = df[~missing_incumb]

    # ── Flag redistricting edge cases (do not exclude) ────────────────────────
    flagged = set(ucfg.get("redistricting_flag_districts", []))
    df["redistricting_flagged"] = df["district_id"].isin(flagged)
    if flagged:
        logger.info(f"Redistricting-flagged districts ({len(flagged)}): {sorted(flagged)}")

    logger.info(f"Final universe: {len(df)} races")

    # ── Build RaceRecord list ─────────────────────────────────────────────────
    records = []
    for _, row in df.iterrows():
        records.append(RaceRecord(
            district_id=row["district_id"],
            state=row["state"],
            district=int(row["district"]) if pd.notna(row.get("district")) else 0,
            cook_rating=str(row.get("cook_rating", "")),
            incumb_status=str(row["incumb_status"]),
            pvi=float(row["pvi"]),
            d_total=float(row["d_total"]),
            r_total=float(row["r_total"]),
            cvap=int(row["cvap"]) if pd.notna(row.get("cvap")) else 0,
            generic_ballot=gb,
            redistricting_flagged=bool(row["redistricting_flagged"]),
            outcome=row.get("winner"),
        ))

    return records


def competitive_subset(races: list[RaceRecord]) -> list[RaceRecord]:
    """Return only the competitive races (Cook Toss-Up, Lean D, Lean R)."""
    competitive = set(config.competitive_ratings())
    return [r for r in races if r.cook_rating in competitive]
