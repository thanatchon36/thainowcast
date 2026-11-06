"""Live nowcast: the first unreleased period of each target as of a given date."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from ..config import Config
from ..data.panel import Panel
from ..features import transform_wide
from ..models.dfm import DFM, prepare_endog
from .backtest import ModelSpec, final_horizon, origins_for

TARGET_LABEL = {"gdp_yoy": "Real GDP growth (y-o-y)", "cpi_yoy": "Headline CPI inflation (y-o-y)", "gdp_qoq_sa": "Real GDP growth (q-o-q SA)"}


def next_unreleased(panel: Panel, target_id: str, asof: pd.Timestamp) -> pd.Period:
    spec = panel.specs[target_id]
    sub = panel.obs[panel.obs["series"] == target_id]
    idx = pd.PeriodIndex(sub["period"], freq=spec.frequency)
    unreleased = idx[(sub["release"] > asof).to_numpy()]
    return unreleased.min() if len(unreleased) else idx.max() + 1


def error_quantiles(bt: pd.DataFrame, alpha: float = 0.2) -> dict[tuple[str, str, str], float]:
    out = {}
    for (fs, m, h), g in bt.groupby(["feature_set", "model", "horizon"]):
        e = g["error"].abs().dropna()
        if len(e) >= 8:
            out[(fs, m, h)] = float(np.quantile(e, 1 - alpha))
    return out


def run_live(panel: Panel, cfg: Config, target_id: str, specs: list[ModelSpec], asof: pd.Timestamp, bt: pd.DataFrame, summary: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """Returns (summary dict, evolution frame: one row per model x origin)."""
    ind_ids = list(cfg.indicators)
    target = next_unreleased(panel, target_id, asof)
    h_final = final_horizon(target_id, cfg)
    quants = error_quantiles(bt, cfg.backtest.get("conformal_alpha", 0.2))
    origins = [(h, o) for h, o in origins_for(target, cfg.targets[target_id].release_lag_days) if o <= asof]
    if target.freqstr.startswith("M"):
        mid = target.to_timestamp(how="start") + pd.Timedelta(days=14)
        origins = [("mid", mid)] + origins if mid <= asof else origins
    if not origins or origins[-1][1] != asof:
        origins.append(("latest", asof))
    rows = []
    for h, o in origins:
        y = panel.series_available(o, target_id)
        X = transform_wide(panel.wide_available(o, ind_ids, "M"), cfg.indicators)
        for ms in specs:
            cols = cfg.set_columns(ms.feature_set)
            Xs = X[cols] if cols else X.iloc[:, :0]
            try:
                val = float(ms.model.nowcast(y, Xs, target, o))
            except Exception:
                val = np.nan
            hq = h if h in {"M1", "M2", "M3", "M0", "PR"} else h_final
            q = quants.get((ms.feature_set, ms.name, hq), np.nan)
            rows.append(dict(target=target_id, period=str(target), horizon=h, origin=o, model=ms.name, feature_set=ms.feature_set, nowcast=val, lo=val - q, hi=val + q))
    evo = pd.DataFrame(rows)

    # headline = best full-sample RMSFE at the final origin among the two core sets (plus AR as a floor)
    s = summary[(summary["regime"] == "full") & (summary["horizon"] == h_final) & (summary["feature_set"].isin(["all", "hard_only", "none"]))]
    s = s[s["model"] != "rw"].sort_values("rmsfe")
    head_model, head_set = (s["model"].iloc[0], s["feature_set"].iloc[0]) if len(s) else ("ar", "none")
    latest = evo[evo["horizon"] == origins[-1][0]].set_index(["model", "feature_set"])
    head = latest.loc[(head_model, head_set)]
    evo.attrs["headline_model"], evo.attrs["headline_set"] = head_model, head_set
    out = {
        "label": TARGET_LABEL.get(target_id, target_id),
        "period": str(target),
        "release_expected": panel.release_of(target_id, target).strftime("%Y-%m-%d") if pd.notna(panel.release_of(target_id, target)) else None,
        "headline": {"model": head_model, "feature_set": head_set, "value": float(head["nowcast"]), "lo": float(head["lo"]), "hi": float(head["hi"]), "rmsfe_full": float(s["rmsfe"].iloc[0]) if len(s) else None},
        "models": [
            {"model": m, "feature_set": fs, "value": float(r["nowcast"]), "lo": float(r["lo"]), "hi": float(r["hi"])}
            for (m, fs), r in latest.iterrows()
        ],
        "origins": [{"horizon": h, "origin": o.strftime("%Y-%m-%d")} for h, o in origins],
    }
    return out, evo


def dfm_news(panel: Panel, cfg: Config, target_id: str, feature_set: str, origin_prev: pd.Timestamp, origin_new: pd.Timestamp, target: pd.Period, dfm: DFM | None = None) -> tuple[pd.DataFrame, dict]:
    """Decompose the change in the DFM nowcast between two origins into the contribution of
    each newly released observation (Kalman-filter news, Bańbura & Modugno 2014 [ต้องตรวจ]).
    Falls back to a loading-weighted surprise approximation if statsmodels' ``news`` fails."""
    dfm = dfm or DFM()
    ind_ids = list(cfg.indicators)
    cols = cfg.set_columns(feature_set)
    datasets = {}
    for tag, o in [("prev", origin_prev), ("new", origin_new)]:
        y = panel.series_available(o, target_id)
        X = transform_wide(panel.wide_available(o, ind_ids, "M"), cfg.indicators)[cols]
        datasets[tag] = prepare_endog(y, X, target, dfm.min_obs)
    Xm_new, yq_new, when, col = datasets["new"]
    Xm_prev, yq_prev, _, _ = datasets["prev"]
    # same column set for both (needed for shared parameters)
    common = [c for c in Xm_new.columns if c in Xm_prev.columns]
    Xm_new, Xm_prev = Xm_new[common], Xm_prev[common].reindex(Xm_new.index)
    if yq_prev is not None:
        yq_prev = yq_prev.reindex(yq_new.index)
    key = ("news", col, tuple(common), origin_new.year)
    res_new = dfm.results(Xm_new, yq_new, key)
    res_prev = dfm.build(Xm_prev, yq_prev).smooth(res_new.params)
    pred = lambda r: float(r.get_prediction(start=when, end=when, information_set="smoothed").predicted_mean[col].iloc[0])  # noqa: E731
    v_prev, v_new = pred(res_prev), pred(res_new)
    meta = {"nowcast_prev": v_prev, "nowcast_new": v_new, "change": v_new - v_prev, "method": "statsmodels news"}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            nw = res_new.news(res_prev, impact_date=when, impacted_variable=col, comparison_type="previous")
        det = nw.details_by_impact.reset_index()
        cmap = {c: c.lower() for c in det.columns}
        det = det.rename(columns=cmap)
        upd_col = next(c for c in det.columns if "updated variable" in c)
        date_col = next(c for c in det.columns if "update date" in c)
        table = pd.DataFrame(
            {
                "series": det[upd_col].astype(str),
                "update_period": det[date_col].astype(str),
                "observed": det["observed"].astype(float),
                "forecast_prev": det[[c for c in det.columns if c.startswith("forecast")][0]].astype(float),
                "news": det["news"].astype(float),
                "weight": det["weight"].astype(float),
                "impact": det["impact"].astype(float),
            }
        )
        table = table[table["series"] != col]
    except Exception as exc:  # approximation: standardized surprise x loading, scaled to the total change
        meta["method"] = f"approximation (statsmodels news failed: {exc.__class__.__name__})"
        new_obs = Xm_new.notna() & ~Xm_prev.notna()
        rows = []
        pm = res_prev.get_prediction(start=Xm_new.index[0], end=Xm_new.index[-1], information_set="smoothed").predicted_mean
        for c in common:
            for p in Xm_new.index[new_obs[c].to_numpy()]:
                obs = float(Xm_new.loc[p, c])
                fc = float(pm.loc[p, c]) if c in pm.columns else np.nan
                rows.append(dict(series=c, update_period=str(p), observed=obs, forecast_prev=fc, news=obs - fc, weight=np.nan, impact=np.nan))
        table = pd.DataFrame(rows)
        if len(table):
            sd = Xm_new.std()
            z = (table["news"] / table["series"].map(sd)).fillna(0.0)
            table["impact"] = z / (z.abs().sum() or 1.0) * (v_new - v_prev)
    table.attrs.update(meta)
    return table, meta
