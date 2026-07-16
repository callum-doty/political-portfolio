#!/usr/bin/env python3
"""
Estimate the national-environment (generic ballot) volatility term
structure sigma_G(delta_t) -- Paper III Section 5.

Pools four historical cycles (2018, 2020, 2022, 2024; 538's own daily
trend estimate, recovered via the Wayback Machine -- see
docs/data_catalog.md Section 1.8b) with the live 2026 series (this
project's own 21-day trailing average of raw polls) to get a genuinely
cross-cycle realized-volatility estimate, rather than the single-path,
one-cycle exercise this project could previously only support.

Output: outputs/gb_volatility_term_structure.csv
"""

from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
HORIZONS_DAYS = [30, 60, 90, 180, 270, 365, 450]


def load_historical_series() -> dict[int, pd.Series]:
    """Return {cycle: G_t series indexed by date}, G_t = dem% - rep%."""
    df = pd.read_csv(ROOT / "data/raw/generic_ballot/generic_ballot_historical_538.csv")
    df["date"] = pd.to_datetime(df["date"])
    series = {}
    for cycle, g in df.groupby("cycle"):
        piv = g.pivot_table(index="date", columns="candidate", values="pct_estimate")
        piv = piv.sort_index()
        gt = (piv["Democrats"] - piv["Republicans"]).asfreq("D").interpolate()
        series[int(cycle)] = gt
    return series


def load_live_2026_series() -> pd.Series:
    """21-day trailing average of the raw 2026 polls (same construction as
    Paper III Section 5.3's original single-cycle exercise)."""
    df = pd.read_csv(ROOT / "data/live/generic_ballot_polls.csv")
    df["mid_date"] = pd.to_datetime(df["start_date"]) + \
        (pd.to_datetime(df["end_date"]) - pd.to_datetime(df["start_date"])) / 2
    df = df.sort_values("mid_date").reset_index(drop=True)
    daily = df.set_index("mid_date")["gb"].resample("D").mean().interpolate()
    return daily.rolling("21D").mean().dropna()


def realized_vol_by_horizon(series: pd.Series, horizons: list[int]) -> dict[int, tuple[float, int]]:
    """Return {horizon_days: (std(delta_G), n_pairs)} for one series."""
    out = {}
    for h in horizons:
        shifted = series.shift(-h)
        delta = (shifted - series).dropna()
        if len(delta) < 5:
            continue
        out[h] = (float(delta.std()), int(len(delta)))
    return out


def pooled_vol_by_horizon(all_series: dict[str, pd.Series], horizons: list[int]) -> pd.DataFrame:
    """Pool all delta_G observations across every series (cycle) at each
    horizon, then take one std -- this is the actual cross-cycle pooling,
    not just an average of each cycle's own std."""
    rows = []
    for h in horizons:
        pooled_deltas = []
        n_cycles_covering = 0
        for name, s in all_series.items():
            shifted = s.shift(-h)
            delta = (shifted - s).dropna()
            if len(delta) >= 5:
                pooled_deltas.append(delta.values)
                n_cycles_covering += 1
        if not pooled_deltas:
            continue
        pooled = np.concatenate(pooled_deltas)
        rows.append({
            "horizon_days": h,
            "horizon_months": round(h / 30.44, 1),
            "n_cycles_covering": n_cycles_covering,
            "n_pooled_obs": len(pooled),
            "pooled_std_dG": float(np.std(pooled, ddof=1)),
            "pooled_std_over_sqrt_days": float(np.std(pooled, ddof=1) / np.sqrt(h)),
        })
    return pd.DataFrame(rows)


def main():
    hist = load_historical_series()
    live_2026 = load_live_2026_series()

    all_series = {f"{c}_538": s for c, s in hist.items()}
    all_series["2026_live"] = live_2026

    print("=== Per-series length ===")
    for name, s in all_series.items():
        print(f"  {name}: {len(s)} days, {s.index.min().date()} -> {s.index.max().date()}")

    print("\n=== Per-cycle realized volatility (not pooled) ===")
    per_cycle_rows = []
    for name, s in all_series.items():
        vol = realized_vol_by_horizon(s, HORIZONS_DAYS)
        for h, (sd, n) in vol.items():
            per_cycle_rows.append({"series": name, "horizon_days": h, "std_dG": sd, "n_pairs": n})
    per_cycle_df = pd.DataFrame(per_cycle_rows)
    print(per_cycle_df.pivot(index="horizon_days", columns="series", values="std_dG").to_string())

    print("\n=== Pooled across all 5 series (4 historical cycles + 2026 live) ===")
    pooled = pooled_vol_by_horizon(all_series, HORIZONS_DAYS)
    print(pooled.to_string(index=False))

    print("\n=== Pooled across the 4 HISTORICAL cycles only (excludes 2026, methodologically cleaner) ===")
    hist_only = {f"{c}_538": s for c, s in hist.items()}
    pooled_hist = pooled_vol_by_horizon(hist_only, HORIZONS_DAYS)
    print(pooled_hist.to_string(index=False))

    out_dir = ROOT / "outputs"
    per_cycle_df.to_csv(out_dir / "gb_volatility_by_cycle.csv", index=False)
    pooled.to_csv(out_dir / "gb_volatility_term_structure.csv", index=False)
    pooled_hist.to_csv(out_dir / "gb_volatility_term_structure_historical_only.csv", index=False)
    print(f"\nSaved -> {out_dir / 'gb_volatility_term_structure.csv'}")
    print(f"Saved -> {out_dir / 'gb_volatility_term_structure_historical_only.csv'}")


if __name__ == "__main__":
    main()
