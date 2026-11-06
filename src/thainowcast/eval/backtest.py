"""Pseudo-real-time backtest: for every target period and every nowcast origin, rebuild the
information set from release dates, re-estimate each model, and record the nowcast."""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config import Config
from ..data.calendar import month_end_ts, release_date
from ..data.panel import Panel
from ..features import transform_wide
from ..models import MODELS, NowcastModel


@dataclass
class ModelSpec:
    name: str
    feature_set: str
    model: NowcastModel

    @property
    def key(self) -> str:
        return f"{self.name}:{self.feature_set}"


def origins_for(target: pd.Period, release_lag_days: int | None = None) -> list[tuple[str, pd.Timestamp]]:
    """Nowcast origins: the end of each month of a quarter (M1..M3) or the end of the target
    month (M0), plus PR = the day before the official release when the lag is given (the
    last useful nowcast, after most of the period's monthly data have been published)."""
    if target.freqstr.startswith("Q"):
        first = target.asfreq("M", how="start")
        out = [(f"M{i + 1}", month_end_ts(first + i)) for i in range(3)]
    else:
        out = [("M0", month_end_ts(target))]
    if release_lag_days is not None:
        pre = release_date(target, release_lag_days) - pd.Timedelta(days=1)
        if pre > out[-1][1]:
            out.append(("PR", pre))
    return out


def final_horizon(target_id: str, cfg: Config) -> str:
    return "PR"


def horizons_for(target_id: str, cfg: Config) -> list[str]:
    return ["M1", "M2", "M3", "PR"] if cfg.targets[target_id].frequency == "Q" else ["M0", "PR"]


def model_specs_for(cfg: Config, target_id: str, fast: bool = False) -> list[ModelSpec]:
    """The model x feature-set grid run for each target."""
    sets = list(cfg.feature_sets)
    quarterly = cfg.targets[target_id].frequency == "Q"
    specs = [ModelSpec("rw", "none", MODELS["rw"]()), ModelSpec("ar", "none", MODELS["ar"]())]
    core = ["hard_only", "all"]
    if fast:
        specs += [ModelSpec("bridge", s, MODELS["bridge"]()) for s in core]
        specs += [ModelSpec("enet", s, MODELS["enet"]()) for s in core]
        specs += [ModelSpec("dfm", s, MODELS["dfm"]()) for s in core]
        return specs
    specs += [ModelSpec("bridge", s, MODELS["bridge"]()) for s in sets]
    specs += [ModelSpec("enet", s, MODELS["enet"]()) for s in sets]
    if quarterly:
        specs += [ModelSpec("midas", s, MODELS["midas"]()) for s in core]
        specs += [ModelSpec("lgbm", s, MODELS["lgbm"]()) for s in core]
    else:
        specs += [ModelSpec("lgbm", s, MODELS["lgbm"]()) for s in sets]
    specs += [ModelSpec("dfm", s, MODELS["dfm"]()) for s in core]
    return specs


def backtest_periods(panel: Panel, cfg: Config, target_id: str, asof_max: pd.Timestamp) -> list[pd.Period]:
    """Target periods whose actual value is published by ``asof_max`` and that fall after the
    configured backtest start."""
    spec = cfg.targets[target_id]
    start = pd.Period(cfg.backtest["start"], freq="M").asfreq(spec.frequency, how="start")
    sub = panel.obs[(panel.obs["series"] == target_id) & (panel.obs["release"] <= asof_max)]
    idx = pd.PeriodIndex(sub["period"], freq=spec.frequency).sort_values()
    return [p for p in idx if p >= start]


def run_backtest(panel: Panel, cfg: Config, target_id: str, specs: list[ModelSpec], periods: list[pd.Period], log=print) -> pd.DataFrame:
    ind_ids = list(cfg.indicators)
    actual = panel.actual(target_id)
    rows = []
    t0 = time.time()
    for i, p in enumerate(periods):
        for h, asof in origins_for(p, cfg.targets[target_id].release_lag_days):
            y = panel.series_available(asof, target_id)
            X = transform_wide(panel.wide_available(asof, ind_ids, "M"), cfg.indicators)
            for ms in specs:
                cols = cfg.set_columns(ms.feature_set)
                Xs = X[cols] if cols else X.iloc[:, :0]
                try:
                    val = float(ms.model.nowcast(y, Xs, p, asof))
                except Exception as exc:  # a model failing at one origin must not kill the run
                    val = np.nan
                    log(f"  ! {ms.key} failed at {p}/{h}: {exc!r}")
                rows.append(
                    dict(
                        target=target_id, period=str(p), horizon=h, origin=asof, model=ms.name,
                        feature_set=ms.feature_set, nowcast=val, actual=float(actual.get(p, np.nan)),
                        actual_release=panel.release_of(target_id, p),
                    )
                )
        if (i + 1) % 8 == 0 or i == len(periods) - 1:
            log(f"  {target_id}: {i + 1}/{len(periods)} periods done ({time.time() - t0:.0f}s)")
    bt = pd.DataFrame(rows)
    bt["error"] = bt["nowcast"] - bt["actual"]
    return bt
