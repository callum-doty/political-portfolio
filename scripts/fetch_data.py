#!/usr/bin/env python3
"""
Fetch all raw data required by the backtest pipeline.

FEC data strategy (two tiers)
──────────────────────────────
TIER 1 — Bulk downloads (no API key, no rate limit):
  Candidate committee totals:
    https://www.fec.gov/files/bulk-downloads/{year}/weball{yy}.zip
    Pipe-delimited, ~170 KB per cycle — downloads in <1 second.

TIER 2 — FEC API (requires registered key for multi-cycle runs):
  DCCC/NRCC independent expenditures:
    /schedules/schedule_e/?committee_id=C00000935   (DCCC)
    /schedules/schedule_e/?committee_id=C00075960   (NRCC)
    ~1,000–3,000 rows per committee per cycle (~10–30 pages each).
  DCCC/NRCC coordinated party expenditures:
    /schedules/schedule_f/?committee_id=...
    Fewer records than IEs.

  *** DEMO_KEY has 30 req/hr — it exhausts after ~3 pages of IE data. ***
  *** Use --skip-party-spend to run on candidate committee data only,  ***
  *** or register a free key: https://api.open.fec.gov/developers      ***

  Registered key: 1,000 req/hr — handles all cycles without throttling.

Usage
─────
    # Candidate committee totals + Census CVAP (no API key needed):
    python scripts/fetch_data.py --skip-party-spend

    # Full run with registered FEC API key (party IEs + coordinated):
    python scripts/fetch_data.py --fec-api-key YOUR_KEY

    python scripts/fetch_data.py --only fec --cycles 2024
    python scripts/fetch_data.py --only census
    python scripts/fetch_data.py --only incumbency --cycles 2024

Manual data required (not available via API)
────────────────────────────────────────────
  MIT MEDSL House results:
    https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/IG0UN2
    → data/raw/mit_elections/house_results_2012_2024.csv

  Cook PVI + ratings (proprietary):
    → data/raw/cook_pvi/cook_pvi_{cycle}.csv  (columns: district_id, pvi_raw)
    → data/raw/cook_pvi/cook_ratings_2024.csv (columns: district_id, rating)
"""

from __future__ import annotations
import argparse
import io
import logging
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backtest import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("fetch_data")

FEC_API_BASE = "https://api.open.fec.gov/v1"
FEC_BULK_BASE = "https://www.fec.gov/files/bulk-downloads"

DCCC_COMMITTEE_ID = "C00000935"
NRCC_COMMITTEE_ID = "C00075473"


FIPS_TO_STATE = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
    "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI",
    "56": "WY",
}


# ─── Bulk download helpers ────────────────────────────────────────────────────

def _download_zip(url: str, member_name: str) -> bytes:
    """Download a ZIP from FEC and return the bytes of a named member."""
    import requests
    logger.info(f"Downloading {url}…")
    resp = requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()
    content = b"".join(resp.iter_content(chunk_size=1 << 20))
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        names = zf.namelist()
        # The zip may contain just one file, or a file with the same stem
        match = next((n for n in names if member_name.lower() in n.lower()), names[0])
        logger.info(f"  Extracting {match} ({len(content) // 1024:,} KB zip)")
        return zf.read(match)


def _cycle_to_yy(cycle: int) -> str:
    return str(cycle)[-2:]


# ─── Tier 1: Bulk candidate committee totals ──────────────────────────────────

def _parse_weball_bytes(wb_bytes: bytes) -> "pd.DataFrame":
    """
    Parse raw weball pipe-delimited bytes into a DataFrame of House candidates.

    weball column layout (0-indexed, verified against FEC bulk spec):
      col  0: CAND_ID              H… = House, S… = Senate, P… = President
      col  1: CAND_NAME
      col  2: CAND_ICI             I=Incumbent, C=Challenger, O=Open
      col  3: PTY_CD               numeric party code
      col  4: CAND_PTY_AFFILIATION DEM, REP, …
      col  5: TTL_RECEIPTS         total receipts
      col  7: TTL_DISB             ← total disbursements (spend)
      col  9: COH_BOP              cash on hand beginning of period
      col 10: COH_COP              cash on hand close of period
      col 17: TTL_INDIV_CONTRIB    total individual contributions received
      col 18: CAND_OFFICE_ST       state abbreviation
      col 19: CAND_OFFICE_DISTRICT two-digit district number
    """
    import pandas as pd
    import io as _io
    df = pd.read_csv(
        _io.BytesIO(wb_bytes), sep="|", header=None,
        names=list(range(31)), dtype=str, on_bad_lines="skip",
    )
    return df[df[0].str.startswith("H", na=False)].copy()


