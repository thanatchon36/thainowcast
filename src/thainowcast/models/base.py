"""Common interface: every model implements ``nowcast(y, X, target, origin) -> float``.

``y``      released history of the target (PeriodIndex at the target frequency)
``X``      monthly transformed indicators known at ``origin`` (NaN at the ragged edge)
``target`` the period being nowcast
``origin`` the date the nowcast is made
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class NowcastModel(ABC):
    name: str = "base"

    def __init__(self, **params):
        self.params = params

    @abstractmethod
    def nowcast(self, y: pd.Series, X: pd.DataFrame, target: pd.Period, origin: pd.Timestamp) -> float:
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.params})"


def steps_ahead(y: pd.Series, target: pd.Period) -> int:
    return int(target.ordinal - y.index[-1].ordinal)


def fallback_ar(y: pd.Series, target: pd.Period) -> float:
    """Used when a model cannot be estimated at an origin (too little data etc.)."""
    from .benchmarks import AR

    return AR().nowcast(y, pd.DataFrame(), target, pd.NaT)
