"""The information set at any origin must contain only observations published by that origin."""
import numpy as np
import pandas as pd

from thainowcast.features import transform_wide
from thainowcast.eval.backtest import origins_for
from thainowcast.eval.metrics import add_intervals


def _released_mask(panel, sid, asof):
    sub = panel.obs[panel.obs["series"] == sid]
    return sub.set_index("period")["release"] <= asof


def test_wide_available_respects_release_dates(panel, cfg):
    rng = np.random.default_rng(0)
    ids = list(cfg.indicators)
    lo, hi = panel.span("M")
    for _ in range(40):
        asof = pd.Timestamp("2010-01-01") + pd.Timedelta(days=int(rng.integers(0, 6000)))
        wide = panel.wide_available(asof, ids, "M")
        for sid in ids:
            rel = _released_mask(panel, sid, asof)
            observed = wide[sid].dropna().index.astype(str)
            assert all(rel.get(p, False) for p in observed), f"{sid} leaked at {asof.date()}"


def test_target_history_respects_release(panel):
    asof = pd.Timestamp("2024-07-31")  # 2024Q2 GDP is released on 2024-08-17
    y = panel.series_available(asof, "gdp_yoy")
    assert y.index[-1] == pd.Period("2024Q1", freq="Q")
    y2 = panel.series_available(pd.Timestamp("2024-08-17"), "gdp_yoy")
    assert y2.index[-1] == pd.Period("2024Q2", freq="Q")


def test_transform_does_not_create_future_values(panel, cfg):
    asof = pd.Timestamp("2024-08-31")
    ids = list(cfg.indicators)
    raw = panel.wide_available(asof, ids, "M")
    X = transform_wide(raw, cfg.indicators)
    for sid in ids:
        last_raw = raw[sid].last_valid_index()
        last_x = X[sid].last_valid_index()
        assert last_x is None or last_raw is None or last_x <= last_raw


def test_origins_inside_target_period():
    q = pd.Period("2026Q3", freq="Q")
    o = origins_for(q, 48)
    assert [h for h, _ in o] == ["M1", "M2", "M3", "PR"]
    assert o[2][1] == pd.Timestamp("2026-09-30") and o[3][1] == pd.Timestamp("2026-11-16")


def test_conformal_uses_only_published_errors():
    bt = pd.DataFrame({
        "period": ["2020Q1", "2020Q2", "2020Q3", "2020Q4"] * 1,
        "horizon": "M3", "model": "m", "feature_set": "s",
        "origin": pd.to_datetime(["2020-03-31", "2020-06-30", "2020-09-30", "2020-12-31"]),
        "nowcast": [1.0, 1.0, 1.0, 1.0], "actual": [1.5, 0.0, 2.0, 1.0],
        "actual_release": pd.to_datetime(["2020-05-18", "2020-08-17", "2020-11-16", "2021-02-15"]),
    })
    bt["error"] = bt["nowcast"] - bt["actual"]
    out = add_intervals(bt, alpha=0.2, min_n=1)
    # at the 2020Q2 origin (2020-06-30) only 2020Q1 (released 2020-05-18) is known -> half-width = |error_Q1| = 0.5
    row = out[out["period"] == "2020Q2"].iloc[0]
    assert abs((row["hi"] - row["lo"]) / 2 - 0.5) < 1e-9
    # at the 2020Q1 origin nothing is known yet
    assert np.isnan(out[out["period"] == "2020Q1"]["lo"].iloc[0])