def _weball_to_disbursements(house: "pd.DataFrame", cycle: int) -> "pd.DataFrame":
    """Convert parsed weball House rows to the candidate_disbursements schema."""
    import pandas as pd
    ici_map = {"I": "Incumbent", "C": "Challenger", "O": "Open seat"}
    # Map FEC party affiliations to D/R.
    # DFL = Democratic-Farmer-Labor (Minnesota's Democratic party).
    # WFP = Working Families Party (NY/CT/etc., nominates Democratic candidates).
    party_map = {
        "DEM": "D", "DFL": "D", "WFP": "D",   # Democratic-aligned
        "REP": "R", "CON": "R",                 # Republican-aligned (CON = NY Conservative)
    }

    raw_party = house[4].str.strip()
    mapped_party = raw_party.map(party_map)
    # Any unmapped code stays as-is (e.g., IND, LIB, GRE) — filtered out later
    mapped_party = mapped_party.fillna(raw_party)

    ttl_receipts = pd.to_numeric(house[5], errors="coerce").fillna(0)
    ttl_indiv = pd.to_numeric(house[17], errors="coerce").fillna(0)

    out = pd.DataFrame({
        "fec_candidate_id":        house[0].str.strip(),
        "candidate_name":          house[1].str.strip(),
        "incumbent_challenge_full": house[2].str.strip().map(ici_map).fillna("Open seat"),
        "party":                   mapped_party,
        "state":                   house[18].str.strip(),
        "district_num":            house[19].str.strip().str.zfill(2),
        "candidate_disbursements": pd.to_numeric(house[7], errors="coerce").fillna(0),
        "ttl_receipts":            ttl_receipts,
        "ttl_indiv_contrib":       ttl_indiv,
        "cycle":                   cycle,
    })
    out["district_id"] = out["state"] + "-" + out["district_num"]
    # indiv_share: fraction of receipts from individual donors (0–1)
    out["indiv_share"] = (
        (ttl_indiv / ttl_receipts.replace(0, float("nan")))
        .clip(0.0, 1.0)
        .fillna(0.0)
    )
    return out.drop(columns=["state", "district_num"])


def fetch_candidate_totals_local(cycle: int, force: bool = False) -> bool:
    """
    Build candidate_disbursements_{cycle}.csv from a locally cached weball file.

    Reads from data/raw/bulk_all/weball{yy}.txt or
    data/raw/house_senate_current_campaigns/webl{yy}.txt, whichever exists.
    Returns True if the output was written, False if skipped.
    """
    import pandas as pd

    out_path = config.raw_path("fec") / f"candidate_disbursements_{cycle}.csv"
    if out_path.exists() and not force:
        logger.info(f"Candidate totals {cycle}: already present, skipping")
        return False

    yy = _cycle_to_yy(cycle)
    local_paths = [
        config.raw_path("bulk_all") if hasattr(config, "raw_path") else None,
        Path(__file__).parent.parent / "data" / "raw" / "bulk_all" / f"weball{yy}.txt",
        Path(__file__).parent.parent / "data" / "raw" / "house_senate_current_campaigns" / f"webl{yy}.txt",
    ]
    # Resolve: use the first existing local file
    local_file = None
    for p in local_paths[1:]:
        if p and p.exists():
            local_file = p
            break

    if local_file is None:
        logger.info(f"No local bulk file for {cycle}; will download")
        return False

    logger.info(f"Reading candidate totals for {cycle} from local file: {local_file.name}")
    with open(local_file, "rb") as f:
        wb_bytes = f.read()

    house = _parse_weball_bytes(wb_bytes)
    logger.info(f"  {len(house)} House candidate rows in {local_file.name}")
    out = _weball_to_disbursements(house, cycle)

    out[[
        "district_id", "fec_candidate_id", "candidate_name", "party",
        "cycle", "candidate_disbursements", "incumbent_challenge_full",
        "ttl_receipts", "ttl_indiv_contrib", "indiv_share",
    ]].to_csv(out_path, index=False)
    logger.info(f"Saved {len(out)} House candidates → {out_path}")
    return True


