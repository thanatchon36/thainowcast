"""Figures. Every figure is produced from the backtest/live tables, never from hand-typed numbers."""
from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ..config import Config  # noqa: E402
from .report import short_name  # noqa: E402

GROUP_COLORS = {
    "hard": "#2f4b7c", "alt_trends": "#d45087", "alt_lights": "#ff7c43", "alt_no2": "#665191",
    "alt_prices": "#a05195", "alt_mobility": "#ffa600", "target": "#111111",
}
MODEL_COLORS = {"rw": "#9e9e9e", "ar": "#555555", "bridge": "#2f4b7c", "midas": "#665191", "dfm": "#d45087", "enet": "#ff7c43", "lgbm": "#2a9d8f"}


def _save(fig, path: Path, rect: tuple[float, float, float, float] = (0, 0, 1, 1)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=rect)  # rect leaves room for a figure-level legend
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _ptime(periods: pd.Series) -> np.ndarray:
    """Period strings -> timestamps at period end, for plotting."""
    return np.array([pd.Period(p).to_timestamp(how="end") for p in periods])


GROUP_LABELS = {
    "hard": "Official statistics", "alt_prices": "Online prices", "alt_trends": "Google Trends",
    "alt_no2": "NO2 (Sentinel-5P)", "alt_mobility": "Mobility", "alt_lights": "Nighttime lights",
}


def plot_release_calendar(cfg: Config, path: Path) -> Path:
    order = list(GROUP_LABELS)
    specs = sorted(cfg.indicators.values(),
                   key=lambda s: (order.index(s.group) if s.group in order else len(order), s.release_lag_days, s.name_en))
    lags = [s.release_lag_days for s in specs]
    y = np.arange(len(specs))
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.barh(y, lags, height=0.7, color=[GROUP_COLORS.get(s.group, "#333") for s in specs], zorder=2)
    for yi, lag in zip(y, lags):
        ax.text(lag + 0.5, yi, f"{lag}", va="center", fontsize=7, color="#333", zorder=4,
                bbox={"boxstyle": "square,pad=0.15", "fc": "white", "ec": "none"})
    ax.set_yticks(y, [short_name(s.name_en) for s in specs], fontsize=7.5)
    # thin rules between groups
    for yi in np.flatnonzero([a.group != b.group for a, b in pairwise(specs)]):
        ax.axhline(yi + 0.5, color="#bbbbbb", lw=0.6, zorder=1)

    # target releases: one line per distinct lag, labelled in the empty band above the first bar
    xmax = max(lags + [t.release_lag_days for t in cfg.targets.values()]) + 4
    by_lag: dict[int, list[str]] = {}
    for t in cfg.targets.values():
        short = t.id.split("_")[0].upper()
        if short not in by_lag.setdefault(t.release_lag_days, []):
            by_lag[t.release_lag_days].append(short)
    for lag, shorts in by_lag.items():
        ax.axvline(lag, ls="--", lw=1, color=GROUP_COLORS["target"], zorder=3)
        right = lag > xmax / 2
        ax.text(lag + (-0.6 if right else 0.6), -1.25, f"{' / '.join(shorts)} release: day {lag}",
                ha="right" if right else "left", va="center", fontsize=7.5, fontweight="bold")

    ax.set_xlim(0, xmax)
    ax.set_ylim(len(specs) - 0.5, -2.0)
    ax.set_xlabel("days after the end of the reference period until publication", fontsize=9)
    ax.tick_params(axis="x", labelsize=8)
    ax.grid(axis="x", color="#e5e5e5", lw=0.6, zorder=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    groups = [g for g in order if any(s.group == g for s in specs)]
    handles = [plt.Rectangle((0, 0), 1, 1, color=GROUP_COLORS[g]) for g in groups]
    fig.legend(handles, [GROUP_LABELS[g] for g in groups], fontsize=7.5, ncol=3, frameon=False,
               loc="lower center", bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0.01, 0.045, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


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
    # below the axes, so it can never sit on a crisis-period dip
    ax.legend(fontsize=7.5, ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.08))
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
    fig, axes = plt.subplots(1, 2, figsize=(9, 2.15), sharey=True)
    for ax, abl, title in zip(axes, [abl_gdp, abl_cpi], ["GDP (origin PR)", "CPI (origin PR)"]):
        sets = [s for s in ["hard_only", "hard_trends", "hard_lights", "hard_no2", "hard_prices", "all"] if s in set(abl["feature_set"])]
        models = sorted(abl["model"].unique(), key=lambda m: list(MODEL_COLORS).index(m) if m in MODEL_COLORS else 99)
        w = 0.8 / max(1, len(models))
        for j, m in enumerate(models):
            vals = [abl[(abl["model"] == m) & (abl["feature_set"] == s)]["rel_to_hard"].mean() for s in sets]
            ax.bar(np.arange(len(sets)) + j * w - 0.4 + w / 2, vals, width=w, label=m, color=MODEL_COLORS.get(m, "#999"))
        ax.axhline(1, color="#111", lw=0.8, ls="--")
        ax.set_xticks(np.arange(len(sets)))
        ax.set_xticklabels([s.replace("hard_", "+") if s != "hard_only" else "hard only" for s in sets], fontsize=8)
        ax.set_title(title, fontsize=10)
    axes[0].set_ylabel("RMSFE relative to\nhard-data-only", fontsize=9)
    # Legend in one row at the top of the CPI panel, whose bars stay well below the GDP maximum that sets the
    # shared y-axis; the axis gets headroom so the row never touches a bar.
    top = max(ax.get_ylim()[1] for ax in axes)
    axes[0].set_ylim(0, top * 1.12)
    handles, labels = axes[0].get_legend_handles_labels()
    axes[1].legend(handles, labels, fontsize=7.5, ncol=len(labels), frameon=False, loc="upper center",
                   columnspacing=1.2, handlelength=1.4, borderaxespad=0.3)
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
    ax.legend(fontsize=7.5, frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1.0))
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


