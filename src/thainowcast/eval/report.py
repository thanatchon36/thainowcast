"""Markdown tables for the paper. Every table is regenerated from the result CSVs."""
from __future__ import annotations

from pathlib import Path

import re

import numpy as np
import pandas as pd

from ..config import Config

MODEL_LABEL = {"rw": "Random walk", "ar": "AR(p)", "bridge": "Bridge (PCA)", "midas": "MIDAS", "dfm": "DFM (mixed-freq.)", "enet": "Elastic net", "lgbm": "LightGBM"}
SET_LABEL = {"none": "–", "hard_only": "hard only", "hard_trends": "hard + Trends", "hard_lights": "hard + lights", "hard_no2": "hard + NO2", "hard_prices": "hard + online prices", "all": "all"}
GROUP_LABEL = {"target": "target", "hard": "hard", "alt_trends": "Trends", "alt_lights": "lights", "alt_no2": "NO2", "alt_prices": "online prices", "alt_mobility": "mobility"}
REGIME_LABEL = {"full": "full sample", "pre_covid": "pre-COVID", "covid": "COVID", "post_covid": "post-COVID"}

MINUS = "−"
# a cell that reads as a number: optional bold, sign, digits, DM stars, or a band "a–b"
_NUMERIC = re.compile(r"(\*\*)?[−-]?\d+(\.\d+)?(\*{1,3})?(–[−-]?\d+(\.\d+)?)?(\*\*)?")


def num(v: float, fmt: str = "{:.2f}") -> str:
    """A float for a table cell: typographic minus, and no '-0.00' when the value rounds to zero."""
    s = fmt.format(v)
    if float(s) == 0:
        s = s.lstrip("-")
    return s.replace("-", MINUS)


def md_table(df: pd.DataFrame, floatfmt: str = "{:.2f}", index: bool = False) -> str:
    """Pipe table; columns whose every non-empty cell is numeric are right-aligned."""
    if index:
        df = df.reset_index()
    cols = list(df.columns)

    def fmt(v):
        if isinstance(v, float):
            return "" if np.isnan(v) else num(v, floatfmt)
        if isinstance(v, (pd.Timestamp,)):
            return v.strftime("%Y-%m-%d")
        return str(v)

    body = [[fmt(row[c]) for c in cols] for _, row in df.iterrows()]
    right = [bool(cells) and all(_NUMERIC.fullmatch(x) for x in cells) for cells in ([r[j] for r in body if r[j]] for j in range(len(cols)))]
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join("--:" if r else "---" for r in right) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


