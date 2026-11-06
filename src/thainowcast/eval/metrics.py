"""Accuracy summaries, conformal intervals, relative RMSFE and DM tables."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Config
from .dm import dm_test

KEYS = ["feature_set", "model", "horizon"]


def regime_of(period: str, cfg: Config) -> str:
    y = int(str(period)[:4])
    for name, (a, b) in cfg.backtest["regimes"].items():
        if int(a[:4]) <= y <= int(b[:4]):
            return name
    return "other"


def add_intervals(bt: pd.DataFrame, alpha: float = 0.2, min_n: int = 8) -> pd.DataFrame:
    """Split-conformal style intervals: at each origin, the (1-alpha) quantile of the absolute
    errors of all *already published* target periods for the same model/feature set/horizon.
    Nothing from the future of the origin is used."""
    bt = bt.sort_values("origin").copy()
    lo, hi = np.full(len(bt), np.nan), np.full(len(bt), np.nan)
    pos = {idx: i for i, idx in enumerate(bt.index)}
    for _, g in bt.groupby(KEYS, sort=False):
        err = g["error"].abs().to_numpy()
        rel = g["actual_release"].to_numpy()
        orig = g["origin"].to_numpy()
        for i, idx in enumerate(g.index):
            past = err[(rel <= orig[i]) & np.isfinite(err)]
            if len(past) >= min_n:
                q = float(np.quantile(past, 1 - alpha))
                lo[pos[idx]], hi[pos[idx]] = g["nowcast"].iloc[i] - q, g["nowcast"].iloc[i] + q
    bt["lo"], bt["hi"] = lo, hi
    bt["covered"] = (bt["actual"] >= bt["lo"]) & (bt["actual"] <= bt["hi"])
    bt.loc[bt["lo"].isna(), "covered"] = np.nan
    return bt.sort_values(["period", "horizon", "model", "feature_set"]).reset_index(drop=True)


def summarize(bt: pd.DataFrame, cfg: Config, benchmark: str = "ar") -> pd.DataFrame:
    bt = bt.copy()
    bt["regime"] = bt["period"].map(lambda p: regime_of(p, cfg))
    frames = []
    for regime, sub in [("full", bt)] + [(r, bt[bt["regime"] == r]) for r in cfg.backtest["regimes"]]:
        g = sub.dropna(subset=["error"]).groupby(KEYS)["error"]
        s = pd.DataFrame({"rmsfe": g.apply(lambda e: float(np.sqrt(np.mean(e**2)))), "mae": g.apply(lambda e: float(np.mean(np.abs(e)))), "n": g.size()})
        s["regime"] = regime
        frames.append(s.reset_index())
    out = pd.concat(frames, ignore_index=True)
    bench = out[(out["model"] == benchmark)][["horizon", "regime", "rmsfe"]].rename(columns={"rmsfe": "rmsfe_bench"})
    out = out.merge(bench, on=["horizon", "regime"], how="left")
    out["rel_rmsfe"] = out["rmsfe"] / out["rmsfe_bench"]
    return out


def dm_table(bt: pd.DataFrame, benchmark: str = "ar") -> pd.DataFrame:
    rows = []
    bench = bt[bt["model"] == benchmark].set_index(["period", "horizon"])["error"]
    for (fs, model, h), g in bt.groupby(KEYS):
        if model == benchmark:
            continue
        e_b = bench.reindex(pd.MultiIndex.from_arrays([g["period"], g["horizon"]])).to_numpy()
        stat, p, n = dm_test(g["error"].to_numpy(), e_b, h=1)
        rows.append(dict(feature_set=fs, model=model, horizon=h, dm_stat=stat, p_value=p, n=n))
    return pd.DataFrame(rows)


def coverage_table(bt: pd.DataFrame) -> pd.DataFrame:
    sub = bt.dropna(subset=["covered"]).copy()
    sub["width"] = sub["hi"] - sub["lo"]
    sub["covered"] = sub["covered"].astype(float)
    g = sub.groupby(KEYS)
    out = pd.DataFrame({"coverage": g["covered"].mean(), "width": g["width"].mean(), "n": g.size()})
    return out.reset_index()


def ablation_table(summary: pd.DataFrame, horizon: str, base_set: str = "hard_only", regime: str = "full") -> pd.DataFrame:
    """Relative RMSFE of each feature set versus hard-data-only, model by model."""
    s = summary[(summary["horizon"] == horizon) & (summary["regime"] == regime) & (summary["feature_set"] != "none")]
    base = s[s["feature_set"] == base_set].set_index("model")["rmsfe"]
    s = s.copy()
    s["rel_to_hard"] = s.apply(lambda r: r["rmsfe"] / base.get(r["model"], np.nan), axis=1)
    return s[["model", "feature_set", "rmsfe", "rel_to_hard", "n"]].sort_values(["model", "feature_set"]).reset_index(drop=True)