NIGHT = {  # the palette of the paper's night-lights figures, reused for the README preview
    "bg": "#03060d", "panel": "#0d1424", "rule": "#1f2a44", "ink": "#e8eefc", "muted": "#9fb0d0",
    "amber": "#f5a623", "pale": "#ffe8a3", "up": "#5ec9a0", "down": "#f07a95",
}
NIGHT_MODELS = {"rw": "#7d8db0", "ar": "#6f8fbf", "bridge": "#8fd0ff", "midas": "#ff9f6f", "dfm": "#c58fff", "enet": "#f5a623", "lgbm": "#5ec9a0"}


def _night_axes(ax, title: str) -> None:
    ax.set_facecolor(NIGHT["panel"])
    ax.set_title(title, fontsize=8, color=NIGHT["ink"], loc="left", pad=6)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(NIGHT["rule"])
    ax.tick_params(colors=NIGHT["muted"], labelsize=6.5, length=2)
    ax.grid(axis="y", color=NIGHT["rule"], lw=0.6)
    ax.set_axisbelow(True)


def _card(ax, t: dict, synthetic: bool) -> None:
    from matplotlib.patches import FancyBboxPatch

    ax.axis("off")
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.015,rounding_size=0.03", transform=ax.transAxes,
                                fc=NIGHT["panel"], ec=NIGHT["rule"], lw=0.8, clip_on=False))
    h = t["headline"]
    ax.text(0.05, 0.84, t["label"], fontsize=8.5, color=NIGHT["muted"], va="center")
    ax.text(0.95, 0.84, t["period"], fontsize=8.5, color=NIGHT["pale"], va="center", ha="right")
    ax.text(0.05, 0.52, f"{h['value']:.2f}%", fontsize=24, fontweight="bold", color=NIGHT["amber"], va="center")
    ax.text(0.05, 0.27, f"80% band {h['lo']:.2f} to {h['hi']:.2f}", fontsize=7.5, color=NIGHT["ink"], va="center")
    ax.text(0.05, 0.10, f"{h['model']} · {h['feature_set']}", fontsize=6.5, color=NIGHT["bg"], va="center",
            bbox=dict(boxstyle="round,pad=0.35", fc=NIGHT["amber"], ec="none"))
    ax.text(0.95, 0.10, f"official release {t['release_expected']}", fontsize=6.5, color=NIGHT["muted"], va="center", ha="right")
    # the whole model race for this target: one dot per model/feature set, the headline in amber
    strip = ax.inset_axes((0.52, 0.42, 0.43, 0.24))
    strip.set_facecolor("none")
    vals = [m["value"] for m in t["models"]]
    strip.scatter(vals, np.zeros(len(vals)), s=14, color=NIGHT["muted"], alpha=0.7, lw=0)
    strip.scatter([h["value"]], [0], s=34, color=NIGHT["amber"], zorder=3)
    strip.plot([h["lo"], h["hi"]], [0, 0], color=NIGHT["amber"], lw=1.2, alpha=0.5, zorder=2)
    strip.set_yticks([])
    strip.set_ylim(-0.6, 1.4)
    strip.tick_params(axis="x", colors=NIGHT["muted"], labelsize=5.5, length=2, pad=1)
    for side in ("top", "right", "left"):
        strip.spines[side].set_visible(False)
    strip.spines["bottom"].set_color(NIGHT["rule"])
    strip.text(0, 0.95, f"{len(vals)} model nowcasts", fontsize=5.5, color=NIGHT["muted"], transform=strip.transAxes, va="top")


