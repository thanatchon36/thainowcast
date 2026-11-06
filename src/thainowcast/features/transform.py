"""Stationarity transforms applied to raw levels (growth rates etc.)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import SeriesSpec

_SHIFT = {"M": 12, "Q": 4}


def transform_series(s: pd.Series, how: str, freq: str = "M") -> pd.Series:
    n = _SHIFT[freq]
    s = s.astype(float)
    if how in ("level", "none"):
        return s
    if how == "yoy":
        return 100.0 * (s / s.shift(n) - 1.0)
    if how == "log_yoy":
        with np.errstate(divide="ignore", invalid="ignore"):
            return 100.0 * np.log(s / s.shift(n))
    if how == "yoy_diff":
        return s - s.shift(n)
    raise ValueError(f"unknown transform {how!r}")


def transform_wide(raw: pd.DataFrame, specs: dict[str, SeriesSpec]) -> pd.DataFrame:
    """Apply each column's registry transform. Only past values of the same column are
    used, so a transformed value is available exactly when its latest input is."""
    out = {col: transform_series(raw[col], specs[col].transform, specs[col].frequency) for col in raw.columns}
    return pd.DataFrame(out, index=raw.index)