def fetch_candidate_totals_bulk(cycle: int, force: bool = False) -> None:
    """
    Download and parse FEC bulk weball file to produce
    candidate_disbursements_{cycle}.csv with no API key required.

    Prefers local weball file (data/raw/bulk_all/ or
    data/raw/house_senate_current_campaigns/) over download when available.

    Output schema:
        district_id, fec_candidate_id, candidate_name, party, cycle,
        candidate_disbursements, incumbent_challenge_full,
        ttl_receipts, ttl_indiv_contrib, indiv_share
    """
    import pandas as pd

    out_path = config.raw_path("fec") / f"candidate_disbursements_{cycle}.csv"
    if out_path.exists() and not force:
        logger.info(f"Candidate totals {cycle}: already present, skipping")
        return

    # Prefer local file over download
    if fetch_candidate_totals_local(cycle, force=force):
        return

    yy = _cycle_to_yy(cycle)
    wb_bytes = _download_zip(f"{FEC_BULK_BASE}/{cycle}/weball{yy}.zip", f"weball{yy}.txt")
    house = _parse_weball_bytes(wb_bytes)
    logger.info(f"  {len(house)} House candidate rows in weball{yy}")
    out = _weball_to_disbursements(house, cycle)

    out[[
        "district_id", "fec_candidate_id", "candidate_name", "party",
        "cycle", "candidate_disbursements", "incumbent_challenge_full",
        "ttl_receipts", "ttl_indiv_contrib", "indiv_share",
    ]].to_csv(out_path, index=False)
    logger.info(f"Saved {len(out)} House candidates → {out_path}")


# ─── FEC API helpers ──────────────────────────────────────────────────────────

def _fec_get(session, endpoint: str, params: dict, timeout: int = 60) -> dict:
    """Single FEC API GET with retry on rate-limit (429) and server errors."""
    url = f"{FEC_API_BASE}/{endpoint.lstrip('/')}"
    for attempt in range(5):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            if resp.status_code == 429:
                if attempt >= 2:
                    raise RuntimeError(
                        "FEC API rate limit exceeded after 3 attempts. "
                        "Options: (a) register a free key at https://api.open.fec.gov/developers "
                        "and pass --fec-api-key YOUR_KEY, "
                        "or (b) add --skip-party-spend to run on candidate committee data only."
                    )
                wait = 60
                logger.warning(f"Rate limited. Sleeping {wait}s…")
                time.sleep(wait)
                continue
            if resp.status_code >= 500:
                wait = 10 * (attempt + 1)
                logger.warning(f"Server error {resp.status_code}. Retrying in {wait}s…")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            time.sleep(1.5)  # polite pause; stays within DEMO_KEY limit for small pulls
            return resp.json()
        except RuntimeError:
            raise  # don't retry our own bailout errors (rate limit, etc.)
        except Exception as e:
            if attempt == 4:
                raise
            wait = 10 * (attempt + 1)
            logger.warning(f"Request error ({e}). Retrying in {wait}s…")
            time.sleep(wait)
    raise RuntimeError("FEC API request failed after 5 attempts")


def _fec_paginate(session, endpoint: str, params: dict) -> list[dict]:
    """Paginate through all pages of a FEC API endpoint."""
    all_results: list[dict] = []
    page = 1
    while True:
        data = _fec_get(session, endpoint, {**params, "page": page, "per_page": 100})
        results = data.get("results", [])
        all_results.extend(results)
        pagination = data.get("pagination", {})
        total_pages = pagination.get("pages", 1)
        logger.info(f"  Page {page}/{total_pages} ({len(all_results)} records)")
        if page >= total_pages:
            break
        page += 1
    return all_results


# ─── Tier 2: DCCC / NRCC IEs via API (filtered → small result set) ───────────

