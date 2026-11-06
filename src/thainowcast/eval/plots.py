"""Figures. Every figure is produced from the backtest/live tables, never from hand-typed numbers."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ..config import Config  # noqa: E402

GROUP_COLORS = {
    "hard": "#2f4b7c", "alt_trends": "#d45087", "alt_lights": "#ff7c43", "alt_no2": "#665191",
    "alt_prices": "#a05195", "alt_mobility": "#ffa600", "target": "#111111",
}
MODEL_COLORS = {"rw": "#9e9e9e", "ar": "#555555", "bridge": "#2f4b7c", "midas": "#665191", "dfm": "#d45087", "enet": "#ff7c43", "lgbm": "#2a9d8f"}


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _ptime(periods: pd.Series) -> np.ndarray:
    """Period strings -> timestamps at period end, for plotting."""
    return np.array([pd.Period(p).to_timestamp(how="end") for p in periods])


def plot_release_calendar(cfg: Config, path: Path) -> Path:
    specs = sorted(cfg.indicators.values(), key=lambda s: (s.group, s.release_lag_days))
    fig, ax = plt.subplots(figsize=(8, 6.5))
    names = [f"{s.name_en[:38]}" for s in specs]
    lags = [s.release_lag_days for s in specs]
    colors = [GROUP_COLORS.get(s.group, "#333") for s in specs]
    ax.barh(names, lags, color=colors)
    for t in cfg.targets.values():
        ax.axvline(t.release_lag_days, ls="--", lw=1, color=GROUP_COLORS["target"])
        ax.text(t.release_lag_days + 0.5, 0.2, f"{t.id} release", rotation=90, fontsize=7, va="bottom")
    ax.set_xlabel("days after the end of the reference period until publication")
    ax.set_title("Release calendar used by the pseudo-real-time engine")
    ax.invert_yaxis()
    ax.tick_params(axis="y", labelsize=7)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for g, c in GROUP_COLORS.items() if g != "target"]
    ax.legend(handles, [g for g in GROUP_COLORS if g != "target"], fontsize=7, loc="lower right")
    return _save(fig, path)


def plot_targets(panel, cfg: Config, path: Path) -> Path:
    fig, axes = plt.subplots(2, 1, figsize=(8, 5.5), sharex=False)
    for ax, tid, title in zip(axes, ["gdp_yoy", "cpi_yoy"], ["Real GDP growth, y-o-y (%)", "Headline CPI inflation, y-o-y (%)"]):
        s = panel.actual(tid)
        ax.plot(s.index.to_timestamp(how="end"), s.values, color="#111", lw=1.3)
        ax.axhline(0, color="#999", lw=0.6)
        for name, (a, b) in cfg.backtest["regimes"].items():
            ax.axvspan(pd.Timestamp(a), min(pd.Timestamp(b), s.index[-1].to_timestamp(how="end")), alpha=0.08, color={"pre_covid": "#2f4b7c", "covid": "#d45087", "post_covid": "#2a9d8f"}[name])
        ax.set_title(title + ("  [SYNTHETIC]" if tid in panel.synthetic_ids else ""), fontsize=10)
    return _save(fig, path)


def plot_nowcast_vs_actual(bt: pd.DataFrame, horizon: str, selections: list[tuple[str, str, str]], path: Path, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    sub = bt[bt["horizon"] == horizon]
    first = sub[(sub["model"] == selections[0][0]) & (sub["feature_set"] == selections[0][1])].sort_values("period")
    t = _ptime(first["period"])
    ax.plot(t, first["actual"], color="#111", lw=1.6, label="actual (first value available)")
    if first["lo"].notna().any():
        ax.fill_between(t, first["lo"], first["hi"], color=MODEL_COLORS.get(selections[0][0], "#999"), alpha=0.15, label=f"80% conformal band ({selections[0][2]})")
    for model, fs, label in selections:
        s = sub[(sub["model"] == model) & (sub["feature_set"] == fs)].sort_values("period")
        ax.plot(_ptime(s["period"]), s["nowcast"], lw=1.2, color=MODEL_COLORS.get(model, "#999"), label=label, marker="o", ms=2)
    ax.axhline(0, color="#999", lw=0.6)
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=7, ncol=2)
    return _save(fig, path)


def plot_rmsfe_by_horizon(summary: pd.DataFrame, feature_set: str, path: Path, title: str) -> Path:
    s = summary[(summary["regime"] == "full") & (summary["feature_set"].isin([feature_set, "none"]))]
    models = [m for m in ["rw", "ar", "bridge", "midas", "dfm", "enet", "lgbm"] if m in set(s["model"])]
    horizons = sorted(s["horizon"].unique())
    fig, ax = plt.subplots(figsize=(8, 3.8))
    w = 0.8 / max(1, len(horizons))
    for j, h in enumerate(horizons):
        vals = [s[(s["model"] == m) & (s["horizon"] == h)]["rmsfe"].mean() for m in models]
        ax.bar(np.arange(len(models)) + j * w - 0.4 + w / 2, vals, width=w, label=h, color=plt.cm.viridis(j / max(1, len(horizons) - 1)) if len(horizons) > 1 else "#2f4b7c")
    ax.set_xticks(np.arange(len(models)))
    ax.set_xticklabels(models)
    ax.set_ylabel("RMSFE (pp)")
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8, title="origin")
    return _save(fig, path)


def plot_ablation(abl_gdp: pd.DataFrame, abl_cpi: pd.DataFrame, path: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8), sharey=True)
    for ax, abl, title in zip(axes, [abl_gdp, abl_cpi], ["GDP (origin PR)", "CPI (origin PR)"]):
        sets = [s for s in ["hard_only", "hard_trends", "hard_lights", "hard_no2", "hard_prices", "all"] if s in set(abl["feature_set"])]
        models = sorted(abl["model"].unique(), key=lambda m: list(MODEL_COLORS).index(m) if m in MODEL_COLORS else 99)
        w = 0.8 / max(1, len(models))
        for j, m in enumerate(models):
            vals = [abl[(abl["model"] == m) & (abl["feature_set"] == s)]["rel_to_hard"].mean() for s in sets]
            ax.bar(np.arange(len(sets)) + j * w - 0.4 + w / 2, vals, width=w, label=m, color=MODEL_COLORS.get(m, "#999"))
        ax.axhline(1, color="#111", lw=0.8, ls="--")
        ax.set_xticks(np.arange(len(sets)))
        ax.set_xticklabels([s.replace("hard_", "+") if s != "hard_only" else "hard only" for s in sets], rotation=20, fontsize=8)
        ax.set_title(title, fontsize=10)
    axes[0].set_ylabel("RMSFE relative to hard-data-only")
    axes[0].legend(fontsize=7)
    return _save(fig, path)


def plot_evolution(evo: pd.DataFrame, path: Path, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    for (model, fs), g in evo.groupby(["model", "feature_set"]):
        g = g.sort_values("origin")
        ax.plot(g["origin"], g["nowcast"], marker="o", ms=4, lw=1.2, color=MODEL_COLORS.get(model, "#999"), label=f"{model} ({fs})", alpha=0.9)
        if g["lo"].notna().any() and model == evo.attrs.get("headline_model") and fs == evo.attrs.get("headline_set"):
            ax.fill_between(g["origin"], g["lo"], g["hi"], color=MODEL_COLORS.get(model, "#999"), alpha=0.15)
    ax.set_title(title, fontsize=10)
    ax.set_ylabel("nowcast (%)")
    ax.legend(fontsize=6, ncol=3)
    fig.autofmt_xdate()
    return _save(fig, path)


def plot_news(news: pd.DataFrame, path: Path, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    if news is None or news.empty:
        ax.text(0.5, 0.5, "no new releases between the two origins", ha="center", va="center")
        return _save(fig, path)
    agg = news.groupby("series")["impact"].sum().sort_values()
    colors = ["#d45087" if v < 0 else "#2a9d8f" for v in agg.values]
    ax.barh(agg.index, agg.values, color=colors)
    ax.axvline(0, color="#111", lw=0.8)
    ax.set_xlabel("impact on the nowcast (pp)")
    ax.set_title(title, fontsize=10)
    ax.tick_params(axis="y", labelsize=8)
    return _save(fig, path)


def plot_dashboard_preview(live: dict, path: Path) -> Path:
    """A one-image summary used in the README in place of a screen recording."""
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2))
    for ax, tid in zip(axes, ["gdp_yoy", "cpi_yoy"]):
        t = live["targets"][tid]
        ax.axis("off")
        head = t["headline"]
        ax.text(0.02, 0.85, t["label"], fontsize=11, weight="bold")
        ax.text(0.02, 0.62, f"{t['period']}: {head['value']:.2f}%", fontsize=20)
        ax.text(0.02, 0.45, f"80% band {head['lo']:.2f} to {head['hi']:.2f}  |  {head['model']} ({head['feature_set']})", fontsize=8)
        ax.text(0.02, 0.25, f"as of {live['asof']}", fontsize=8, color="#555")
        if live.get("synthetic"):
            ax.text(0.02, 0.05, "SYNTHETIC DATA", fontsize=9, color="#d45087", weight="bold")
    return _save(fig, path)
