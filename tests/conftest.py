import warnings

import pandas as pd
import pytest

from thainowcast.config import load_config
from thainowcast.data.loaders import load_panel
from thainowcast.data.synthetic import generate


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture(scope="session")
def panel(cfg, tmp_path_factory):
    raw = tmp_path_factory.mktemp("raw")
    generate(cfg, raw, seed=7)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return load_panel(cfg, raw)


@pytest.fixture
def asof():
    return pd.Timestamp("2024-08-31")