def fetch_ie_by_committee(cycle: int, api_key: str, committee_id: str, party: str) -> None:
    """
    Fetch independent expenditures made by DCCC or NRCC for a cycle.

    Filtered to a single committee, so ~1,000–3,000 rows (10–30 pages).
    This is manageable even with DEMO_KEY.

    Output schema: district_id, party, cycle, support_oppose, amount
    """
    import requests
    import pandas as pd

    label = "DCCC" if committee_id == DCCC_COMMITTEE_ID else "NRCC"
    out_path = config.raw_path("fec") / f"ie_{label.lower()}_{cycle}.csv"
    if out_path.exists():
        logger.info(f"IE {label} {cycle}: already present, skipping")
        return

    logger.info(f"Fetching {label} IEs for {cycle} via API…")
    with requests.Session() as session:
        records = _fec_paginate(session, "/schedules/schedule_e/", {
            "api_key":      api_key,
            "committee_id": committee_id,
            "cycle":        cycle,
            "sort":         "-expenditure_date",
        })

    if not records:
        logger.warning(f"No IE records for {label} {cycle}")
        pd.DataFrame(columns=["district_id", "party", "cycle", "support_oppose", "amount"]
                     ).to_csv(out_path, index=False)
        return

    df = pd.DataFrame(records)
    df["state"]       = df.get("candidate_office_state", "").fillna("")
    df["district_num"]= df.get("candidate_office_district", "00").fillna("00").astype(str).str.zfill(2)
    df["district_id"] = df["state"] + "-" + df["district_num"]
    df["support_oppose"] = df.get("support_oppose_indicator", "S").fillna("S")
    df["amount"]      = pd.to_numeric(df.get("expenditure_amount", 0), errors="coerce").fillna(0)
    df["party"]       = party
    df["cycle"]       = cycle

    df[["district_id", "party", "cycle", "support_oppose", "amount"]].to_csv(out_path, index=False)
    logger.info(f"Saved {len(df)} IE transactions → {out_path}")


def fetch_coordinated_by_committee(cycle: int, api_key: str, committee_id: str, party: str) -> None:
    """
    Fetch Schedule F coordinated party expenditures by DCCC or NRCC.
    Output schema: district_id, party, cycle, coordinated_expenditures
    """
    import requests
    import pandas as pd

    label = "DCCC" if committee_id == DCCC_COMMITTEE_ID else "NRCC"
    out_path = config.raw_path("fec") / f"coordinated_{label.lower()}_{cycle}.csv"
    if out_path.exists():
        logger.info(f"Coordinated {label} {cycle}: already present, skipping")
        return

    logger.info(f"Fetching {label} coordinated expenditures for {cycle} via API…")
    with requests.Session() as session:
        records = _fec_paginate(session, "/schedules/schedule_f/", {
            "api_key":          api_key,
            "committee_id":     committee_id,
            "cycle":            cycle,
            "candidate_office": "H",
        })

    if not records:
        logger.warning(f"No coordinated expenditure records for {label} {cycle}")
        pd.DataFrame(columns=["district_id", "party", "cycle", "coordinated_expenditures"]
                     ).to_csv(out_path, index=False)
        return

    df = pd.DataFrame(records)
    df["state"]       = df.get("candidate_office_state", "").fillna("")
    df["district_num"]= df.get("candidate_office_district", "00").fillna("00").astype(str).str.zfill(2)
    df["district_id"] = df["state"] + "-" + df["district_num"]
    df["amount"]      = pd.to_numeric(df.get("expenditure_amount", 0), errors="coerce").fillna(0)
    df["party"]       = party
    df["cycle"]       = cycle

    out = (
        df.groupby(["district_id", "party", "cycle"])["amount"]
        .sum().reset_index()
        .rename(columns={"amount": "coordinated_expenditures"})
    )
    out.to_csv(out_path, index=False)
    logger.info(f"Saved {len(out)} districts → {out_path}")