def plot_dashboard_preview(live: dict, evolution: dict[str, pd.DataFrame], path: Path) -> Path:
    """A one-image summary of the live dashboard for the README: headline cards, the nowcast evolution
    across origins and the news decomposition, in the night palette of the paper's maps."""
    fig = plt.figure(figsize=(10, 5.6), facecolor=NIGHT["bg"])
    gs = fig.add_gridspec(2, 6, left=0.05, right=0.975, top=0.86, bottom=0.12, hspace=0.42, wspace=0.9, height_ratios=[0.9, 1.15])
    fig.text(0.05, 0.945, "thainowcast", fontsize=14, fontweight="bold", color=NIGHT["amber"], va="center")
    fig.text(0.975, 0.945, f"live nowcast · information set as of {live['asof']}", fontsize=8, color=NIGHT["muted"], va="center", ha="right")

    for col, tid in zip((slice(0, 3), slice(3, 6)), ("gdp_yoy", "cpi_yoy")):
        _card(fig.add_subplot(gs[0, col]), live["targets"][tid], bool(live.get("synthetic")))

    for col, tid in zip((slice(0, 2), slice(2, 4)), ("gdp_yoy", "cpi_yoy")):
        t = live["targets"][tid]
        ax = fig.add_subplot(gs[1, col])
        _night_axes(ax, f"{t['label']} {t['period']}: nowcast by origin")
        evo = evolution.get(tid)
        if evo is None or evo.empty:
            ax.text(0.5, 0.5, "no evolution", ha="center", va="center", color=NIGHT["muted"], transform=ax.transAxes)
            continue
        head = (t["headline"]["model"], t["headline"]["feature_set"])
        origins = sorted(evo["origin"].unique())
        horizon = evo.drop_duplicates("origin").set_index("origin")["horizon"]
        shown = {("ar", "none"), ("bridge", "all"), ("dfm", "all"), ("enet", "all"), head}
        for (model, fs), g in evo.groupby(["model", "feature_set"]):
            if (model, fs) not in shown:
                continue
            g = g.sort_values("origin")
            x = [origins.index(o) for o in g["origin"]]
            is_head = (model, fs) == head
            color = NIGHT_MODELS.get(model, NIGHT["muted"])
            ax.plot(x, g["nowcast"], marker="o", ms=3.5 if is_head else 2.5, lw=2 if is_head else 1, color=color,
                    alpha=1 if is_head else 0.75, label=f"{model} ({fs})" + (" · headline" if is_head else ""), zorder=3 if is_head else 2)
            if is_head and g["lo"].notna().any():
                ax.fill_between(x, g["lo"], g["hi"], color=color, alpha=0.12, lw=0)
        ax.set_xticks(range(len(origins)))
        ax.set_xticklabels([f"{horizon[o]}\n{o}" for o in origins])
        ax.set_ylabel("%", color=NIGHT["muted"], fontsize=7)
        ax.legend(fontsize=5.5, frameon=False, labelcolor=NIGHT["muted"], loc="best")

    ax = fig.add_subplot(gs[1, 4:])
    news = live.get("news")
    if news and news.get("by_series"):
        rows = sorted(news["by_series"], key=lambda r: abs(r["impact"]), reverse=True)[:8]
        rows = sorted(rows, key=lambda r: r["impact"])
        _night_axes(ax, f"GDP news: {news['nowcast_prev']:.2f} → {news['nowcast_new']:.2f} since {news['from']}")
        ax.barh([r["series"] for r in rows], [r["impact"] for r in rows],
                color=[NIGHT["down"] if r["impact"] < 0 else NIGHT["up"] for r in rows], height=0.65)
        ax.axvline(0, color=NIGHT["muted"], lw=0.6)
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", color=NIGHT["rule"], lw=0.6)
        ax.set_xlabel("impact on the nowcast (pp)", color=NIGHT["muted"], fontsize=6.5)
    else:
        _night_axes(ax, "GDP news")
        ax.text(0.5, 0.5, "no new releases between origins", ha="center", va="center", color=NIGHT["muted"], transform=ax.transAxes, fontsize=7)

    fig.text(0.05, 0.035, "Full dashboard: dashboard/index.html (static) · app/streamlit_app.py (interactive)", fontsize=6.5, color=NIGHT["muted"])
    if live.get("synthetic"):
        fig.text(0.975, 0.035, "SYNTHETIC DATA · nothing here describes the Thai economy", fontsize=6.5, color=NIGHT["down"], ha="right", fontweight="bold")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, facecolor=NIGHT["bg"])
    plt.close(fig)
    return path
