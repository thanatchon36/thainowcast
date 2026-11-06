"""Assemble paper/paper.md (placeholders -> generated tables/figures) and build the PDF with pandoc + xelatex."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path


def _fill(text: str, paper_dir: Path, processed: Path) -> str:
    live = json.loads((processed / "live_nowcast.json").read_text(encoding="utf-8")) if (processed / "live_nowcast.json").exists() else {}

    def include(m: re.Match) -> str:
        p = paper_dir / m.group(1)
        return _size_columns(p.read_text(encoding="utf-8").strip()) if p.exists() else f"*[missing: {m.group(1)}]*"

    text = re.sub(r"\{\{include:([^}]+)\}\}", include, text)
    text = _fill_numbers(text, processed)
    text = text.replace("{{asof}}", live.get("asof", "n/a"))
    text = text.replace("{{synthetic_flag}}", "SYNTHETIC-DATA RUN" if live.get("synthetic") else "REAL-DATA RUN")
    for tid in live.get("targets", {}):
        t = live["targets"][tid]
        h = t["headline"]
        text = text.replace(f"{{{{live:{tid}:period}}}}", t["period"])
        text = text.replace(f"{{{{live:{tid}:value}}}}", f"{h['value']:.2f}")
        text = text.replace(f"{{{{live:{tid}:lo}}}}", f"{h['lo']:.2f}")
        text = text.replace(f"{{{{live:{tid}:hi}}}}", f"{h['hi']:.2f}")
        text = text.replace(f"{{{{live:{tid}:model}}}}", f"{h['model']} ({h['feature_set']})")
    return text


def _size_columns(table: str) -> str:
    """Rewrite a pipe table's |---| separator so pandoc's relative column widths follow the content
    (dash count = longest body cell, capped, but never below the longest unbreakable word),
    instead of splitting the page evenly."""
    lines = table.splitlines()
    if len(lines) < 3 or not re.fullmatch(r"\|(\s*:?-+:?\s*\|)+", lines[1].strip()):
        return table
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines]

    def ems(s: str) -> int:  # capitals, digits and underscores are wider than the average lowercase letter
        return round(sum(1.3 if ch.isupper() or ch.isdigit() or ch == "_" else 1.0 for ch in s))

    widths = []
    for j in range(len(rows[0])):
        cells = [r[j] for r in rows[:1] + rows[2:] if j < len(r)]
        word = max((ems(w) for c in cells for w in c.split()), default=1)
        body = max((ems(c) for c in cells[1:]), default=1)
        widths.append(max(word, min(16, body)) + 1)
    lines[1] = "|" + "|".join("-" * w for w in widths) + "|"
    return "\n".join(lines)


def _fill_numbers(text: str, processed: Path) -> str:
    """Numeric placeholders resolved from the result CSVs, so no number in the text is typed by hand."""
    import numpy as np
    import pandas as pd

    label = {"rw": "the random walk", "ar": "the AR benchmark", "bridge": "the factor bridge equation", "midas": "MIDAS", "dfm": "the mixed-frequency DFM", "enet": "the elastic net", "lgbm": "LightGBM"}
    setlabel = {"none": "", "hard_only": "hard data only", "all": "all data", "hard_trends": "hard data + Trends", "hard_lights": "hard data + lights", "hard_no2": "hard data + NO2", "hard_prices": "hard data + online prices"}
    cache: dict[str, pd.DataFrame] = {}

    def load(kind: str, tid: str) -> pd.DataFrame | None:
        key = f"{kind}_{tid}"
        if key not in cache:
            f = processed / f"{key}.csv"
            cache[key] = pd.read_csv(f) if f.exists() else None
        return cache[key]

    def f2(v) -> str:
        return "n/a" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{float(v):.2f}"

    def rmsfe(m: re.Match) -> str:
        tid, model, fs, h = m.groups()
        s = load("summary", tid)
        if s is None:
            return "n/a"
        v = s[(s.regime == "full") & (s.model == model) & (s.feature_set == fs) & (s.horizon == h)]["rmsfe"]
        return f2(v.iloc[0]) if len(v) else "n/a"

    def regime(m: re.Match) -> str:
        tid, model, fs, h, rg = m.groups()
        s = load("summary", tid)
        if s is None:
            return "n/a"
        v = s[(s.regime == rg) & (s.model == model) & (s.feature_set == fs) & (s.horizon == h)]["rmsfe"]
        return f2(v.iloc[0]) if len(v) else "n/a"

    def abl(m: re.Match) -> str:
        tid, model, fs = m.groups()
        a = load("ablation", tid)
        if a is None:
            return "n/a"
        v = a[(a.model == model) & (a.feature_set == fs)]["rel_to_hard"]
        return f2(v.iloc[0]) if len(v) else "n/a"

    def best(m: re.Match) -> str:
        tid, what = m.groups()
        s = load("summary", tid)
        if s is None:
            return "n/a"
        b = s[(s.regime == "full") & (s.horizon == "PR") & (s.model != "rw")].sort_values("rmsfe").iloc[0]
        if what == "label":
            return f"{label[b.model]} on {setlabel.get(b.feature_set, b.feature_set)}" if b.feature_set != "none" else label[b.model]
        if what == "rmsfe":
            return f2(b.rmsfe)
        return f2(b.rel_rmsfe)

    def cov(m: re.Match) -> str:
        which, tid = m.groups()
        c = load("coverage", tid)
        if c is None:
            return "n/a"
        v = c[(c.horizon == "PR") & (c.feature_set.isin(["hard_only", "all"]))]["coverage"]
        return f2(v.min() if which == "covmin" else v.max()) if len(v) else "n/a"

    text = re.sub(r"\{\{rmsfe:(\w+):(\w+):(\w+):(\w+)\}\}", rmsfe, text)
    text = re.sub(r"\{\{regime:(\w+):(\w+):(\w+):(\w+):(\w+)\}\}", regime, text)
    text = re.sub(r"\{\{abl:(\w+):(\w+):(\w+)\}\}", abl, text)
    text = re.sub(r"\{\{best:(\w+):(\w+)\}\}", best, text)
    text = re.sub(r"\{\{(covmin|covmax):(\w+)\}\}", cov, text)
    return text


def build_paper(paper_dir: Path, processed: Path) -> Path:
    """paper.md -> paper_build.md (filled) -> paper.tex (pandoc, template.tex) -> paper.pdf (tectonic, XeTeX).

    paper.tex is the self-contained arXiv source; scripts/arxiv_bundle.py packs it with its figures."""
    src = paper_dir / "paper.md"
    build_md = paper_dir / "paper_build.md"
    build_md.write_text(_fill(src.read_text(encoding="utf-8"), paper_dir, processed), encoding="utf-8")
    for tool in ("pandoc", "tectonic"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"{tool} not found; install pandoc and tectonic to build the paper")
    subprocess.run(
        ["pandoc", build_md.name, "-o", "paper.tex", "--template", "template.tex", "--number-sections"],
        check=True, cwd=str(paper_dir),
    )
    subprocess.run(["tectonic", "-X", "compile", "--keep-logs", "paper.tex"], check=True, cwd=str(paper_dir))
    return paper_dir / "paper.pdf"
