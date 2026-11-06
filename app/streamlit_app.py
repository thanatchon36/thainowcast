"""Interactive ThaiNowcast dashboard: `make app` (needs the eval + live outputs)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"

st.set_page_config(page_title="ThaiNowcast", layout="wide")
live = json.loads((P / "live_nowcast.json").read_text(encoding="utf-8"))
if live.get("synthetic"):
    st.error("Synthetic data: the pipeline ran on generated test series. These numbers validate the code, not the economy.")
st.title("ThaiNowcast")
st.caption(f"Information set as of {live['asof']}")

cols = st.columns(len(live["targets"]))
for col, (tid, t) in zip(cols, live["targets"].items()):
    h = t["headline"]
    col.metric(f"{t['label']} {t['period']}", f"{h['value']:.2f}%", help=f"{h['model']} on {h['feature_set']} features; release expected {t.get('release_expected')}")
    col.write(f"80% band {h['lo']:.2f} to {h['hi']:.2f}")

tab_evo, tab_news, tab_bt, tab_data = st.tabs(["Nowcast evolution", "News", "Backtest", "Data flow"])

with tab_evo:
    for tid, t in live["targets"].items():
        evo = pd.read_csv(P / f"live_evolution_{tid}.csv", parse_dates=["origin"])
        core = evo[evo["feature_set"].isin(["all", "none"]) & evo["model"].isin(["ar", "dfm", "enet", "bridge"])]
        wide = core.assign(key=core["model"] + " (" + core["feature_set"] + ")").pivot(index="origin", columns="key", values="nowcast")
        st.subheader(f"{t['label']} {t['period']}")
        st.line_chart(wide)

with tab_news:
    n = live.get("news")
    if n:
        st.write(f"DFM (all): {n['nowcast_prev']:.2f}% at {n['from']} to {n['nowcast_new']:.2f}% at {n['to']} ({n['method']})")
        df = pd.DataFrame(n["by_series"]).set_index("series")
        st.bar_chart(df["impact"])
        st.dataframe(pd.read_csv(P / "live_news_gdp.csv"), use_container_width=True)
    else:
        st.info("No news decomposition available.")

with tab_bt:
    for tid, t in live["targets"].items():
        s = pd.read_csv(P / f"summary_{tid}.csv")
        hf = "PR"
        st.subheader(f"{t['label']}: RMSFE by model, feature set and regime (origin {hf})")
        st.dataframe(s[s["horizon"] == hf].pivot_table(index=["model", "feature_set"], columns="regime", values="rmsfe").round(3), use_container_width=True)

with tab_data:
    st.dataframe(pd.read_csv(P / "availability.csv"), use_container_width=True)