def _blank_repeats(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Print a grouping label (the model) only on the first row of its group."""
    df = df.copy()
    df.loc[df[col].eq(df[col].shift()), col] = ""
    return df


def _order(df: pd.DataFrame) -> pd.DataFrame:
    """Models in MODEL_LABEL order, feature sets from narrowest to widest."""
    mo, so = list(MODEL_LABEL), list(SET_LABEL)
    key = df["model"].map(lambda m: mo.index(m) if m in mo else 99) * 100 + df["feature_set"].map(lambda s: so.index(s) if s in so else 99)
    return df.assign(_k=key).sort_values("_k").drop(columns="_k")


def stars(p: float) -> str:
    if not np.isfinite(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def short_name(name: str, width: int = 44) -> str:
    """A series name for a table or axis: drop the '(TH)' tag and, if still too long, a trailing parenthetical."""
    name = name.replace(" (TH)", "")
    if len(name) > width and name.endswith(")") and " (" in name:
        name = name[: name.rindex(" (")]
    return name


def latin_agency(agency: str) -> str:
    """The PDF font has no Thai glyphs: drop Thai words, then any parentheses left with no letters in them
    ('OIE (สศอ.)' -> 'OIE', not 'OIE (.)')."""
    s = re.sub(r"[฀-๿]+", "", agency)
    return re.sub(r"\s*\([^A-Za-z0-9]*\)", "", s).strip()


def data_audit_table(cfg: Config, panel) -> pd.DataFrame:
    rows = []
    for sid, spec in cfg.specs.items():
        s = panel.actual(sid)
        rows.append(
            {
                "id": sid,
                "series": spec.name_en,
                "source": latin_agency(spec.agency),
                "group": GROUP_LABEL.get(spec.group, spec.group),
                "freq": spec.frequency,
                "first": str(s.index[0]),
                "last": str(s.index[-1]),
                "lag (days)": spec.release_lag_days,
                "transform": spec.transform,
                "status": "synthetic" if sid in panel.synthetic_ids else "real",
            }
        )
    df = pd.DataFrame(rows)
    # a column with one value in every row says nothing; the caption reports the run's status instead
    return df.drop(columns="status") if df["status"].nunique() == 1 else df


def rmsfe_table(summary: pd.DataFrame, dm: pd.DataFrame, feature_sets: list[str], horizons: list[str], regime: str = "full") -> pd.DataFrame:
    """RMSFE with DM stars (vs AR) in a model x (feature set, horizon) layout."""
    short = {"hard_only": "hard", "all": "all"}  # the caption spells these out
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
                col = f"{short.get(fs, SET_LABEL.get(fs, fs))} {h}" if m not in ("rw", "ar") else h
                row[col] = f"{v['rmsfe'].iloc[0]:.2f}{stars(p)}"
        rows.append(row)
    out = pd.DataFrame(rows).fillna("")
    return out


def regime_table(summary: pd.DataFrame, horizon: str, feature_set: str) -> pd.DataFrame:
    s = summary[(summary["horizon"] == horizon) & (summary["feature_set"].isin([feature_set, "none"]))]
    piv = s.pivot_table(index="model", columns="regime", values="rmsfe")
    piv = piv.reindex([m for m in MODEL_LABEL if m in piv.index])
    piv.index = [MODEL_LABEL[m] for m in piv.index]
    cols = [c for c in REGIME_LABEL if c in piv.columns]
    return piv[cols].rename(columns=REGIME_LABEL).reset_index().rename(columns={"index": "model"})


def ablation_paper_table(abl: pd.DataFrame) -> pd.DataFrame:
    """Ablation at one origin: model, feature set, RMSFE and the ratio to the same model on hard data only."""
    a = _order(abl)
    out = pd.DataFrame({
        "model": a["model"].map(MODEL_LABEL),
        "feature set": a["feature_set"].map(lambda s: SET_LABEL.get(s, s)),
        "RMSFE": a["rmsfe"].astype(float),
        "relative to hard only": a["rel_to_hard"].astype(float),
    })
    return _blank_repeats(out, "model")


def coverage_paper_table(cov: pd.DataFrame, horizon: str) -> pd.DataFrame:
    """Coverage and width of the conformal bands at one origin, for the benchmarks and the two extreme feature sets."""
    c = _order(cov[(cov["horizon"] == horizon) & cov["feature_set"].isin(["none", "hard_only", "all"])])
    out = pd.DataFrame({
        "model": c["model"].map(MODEL_LABEL),
        "feature set": c["feature_set"].map(lambda s: SET_LABEL.get(s, s)),
        "coverage": c["coverage"].astype(float),
        "width (pp)": c["width"].astype(float),
    })
    return _blank_repeats(out, "model")


def live_table(live: dict) -> pd.DataFrame:
    """Current nowcasts: one row per model and feature set, one column pair (nowcast, 80% band) per target.
    The headline nowcast of each target is set in bold."""
    targets = list(live["targets"])
    cells: dict[tuple[str, str], dict[str, str]] = {}
    for tid in targets:
        t = live["targets"][tid]
        h = t["headline"]
        short = "GDP" if tid.startswith("gdp") else "CPI"
        name = f"{short} {t['period']}"
        for m in t["models"]:
            v = num(m["value"])
            if (m["model"], m["feature_set"]) == (h["model"], h["feature_set"]):
                v = f"**{v}**"
            row = cells.setdefault((m["model"], m["feature_set"]), {})
            row[name] = v
            row[f"{short} 80% band"] = f"{num(m['lo'])}–{num(m['hi'])}"
    keys = _order(pd.DataFrame(list(cells), columns=["model", "feature_set"]))
    rows = []
    for m, fs in keys.itertuples(index=False):
        rows.append({"model": MODEL_LABEL.get(m, m), "feature set": SET_LABEL.get(fs, fs), **cells[(m, fs)]})
    out = pd.DataFrame(rows).fillna("")
    return _blank_repeats(out, "model")


def news_table(news: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """News decomposition by series: the impact on the nowcast (pp) and the summed surprise of the releases."""
    top = news.groupby("series").agg(impact=("impact", "sum"), news=("news", "sum"), releases=("news", "size")).sort_values("impact")
    return pd.DataFrame({
        "series": [short_name(cfg.specs[s].name_en) if s in cfg.specs else s for s in top.index],
        "releases": top["releases"].astype(int).values,
        "surprise": [num(v, "{:.2f}") for v in top["news"]],
        "impact (pp)": [num(v, "{:.3f}") for v in top["impact"]],
    })
