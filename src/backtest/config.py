"""Load and expose the central configuration."""

from __future__ import annotations
import os
from pathlib import Path
import yaml

_ROOT = Path(__file__).parent.parent.parent  # repo root


def _load() -> dict:
    cfg_path = _ROOT / "config.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


_cfg = _load()


# ─── Convenience accessors ────────────────────────────────────────────────────

def raw_path(source: str) -> Path:
    return _ROOT / _cfg["paths"]["raw"][source]


def processed_path() -> Path:
    return _ROOT / _cfg["paths"]["processed"]


def outputs_path() -> Path:
    return (_ROOT / _cfg["paths"]["outputs"]).resolve()


def universe_cfg() -> dict:
    return _cfg["universe"]


def panel_cycles() -> list[int]:
    return _cfg["panel"]["cycles"]


def min_repeat_pairs() -> int:
    return _cfg["panel"]["min_repeat_challenger_pairs"]


def generic_ballot_2024() -> float:
    gb = _cfg["generic_ballot_2024"]
    if gb is None:
        raise ValueError("generic_ballot_2024 not set in config.yaml")
    return float(gb)


def beta_rc_prior() -> dict:
    return _cfg.get("beta_rc", {})


def uncertainty_cfg() -> dict:
    return _cfg["uncertainty"]


def optimizer_cfg() -> dict:
    return _cfg["optimizer"]


def validation_cfg() -> dict:
    return _cfg["validation"]


def cook_win_probs() -> dict[str, float]:
    return _cfg["cook_win_probs"]


def outputs_cfg() -> dict:
    return _cfg["outputs"]


def competitive_ratings() -> list[str]:
    return _cfg["universe"]["competitive_ratings"]


def reload() -> None:
    """Re-read config.yaml from disk (useful after run_estimation writes beta_rc)."""
    global _cfg
    _cfg = _load()
