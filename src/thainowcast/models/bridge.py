"""Bridge equation with principal components."""
from __future__ import annotations

import numpy as np
from sklearn.decomposition import PCA

from ..features.align import features_at_target_freq
from .base import NowcastModel, fallback_ar
from .design import build_design


class Bridge(NowcastModel):
    """Monthly indicators are completed to the end of the target period with AR(1) forecasts,
    averaged to the target frequency, reduced to ``n_factors`` principal components and
    regressed on the target by OLS (a 'factor bridge equation')."""

    name = "bridge"

    def __init__(self, n_factors: int = 2):
        super().__init__(n_factors=n_factors)
        self.k = n_factors

    def nowcast(self, y, X, target, origin) -> float:
        F = features_at_target_freq(X, target)
        d = build_design(F, y, target)
        if d is None:
            return fallback_ar(y, target)
        k = max(1, min(self.k, d.X.shape[1], d.X.shape[0] // 10))
        pca = PCA(n_components=k, random_state=0).fit(d.X)
        Z = pca.transform(d.X)
        z = pca.transform(d.x_new[None, :]).ravel()
        A = np.column_stack([np.ones(len(Z)), Z])
        beta, *_ = np.linalg.lstsq(A, d.y, rcond=None)
        return float(np.r_[1.0, z] @ beta)
