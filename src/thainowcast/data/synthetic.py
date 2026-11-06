"""Synthetic data generator -- FOR PIPELINE TESTS ONLY.

Every file written here is named ``synthetic_<file>.csv``. The data-generating
process is a one-factor model with event shocks placed where Thai history had
them (global financial crisis 2008-09, the 2011 floods, the 2014 political
crisis, COVID-19 2020-21, the 2022 energy-price spike). It exists so that the
pseudo-real-time machinery, the ragged edge, the mixed-frequency models and the
evaluation code can be exercised end-to-end without network access. It carries no
information about the Thai economy. Results computed on it validate the
*pipeline*, never the *economics*.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import RAW_DIR, Config

SEED = 20261105
END_MONTH = "2026-10"

# Event shocks added to the common activity factor, by month range (inclusive).
FACTOR_SHOCKS = [
    ("2008-10", "2009-03", -3.5), ("2009-04", "2009-09", -2.0),
    ("2010-01", "2010-06", +2.5), ("2010-07", "2010-12", +1.0),
    ("2011-10", "2011-10", -6.0), ("2011-11", "2011-11", -8.0), ("2011-12", "2011-12", -5.0),
    ("2012-01", "2012-03", -1.0), ("2012-04", "2012-12", +3.0),
    ("2014-01", "2014-06", -1.5),
    ("2020-03", "2020-03", -4.0), ("2020-04", "2020-04", -15.0), ("2020-05", "2020-05", -13.0),
    ("2020-06", "2020-06", -8.0), ("2020-07", "2020-12", -4.0),
    ("2021-01", "2021-06", -2.0), ("2021-07", "2021-09", -5.0), ("2021-10", "2021-12", -2.0),
    ("2022-01", "2022-06", +1.0), ("2022-07", "2022-12", +2.0),
]

OIL_SHOCKS = [
    ("2008-01", "2008-07", +35.0), ("2008-11", "2009-06", -35.0), ("2011-01", "2011-12", +15.0),
    ("2015-01", "2015-12", -25.0), ("2016-01", "2016-06", -15.0), ("2020-04", "2020-06", -30.0),
    ("2021-03", "2021-12", +25.0), ("2022-03", "2022-09", +40.0), ("2023-01", "2023-12", -15.0),
]
AGRI_SHOCKS = [("2008-01", "2008-09", +15.0), ("2022-01", "2022-12", +8.0)]

# Generic monthly indicators driven by the factor: yoy = a + lam * f(t-d) + extra + AR(1) noise
GENERIC = {
    "mpi": dict(a=1.5, lam=1.4, d=0, sig=1.5, seas=0.08),
    "pci": dict(a=3.0, lam=0.9, d=0, sig=1.0, seas=0.05),
    "pii": dict(a=3.0, lam=1.3, d=1, sig=2.0, seas=0.04),
    "credit": dict(a=6.0, lam=0.4, d=2, sig=0.8, seas=0.01),
    "promptpay": dict(a=25.0, lam=0.8, d=0, sig=3.0, seas=0.03),
    "exports": dict(a=5.0, lam=2.0, d=0, sig=4.0, seas=0.06),
    "imports": dict(a=5.5, lam=2.2, d=0, sig=4.5, seas=0.06),
    "electricity": dict(a=2.5, lam=0.7, d=0, sig=1.5, seas=0.10),
    "vehicle_reg": dict(a=2.0, lam=1.8, d=0, sig=4.0, seas=0.08),
    "expressway": dict(a=3.0, lam=0.8, d=0, sig=2.0, seas=0.03,
                       extra=[("2020-04", "2020-05", -30.0), ("2021-07", "2021-09", -20.0)]),
    "nightlights": dict(a=2.5, lam=0.3, d=0, sig=2.0, seas=0.03),
    "no2": dict(a=0.5, lam=0.8, d=0, sig=4.0, seas=0.25),
}
TRENDS = {  # Google Trends style 0-100 indices: level = base + lam*f + extra + noise
    "gt_unemploy": dict(base=40, lam=-3.0, sig=6.0,
                        extra=[("2020-04", "2020-06", 45.0), ("2020-07", "2020-12", 20.0), ("2021-07", "2021-09", 25.0)]),
    "gt_loan": dict(base=50, lam=-2.0, sig=5.0, extra=[("2020-04", "2020-08", 20.0)]),
    "gt_car_installment": dict(base=45, lam=-2.5, sig=5.0, extra=[("2020-04", "2020-06", 15.0)]),
    "gt_travel": dict(base=50, lam=2.5, sig=6.0,
                      extra=[("2020-03", "2021-10", -35.0), ("2021-11", "2022-06", -15.0)]),
}


def _ar1(n: int, rho: float, sigma: float, rng: np.random.Generator) -> np.ndarray:
    x = np.zeros(n)
    e = rng.normal(0.0, sigma, n)
    for t in range(1, n):
        x[t] = rho * x[t - 1] + e[t]
    return x


def _add(s: pd.Series, spans: list[tuple[str, str, float]] | None) -> pd.Series:
    for a, b, v in spans or []:
        s.loc[a:b] = s.loc[a:b] + v
    return s


def yoy_to_levels(yoy: pd.Series, start: pd.Period, rng: np.random.Generator, seas: float, base: float = 100.0) -> pd.Series:
    """Build an index level from a YoY path so that 100*(L_t/L_{t-12}-1) == yoy_t for t >= start+12."""
    idx = pd.period_range(start, yoy.index[-1], freq="M")
    phase = rng.uniform(0, 12)
    seasonal = 1 + seas * np.sin(2 * np.pi * (np.arange(12) + phase) / 12)
    L = np.empty(len(idx))
    for i, p in enumerate(idx):
        if i < 12:
            L[i] = base * seasonal[p.month - 1] * (1 + 0.004 * i)
        else:
            L[i] = L[i - 12] * (1 + yoy.loc[p] / 100.0)
    return pd.Series(L, index=idx)


def covid_path(months: pd.PeriodIndex, floor: float, recovery_months: int) -> pd.Series:
    """Multiplicative path: 1 before Feb-2020, collapse to `floor`, linear recovery from Nov-2021."""
    m = pd.Series(1.0, index=months)
    m.loc["2020-02"] = 0.6
    m.loc["2020-03"] = 0.3
    m.loc["2020-04":"2021-10"] = floor
    rec_start = pd.Period("2021-11", freq="M")
    for i in range(recovery_months):
        p = rec_start + i
        if p in m.index:
            m.loc[p] = floor + (1 - floor) * (i + 1) / recovery_months
    return m


def generate(cfg: Config, raw_dir: Path | str = RAW_DIR, seed: int = SEED, end_month: str = END_MONTH) -> list[Path]:
    rng = np.random.default_rng(seed)
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    months = pd.period_range("2003-01", end_month, freq="M")
    T = len(months)

    # --- latent drivers --------------------------------------------------------
    f = _add(pd.Series(_ar1(T, 0.85, 0.7, rng), index=months), FACTOR_SHOCKS)
    trend = pd.Series(4.3, index=months)
    trend.loc["2013-01":"2019-12"] = 3.2
    trend.loc["2020-01":"2021-12"] = 3.0
    trend.loc["2022-01":] = 2.4
    oil = _add(pd.Series(_ar1(T, 0.9, 3.0, rng) + 2.0, index=months), OIL_SHOCKS)
    agri = _add(pd.Series(_ar1(T, 0.8, 3.0, rng) + 3.0, index=months), AGRI_SHOCKS)
    core = pd.Series(_ar1(T, 0.9, 0.15, rng), index=months)
    cpi = 1.2 + 0.08 * oil + 0.12 * agri + core + 0.08 * f.shift(6).fillna(0.0) + rng.normal(0, 0.2, T)

    # --- targets ----------------------------------------------------------------
    quarters = f.index.asfreq("Q")
    fq = f.groupby(quarters).mean()
    nq = f.groupby(quarters).size()
    fq = fq[nq == 3]  # complete quarters only
    trq = trend.groupby(quarters).mean().loc[fq.index]
    gdp_yoy = trq + 1.1 * fq + rng.normal(0, 0.5, len(fq))
    gdp_qoq = 0.75 + 0.9 * (fq - fq.shift(1)) + rng.normal(0, 0.4, len(fq))

    series: dict[str, pd.Series] = {
        "gdp_yoy": gdp_yoy.loc["2005Q1":],
        "gdp_qoq_sa": gdp_qoq.loc["2005Q1":],
        "cpi_yoy": cpi.loc["2005-01":],
    }

    # --- indicators ---------------------------------------------------------------
    def generic(sid: str, p: dict) -> pd.Series:
        spec = cfg.indicators[sid]
        yoy = p["a"] + p["lam"] * f.shift(p["d"]).bfill() + _ar1(T, 0.6, p["sig"], rng)
        yoy = _add(pd.Series(yoy.to_numpy(), index=months), p.get("extra"))
        return yoy_to_levels(yoy, spec.start_period, rng, p["seas"])

    for sid, p in GENERIC.items():
        series[sid] = generic(sid, p)

    tour_yoy = pd.Series(8.0 + 2.5 * f + _ar1(T, 0.6, 5.0, rng), index=months)
    series["tourists"] = yoy_to_levels(tour_yoy, cfg.indicators["tourists"].start_period, rng, 0.15)
    series["tourists"] = series["tourists"] * covid_path(series["tourists"].index, 0.01, 32)
    aot_yoy = pd.Series(6.0 + 1.5 * f + _ar1(T, 0.6, 3.0, rng), index=months)
    series["aot_pax"] = yoy_to_levels(aot_yoy, cfg.indicators["aot_pax"].start_period, rng, 0.10)
    series["aot_pax"] = series["aot_pax"] * covid_path(series["aot_pax"].index, 0.15, 24)

    series["oil_retail"] = yoy_to_levels(oil, cfg.indicators["oil_retail"].start_period, rng, 0.0, base=25.0)
    series["agri_price"] = yoy_to_levels(agri, cfg.indicators["agri_price"].start_period, rng, 0.06)

    for sid, p in TRENDS.items():
        lvl = p["base"] + p["lam"] * f + rng.normal(0, p["sig"], T)
        lvl = _add(pd.Series(lvl.to_numpy(), index=months), p.get("extra")).clip(5, 100)
        series[sid] = lvl.loc[cfg.indicators[sid].start_period:]
    gtp = (40 + 4.0 * (cpi - 1.5) + rng.normal(0, 5.0, T)).clip(5, 100)
    series["gt_prices"] = pd.Series(gtp.to_numpy(), index=months).loc[cfg.indicators["gt_prices"].start_period:]

    op_yoy = pd.Series(0.9 * cpi + rng.normal(0, 0.3, T), index=months)
    series["online_prices"] = yoy_to_levels(op_yoy, cfg.indicators["online_prices"].start_period, rng, 0.0)

    mob_spec = cfg.indicators["mobility"]
    mob_idx = pd.period_range(mob_spec.start_period, mob_spec.end_period, freq="M")
    mob = pd.Series(2.0 * f.loc[mob_idx].to_numpy() + rng.normal(0, 3.0, len(mob_idx)), index=mob_idx)
    series["mobility"] = _add(mob, [("2020-04", "2020-05", -25.0), ("2021-07", "2021-09", -15.0)])

    # --- write --------------------------------------------------------------------
    written = []
    for sid, s in series.items():
        spec = cfg.specs[sid]
        path = raw_dir / f"synthetic_{spec.file}"
        pd.DataFrame({"period": s.index.astype(str), "value": np.round(s.to_numpy(dtype=float), 6)}).to_csv(path, index=False)
        written.append(path)

    manifest = {
        "WARNING": "SYNTHETIC DATA. Generated by thainowcast.data.synthetic for pipeline tests only.",
        "seed": seed,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dgp": "one AR(1) common factor + event shocks; GDP_yoy = trend + 1.1*mean_q(f) + e; "
               "CPI_yoy = 1.2 + 0.08*oil + 0.12*agri + core + 0.08*f(t-6) + e; "
               "indicators yoy = a + lam*f(t-d) + extra + AR(1) idiosyncratic; levels rebuilt from yoy with seasonality",
        "files": [p.name for p in written],
    }
    (raw_dir / "synthetic_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (raw_dir / "SYNTHETIC_README.txt").write_text(
        "All synthetic_*.csv files in this folder are generated test data (see synthetic_manifest.json).\n"
        "They are loaded only when the real file (same name without the prefix) is missing, and the\n"
        "loader prints a warning every time. Replace them with real data via docs/data_sources.md.\n",
        encoding="utf-8",
    )
    return written
