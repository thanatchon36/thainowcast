"""Configuration: indicator registry (config/indicators.yaml) and project paths."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "indicators.yaml"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
PAPER_DIR = ROOT / "paper"
DASHBOARD_DIR = ROOT / "dashboard"


@dataclass(frozen=True)
class SeriesSpec:
    """One row of the registry: a target or an indicator."""

    id: str
    name_th: str
    name_en: str
    agency: str
    group: str
    frequency: str  # "M" or "Q"
    start: str
    release_lag_days: int
    transform: str
    fetch: str
    file: str
    end: str | None = None

    @property
    def start_period(self) -> pd.Period:
        return pd.Period(self.start, freq=self.frequency)

    @property
    def end_period(self) -> pd.Period | None:
        return pd.Period(self.end, freq=self.frequency) if self.end else None

    @property
    def is_target(self) -> bool:
        return self.group == "target"


@dataclass
class Config:
    targets: dict[str, SeriesSpec]
    indicators: dict[str, SeriesSpec]
    feature_sets: dict[str, list[str]]  # set name -> list of groups
    backtest: dict

    @property
    def specs(self) -> dict[str, SeriesSpec]:
        return {**self.targets, **self.indicators}

    def set_columns(self, set_name: str) -> list[str]:
        """Indicator ids belonging to a feature set (preserves registry order)."""
        if set_name == "none":
            return []
        groups = set(self.feature_sets[set_name])
        return [sid for sid, s in self.indicators.items() if s.group in groups]

    @property
    def groups(self) -> list[str]:
        seen: list[str] = []
        for s in self.indicators.values():
            if s.group not in seen:
                seen.append(s.group)
        return seen


def _spec(sid: str, d: dict, default_group: str | None = None) -> SeriesSpec:
    d = dict(d)
    group = d.pop("group", default_group)
    return SeriesSpec(id=sid, group=group, **d)


def load_config(path: Path | str = CONFIG_PATH) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    targets = {k: _spec(k, v, "target") for k, v in raw["targets"].items()}
    indicators = {k: _spec(k, v) for k, v in raw["indicators"].items()}
    return Config(targets=targets, indicators=indicators, feature_sets=raw["feature_sets"], backtest=raw["backtest"])
