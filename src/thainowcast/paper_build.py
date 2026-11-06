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
    geo_path = paper_dir / "figures" / "geo_summary.json"
    geo = json.loads(geo_path.read_text(encoding="utf-8")) if geo_path.exists() else {}
    text = re.sub(r"\{\{geo:(\w+)\}\}", lambda m: str(geo[m.group(1)]) if m.group(1) in geo else f"*[missing geo:{m.group(1)}]*", text)
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


TEXT_WIDTH_PT = 453.5  # A4 with 2.5 cm margins (template.tex)
TABLE_CHAR_PT = 3.5    # width of one ems() unit in \footnotesize Libertinus, measured on the built PDF
TABLE_COLSEP_PT = 6.0  # 2 x \tabcolsep (3pt) per column


def _size_columns(table: str) -> str:
    """Rewrite a pipe table's |---| separator so pandoc's column widths follow the content.

    pandoc sets a table at its natural width when every source line is short (72 characters), and
    otherwise spreads it over the full text width with relative widths taken from the dash counts.
    For a wide table each column starts at its natural width (longest cell); if the total exceeds
    the page, the widest columns are narrowed first, never below their longest unbreakable word,
    so long text wraps while numbers and identifiers stay on one line. Alignment colons are kept."""
    lines = table.splitlines()
    if len(lines) < 3 or not re.fullmatch(r"\|(\s*:?-+:?\s*\|)+", lines[1].strip()):
        return table
    seps = [c.strip() for c in lines[1].strip().strip("|").split("|")]
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines]

    def dashes(n: int, sep: str) -> str:
        return (":" if sep.startswith(":") else "") + "-" * n + (":" if sep.endswith(":") else "")

    if all(len(ln) <= 72 for i, ln in enumerate(lines) if i != 1):
        lines[1] = "|" + "|".join(dashes(3, s) for s in seps) + "|"
        return "\n".join(lines)

    def ems(s: str) -> float:  # capitals, digits and underscores are wider than the average lowercase letter
        s = s.replace("**", "")
        return sum(1.3 if ch.isupper() or ch.isdigit() or ch == "_" else 1.0 for ch in s)

    n = len(seps)
    word, width = [], []
    for j in range(n):
        cells = [r[j] for r in rows[:1] + rows[2:] if j < len(r)]
        word.append(max((ems(w) for c in cells for w in c.split()), default=1.0) + 2)
        width.append(max([word[j]] + [ems(c) + 1 for c in cells[1:]]))
    budget = (TEXT_WIDTH_PT - TABLE_COLSEP_PT * n) / TABLE_CHAR_PT
    while sum(width) > budget:
        shrinkable = [j for j in range(n) if width[j] > word[j]]
        if not shrinkable:
            break
        j = max(shrinkable, key=lambda k: width[k])
        width[j] = max(word[j], width[j] - 1)
    lines[1] = "|" + "|".join(dashes(max(3, round(w)), s) for w, s in zip(width, seps)) + "|"
    return "\n".join(lines)


def _keep_short_tables_together(tex: str, short: int = 15, edge: int = 3) -> str:
    """longtable may break a page between any two body rows, which can strand one row on the next page.
    Ending a row with \\\\* forbids a break after it: a short table (up to `short` rows) is kept whole,
    and a longer one may break only with at least `edge` rows on each side of the break."""
    def fix(m: re.Match) -> str:
        table = m.group(0)
        head, sep, body = table.partition("\\endlastfoot")
        if not sep:
            return table
        ends = [e.start() for e in re.finditer(r"\\\\(?=\s*\n)", body)]
        keep = set(ends) if len(ends) <= short else set(ends[:edge] + ends[-edge - 1:])
        for pos in sorted(keep, reverse=True):
            body = body[: pos + 2] + "*" + body[pos + 2:]
        return head + sep + body

    return re.sub(r"\\begin\{longtable\}.*?\\end\{longtable\}", fix, tex, flags=re.DOTALL)


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

    def nobs(m: re.Match) -> str:
        """Number of evaluation periods behind a table, from its CSV's n column ('37 to 38' if it varies)."""
        kind, tid = m.groups()
        t = load(kind, tid)
        if t is None or "n" not in t:
            return "n/a"
        if kind == "coverage":
            t = t[t.horizon == "PR"]
        lo, hi = int(t["n"].min()), int(t["n"].max())
        return str(lo) if lo == hi else f"{lo} to {hi}"

    def audit(m: re.Match) -> str:
        meta = processed / "panel.meta.json"
        if not meta.exists():
            return "n/a"
        from .config import load_config

        n_syn, n_all = len(json.loads(meta.read_text(encoding="utf-8")).get("synthetic_ids", [])), len(load_config().specs)
        if n_syn == n_all:
            return f"All {n_all} series in this run are synthetic substitutes; no real file was found."
        if n_syn == 0:
            return f"All {n_all} series in this run were loaded from real files."
        return f"{n_syn} of the {n_all} series in this run are synthetic substitutes (status column)."

    text = re.sub(r"\{\{n:(\w+):(\w+)\}\}", nobs, text)
    text = re.sub(r"\{\{audit:status\}\}", audit, text)
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
    tex = paper_dir / "paper.tex"
    tex.write_text(_keep_short_tables_together(tex.read_text(encoding="utf-8")), encoding="utf-8")
    subprocess.run(["tectonic", "-X", "compile", "--keep-logs", "paper.tex"], check=True, cwd=str(paper_dir))
    return paper_dir / "paper.pdf"
