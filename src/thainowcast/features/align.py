"""Ragged-edge handling and temporal aggregation (the 'bridge' step)."""
from __future__ import annotations

import numpy as np
import pandas as pd

MAX_EXTRAPOLATE = 6  # months; longer trailing gaps leave the column unusable at that origin


def ar1_params(v: np.ndarray) -> tuple[float, float]:
    v = v[~np.isnan(v)]
    if len(v) < 24:
        return (float(v.mean()) if len(v) else 0.0, 0.0)
    m = float(v.mean())
    x = v - m
    denom = float(x[:-1] @ x[:-1])
    phi = float(x[:-1] @ x[1:]) / denom if denom > 0 else 0.0
    return m, float(np.clip(phi, -0.95, 0.95))


def ar1_extrapolate(v: np.ndarray, n_ahead: int) -> np.ndarray:
    m, phi = ar1_params(v)
    valid = v[~np.isnan(v)]
    last = float(valid[-1] - m) if len(valid) else 0.0
    out = np.empty(n_ahead)
    for i in range(n_ahead):
        last *= phi
        out[i] = last + m
    return out


def complete_to_period(X: pd.DataFrame, through: pd.Period, max_gap: int = MAX_EXTRAPOLATE) -> pd.DataFrame:
    """Extend a monthly panel to ``through``; fill each column's trailing gap with AR(1) forecasts."""
    if len(X.index) == 0:
        return X
    idx = pd.period_range(X.index[0], max(X.index[-1], through), freq="M")
    Xc = X.reindex(idx).astype(float).copy()
    for j, col in enumerate(Xc.columns):
        s = Xc[col]
        last = s.last_valid_index()
        if last is None:
            continue
        gap = through.ordinal - last.ordinal
        if gap <= 0 or gap > max_gap:
            continue
        pos = idx.get_loc(last)
        hist = s.iloc[: pos + 1].to_numpy(dtype=float)
        Xc.iloc[pos + 1 : pos + 1 + gap, j] = ar1_extrapolate(hist, gap)
    Xc = Xc.interpolate(limit_area="inside")
    return Xc.loc[:through]


def to_quarterly(Xm: pd.DataFrame) -> pd.DataFrame:
    """Quarterly means; a quarter counts only when all three months are present."""
    q = Xm.index.asfreq("Q")
    g = Xm.groupby(q)
    return g.mean().where(g.count() == 3)


def features_at_target_freq(X: pd.DataFrame, target: pd.Period) -> pd.DataFrame:
    """Monthly features -> frame at the target's frequency, extended through the target period."""
    if target.freqstr.startswith("Q"):
        return to_quarterly(complete_to_period(X, target.asfreq("M", how="end")))
    return complete_to_period(X, target)
