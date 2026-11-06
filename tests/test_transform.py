import numpy as np
import pandas as pd

from thainowcast.features.align import complete_to_period, to_quarterly
from thainowcast.features.transform import transform_series


def test_yoy():
    idx = pd.period_range("2020-01", "2021-12", freq="M")
    s = pd.Series(np.arange(100, 124, dtype=float), index=idx)
    y = transform_series(s, "yoy", "M")
    assert np.isnan(y.iloc[11]) and abs(y.loc["2021-01"] - 12.0) < 1e-9


def test_ragged_edge_fill_and_long_gap():
    idx = pd.period_range("2015-01", "2024-06", freq="M")
    X = pd.DataFrame({"a": np.sin(np.arange(len(idx)) / 3), "b": np.cos(np.arange(len(idx)) / 5)}, index=idx)
    X.loc["2024-05":, "a"] = np.nan  # 2-month trailing gap -> filled
    X.loc["2023-01":, "b"] = np.nan  # 18-month gap -> left missing
    Xc = complete_to_period(X, pd.Period("2024-09", freq="M"))
    assert Xc.index[-1] == pd.Period("2024-09", freq="M")
    assert Xc["a"].loc["2024-05":].notna().all()
    assert Xc["b"].loc["2024-09"] != Xc["b"].loc["2024-09"]  # NaN
    q = to_quarterly(Xc)
    assert q.index[-1] == pd.Period("2024Q3", freq="Q")
    assert np.isfinite(q["a"].iloc[-1])
