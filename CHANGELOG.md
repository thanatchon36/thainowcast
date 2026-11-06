# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-05

### Added
- Indicator registry and release calendar (`config/indicators.yaml`): 26 series with agency, start, publication
  lag, transform and fetch method.
- Pseudo-real-time information sets: every observation is stored with its publication date, and
  `tests/test_leakage.py` fails if a model sees data released after its origin.
- Ragged-edge handling: AR(1) completion of trailing gaps, quarterly aggregation and a history-for-breadth rule.
- Model race: random walk, AR(p), factor bridge, MIDAS, mixed-frequency dynamic factor model, elastic net, LightGBM.
- Evaluation: expanding-window backtest from 2015, RMSFE/MAE by regime, Diebold-Mariano with HLN correction,
  conformal 80% intervals and an ablation for each alternative data family.
- Live nowcast with evolution across origins and a Kalman-filter news decomposition.
- Static HTML dashboard, Streamlit app, the working paper (`paper/paper.pdf`) and a 3-minute pitch outline.
- Paper build in arXiv layout: pandoc renders `paper/paper.tex` from `paper/template.tex`, tectonic compiles it, and
  `make arxiv` writes the self-contained source bundle `paper/arxiv.tar.gz`. References checked against
  Crossref, arXiv, NeurIPS and RePEc.
- Paper section 3.3, "The geography of activity, seen from space": a province map of Thailand and three
  nighttime-lights figures (the country in 2016, Bangkok and the Eastern Seaboard in 2012 and 2016, light
  share by province) built by `make geo` from NASA Black Marble composites and geoBoundaries ADM1. These are
  real data; the numbers in that section come from `paper/figures/geo_summary.json`.
- Synthetic test data in `data/raw/synthetic_*.csv`, used only when a real file is missing.