def consolidate_fec_files(cycle: int) -> None:
    """Merge per-committee IE and coordinated files into single canonical files."""
    import pandas as pd

    fec_dir = config.raw_path("fec")
    for kind, col in [("coordinated", "coordinated_expenditures"), ("ie", "amount")]:
        out = fec_dir / f"{'coordinated_expenditures' if kind == 'coordinated' else 'independent_expenditures'}_{cycle}.csv"
        if not out.exists():
            frames = [
                pd.read_csv(fec_dir / f"{kind}_{label}_{cycle}.csv")
                for label in ["dccc", "nrcc"]
                if (fec_dir / f"{kind}_{label}_{cycle}.csv").exists()
            ]
            if frames:
                pd.concat(frames, ignore_index=True).to_csv(out, index=False)
                logger.info(f"Consolidated → {out}")


# ─── Skip-mode: empty party spend placeholders ───────────────────────────────

def generate_empty_party_spend_files(cycle: int) -> None:
    """
    Write zero-row canonical party spend files so the pipeline can run with
    candidate committee data only (no API key required).

    To add real party spending later: delete these files and re-run without
    --skip-party-spend.
    """
    import pandas as pd

    fec_dir = config.raw_path("fec")

    ie_path = fec_dir / f"independent_expenditures_{cycle}.csv"
    if not ie_path.exists():
        pd.DataFrame(columns=["district_id", "party", "cycle", "support_oppose", "amount"]
                     ).to_csv(ie_path, index=False)
        logger.info(f"Empty placeholder → {ie_path.name}")

    coord_path = fec_dir / f"coordinated_expenditures_{cycle}.csv"
    if not coord_path.exists():
        pd.DataFrame(columns=["district_id", "party", "cycle", "coordinated_expenditures"]
                     ).to_csv(coord_path, index=False)
        logger.info(f"Empty placeholder → {coord_path.name}")


# ─── Incumbency (derived from candidate totals, no API needed) ────────────────

def derive_incumbency(cycle: int) -> None:
    """
    Build incumbency_{cycle}.csv from candidate_disbursements_{cycle}.csv.

    incumb_status is from the Democratic candidate's perspective:
      D candidate "Incumbent"  → "Incumbent"
      D candidate "Challenger" → "Challenger"
      "Open seat"              → "Open"

    Also captures incumbent_name / challenger_name for repeat-challenger
    pair identification in estimation/beta_rc.py.
    """
    import pandas as pd

    out_path = config.raw_path("fec") / f"incumbency_{cycle}.csv"
    if out_path.exists():
        logger.info(f"Incumbency {cycle}: already present, skipping")
        return

    cand_path = config.raw_path("fec") / f"candidate_disbursements_{cycle}.csv"
    if not cand_path.exists():
        logger.warning(f"candidate_disbursements_{cycle}.csv not found — run --only fec first")
        return

    logger.info(f"Deriving incumbency {cycle}…")
    df = pd.read_csv(cand_path, dtype={"district_id": str, "party": str})
    df = df[df["party"].isin(["D", "R"])]

    # Top spender per party × district as nominee proxy
    df = (
        df.sort_values("candidate_disbursements", ascending=False)
        .groupby(["district_id", "party"], sort=False).first().reset_index()
    )

    rows = []
    for dist_id, grp in df.groupby("district_id"):
        d_row = grp[grp["party"] == "D"]
        r_row = grp[grp["party"] == "R"]

        d_ic = str(d_row["incumbent_challenge_full"].iloc[0]) if not d_row.empty else "Open seat"

        if d_ic == "Incumbent":
            incumb_status   = "Incumbent"
            incumbent_name  = d_row["candidate_name"].iloc[0] if not d_row.empty else ""
            challenger_name = r_row["candidate_name"].iloc[0] if not r_row.empty else ""
        elif d_ic == "Challenger":
            incumb_status   = "Challenger"
            incumbent_name  = r_row["candidate_name"].iloc[0] if not r_row.empty else ""
            challenger_name = d_row["candidate_name"].iloc[0] if not d_row.empty else ""
        else:
            incumb_status   = "Open"
            incumbent_name  = ""
            challenger_name = d_row["candidate_name"].iloc[0] if not d_row.empty else ""

        rows.append({
            "district_id":    dist_id,
            "cycle":          cycle,
            "incumb_status":  incumb_status,
            "incumbent_name": incumbent_name,
            "challenger_name": challenger_name,
        })

    pd.DataFrame(rows).to_csv(out_path, index=False)
    logger.info(f"Saved {len(rows)} districts → {out_path}")


