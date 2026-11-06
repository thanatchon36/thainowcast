"""Diebold-Mariano test with the Harvey-Leybourne-Newbold small-sample correction [ต้องตรวจ refs]."""
from __future__ import annotations

import numpy as np
from scipy import stats


def dm_test(e_model: np.ndarray, e_bench: np.ndarray, h: int = 1, loss: str = "squared") -> tuple[float, float, int]:
    """Return (HLN-adjusted DM statistic, two-sided p-value, n).

    Negative statistic = the model's loss is lower than the benchmark's.
    """
    e1, e2 = np.asarray(e_model, float), np.asarray(e_bench, float)
    ok = np.isfinite(e1) & np.isfinite(e2)
    e1, e2 = e1[ok], e2[ok]
    n = len(e1)
    if n < 10:
        return np.nan, np.nan, n
    d = (e1**2 - e2**2) if loss == "squared" else (np.abs(e1) - np.abs(e2))
    dbar = d.mean()
    dc = d - dbar
    lrv = float(dc @ dc) / n
    for k in range(1, h):
        gk = float(dc[k:] @ dc[:-k]) / n
        lrv += 2.0 * (1.0 - k / h) * gk
    if lrv <= 0:
        return np.nan, np.nan, n
    dm = dbar / np.sqrt(lrv / n)
    hln = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n) * dm
    p = 2.0 * (1.0 - stats.t.cdf(abs(hln), df=n - 1))
    return float(hln), float(p), n
