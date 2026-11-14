"""Load config.toml."""
from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: str | Path | None = None) -> dict:
    with open(Path(path) if path else ROOT / "config.toml", "rb") as f:
        cfg = tomllib.load(f)
    cfg["_root"] = str(ROOT)
    return cfg


def pair_symbols(cfg: dict) -> dict[str, str]:
    return {p: v[0] for p, v in cfg["pairs"].items()}


def pair_cost(cfg: dict, pair: str) -> float:
    """Cost per side as a fraction of traded notional: half the spread + slippage."""
    spread_bps = cfg["pairs"][pair][1]
    return (spread_bps / 2 + cfg["costs"]["slippage_bps"]) / 1e4
