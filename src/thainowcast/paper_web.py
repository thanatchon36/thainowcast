"""Build the web reader docs/paper/ from paper/paper.md (same text and numbers as the PDF).

pandoc renders the filled Markdown with paper/reader.html: masthead, abstract, a results strip whose
numbers are resolved from data/processed by the same placeholders as the paper, contents, numbered
sections and the appendices. The PDF and the figures it uses are copied next to the page; GitHub
Pages serves docs/ at https://thanatchon36.github.io/thainowcast/. Requires pandoc on PATH.
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
from pathlib import Path

from .eval.report import MODEL_LABEL, SET_LABEL
from .paper_build import _fill

REPO_URL = "https://github.com/thanatchon36/thainowcast"
PAPER_URL = "https://thanatchon36.github.io/thainowcast/paper/"
DATA_URL = "https://huggingface.co/datasets/thanatchon36/thainowcast"
CONCEPT_DOI = "10.5281/zenodo.23995547"
NIGHT_FIGURES = {"fig_lights_thailand.png", "fig_lights_bkk_eec.png"}  # dark by design: no light plate

# (label, style, finding, detail) with {{...}} placeholders resolved like paper.md.
# style: "ref" = pipeline result on the synthetic economy, "null" = pending.
RESULTS = [
    (
        "GDP · nowcast",
        "ref",
        "{{live:gdp_yoy:period}} growth nowcast {{live:gdp_yoy:value}}% y-o-y",
        "80% band {{live:gdp_yoy:lo}} to {{live:gdp_yoy:hi}}; {{live:gdp_yoy:model}}; information set {{asof}}",
    ),
    (
        "CPI · nowcast",
        "ref",
        "{{live:cpi_yoy:period}} headline inflation nowcast {{live:cpi_yoy:value}}% y-o-y",
        "80% band {{live:cpi_yoy:lo}} to {{live:cpi_yoy:hi}}; {{live:cpi_yoy:model}}",
    ),
    (
        "GDP · backtest",
        "ref",
        "Best pre-release RMSFE {{best:gdp_yoy:rmsfe}} pp against {{rmsfe:gdp_yoy:ar:none:PR}} for AR",
        "{{best:gdp_yoy:label}}; ratio to AR {{best:gdp_yoy:rel}}; gains concentrated in the COVID quarters",
    ),
    (
        "CPI · backtest",
        "ref",
        "Elastic net with all data: pre-release RMSFE {{rmsfe:cpi_yoy:enet:all:PR}} pp against {{rmsfe:cpi_yoy:ar:none:PR}} for AR",
        "{{rmsfe:cpi_yoy:enet:hard_only:PR}} with hard data only; no model beats AR at the end-of-month origin",
    ),
    (
        "Alternative data",
        "ref",
        "Online prices cut the CPI elastic-net RMSFE to {{abl:cpi_yoy:enet:hard_prices}} of hard data only",
        (
            "noisy or short families can hurt: elastic net with lights {{abl:gdp_yoy:enet:hard_lights}}, "
            "bridge with Trends {{abl:gdp_yoy:bridge:hard_trends}} for GDP"
        ),
    ),
    (
        "Intervals",
        "ref",
        "80% conformal coverage {{covmin:gdp_yoy}} to {{covmax:gdp_yoy}} for GDP, {{covmin:cpi_yoy}} to {{covmax:cpi_yoy}} for CPI",
        "pre-release origin, calibrated on past nowcast errors; undercoverage concentrated in 2020",
    ),
    (
        "Thai data",
        "null",
        "Real-data results pending",
        "every number here comes from a synthetic one-factor economy; make all on the real files replaces them",
    ),
]


def _number_captions(page: str) -> str:
    """Table and figure numbers in captions, in document order (the PDF numbers them the same way)."""
    count = {"caption": 0, "figcaption": 0}

    def caption(m: re.Match) -> str:
        tag, attrs, para = m.group(1), m.group(2), m.group(3) or ""
        count[tag] += 1
        word = "Table" if tag == "caption" else "Figure"
        return f"<{tag}{attrs}>{para}<b>{word} {count[tag]}.</b> "

    return re.sub(r"<(caption|figcaption)(\b[^>]*)>(\s*<p>)?", caption, page)


def _web_images(page: str) -> str:
    """Drop the PDF sizing (height=88% etc.), load lazily, and mark the night-lights maps."""
    def img(m: re.Match) -> str:
        tag = re.sub(r'\s(?:style|width|height)="[^"]*"', "", m.group(0))
        name = re.search(r'src="figures/([^"]+)"', tag)
        extra = ' loading="lazy"'
        if name and name.group(1) in NIGHT_FIGURES:
            extra += ' class="night"'
        return tag.replace("<img ", f"<img{extra} ", 1)

    return re.sub(r"<img\b[^>]*>", img, page)


def build_web(paper_dir: Path, processed: Path, out_dir: Path) -> Path:
    """paper.md -> filled Markdown -> out_dir/index.html (pandoc, reader.html), plus paper.pdf and figures."""
    if shutil.which("pandoc") is None:
        raise RuntimeError("pandoc not found; install pandoc to build the web reader")
    def fill(s: str) -> str:
        return _fill(s, paper_dir, processed)

    text = fill((paper_dir / "paper.md").read_text(encoding="utf-8"))
    page = subprocess.run(
        [
            "pandoc", "--from=markdown", "--to=html5", "--mathml", "--wrap=none", "--standalone",
            "--template=reader.html", "--number-sections", "--toc", "--toc-depth=1",
            "--metadata=pagetitle:ThaiNowcast",
            (
                "--metadata=description:Working paper: pseudo-real-time nowcasting of Thai GDP and "
                "inflation with official and alternative data."
            ),
        ],
        input=text, capture_output=True, text=True, check=True, cwd=str(paper_dir),
    ).stdout

    page = _number_captions(page)
    page = _web_images(page)
    # The caption sits above the table, outside its sideways scroll, so it wraps at the text width.
    page = re.sub(
        r"<table\b[^>]*>\s*<caption>(.*?)</caption>(.*?)</table>",
        r'<div class="tbl"><p class="tcap">\1</p><div class="tscroll"><table>\2</table></div></div>',
        page, flags=re.DOTALL,
    )
    # Column widths are sized for the PDF page; in the browser the tables size to their content and scroll.
    page = re.sub(r"<colgroup>.*?</colgroup>\s*", "", page, flags=re.DOTALL)

    def strip_text(s: str) -> str:  # "enet (hard_only)" -> "Elastic net, hard data only"
        s = fill(s)
        return re.sub(
            r"\b(\w+) \((\w+)\)",
            lambda m: f"{MODEL_LABEL[m.group(1)]}, {SET_LABEL[m.group(2)].replace('hard', 'hard data', 1)}"
            if m.group(1) in MODEL_LABEL and m.group(2) in SET_LABEL else m.group(0),
            s,
        )

    items = "\n".join(
        f'<li class="r r-{style}"><span class="r-id">{html.escape(label)}</span>'
        f'<span class="r-text">{html.escape(strip_text(finding))}<small>{html.escape(strip_text(detail))}</small></span></li>'
        for label, style, finding, detail in RESULTS
    )
    missing = re.findall(r"n/a|\[missing[^\]]*\]|\{\{[^}]*\}\}", items)
    if missing:
        raise RuntimeError(f"results strip has unresolved numbers: {missing}")
    actions = (
        '<li><a href="paper.pdf">Download PDF</a></li>'
        f'<li><a href="{REPO_URL}">Code and replication</a></li>'
        f'<li><a href="{DATA_URL}">Data (Hugging Face)</a></li>'
        f'<li><a href="https://doi.org/{CONCEPT_DOI}">Zenodo archive</a></li>'
    )
    title = re.search(r"<h1>(.*?)</h1>", page, re.DOTALL).group(1)
    subtitle = re.search(r'<p class="subtitle">(.*?)</p>', page, re.DOTALL)
    full_title = html.unescape(title + (": " + subtitle.group(1) if subtitle else ""))
    bib = (
        "@techreport{chongmankhong2026thainowcast,\n"
        "  author      = {Chongmankhong, Thanatchon},\n"
        f"  title       = {{{full_title}}},\n"
        "  year        = {2026},\n"
        "  type        = {Working paper},\n"
        f"  doi         = {{{CONCEPT_DOI}}},\n"
        f"  url         = {{{PAPER_URL}}}\n"
        "}"
    )
    cite = f"<h2>How to cite</h2><pre><code>{html.escape(bib)}</code></pre>"
    colophon = (
        "<p>Rendered from <code>paper/paper.md</code> by <code>thainowcast.paper_web</code> "
        "(<code>make web</code>). Every number is resolved from the result files in "
        "<code>data/processed/</code> by the same placeholders as the PDF, which is authoritative. "
        "This run uses synthetic data throughout.</p>"
    )
    for marker, value in (
        ("<!--ACTIONS-->", actions),
        ("<!--RESULTS-NOTE-->", (
            "Headline numbers, generated from the result files. All of them come from the synthetic "
            "economy and validate the pipeline, not the Thai economy. Amber: pipeline results; grey: pending."
        )),
        ("<!--RESULTS-->", items),
        ("<!--CITE-->", cite),
        ("<!--COLOPHON-->", colophon),
    ):
        if marker not in page:
            raise RuntimeError(f"reader.html lacks {marker}")
        page = page.replace(marker, value)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    pdf = paper_dir / "paper.pdf"
    if pdf.exists():
        shutil.copyfile(pdf, out_dir / "paper.pdf")
    (out_dir / "figures").mkdir(exist_ok=True)
    for name in sorted(set(re.findall(r'src="figures/([\w.-]+)"', page))):
        shutil.copyfile(paper_dir / "figures" / name, out_dir / "figures" / name)
    return out_dir / "index.html"
