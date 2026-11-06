import numpy as np
import pandas as pd
import pytest

from thainowcast.features import transform_wide
from thainowcast.models import MODELS


@pytest.mark.parametrize("name", list(MODELS))
def test_each_model_returns_finite_nowcast(name, panel, cfg, asof):
    target = pd.Period("2024Q3", freq="Q")
    y = panel.series_available(asof, "gdp_yoy")
    X = transform_wide(panel.wide_available(asof, list(cfg.indicators), "M"), cfg.indicators)[cfg.set_columns("all")]
    kw = {"maxiter": 10} if name == "dfm" else {}
    v = MODELS[name](**kw).nowcast(y, X, target, asof)
    assert np.isfinite(v)
    assert -20 < v < 20


@pytest.mark.parametrize("name", ["ar", "bridge", "dfm", "enet", "lgbm"])
def test_models_handle_monthly_target(name, panel, cfg, asof):
    target = pd.Period("2024-08", freq="M")
    y = panel.series_available(asof, "cpi_yoy")
    X = transform_wide(panel.wide_available(asof, list(cfg.indicators), "M"), cfg.indicators)[cfg.set_columns("hard_only")]
    kw = {"maxiter": 10} if name == "dfm" else {}
    assert np.isfinite(MODELS[name](**kw).nowcast(y, X, target, asof))


def test_ar_horizon_depends_on_release(panel, asof):
    """At the end of month 1 the previous quarter is not yet published, so AR forecasts 2 steps."""
    from thainowcast.models.base import steps_ahead

    y1 = panel.series_available(pd.Timestamp("2024-07-31"), "gdp_yoy")
    y2 = panel.series_available(pd.Timestamp("2024-08-31"), "gdp_yoy")
    t = pd.Period("2024Q3", freq="Q")
    assert steps_ahead(y1, t) == 2 and steps_ahead(y2, t) == 1
