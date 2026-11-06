"""ThaiNowcast command line: python -m thainowcast.cli <command>."""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import pandas as pd

from .config import DASHBOARD_DIR, PAPER_DIR, PROCESSED_DIR, RAW_DIR, load_config

TARGETS_DEFAULT = ["gdp_yoy", "cpi_yoy"]


def _panel(cfg):
    from .data.loaders import load_panel

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return load_panel(cfg, RAW_DIR)


def cmd_synthetic(args):
    from .data.synthetic import generate

    cfg = load_config()
    paths = generate(cfg, RAW_DIR, seed=args.seed)
    print(f"wrote {len(paths)} synthetic_* files to {RAW_DIR} (pipeline tests only)")


def cmd_data(args):
    cfg = load_config()
    have_real = [s for s in cfg.specs.values() if (RAW_DIR / s.file).exists()]
    have_syn = [s for s in cfg.specs.values() if (RAW_DIR / f"synthetic_{s.file}").exists()]
    if not have_real and not have_syn:
        print("no raw data found; generating synthetic test data (make synthetic)", file=sys.stderr)
        cmd_synthetic(args)
    panel = _panel(cfg)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    panel.save(PROCESSED_DIR / "panel.csv")
    asof = pd.Timestamp(args.asof)
    avail = panel.availability_table(asof)
    avail.to_csv(PROCESSED_DIR / "availability.csv", index=False)
    print(f"panel: {len(cfg.specs)} series, {len(panel.obs)} observations, {len(panel.synthetic_ids)} synthetic")
    print(avail[["series", "group", "lag_days", "last_period", "released", "synthetic"]].to_string(index=False))


def cmd_eval(args):
    from .eval.backtest import backtest_periods, final_horizon, horizons_for, model_specs_for, run_backtest
    from .eval.metrics import ablation_table, add_intervals, coverage_table, dm_table, summarize
    from .eval.plots import plot_ablation, plot_nowcast_vs_actual, plot_release_calendar, plot_rmsfe_by_horizon, plot_targets
    from .eval.report import (
        ablation_paper_table,
        coverage_paper_table,
        data_audit_table,
        md_table,
        regime_table,
        rmsfe_table,
        write,
    )

    cfg = load_config()
    panel = _panel(cfg)
    asof = pd.Timestamp(args.asof)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    tables, figs = PAPER_DIR / "tables", PAPER_DIR / "figures"
    write(tables / "tab_data_audit.md", md_table(data_audit_table(cfg, panel)))
    plot_release_calendar(cfg, figs / "fig_release_calendar.png")
    plot_targets(panel, cfg, figs / "fig_targets.png")
    results = {}
    for target_id in args.targets:
        periods = backtest_periods(panel, cfg, target_id, asof)
        if args.limit:
            periods = periods[-args.limit :]
        specs = model_specs_for(cfg, target_id, fast=args.fast)
        print(f"== {target_id}: {len(periods)} periods x {len(specs)} model specs ({periods[0]}..{periods[-1]})")
        t0 = time.time()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            bt = run_backtest(panel, cfg, target_id, specs, periods)
            bt = add_intervals(bt, alpha=cfg.backtest.get("conformal_alpha", 0.2))
        bt.to_csv(PROCESSED_DIR / f"backtest_{target_id}.csv", index=False)
        summary = summarize(bt, cfg, benchmark=cfg.backtest.get("benchmark", "ar"))
        dm = dm_table(bt, benchmark=cfg.backtest.get("benchmark", "ar"))
        cov = coverage_table(bt)
        hf = final_horizon(target_id, cfg)
        abl = ablation_table(summary, hf)
        for name, df in [("summary", summary), ("dm", dm), ("coverage", cov), ("ablation", abl)]:
            df.to_csv(PROCESSED_DIR / f"{name}_{target_id}.csv", index=False)
        horizons = horizons_for(target_id, cfg)
        write(tables / f"tab_rmsfe_{target_id}.md", md_table(rmsfe_table(summary, dm, ["hard_only", "all"], horizons)))
        write(tables / f"tab_regime_{target_id}.md", md_table(regime_table(summary, hf, "all")))
        write(tables / f"tab_ablation_{target_id}.md", md_table(ablation_paper_table(abl)))
        write(tables / f"tab_coverage_{target_id}.md", md_table(coverage_paper_table(cov, hf)))
        best = summary[(summary["regime"] == "full") & (summary["horizon"] == hf) & (summary["model"] != "rw")].sort_values("rmsfe").iloc[0]
        sel = [(best["model"], best["feature_set"], f"{best['model']} ({best['feature_set']})")]
        for m, fs in [("dfm", "all"), ("enet", "all"), ("ar", "none")]:
            if (m, fs) != (best["model"], best["feature_set"]) and ((bt["model"] == m) & (bt["feature_set"] == fs)).any():
                sel.append((m, fs, f"{m} ({fs})"))
        label = "GDP y-o-y" if target_id.startswith("gdp") else "CPI y-o-y"
        plot_nowcast_vs_actual(bt, hf, sel[:4], figs / f"fig_nowcast_{target_id}.png", f"{label}: nowcast at origin {hf} vs actual" + (" [SYNTHETIC]" if panel.is_synthetic else ""))
        plot_rmsfe_by_horizon(summary, "all", figs / f"fig_rmsfe_{target_id}.png", f"{label}: RMSFE by model and origin (feature set: all)")
        results[target_id] = abl
        print(f"   done in {time.time() - t0:.0f}s; best at {hf}: {best['model']} ({best['feature_set']}) RMSFE {best['rmsfe']:.3f} vs AR {best['rmsfe_bench']:.3f}")
    if "gdp_yoy" in results and "cpi_yoy" in results:
        plot_ablation(results["gdp_yoy"], results["cpi_yoy"], figs / "fig_ablation.png")
    print("eval complete ->", PROCESSED_DIR, "and", tables)