# ─── Comprehensive independent expenditures ──────────────────────────────────

def build_comprehensive_ie(cycle: int, force: bool = False) -> None:
    """
    Build independent_expenditures_{cycle}.csv from the comprehensive FEC IE file
    (data/raw/independent_expenditure/independent_expenditure_{cycle}.csv).

    This replaces the DCCC/NRCC-only IE approach with ALL outside group spending,
    which is especially important for capturing R-aligned spending (super PACs and
    other Republican-aligned groups that often outspend the NRCC in competitive races).

    Party alignment is computed from candidate party × support/oppose indicator:
      D-aligned: (candidate is D AND support) OR (candidate is R AND oppose)
      R-aligned: (candidate is R AND support) OR (candidate is D AND oppose)

    Output schema: district_id, party [D or R aligned], cycle, amount
    (same schema as the DCCC/NRCC-only file it replaces)
    """
    import pandas as pd

    out_path = config.raw_path("fec") / f"independent_expenditures_{cycle}.csv"
    if out_path.exists() and not force:
        logger.info(f"Independent expenditures {cycle}: already present, skipping")
        return

    src_dir = Path(__file__).parent.parent / "data" / "raw" / "independent_expenditure"
    src_path = src_dir / f"independent_expenditure_{cycle}.csv"
    if not src_path.exists():
        logger.warning(
            f"Comprehensive IE file not found: {src_path}. "
            "Falling back to DCCC/NRCC-only approach."
        )
        return

    logger.info(f"Building comprehensive IEs for {cycle} from {src_path.name}…")
    df = pd.read_csv(src_path, dtype=str, low_memory=False)

    # Filter to House general election races
    df = df[(df["can_office"] == "H") & (df["ele_type"] == "G")].copy()
    logger.info(f"  {len(df)} House general IE rows")

    df["exp_amo"] = pd.to_numeric(df["exp_amo"], errors="coerce").fillna(0).abs()

    # Build district_id
    df["state"] = df["can_office_state"].str.strip().str.upper()
    df["dist"]  = df["can_office_dis"].str.strip().str.zfill(2)
    df["district_id"] = df["state"] + "-" + df["dist"]

    # Determine party alignment
    is_dem_cand = df["cand_pty_aff"].str.upper().str.contains("DEMOCRAT", na=False)
    is_rep_cand = df["cand_pty_aff"].str.upper().str.contains("REPUBLICAN", na=False)
    is_support  = df["sup_opp"].str.upper() == "S"
    is_oppose   = df["sup_opp"].str.upper() == "O"

    d_aligned = (is_dem_cand & is_support) | (is_rep_cand & is_oppose)
    r_aligned = (is_rep_cand & is_support) | (is_dem_cand & is_oppose)

    d_ie = (
        df[d_aligned].groupby("district_id")["exp_amo"].sum()
        .reset_index().rename(columns={"exp_amo": "amount"})
    )
    d_ie["party"] = "D"

    r_ie = (
        df[r_aligned].groupby("district_id")["exp_amo"].sum()
        .reset_index().rename(columns={"exp_amo": "amount"})
    )
    r_ie["party"] = "R"

    out = pd.concat([d_ie, r_ie], ignore_index=True)
    out["cycle"] = cycle

    out[["district_id", "party", "cycle", "amount"]].to_csv(out_path, index=False)
    logger.info(
        f"Comprehensive IEs saved: {len(d_ie)} D-aligned districts, "
        f"{len(r_ie)} R-aligned districts → {out_path}"
    )


def rebuild_all_from_local(cycles: list[int]) -> None:
    """
    Regenerate candidate_disbursements, independent_expenditures, and incumbency CSVs
    for all cycles from local bulk files. Use this after adding new data or fixing bugs.
    """
    import os
    for cycle in cycles:
        logger.info(f"─── Rebuilding cycle {cycle} ───")
        fetch_candidate_totals_local(cycle, force=True)
        build_comprehensive_ie(cycle, force=True)
        # Force-rebuild incumbency by deleting existing file first
        inc_path = config.raw_path("fec") / f"incumbency_{cycle}.csv"
        if inc_path.exists():
            os.remove(inc_path)
        derive_incumbency(cycle)
    logger.info("Rebuild complete.")


