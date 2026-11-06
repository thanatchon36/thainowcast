import warnings

import pandas as pd
import pytest

from thainowcast.data.loaders import SyntheticDataWarning, load_series, read_series_csv


def test_synthetic_fallback_warns(cfg, tmp_path):
    spec = cfg.indicators["mpi"]
    pd.DataFrame({"period": ["2020-01", "2020-02"], "value": [1.0, 2.0]}).to_csv(tmp_path / f"synthetic_{spec.file}", index=False)
    with pytest.warns(SyntheticDataWarning):
        s, is_syn = load_series(spec, tmp_path)
    assert is_syn and len(s) == 2 and isinstance(s.index, pd.PeriodIndex)


def test_real_file_takes_precedence(cfg, tmp_path):
    spec = cfg.indicators["mpi"]
    pd.DataFrame({"period": ["2020-01"], "value": [5.0]}).to_csv(tmp_path / spec.file, index=False)
    pd.DataFrame({"period": ["2020-01"], "value": [1.0]}).to_csv(tmp_path / f"synthetic_{spec.file}", index=False)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        s, is_syn = load_series(spec, tmp_path)
    assert not is_syn and s.iloc[0] == 5.0


def test_missing_file_explains_how_to_fetch(cfg, tmp_path):
    with pytest.raises(FileNotFoundError, match="How to get it"):
        load_series(cfg.indicators["mpi"], tmp_path)


def test_schema_validation(tmp_path):
    (tmp_path / "bad.csv").write_text("date,value\n2020-01,1\n")
    with pytest.raises(ValueError, match="period,value"):
        read_series_csv(tmp_path / "bad.csv", "M")


def test_panel_schema(panel, cfg):
    assert set(panel.obs.columns) == {"series", "freq", "period", "value", "release"}
    assert set(panel.obs["series"]) == set(cfg.specs)
    assert not panel.obs.duplicated(["series", "period"]).any()
