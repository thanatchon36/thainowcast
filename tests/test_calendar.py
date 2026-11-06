import pandas as pd

from thainowcast.data.calendar import period_end, release_date


def test_month_end_and_lag():
    p = pd.Period("2024-02", freq="M")
    assert period_end(p) == pd.Timestamp("2024-02-29")
    assert release_date(p, 30) == pd.Timestamp("2024-03-30")


def test_quarter_release():
    q = pd.Period("2026Q3", freq="Q")
    assert period_end(q) == pd.Timestamp("2026-09-30")
    assert release_date(q, 48) == pd.Timestamp("2026-11-17")
