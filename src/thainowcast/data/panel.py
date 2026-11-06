"""Panel: every observation together with the date it became public.

The models never touch the raw files. They only ever see the output of
:meth:`Panel.wide_available` / :meth:`Panel.series_available`, which keep an
observation only if ``release <= asof``. Keeping the information-set logic in one
place is what makes the leakage test (tests/test_leakage.py) meaningful.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import SeriesSpec
from .calendar import release_dates


@dataclass
class Panel:
    obs: pd.DataFrame  # columns: series, freq, period (str), value, release (Timestamp)
    specs: dict[str, SeriesSpec]
    synthetic_ids: set[str] = field(default_factory=set)

    # ------------------------------------------------------------------ build
    @classmethod
    def from_series(
        cls,
        series: dict[str, pd.Series],
        specs: dict[str, SeriesSpec],
        synthetic_ids: set[str] | list[str] | tuple[str, ...] = (),
    ) -> "Panel":
        frames = []
        for sid, s in series.items():
            spec = specs[sid]
            s = s.dropna()
            idx = pd.PeriodIndex(s.index, freq=spec.frequency)
            frames.append(
                pd.DataFrame(
                    {
                        "series": sid,
                        "freq": spec.frequency,
                        "period": idx.astype(str),
                        "value": s.to_numpy(dtype=float),
                        "release": release_dates(idx, spec.release_lag_days),
                    }
                )
            )
        obs = pd.concat(frames, ignore_index=True)
        return cls(obs=obs, specs=specs, synthetic_ids=set(synthetic_ids))

    # ------------------------------------------------------------------ spans
    def span(self, freq: str) -> tuple[pd.Period, pd.Period]:
        sub = self.obs.loc[self.obs["freq"] == freq, "period"]
        idx = pd.PeriodIndex(sub.unique(), freq=freq)
        return idx.min(), idx.max()

    @property
    def is_synthetic(self) -> bool:
        return bool(self.synthetic_ids)

    # ------------------------------------------------------- information sets
    def wide_available(self, asof: pd.Timestamp, ids: list[str], freq: str = "M") -> pd.DataFrame:
        """Wide frame of raw levels known at ``asof`` (NaN where not yet published)."""
        asof = pd.Timestamp(asof)
        mask = (self.obs["release"] <= asof) & (self.obs["freq"] == freq) & self.obs["series"].isin(ids)
        sub = self.obs.loc[mask]
        lo, hi = self.span(freq)
        full = pd.period_range(lo, hi, freq=freq)
        if sub.empty:
            return pd.DataFrame(np.nan, index=full, columns=list(ids), dtype=float)
        wide = sub.pivot(index="period", columns="series", values="value")
        wide.index = pd.PeriodIndex(wide.index, freq=freq)
        return wide.sort_index().reindex(full).reindex(columns=list(ids)).astype(float)

    def series_available(self, asof: pd.Timestamp, sid: str) -> pd.Series:
        """Released history of one series (used for the target)."""
        asof = pd.Timestamp(asof)
        spec = self.specs[sid]
        sub = self.obs[(self.obs["series"] == sid) & (self.obs["release"] <= asof)]
        idx = pd.PeriodIndex(sub["period"], freq=spec.frequency)
        return pd.Series(sub["value"].to_numpy(dtype=float), index=idx, name=sid).sort_index()

    def actual(self, sid: str) -> pd.Series:
        """Full series regardless of release date — ONLY for scoring, never for features."""
        spec = self.specs[sid]
        sub = self.obs[self.obs["series"] == sid]
        idx = pd.PeriodIndex(sub["period"], freq=spec.frequency)
        return pd.Series(sub["value"].to_numpy(dtype=float), index=idx, name=sid).sort_index()

    def release_of(self, sid: str, period: pd.Period) -> pd.Timestamp:
        sub = self.obs[(self.obs["series"] == sid) & (self.obs["period"] == str(period))]
        return pd.Timestamp(sub["release"].iloc[0]) if len(sub) else pd.NaT

    def availability_table(self, asof: pd.Timestamp) -> pd.DataFrame:
        """Which reference period of each series is known at ``asof`` (the data flow)."""
        asof = pd.Timestamp(asof)
        rows = []
        for sid, spec in self.specs.items():
            sub = self.obs[(self.obs["series"] == sid) & (self.obs["release"] <= asof)]
            if sub.empty:
                last, rel = "", pd.NaT
            else:
                idx = pd.PeriodIndex(sub["period"], freq=spec.frequency)
                pos = int(idx.argmax())
                last, rel = str(idx[pos]), pd.Timestamp(sub["release"].iloc[pos])
            rows.append(
                {
                    "series": sid,
                    "name_en": spec.name_en,
                    "name_th": spec.name_th,
                    "group": spec.group,
                    "agency": spec.agency,
                    "freq": spec.frequency,
                    "lag_days": spec.release_lag_days,
                    "last_period": last,
                    "released": rel,
                    "synthetic": sid in self.synthetic_ids,
                }
            )
        return pd.DataFrame(rows)

    # -------------------------------------------------------------- persist
    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.obs.to_csv(path, index=False)
        meta = {"synthetic_ids": sorted(self.synthetic_ids), "n_obs": int(len(self.obs))}
        path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str, specs: dict[str, SeriesSpec]) -> "Panel":
        path = Path(path)
        obs = pd.read_csv(path, parse_dates=["release"])
        meta_path = path.with_suffix(".meta.json")
        synth = set(json.loads(meta_path.read_text(encoding="utf-8"))["synthetic_ids"]) if meta_path.exists() else set()
        return cls(obs=obs, specs=specs, synthetic_ids=synth)
