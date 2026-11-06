"""Build the arXiv source bundle, ``paper/arxiv.tar.gz``, from the paper as last built.

arXiv compiles the paper itself, from the root of the bundle, with XeLaTeX (declared in
``00README.json``). This stages ``paper.tex`` (every number and table already filled in) and the
figures it uses, compiles the staged copy once with tectonic to prove it is self-contained, then
tars it. It also prints the title, the plain-text abstract (for the arXiv form) and a comments
line. Run ``make paper`` first.

Usage: ``python scripts/arxiv_bundle.py``.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
STAGE = PAPER / "arxiv"
OUT = PAPER / "arxiv.tar.gz"


def main() -> int:
    tex = (PAPER / "paper.tex").read_text(encoding="utf-8")
    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / "figures").mkdir(parents=True)
    (STAGE / "paper.tex").write_text(tex, encoding="utf-8")
    # the optional argument of \includegraphics carries the alt text, which may itself hold brackets
    figures = sorted(set(re.findall(r"\{figures/([\w.-]+)\}", tex)))
    for name in figures:
        shutil.copyfile(PAPER / "figures" / name, STAGE / "figures" / name)
    (STAGE / "00README.json").write_text(
        json.dumps(
            {
                "spec_version": 1,
                "process": {"compiler": "xelatex"},
                "sources": [{"filename": "paper.tex", "usage": "toplevel"}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    # the staged copy must compile on its own
    subprocess.run(
        ["tectonic", "-X", "compile", "--keep-logs", "paper.tex"], cwd=STAGE, check=True, capture_output=True
    )
    log = (STAGE / "paper.log").read_text(encoding="utf-8", errors="replace")
    pages = re.search(r"Output written on paper\.(?:xdv|pdf) \((\d+) pages", log)
    if pages is None:
        raise SystemExit("staged compile left no page count")
    for name in ("paper.log", "paper.pdf"):
        (STAGE / name).unlink(missing_ok=True)
    with tarfile.open(OUT, "w:gz") as tar:
        for p in sorted(STAGE.rglob("*")):
            if p.is_file():
                tar.add(p, arcname=str(p.relative_to(STAGE)))
    files = sorted(str(p.relative_to(STAGE)) for p in STAGE.rglob("*") if p.is_file())
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} kB, {len(files)} files)")
    print("\n".join(f"  {f}" for f in files))

    # metadata for the submission form, from the filled markdown (numbers already resolved)
    md = (PAPER / "paper_build.md").read_text(encoding="utf-8")
    title = re.search(r'^title: "(.*)"$', md, re.M)
    abstract = re.search(r"^abstract: \|\n((?:  .*\n?)+)", md, re.M)
    if title is None or abstract is None:
        raise SystemExit("paper_build.md lacks the title or abstract")
    body = " ".join(abstract.group(1).split()).replace("`", "")
    print(f"\nTitle:\n{title.group(1)}")
    print(f"\nAbstract ({len(body)} characters; arXiv allows 1,920):\n{body}")
    print(
        f"\nComments:\n{pages.group(1)} pages, {len(figures)} figures. Working paper; results are from "
        "synthetic test data. Code: https://github.com/thanatchon36/thainowcast. JEL C53, C55, E37."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