def cmd_live(args):
    from .eval.backtest import model_specs_for
    from .eval.live import dfm_news, next_unreleased, run_live
    from .eval.plots import plot_dashboard_preview, plot_evolution, plot_news
    from .eval.report import live_table, md_table, news_table, write

    cfg = load_config()
    panel = _panel(cfg)
    asof = pd.Timestamp(args.asof)
    out = {"asof": asof.strftime("%Y-%m-%d"), "synthetic": panel.is_synthetic, "synthetic_ids": sorted(panel.synthetic_ids), "targets": {}}
    figs = PAPER_DIR / "figures"
    evolutions = {}
    for target_id in args.targets:
        bt = pd.read_csv(PROCESSED_DIR / f"backtest_{target_id}.csv", parse_dates=["origin", "actual_release"])
        summary = pd.read_csv(PROCESSED_DIR / f"summary_{target_id}.csv")
        specs = model_specs_for(cfg, target_id, fast=args.fast)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res, evo = run_live(panel, cfg, target_id, specs, asof, bt, summary)
        evo.to_csv(PROCESSED_DIR / f"live_evolution_{target_id}.csv", index=False)
        evolutions[target_id] = evo
        out["targets"][target_id] = res
        label = "GDP y-o-y" if target_id.startswith("gdp") else "CPI y-o-y"
        core = evo[evo["feature_set"].isin(["all", "none"]) & evo["model"].isin(["ar", "dfm", "enet", "bridge"])]
        core.attrs.update(evo.attrs)
        plot_evolution(core, figs / f"fig_evolution_{target_id}.png", f"{label} {res['period']}: nowcast evolution across origins" + (" [SYNTHETIC]" if panel.is_synthetic else ""))
        print(f"{target_id} {res['period']}: headline {res['headline']['model']} ({res['headline']['feature_set']}) = {res['headline']['value']:.2f} [{res['headline']['lo']:.2f}, {res['headline']['hi']:.2f}]")
        if target_id == "gdp_yoy":
            origins = res["origins"]
            if len(origins) >= 2:
                o_prev, o_new = pd.Timestamp(origins[-2]["origin"]), pd.Timestamp(origins[-1]["origin"])
                target = next_unreleased(panel, target_id, asof)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    news, meta = dfm_news(panel, cfg, target_id, "all", o_prev, o_new, target)
                news.to_csv(PROCESSED_DIR / "live_news_gdp.csv", index=False)
                out["news"] = {"target": target_id, "feature_set": "all", "from": o_prev.strftime("%Y-%m-%d"), "to": o_new.strftime("%Y-%m-%d"), **{k: (float(v) if isinstance(v, (int, float)) else v) for k, v in meta.items()},
                               "by_series": [{"series": s, "impact": float(v)} for s, v in news.groupby("series")["impact"].sum().sort_values().items()]}
                plot_news(news, figs / "fig_news_gdp.png", f"GDP {target}: news from releases between {o_prev.date()} and {o_new.date()}" + (" [SYNTHETIC]" if panel.is_synthetic else ""))
                write(PAPER_DIR / "tables" / "tab_news_gdp.md", md_table(news_table(news, cfg)))
                print(f"   news: {meta['nowcast_prev']:.2f} -> {meta['nowcast_new']:.2f} ({meta['method']})")
    (PROCESSED_DIR / "live_nowcast.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    write(PAPER_DIR / "tables" / "tab_live.md", md_table(live_table(out)))
    plot_dashboard_preview(out, evolutions, DASHBOARD_DIR / "preview.png")
    print("live nowcast ->", PROCESSED_DIR / "live_nowcast.json")


def cmd_dashboard(args):
    from .dashboard.static import build_static_dashboard

    path = build_static_dashboard(PROCESSED_DIR, DASHBOARD_DIR / "index.html")
    print("dashboard ->", path)


def cmd_paper(args):
    from .paper_build import build_paper

    pdf = build_paper(PAPER_DIR, PROCESSED_DIR)
    print("paper ->", pdf)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="thainowcast")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in [("synthetic", cmd_synthetic), ("data", cmd_data), ("eval", cmd_eval), ("live", cmd_live), ("dashboard", cmd_dashboard), ("paper", cmd_paper)]:
        p = sub.add_parser(name)
        p.add_argument("--asof", default="2026-11-05")
        p.add_argument("--targets", nargs="*", default=TARGETS_DEFAULT)
        p.add_argument("--fast", action="store_true", help="core models only")
        p.add_argument("--limit", type=int, default=0, help="only the last N target periods")
        p.add_argument("--seed", type=int, default=20261105)
        p.set_defaults(fn=fn)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
