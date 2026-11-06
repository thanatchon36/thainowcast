"""MIDAS regression with exponential Almon weights (quarterly targets)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from .base import NowcastModel, fallback_ar


class MIDAS(NowcastModel):
    """Single-regressor MIDAS. The regressor is the cross-sectional mean of the standardized
    monthly indicators (a crude common factor that tolerates the ragged edge). The weight
    polynomial is re-estimated for every horizon, i.e. for every number of missing months
    in the target quarter, as in the 'MIDAS with leads' literature."""

    name = "midas"

    def __init__(self, n_lags: int = 12, min_train: int = 20):
        super().__init__(n_lags=n_lags)
        self.K = n_lags
        self.min_train = min_train

    @staticmethod
    def _factor(X: pd.DataFrame) -> pd.Series:
        Z = ((X - X.mean()) / X.std(ddof=1)).clip(-4, 4)
        return Z.mean(axis=1, skipna=True).where(Z.notna().sum(axis=1) >= 3)

    @staticmethod
    def _weights(theta: np.ndarray, K: int) -> np.ndarray:
        j = np.arange(K, dtype=float)
        w = np.exp(theta[0] * j + theta[1] * j**2)
        return w / w.sum()

    def nowcast(self, y, X, target, origin) -> float:
        if not target.freqstr.startswith("Q") or X.shape[1] < 3:
            return fallback_ar(y, target)
        x = self._factor(X)
        m3 = target.asfreq("M", how="end")
        last = x.loc[:m3].last_valid_index()
        if last is None:
            return fallback_ar(y, target)
        lead = m3.ordinal - last.ordinal
        if lead > 2:
            return fallback_ar(y, target)
        xv = x.to_numpy(dtype=float)
        ordinal0 = x.index[0].ordinal

        def lag_vector(q: pd.Period) -> np.ndarray | None:
            pos = q.asfreq("M", how="end").ordinal - lead - ordinal0
            if pos - self.K + 1 < 0 or pos >= len(xv):
                return None
            v = xv[pos - self.K + 1 : pos + 1][::-1]  # j=0 is the most recent month
            return None if np.isnan(v).any() else v

        rows, ys = [], []
        for q, yq in y.items():
            if q >= target:
                continue
            lv = lag_vector(q)
            if lv is not None:
                rows.append(lv)
                ys.append(float(yq))
        if len(rows) < self.min_train:
            return fallback_ar(y, target)
        L, yt = np.asarray(rows), np.asarray(ys)
        lnew = lag_vector(target)
        if lnew is None:
            return fallback_ar(y, target)

        def resid(p: np.ndarray) -> np.ndarray:
            w = self._weights(p[2:], self.K)
            return yt - p[0] - p[1] * (L @ w)

        w0 = self._weights(np.array([0.0, -0.02]), self.K)
        z0 = L @ w0
        b1 = float(np.cov(z0, yt)[0, 1] / (np.var(z0, ddof=1) + 1e-12))
        b0 = float(yt.mean() - b1 * z0.mean())
        fit = least_squares(resid, x0=[b0, b1, 0.0, -0.02], bounds=([-np.inf, -np.inf, -1.0, -0.5], [np.inf, np.inf, 1.0, 0.05]))
        p = fit.x
        return float(p[0] + p[1] * (lnew @ self._weights(p[2:], self.K)))
