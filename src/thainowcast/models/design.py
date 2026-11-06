"""Build a balanced training design from a target-frequency feature frame."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MIN_TRAIN = {"Q": 24, "M": 48}


@dataclass
class Design:
    X: np.ndarray  # standardized, clipped training rows
    y: np.ndarray
    x_new: np.ndarray  # standardized target row
    columns: list[str]
    index: pd.PeriodIndex


def build_design(F: pd.DataFrame, y: pd.Series, target: pd.Period, min_train: int | None = None, clip_z: float = 4.0) -> Design | None:
    """Trade breadth for history: columns are added in order of history length as long as at
    least ``min_train`` complete rows remain. Columns missing at the target row are dropped.
    Short alternative-data series therefore enter the linear models only once they have
    enough history (the DFM handles them earlier through its missing-data EM step)."""
    freq = "Q" if target.freqstr.startswith("Q") else "M"
    min_train = min_train or MIN_TRAIN[freq]
    if target not in F.index:
        return None
    x_full = F.loc[target]
    cand = [c for c in F.columns if pd.notna(x_full[c])]
    rows = y.index[y.index < target]
    rows = rows[rows.isin(F.index)]
    if len(rows) < min_train or not cand:
        return None
    Fr = F.loc[rows, cand]
    first_valid = {c: Fr[c].first_valid_index() for c in cand}
    cand = [c for c in cand if first_valid[c] is not None]
    cand.sort(key=lambda c: first_valid[c].ordinal)
    keep: list[str] = []
    start = rows[0]
    for c in cand:
        new_start = max(start, first_valid[c], key=lambda p: p.ordinal)
        if int((rows >= new_start).sum()) >= min_train:
            keep.append(c)
            start = new_start
        else:
            break
    if not keep:
        return None
    rows = rows[rows >= start]
    Xtr = F.loc[rows, keep]
    keep = [c for c in keep if Xtr[c].notna().all()]
    if not keep:
        return None
    Xtr = Xtr[keep].to_numpy(dtype=float)
    ytr = y.loc[rows].to_numpy(dtype=float)
    mu, sd = Xtr.mean(0), Xtr.std(0, ddof=1)
    sd[~np.isfinite(sd) | (sd == 0)] = 1.0
    Xs = np.clip((Xtr - mu) / sd, -clip_z, clip_z)
    xs = np.clip((x_full[keep].to_numpy(dtype=float) - mu) / sd, -clip_z, clip_z)
    return Design(X=Xs, y=ytr, x_new=xs, columns=keep, index=rows)
