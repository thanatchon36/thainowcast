"""Benchmarks: random walk and an AIC-selected AR(p) on the target alone."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.ar_model import AutoReg, ar_select_order

from .base import NowcastModel, steps_ahead


class RandomWalk(NowcastModel):
    name = "rw"

    def nowcast(self, y, X, target, origin) -> float:
        return float(y.iloc[-1])


class AR(NowcastModel):
    name = "ar"

    def __init__(self, max_lags: int = 4):
        super().__init__(max_lags=max_lags)
        self.max_lags = max_lags

    def nowcast(self, y, X, target, origin) -> float:
        v = y.to_numpy(dtype=float)
        h = steps_ahead(y, target)
        if len(v) < 20 or h < 1:
            return float(v.mean()) if len(v) else np.nan
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                sel = ar_select_order(v, maxlag=self.max_lags, ic="aic", trend="c")
                lags = list(sel.ar_lags) if sel.ar_lags else []
                if not lags:
                    return float(v.mean())
                res = AutoReg(v, lags=max(lags), trend="c").fit()
                return float(res.forecast(steps=h)[-1])
        except Exception:
            return float(v[-1])
