"""Regularized regression and gradient boosting on bridge-aggregated features."""
from __future__ import annotations

import warnings

import numpy as np
from sklearn.linear_model import ElasticNetCV
from sklearn.model_selection import TimeSeriesSplit

from ..features.align import features_at_target_freq
from .base import NowcastModel, fallback_ar
from .design import build_design


class ElasticNetNowcast(NowcastModel):
    name = "enet"

    def __init__(self, l1_ratios=(0.1, 0.5, 0.9), n_splits: int = 4):
        super().__init__(l1_ratios=list(l1_ratios), n_splits=n_splits)
        self.l1_ratios, self.n_splits = list(l1_ratios), n_splits

    def nowcast(self, y, X, target, origin) -> float:
        F = features_at_target_freq(X, target)
        d = build_design(F, y, target)
        if d is None:
            return fallback_ar(y, target)
        cv = TimeSeriesSplit(n_splits=max(2, min(self.n_splits, len(d.y) // 8)))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = ElasticNetCV(l1_ratio=self.l1_ratios, cv=cv, alphas=40, max_iter=20000).fit(d.X, d.y)
        return float(m.predict(d.x_new[None, :])[0])


class LightGBMNowcast(NowcastModel):
    name = "lgbm"

    def __init__(self, n_estimators: int = 300, learning_rate: float = 0.03, num_leaves: int = 4, min_child_samples: int = 5):
        super().__init__(n_estimators=n_estimators, learning_rate=learning_rate, num_leaves=num_leaves, min_child_samples=min_child_samples)
        self.kw = dict(n_estimators=n_estimators, learning_rate=learning_rate, num_leaves=num_leaves, min_child_samples=min_child_samples)

    def nowcast(self, y, X, target, origin) -> float:
        import lightgbm as lgb

        F = features_at_target_freq(X, target)
        d = build_design(F, y, target)
        if d is None:
            return fallback_ar(y, target)
        m = lgb.LGBMRegressor(
            subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=0,
            verbose=-1, deterministic=True, force_row_wise=True, n_jobs=1, **self.kw,
        )
        m.fit(d.X, d.y)
        return float(m.predict(d.x_new[None, :])[0])
