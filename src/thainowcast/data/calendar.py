"""Release calendar: when does an observation for a given reference period become public?"""
from __future__ import annotations

import pandas as pd


def period_end(p: pd.Period) -> pd.Timestamp:
    """Last calendar day of the reference period (midnight)."""
    return p.to_timestamp(how="end").normalize()


def release_date(p: pd.Period, lag_days: int) -> pd.Timestamp:
    """Publication date = end of reference period + typical lag."""
    return period_end(p) + pd.Timedelta(days=int(lag_days))


def release_dates(index: pd.PeriodIndex, lag_days: int) -> pd.DatetimeIndex:
    return pd.DatetimeIndex([release_date(p, lag_days) for p in index])


def month_end_ts(p: pd.Period) -> pd.Timestamp:
    """Alias used for nowcast origins (end of a month, as a Timestamp)."""
    return period_end(p)
