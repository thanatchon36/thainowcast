"""Mixed-frequency dynamic factor model (statsmodels ``DynamicFactorMQ``).

Estimation is by EM with arbitrary missing data (Bańbura & Modugno, 2014 [ต้องตรวจ]),
so the ragged edge and short alternative-data series are handled natively. Parameters
are re-estimated once a year (and whenever the set of usable series changes); at every
other origin the state is re-smoothed with the stored parameters, which is how
production nowcasting systems typically run and is what the news decomposition needs.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.dynamic_factor_mq import DynamicFactorMQ

from .base import NowcastModel, fallback_ar


def _winsorize(X: pd.DataFrame, z: float = 4.0) -> pd.DataFrame:
    mu, sd = X.mean(), X.std(ddof=1).replace(0, np.nan)
    return X.clip(lower=mu - z * sd, upper=mu + z * sd, axis=1)


def prepare_endog(y: pd.Series, X: pd.DataFrame, target: pd.Period, min_obs: int = 36):
    """Return (monthly endog, quarterly endog or None, prediction period, target column)."""
    y = y.rename(y.name or "target")
    Xm = _winsorize(X.loc[:, X.notna().sum() >= min_obs].astype(float))
    if target.freqstr.startswith("Q"):
        m_end = target.asfreq("M", how="end")
        idx = pd.period_range(Xm.index[0], max(Xm.index[-1], m_end), freq="M")
        Xm = Xm.reindex(idx)
        qidx = pd.period_range(y.index[0], target, freq="Q")
        yq = y.reindex(qidx).to_frame()
        return Xm, yq, m_end, y.name
    idx = pd.period_range(Xm.index[0], max(Xm.index[-1], target), freq="M")
    Xm = Xm.reindex(idx)
    Xm[y.name] = y.reindex(idx)
    return Xm, None, target, y.name


class DFM(NowcastModel):
    name = "dfm"

    def __init__(self, n_factors: int = 1, factor_order: int = 1, maxiter: int = 50, refit: str = "annual", min_obs: int = 36):
        super().__init__(n_factors=n_factors, factor_order=factor_order, maxiter=maxiter, refit=refit)
        self.n_factors, self.factor_order, self.maxiter, self.refit, self.min_obs = n_factors, factor_order, maxiter, refit, min_obs
        self._cache: dict = {}
        self.last_results = None

    def build(self, Xm: pd.DataFrame, yq: pd.DataFrame | None) -> DynamicFactorMQ:
        return DynamicFactorMQ(
            Xm, endog_quarterly=yq, factors=self.n_factors, factor_orders=self.factor_order,
            idiosyncratic_ar1=True, standardize=True,
        )

    def results(self, Xm: pd.DataFrame, yq: pd.DataFrame | None, key):
        mod = self.build(Xm, yq)
        if key in self._cache:
            try:
                return mod.smooth(self._cache[key])
            except Exception:
                self._cache.pop(key, None)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = mod.fit(disp=False, maxiter=self.maxiter)
        self._cache[key] = res.params
        return res

    def cache_key(self, col: str, Xm: pd.DataFrame, origin) -> tuple:
        stamp = pd.Timestamp(origin).year if self.refit == "annual" else pd.Timestamp(origin)
        return (col, tuple(Xm.columns), stamp)

    def nowcast(self, y, X, target, origin) -> float:
        if X.shape[1] < 3 or len(y) < 24:
            return fallback_ar(y, target)
        Xm, yq, when, col = prepare_endog(y, X, target, self.min_obs)
        if Xm.shape[1] < 3:
            return fallback_ar(y, target)
        key = self.cache_key(col, Xm, origin)
        try:
            res = self.results(Xm, yq, key)
            pred = res.get_prediction(start=when, end=when, information_set="smoothed").predicted_mean
            val = float(pred[col].iloc[0]) if isinstance(pred, pd.DataFrame) else float(np.asarray(pred).ravel()[0])
            if not np.isfinite(val):
                raise ValueError("non-finite nowcast")
            # Guard against a degenerate EM solution (it happens on short, badly scaled panels):
            # anything more than 8 target standard deviations from the mean is treated as a failure.
            if abs(val - float(y.mean())) > 8.0 * max(float(y.std()), 0.5):
                raise ValueError("implausible nowcast from a degenerate EM fit")
            self.last_results = res
            return val
        except Exception:
            self._cache.pop(key, None)
            return fallback_ar(y, target)
