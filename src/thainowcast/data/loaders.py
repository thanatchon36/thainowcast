"""Loaders for the raw CSVs in data/raw/.

Each series lives in one CSV with columns ``period,value`` (``2024-01`` for monthly,
``2024Q1`` for quarterly). The real file name is given by the registry; if it is
absent, ``synthetic_<file>`` is loaded instead and a warning is emitted every time,
so synthetic numbers can never pass for real ones quietly.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pandas as pd

from ..config import RAW_DIR, Config, SeriesSpec
from .panel import Panel


class SyntheticDataWarning(UserWarning):
    """Raised whenever a synthetic_* file stands in for a real series."""


def read_series_csv(path: Path, freq: str) -> pd.Series:
    df = pd.read_csv(path)
    missing = {"period", "value"} - set(df.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}; expected 'period,value'")
    idx = pd.PeriodIndex(df["period"].astype(str), freq=freq)
    s = pd.Series(df["value"].astype(float).to_numpy(), index=idx).sort_index()
    if s.index.has_duplicates:
        raise ValueError(f"{path}: duplicate periods")
    return s


def load_series(spec: SeriesSpec, raw_dir: Path | str = RAW_DIR) -> tuple[pd.Series, bool]:
    """Return (series, is_synthetic)."""
    raw_dir = Path(raw_dir)
    real = raw_dir / spec.file
    synth = raw_dir / f"synthetic_{spec.file}"
    if real.exists():
        return read_series_csv(real, spec.frequency), False
    if synth.exists():
        msg = (
            f"[SYNTHETIC DATA] {spec.id}: loading {synth.name} -- this is NOT real {spec.agency} data. "
            f"To use real data put {real.name} in {raw_dir}. Fetch: {spec.fetch}"
        )
        warnings.warn(msg, SyntheticDataWarning, stacklevel=2)
        print(f"WARNING {msg}", file=sys.stderr)
        return read_series_csv(synth, spec.frequency), True
    raise FileNotFoundError(
        f"{spec.id}: expected {real} (or {synth} for pipeline tests only). How to get it: {spec.fetch}"
    )


def load_panel(cfg: Config, raw_dir: Path | str = RAW_DIR) -> Panel:
    series: dict[str, pd.Series] = {}
    synthetic: set[str] = set()
    for sid, spec in cfg.specs.items():
        s, is_syn = load_series(spec, raw_dir)
        series[sid] = s
        if is_syn:
            synthetic.add(sid)
    panel = Panel.from_series(series, cfg.specs, synthetic)
    if synthetic:
        print(
            f"\n{'=' * 78}\nSYNTHETIC DATA IN USE for {len(synthetic)}/{len(cfg.specs)} series. "
            "Every number downstream is a pipeline test, not a nowcast of Thailand.\n"
            f"{'=' * 78}\n",
            file=sys.stderr,
        )
    return panel