# ─── Census CVAP ─────────────────────────────────────────────────────────────

CVAP_BULK_URL = (
    "https://www2.census.gov/programs-surveys/decennial/rdo/datasets"
    "/2022/2022-cvap/CVAP_2018-2022_ACS_csv_files.zip"
)


def fetch_census_cvap(census_api_key: str = "") -> None:
    """
    Download CVAP per congressional district from the Census CVAP Special
    Tabulation (2018–2022 ACS 5-year).  No API key required — uses the
    bulk ZIP published at www2.census.gov.

    The census_api_key argument is accepted for backward compatibility but
    is no longer used (the Census API now requires a key even for public
    tables, and the bulk file is the preferred source).

    Output schema: district_id, cvap
    """
    import requests
    import pandas as pd

    out_path = config.raw_path("census") / "cvap_2022_acs5.csv"
    if out_path.exists():
        logger.info("Census CVAP: already present, skipping")
        return

    logger.info(f"Downloading Census CVAP bulk file (~54 MB)…")
    for attempt in range(3):
        try:
            resp = requests.get(CVAP_BULK_URL, timeout=300, stream=True)
            resp.raise_for_status()
            break
        except Exception as e:
            if attempt == 2:
                raise
            logger.warning(f"Census download error: {e}. Retrying…")
            time.sleep(10)

    content = b"".join(resp.iter_content(chunk_size=1 << 20))
    logger.info(f"  Downloaded {len(content) // 1024 // 1024} MB; extracting CD.csv…")

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        cd_raw = zf.read("CD.csv")

    df = pd.read_csv(io.BytesIO(cd_raw), dtype=str)

    # Keep only the "Total" CVAP row per district (lntitle has 13 race/ethnicity rows)
    total = df[df["lntitle"] == "Total"].copy()

    # geoid format: "5001800US{STATE_FIPS:02d}{DISTRICT:02d}"
    suffix         = total["geoid"].str.split("US").str[-1]
    total["fips"]  = suffix.str[:2]
    total["dist"]  = suffix.str[2:].str.zfill(2)
    total["state"] = total["fips"].map(FIPS_TO_STATE)
    total["district_id"] = total["state"] + "-" + total["dist"]
    total["cvap"]  = pd.to_numeric(total["cvap_est"], errors="coerce")

    out = (
        total.dropna(subset=["district_id", "state", "cvap"])
        [["district_id", "cvap"]].copy()
    )
    out["cvap"] = out["cvap"].astype(int)
    out.to_csv(out_path, index=False)
    logger.info(f"Saved {len(out)} congressional districts → {out_path}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch backtest raw data")
    parser.add_argument(
        "--fec-api-key", default="DEMO_KEY",
        help="FEC API key for IE/coordinated pulls (Tier 2). "
             "DEMO_KEY has 30 req/hr and will fail on multi-cycle runs. "
             "Register free at https://api.open.fec.gov/developers (1,000 req/hr).",
    )
    parser.add_argument(
        "--skip-party-spend", action="store_true",
        help="Skip DCCC/NRCC IE and coordinated expenditure API calls; "
             "write empty placeholder files instead. The pipeline runs on "
             "candidate committee data only. Use with DEMO_KEY or when no "
             "registered API key is available. "
             "To fill in party spending later: delete the placeholder files "
             "and re-run without this flag.",
    )
    parser.add_argument(
        "--census-api-key", default="",
        help="Census API key — register free at https://api.census.gov/data/key_signup.html",
    )
    parser.add_argument(
        "--cycles", nargs="+", type=int,
        default=config.panel_cycles() + [2024],
    )
    parser.add_argument(
        "--only", choices=["fec", "incumbency", "census", "all"],
        default="all",
    )
    parser.add_argument(
        "--rebuild-local", action="store_true",
        help="Force rebuild of candidate_disbursements and independent_expenditures CSVs "
             "from locally cached bulk files (data/raw/bulk_all/ and "
             "data/raw/independent_expenditure/). Use this to apply the corrected "
             "TTL_DISB column mapping and switch to comprehensive IE data.",
    )
    args = parser.parse_args()

    # Fast path: rebuild everything from local files
    if args.rebuild_local:
        logger.info("Rebuilding all spending CSVs from local bulk files…")
        rebuild_all_from_local(args.cycles)
        return

    if args.fec_api_key == "DEMO_KEY" and not args.skip_party_spend:
        logger.warning(
            "DEMO_KEY detected. Tier 2 (DCCC/NRCC IEs + coordinated) "
            "exhausts the 30 req/hr quota after ~3 pages and will fail. "
            "Add --skip-party-spend to use candidate committee data only, "
            "or register a free key at https://api.open.fec.gov/developers "
            "and pass --fec-api-key YOUR_KEY."
        )

    if args.only in ("fec", "all"):
        for cycle in args.cycles:
            logger.info(f"─── Cycle {cycle} ───")
            fetch_candidate_totals_bulk(cycle)
            # Prefer comprehensive IEs from local file; fall back to DCCC/NRCC-only API
            build_comprehensive_ie(cycle)
            if not (config.raw_path("fec") / f"independent_expenditures_{cycle}.csv").exists():
                if args.skip_party_spend:
                    generate_empty_party_spend_files(cycle)
                else:
                    fetch_ie_by_committee(cycle, args.fec_api_key, DCCC_COMMITTEE_ID, "D")
                    fetch_ie_by_committee(cycle, args.fec_api_key, NRCC_COMMITTEE_ID, "R")
                    consolidate_fec_files(cycle)
            if args.skip_party_spend:
                coord_path = config.raw_path("fec") / f"coordinated_expenditures_{cycle}.csv"
                if not coord_path.exists():
                    generate_empty_party_spend_files(cycle)
            else:
                fetch_coordinated_by_committee(cycle, args.fec_api_key, DCCC_COMMITTEE_ID, "D")
                fetch_coordinated_by_committee(cycle, args.fec_api_key, NRCC_COMMITTEE_ID, "R")
                coord_path = config.raw_path("fec") / f"coordinated_expenditures_{cycle}.csv"
                if not coord_path.exists():
                    consolidate_fec_files(cycle)

    if args.only in ("fec", "incumbency", "all"):
        for cycle in args.cycles:
            derive_incumbency(cycle)

    if args.only in ("census", "all"):
        fetch_census_cvap(args.census_api_key)

    logger.info("\nFetch complete.")
    if getattr(args, "skip_party_spend", False):
        logger.info(
            "Party spend (IEs + coordinated) was skipped — placeholder files written. "
            "D_total / R_total will reflect candidate committee disbursements only. "
            "To add party spending: register at https://api.open.fec.gov/developers, "
            "delete the placeholder files, and re-run with --fec-api-key YOUR_KEY."
        )
    logger.info(
        "\nManual steps still required:\n"
        "\n"
        "  1. MIT MEDSL House results (Harvard Dataverse) — already done if you see this:\n"
        "       https://dataverse.harvard.edu/dataset.xhtml"
        "?persistentId=doi:10.7910/DVN/IG0UN2\n"
        "     → data/raw/mit_elections/1976-2024-house.tab\n"
        "\n"
        "  2. Presidential results by congressional district (for PVI computation):\n"
        "     Source: Daily Kos Elections — 2016 and 2020 presidential results\n"
        "     by 118th Congress districts (post-2021 redistricting maps).\n"
        "     Export their Google Sheet or download from dailykos.com/elections.\n"
        "     Format: district_id, d_votes, r_votes (one row per district).\n"
        "     → data/raw/presidential/pres_2016.csv\n"
        "     → data/raw/presidential/pres_2020.csv\n"
        "     For historical panel cycles 2012–2020, also acquire pre-2021 map\n"
        "     editions (113th–116th Congress) from Daily Kos Elections archives.\n"
        "\n"
        "  3. Cook ratings 2024 (optional — derived from PVI if not present):\n"
        "     → data/raw/cook_pvi/cook_ratings_2024.csv\n"
    )


if __name__ == "__main__":
    main()
