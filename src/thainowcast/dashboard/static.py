"""Self-contained HTML dashboard: one file, data inlined, Chart.js from a pinned CDN URL."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

CHARTJS = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"

SERIES_NAMES = {}


def _collect(processed: Path) -> dict:
    live = json.loads((processed / "live_nowcast.json").read_text(encoding="utf-8"))
    data = {"asof": live["asof"], "synthetic": live["synthetic"], "targets": {}, "news": live.get("news"), "backtest": [], "availability": []}
    for tid, r in live["targets"].items():
        evo = pd.read_csv(processed / f"live_evolution_{tid}.csv")
        keep = evo[evo["feature_set"].isin(["all", "none"]) & evo["model"].isin(["ar", "dfm", "enet", "bridge"])]
        series = []
        for (m, fs), g in keep.groupby(["model", "feature_set"]):
            g = g.sort_values("origin")
            series.append({"label": f"{m} ({fs})", "model": m, "points": [{"x": o, "y": (None if pd.isna(v) else round(float(v), 3)), "lo": (None if pd.isna(lo) else round(float(lo), 3)), "hi": (None if pd.isna(hi) else round(float(hi), 3))} for o, v, lo, hi in zip(g["origin"], g["nowcast"], g["lo"], g["hi"])]})
        summ = pd.read_csv(processed / f"summary_{tid}.csv")
        hf = "PR"
        s = summ[(summ["regime"] == "full") & (summ["horizon"] == hf) & (summ["feature_set"].isin(["all", "hard_only", "none"]))].sort_values("rmsfe")
        data["targets"][tid] = {**r, "evolution": series, "backtest": [{"model": a, "feature_set": b, "rmsfe": round(float(c), 3), "rel": round(float(d), 3)} for a, b, c, d in zip(s["model"], s["feature_set"], s["rmsfe"], s["rel_rmsfe"])], "horizon": hf}
    av = pd.read_csv(processed / "availability.csv")
    data["availability"] = [{"series": a, "name": b, "group": c, "lag": int(d), "last": str(e), "released": str(f)[:10], "synthetic": bool(g)} for a, b, c, d, e, f, g in zip(av["series"], av["name_en"], av["group"], av["lag_days"], av["last_period"], av["released"], av["synthetic"])]
    return data


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>ThaiNowcast</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="__CHARTJS__"></script>
<style>
:root{
  color-scheme: light;
  --bg:#f3f4f6; --panel:#ffffff; --ink:#1b2130; --muted:#5b6474; --rule:#d9dde5;
  --hard:#2f4b7c; --alt:#d45087; --up:#1f7a5a; --down:#b4304f; --band:rgba(47,75,124,.14);
  box-sizing:border-box; padding-top:env(safe-area-inset-top,0px); padding-bottom:env(safe-area-inset-bottom,0px);
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){ color-scheme: dark;
  --bg:#13161c; --panel:#1b1f27; --ink:#e8eaef; --muted:#9aa3b2; --rule:#2c323d; --band:rgba(133,163,214,.18); --hard:#8fb0e6; --alt:#ec7fb0; --up:#5ec9a0; --down:#f07a95; } }
:root[data-theme="dark"]{ color-scheme: dark;
  --bg:#13161c; --panel:#1b1f27; --ink:#e8eaef; --muted:#9aa3b2; --rule:#2c323d; --band:rgba(133,163,214,.18); --hard:#8fb0e6; --alt:#ec7fb0; --up:#5ec9a0; --down:#f07a95; }
html{scroll-padding-top:env(safe-area-inset-top,0px); height:100%}
body{margin:0; background:var(--bg); color:var(--ink); font-family:"IBM Plex Sans", "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height:1.45; font-size:15px}
main{max-width:1040px; margin:0 auto; padding:24px 18px 48px}
h1{font-size:1.5rem; font-weight:600; margin:0 0 4px; letter-spacing:-.01em}
h2{font-size:1.05rem; font-weight:600; margin:28px 0 10px}
p{margin:.3em 0; max-width:70ch}
.muted{color:var(--muted)}
.banner{background:var(--down); color:#fff; padding:10px 14px; border-radius:6px; margin:14px 0 18px; font-weight:500}
.hero{display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:14px; margin-top:16px}
.card{background:var(--panel); border:1px solid var(--rule); border-radius:8px; padding:16px 18px}
.card .big{font-size:2.6rem; font-weight:600; line-height:1.1; font-family:"IBM Plex Mono", ui-monospace, Menlo, monospace}
.card .band{font-family:"IBM Plex Mono", ui-monospace, Menlo, monospace; color:var(--muted); font-size:.9rem}
.card .what{font-size:.9rem; color:var(--muted); margin-top:6px}
.chart{position:relative; height:300px}
.wide{overflow-x:auto}
table{border-collapse:collapse; width:100%; font-size:.86rem; min-width:520px}
th,td{text-align:left; padding:6px 8px; border-bottom:1px solid var(--rule); white-space:nowrap}
th{color:var(--muted); font-weight:500}
td.num{font-family:"IBM Plex Mono", ui-monospace, monospace; text-align:right}
th.num{text-align:right}
.pill{display:inline-block; padding:1px 7px; border-radius:10px; font-size:.75rem; border:1px solid var(--rule); color:var(--muted)}
.pill.hard{border-color:var(--hard); color:var(--hard)}
.pill.alt{border-color:var(--alt); color:var(--alt)}
.grid2{display:grid; grid-template-columns:1fr; gap:14px}
@media (min-width:820px){ .grid2{grid-template-columns:1fr 1fr} }
footer{margin-top:36px; color:var(--muted); font-size:.82rem}
a{color:var(--hard)}
:focus-visible{outline:2px solid var(--alt); outline-offset:2px}
</style>
</head>
<body>
<main>
<h1>ThaiNowcast</h1>
<p class="muted">Pseudo-real-time estimates of the current quarter’s GDP growth and the current month’s inflation, before the official release. Information set as of <span id="asof"></span>.</p>
<div id="banner" class="banner" hidden>Synthetic data. The pipeline ran on generated test series, so these numbers describe the code, not the Thai economy. Replace data/raw with real files to get real nowcasts.</div>

<section class="hero" id="hero"></section>

<h2>How the estimate moved as data arrived</h2>
<p class="muted">Each point is a nowcast made at that date with only the data published by then. The shaded band is the 80% conformal interval of the headline model.</p>
<div class="grid2">
  <div class="card"><div class="chart"><canvas id="evo_gdp"></canvas></div></div>
  <div class="card"><div class="chart"><canvas id="evo_cpi"></canvas></div></div>
</div>

<h2>What changed the GDP number since the last origin</h2>
<p class="muted" id="newsText"></p>
<div class="card"><div class="chart" style="height:360px"><canvas id="news"></canvas></div></div>

<h2>Backtest accuracy at the final origin</h2>
<p class="muted">Root mean squared nowcast error over the pseudo-real-time backtest (2015 onward), and the ratio to the AR benchmark. Lower is better.</p>
<div class="grid2">
  <div class="card wide"><table id="bt_gdp"></table></div>
  <div class="card wide"><table id="bt_cpi"></table></div>
</div>

<h2>Data flow</h2>
<p class="muted">Latest reference period known for each series at the information date, and the publication lag the engine assumes.</p>
<div class="card wide"><table id="avail"></table></div>

<footer>Built by the ThaiNowcast pipeline (<code>make all</code>). Models: AR, factor bridge, MIDAS, mixed-frequency DFM, elastic net, LightGBM. Intervals are conformal from past nowcast errors.</footer>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById("data").textContent);
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
document.getElementById("asof").textContent = DATA.asof;
if (DATA.synthetic) document.getElementById("banner").hidden = false;
const fmt = (v) => (v === null || v === undefined || Number.isNaN(v)) ? "–" : (Math.round(v * 100) / 100).toFixed(2);

// hero cards
const hero = document.getElementById("hero");
for (const [tid, t] of Object.entries(DATA.targets)) {
  const h = t.headline;
  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `<div class="muted">${t.label}, ${t.period}</div>
    <div class="big">${fmt(h.value)}%</div>
    <div class="band">80% band ${fmt(h.lo)} to ${fmt(h.hi)}</div>
    <div class="what">Headline model: ${h.model} on ${h.feature_set} features (best backtest RMSFE ${fmt(h.rmsfe_full)} pp). Official release expected ${t.release_expected || "n/a"}.</div>`;
  hero.appendChild(card);
}

// evolution charts
const colors = { ar: "#777777", dfm: css("--alt"), enet: "#e07b39", bridge: css("--hard") };
function evoChart(id, t) {
  const datasets = [];
  for (const s of t.evolution) {
    const col = colors[s.model] || css("--hard");
    datasets.push({ label: s.label, data: s.points.map(p => ({x: p.x, y: p.y})), borderColor: col, backgroundColor: col, tension: .15, pointRadius: 4, borderWidth: s.model === t.headline.model ? 2.5 : 1.3 });
    if (s.model === t.headline.model && s.label.includes(t.headline.feature_set)) {
      datasets.push({ label: "80% band (upper)", data: s.points.map(p => ({x: p.x, y: p.hi})), borderWidth: 0, pointRadius: 0, fill: "+1", backgroundColor: css("--band") });
      datasets.push({ label: "80% band (lower)", data: s.points.map(p => ({x: p.x, y: p.lo})), borderWidth: 0, pointRadius: 0 });
    }
  }
  new Chart(document.getElementById(id), { type: "line", data: { datasets },
    options: { maintainAspectRatio: false, scales: { x: { type: "category", labels: t.evolution[0].points.map(p => p.x), ticks: { color: css("--muted") }, grid: { color: css("--rule") } }, y: { ticks: { color: css("--muted") }, grid: { color: css("--rule") }, title: { display: true, text: t.label + " (%)", color: css("--muted") } } },
      plugins: { legend: { labels: { color: css("--ink"), filter: (i) => !i.text.startsWith("80% band") } }, title: { display: true, text: t.label + " " + t.period, color: css("--ink") } } } });
}
evoChart("evo_gdp", DATA.targets.gdp_yoy);
evoChart("evo_cpi", DATA.targets.cpi_yoy);

// news
if (DATA.news && DATA.news.by_series) {
  const n = DATA.news;
  document.getElementById("newsText").textContent = `DFM (all features): ${fmt(n.nowcast_prev)}% at ${n.from} to ${fmt(n.nowcast_new)}% at ${n.to}. Bars show the impact of each series’ new releases, using the model’s Kalman-filter weights (${n.method}).`;
  const rows = n.by_series.filter(r => Math.abs(r.impact) > 0.0005);
  new Chart(document.getElementById("news"), { type: "bar", data: { labels: rows.map(r => r.series), datasets: [{ data: rows.map(r => r.impact), backgroundColor: rows.map(r => r.impact < 0 ? css("--down") : css("--up")) }] },
    options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: css("--muted") }, grid: { color: css("--rule") }, title: { display: true, text: "impact on the nowcast (pp)", color: css("--muted") } }, y: { ticks: { color: css("--muted") }, grid: { display: false } } } } });
}

// backtest tables
function btTable(id, t) {
  const el = document.getElementById(id);
  let html = `<tr><th>${t.label} at origin ${t.horizon}</th><th>features</th><th class="num">RMSFE</th><th class="num">vs AR</th></tr>`;
  for (const r of t.backtest) html += `<tr><td>${r.model}</td><td>${r.feature_set}</td><td class="num">${fmt(r.rmsfe)}</td><td class="num">${fmt(r.rel)}</td></tr>`;
  el.innerHTML = html;
}
btTable("bt_gdp", DATA.targets.gdp_yoy);
btTable("bt_cpi", DATA.targets.cpi_yoy);

// availability
let av = `<tr><th>series</th><th>group</th><th class="num">lag (days)</th><th>latest period</th><th>published</th></tr>`;
for (const r of DATA.availability) {
  const cls = r.group === "hard" ? "hard" : (r.group === "target" ? "" : "alt");
  av += `<tr><td>${r.name}${r.synthetic ? ' <span class="pill">synthetic</span>' : ""}</td><td><span class="pill ${cls}">${r.group}</span></td><td class="num">${r.lag}</td><td>${r.last}</td><td>${r.released}</td></tr>`;
}
document.getElementById("avail").innerHTML = av;
</script>
</body>
</html>
"""


def build_static_dashboard(processed: Path, out: Path) -> Path:
    data = _collect(processed)
    html = HTML.replace("__CHARTJS__", CHARTJS).replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
