"""Markdown tables for the paper. Every table is regenerated from the result CSVs."""
from __future__ import annotations

from pathlib import Path

import re

import numpy as np
import pandas as pd

from ..config import Config

MODEL_LABEL = {"rw": "Random walk", "ar": "AR(p)", "bridge": "Bridge (PCA)", "midas": "MIDAS", "dfm": "DFM (mixed-freq.)", "enet": "Elastic net", "lgbm": "LightGBM"}
SET_LABEL = {"none": "–", "hard_only": "hard only", "hard_trends": "hard + Trends", "hard_lights": "hard + lights", "hard_no2": "hard + NO2", "hard_prices": "hard + online prices", "all": "all"}


def md_table(df: pd.DataFrame, floatfmt: str = "{:.2f}", index: bool = False) -> str:
    if index:
        df = df.reset_index()
    cols = list(df.columns)

    def fmt(v):
        if isinstance(v, float):
            return "" if np.isnan(v) else floatfmt.format(v)
        if isinstance(v, (pd.Timestamp,)):
            return v.strftime("%Y-%m-%d")
        return str(v)

    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(fmt(row[c]) for c in cols) + " |")
    return "\n".join(lines)


def stars(p: float) -> str:
    if not np.isfinite(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def data_audit_table(cfg: Config, panel) -> pd.DataFrame:
    rows = []
    for sid, spec in cfg.specs.items():
        s = panel.actual(sid)
        rows.append(
            {
                "id": sid,
                "series": spec.name_en,
                "source": re.sub(r"\s*\(\s*\)", "", re.sub(r"[\u0E00-\u0E7F]+", "", spec.agency)).strip(),  # Latin only (PDF font)
                "group": spec.group,
                "freq": spec.frequency,
                "first": str(s.index[0]),
                "last": str(s.index[-1]),
                "lag (days)": spec.release_lag_days,
                "transform": spec.transform,
                "status": "SYNTHETIC" if sid in panel.synthetic_ids else "real",
            }
        )
    return pd.DataFrame(rows)


def rmsfe_table(summary: pd.DataFrame, dm: pd.DataFrame, feature_sets: list[str], horizons: list[str], regime: str = "full") -> pd.DataFrame:
    """RMSFE with DM stars (vs AR) in a model x (feature set, horizon) layout."""
    s = summary[(summary["regime"] == regime)]
    d = dm.set_index(["feature_set", "model", "horizon"])["p_value"] if len(dm) else pd.Series(dtype=float)
    rows = []
    models = [m for m in MODEL_LABEL if m in set(s["model"])]
    for m in models:
        row = {"model": MODEL_LABEL[m]}
        for fs in (["none"] if m in ("rw", "ar") else feature_sets):
            for h in horizons:
                v = s[(s["model"] == m) & (s["feature_set"] == fs) & (s["horizon"] == h)]
                if v.empty:
                    continue
                p = d.get((fs, m, h), np.nan) if len(d) else np.nan
                col = f"{SET_LABEL.get(fs, fs)} {h}" if m not in ("rw", "ar") else h
                row[col] = f"{v['rmsfe'].iloc[0]:.2f}{stars(p)}"
        rows.append(row)
    out = pd.DataFrame(rows).fillna("")
    return out


def regime_table(summary: pd.DataFrame, horizon: str, feature_set: str) -> pd.DataFrame:
    s = summary[(summary["horizon"] == horizon) & (summary["feature_set"].isin([feature_set, "none"]))]
    piv = s.pivot_table(index="model", columns="regime", values="rmsfe")
    piv = piv.reindex([m for m in MODEL_LABEL if m in piv.index])
    piv.index = [MODEL_LABEL[m] for m in piv.index]
    cols = [c for c in ["full", "pre_covid", "covid", "post_covid"] if c in piv.columns]
    return piv[cols].reset_index().rename(columns={"index": "model"})
