PY ?= .venv/bin/python
ASOF ?= 2026-11-05

.PHONY: setup data synthetic eval live dashboard app paper arxiv test all clean

setup:          ## create venv and install the package (needs uv)
	uv venv .venv --python 3.12
	uv pip install --python .venv/bin/python -e ".[dev,app]"

data:           ## load real CSVs from data/raw; falls back to synthetic_* files with loud warnings
	$(PY) -m thainowcast.cli data

synthetic:      ## (re)generate synthetic test data. NEVER a substitute for real data
	$(PY) -m thainowcast.cli synthetic

eval:           ## pseudo-real-time backtest, metrics, DM tests, ablations, tables, figures
	$(PY) -m thainowcast.cli eval

live:           ## nowcast the current quarter / month as of $(ASOF)
	$(PY) -m thainowcast.cli live --asof $(ASOF)

dashboard:      ## static HTML dashboard -> dashboard/index.html
	$(PY) -m thainowcast.cli dashboard

app:            ## interactive Streamlit app
	$(PY) -m streamlit run app/streamlit_app.py

paper:          ## build paper/paper.tex and paper/paper.pdf (pandoc + tectonic)
	$(PY) -m thainowcast.cli paper

arxiv: paper    ## arXiv source bundle -> paper/arxiv.tar.gz
	$(PY) scripts/arxiv_bundle.py

test:
	$(PY) -m pytest -q

all: data eval live dashboard paper

clean:
	rm -rf data/processed/* paper/paper.pdf paper/paper_build.md paper/paper.tex paper/paper.log paper/arxiv paper/arxiv.tar.gz dashboard/index.html
