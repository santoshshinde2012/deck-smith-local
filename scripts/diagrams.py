"""Build and check the architecture diagrams.

The Mermaid sources live in ``docs/diagrams/*.mmd``. They are rendered with mermaid-cli to SVG,
with a PNG fallback, on a white background into ``docs/assets/diagrams/``, and the Markdown embeds
those images. A pre-rendered image looks the same in GitHub's light and dark themes; a Mermaid
block in Markdown would be re-themed by GitHub and lose its white canvas.

    python scripts/diagrams.py            # check the sources, then render every image and the manifest
    python scripts/diagrams.py --check    # fail if a source breaks a rule or an image is stale
    python scripts/diagrams.py --check --render   # also prove each source renders (CI)

Rules: every node class comes from ``PALETTE`` verbatim; groups use ``GROUP_STYLE``; no ``%%{init}%%``
(the shared theme is ``docs/diagrams/mermaid.json``: white canvas, dark #24292F lines and labels);
each source names itself (``%% diagram: <file name>``) and has a ``%% caption:``; no Markdown file
contains a Mermaid block; every embedded image exists; ``manifest.json`` holds a hash of each source
and the theme, so an image that was not rebuilt after an edit fails the check.

Rendering needs mermaid-cli: ``MMDC`` is the command (default ``mmdc``, for example
``MMDC="npx -y @mermaid-js/mermaid-cli@11.4.2"``) and ``PUPPETEER_CONFIG`` an optional browser config.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "diagrams"
OUT = ROOT / "docs" / "assets" / "diagrams"
THEME = SRC / "mermaid.json"
MANIFEST = OUT / "manifest.json"
DOCS = ["README.md", "ARCHITECTURE.md", *sorted(str(p.relative_to(ROOT)) for p in (ROOT / "docs").glob("*.md"))]
INK = "#24292F"  # lines, edge labels and group titles on the white canvas
PAGE_WIDTH = 4000  # mmdc shrinks a diagram to fit its page, so give wide ones room

# name: (fill, stroke, text, extra). Text on every fill meets WCAG AA (4.5:1) or better.
PALETTE: dict[str, tuple[str, str, str, str]] = {
    "ui": ("#8250DF", "#6639BA", "#FFFFFF", ""),  # people and the UI
    "app": ("#0969DA", "#0550AE", "#FFFFFF", ""),  # API, agent, composition root
    "core": ("#1A7F37", "#116329", "#FFFFFF", ""),  # domain and application core
    "port": ("#FFF8C5", "#9A6700", "#3B2300", ""),  # ports (Protocols)
    "local": ("#DDF4FF", "#0969DA", "#0A3069", ""),  # local adapters
    "dbx": ("#FFF1E5", "#BC4C00", "#762C00", ""),  # Databricks adapters
    "store": ("#EAEEF2", "#57606A", "#24292F", ""),  # data stores and artefacts
    "llm": ("#BF3989", "#99286E", "#FFFFFF", ""),  # LLM gateway and providers
    "obs": ("#1B7C83", "#0E5A60", "#FFFFFF", ""),  # observability
    "ext": ("#57606A", "#32383F", "#FFFFFF", ",stroke-dasharray:4 3"),  # external systems
    "sec": ("#FFEBE9", "#CF222E", "#82071E", ""),  # security decisions and refusals
}
CLASSDEFS = {
    name: f"classDef {name} fill:{f},stroke:{s},stroke-width:2px,color:{t}{x}" for name, (f, s, t, x) in PALETTE.items()
}
GROUP_STYLE = "fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4"
IMAGE_REF = re.compile(r"assets/diagrams/([\w-]+)\.(svg|png)")


def sources() -> dict[str, str]:
    return {p.stem: p.read_text() for p in sorted(SRC.glob("*.mmd"))}


def digest(src: str) -> str:
    return hashlib.sha256((THEME.read_text() + "\0" + src).encode()).hexdigest()


def check_theme() -> list[str]:
    theme = json.loads(THEME.read_text())
    tv = theme.get("themeVariables", {})
    problems = []
    if tv.get("background", "").upper() != "#FFFFFF":
        problems.append(f"{THEME.name}: themeVariables.background must be #FFFFFF")
    for key in ("lineColor", "textColor", "titleColor", "primaryTextColor", "signalColor", "signalTextColor"):
        if tv.get(key, "").upper() != INK:
            problems.append(f"{THEME.name}: themeVariables.{key} must be {INK} so it reads on white")
    if theme.get("htmlLabels") is not False:
        problems.append(f"{THEME.name}: set htmlLabels to false so the SVGs carry plain SVG text")
    return problems


def check_source(name: str, src: str) -> list[str]:
    problems = []
    if not re.search(rf"^%% diagram: {re.escape(name)}$", src, re.M):
        problems.append(f"needs a '%% diagram: {name}' line matching its file name")
    if not re.search(r"^%% caption: \S", src, re.M):
        problems.append("needs a '%% caption: ...' line (used as the image's alt text)")
    if "%%{init" in src:
        problems.append("sets an init block; the shared theme is docs/diagrams/mermaid.json")
    for m in re.finditer(r"^\s*classDef (\S+) (.*)$", src, re.M):
        cls = m.group(1)
        if cls not in CLASSDEFS:
            problems.append(f"classDef {cls!r} is not in the palette")
        elif m.group(0).strip() != CLASSDEFS[cls]:
            want = CLASSDEFS[cls]
            problems.append(f"classDef {cls!r} differs from the palette:\n    {m.group(0).strip()}\n    {want}")
    used = set(re.findall(r":::(\w+)", src)) | set(re.findall(r"^\s*class\s.*\s(\w+)\s*$", src, re.M))
    for cls in sorted(used - set(re.findall(r"^\s*classDef (\S+)", src, re.M))):
        problems.append(f"uses class {cls!r} without defining it")
    for m in re.finditer(r"^\s*style (\S+) (.*)$", src, re.M):
        if m.group(2).strip() != GROUP_STYLE:
            problems.append(f"style {m.group(1)} should be the shared group style: {GROUP_STYLE}")
    return [f"docs/diagrams/{name}.mmd: {p}" for p in problems]


def check_docs(names: set[str]) -> list[str]:
    problems, referenced = [], set()
    for rel in DOCS:
        text = (ROOT / rel).read_text()
        if "```mermaid" in text:
            problems.append(f"{rel}: has a Mermaid block; add it to docs/diagrams/ and embed the image instead")
        for m in IMAGE_REF.finditer(text):
            referenced.add(m.group(1))
            if m.group(1) not in names:
                problems.append(f"{rel}: embeds {m.group(0)}, which has no source in docs/diagrams/")
    problems += [f"docs/diagrams/{n}.mmd: not embedded in any document" for n in sorted(names - referenced)]
    return problems


def check_images(srcs: dict[str, str]) -> list[str]:
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    problems = []
    for name, src in srcs.items():
        missing = [ext for ext in ("svg", "png") if not (OUT / f"{name}.{ext}").exists()]
        if missing or manifest.get(name) != digest(src):
            problems.append(f"{name}: image is missing or stale; run `make diagrams` and commit the result")
    extra = sorted({p.stem for p in OUT.glob("*.*") if p.suffix in (".svg", ".png")} - set(srcs))
    problems += [f"docs/assets/diagrams/{n}.*: no source in docs/diagrams/; delete it" for n in extra]
    problems += [f"manifest.json: entry {n!r} has no source" for n in sorted(set(manifest) - set(srcs))]
    return problems


def render(src: str, out: Path) -> str | None:
    mmdc = shlex.split(os.environ.get("MMDC", "mmdc"))
    with tempfile.NamedTemporaryFile("w", suffix=".mmd", delete=False) as f:
        f.write(src)
    cmd = [*mmdc, "-q", "-i", f.name, "-o", str(out), "-c", str(THEME), "-b", "white", "-w", str(PAGE_WIDTH)]
    if os.environ.get("PUPPETEER_CONFIG"):
        cmd += ["-p", os.environ["PUPPETEER_CONFIG"]]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    os.unlink(f.name)
    if result.returncode != 0:
        return ((result.stderr or result.stdout).strip().splitlines() or ["mmdc failed"])[-1]
    if out.suffix == ".svg":
        svg = out.read_text()
        if "Syntax error" in svg or "<foreignObject" in svg:
            return "syntax error or HTML label in the rendered SVG"
        out.write_text(fixed_size(svg))
    return None


def fixed_size(svg: str) -> str:
    """Give the SVG its natural size, so an <img> shows it at scale and GitHub shrinks it only to fit."""
    box = re.search(r'viewBox="\S+ \S+ ([\d.]+) ([\d.]+)"', svg)
    if not box:
        return svg
    w, h = (round(float(v)) for v in box.groups())
    svg = svg.replace('width="100%"', f'width="{w}" height="{h}"', 1)
    return re.sub(r"max-width: [\d.]+px; ?", "", svg, count=1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="check sources, documents and image freshness only")
    ap.add_argument("--render", action="store_true", help="with --check: also render each source to a temp dir")
    args = ap.parse_args()

    srcs = sources()
    problems = check_theme() + [p for name, src in srcs.items() for p in check_source(name, src)]
    problems += check_docs(set(srcs))
    if args.check:
        problems += check_images(srcs)
        if args.render:
            with tempfile.TemporaryDirectory() as tmp:
                for name, src in srcs.items():
                    err = render(src, Path(tmp) / f"{name}.svg")
                    print(f"{name:<20} {'ok' if err is None else 'FAIL: ' + err}")
                    problems += [f"{name}: render failed: {err}"] if err else []
    elif not problems:
        OUT.mkdir(parents=True, exist_ok=True)
        for old in OUT.glob("*.*"):
            if old.suffix in (".svg", ".png") and old.stem not in srcs:
                old.unlink()
        manifest = {}
        for name, src in srcs.items():
            err = render(src, OUT / f"{name}.svg") or render(src, OUT / f"{name}.png")
            print(f"{name:<20} {'ok' if err is None else 'FAIL: ' + err}")
            if err:
                problems.append(f"{name}: render failed: {err}")
            else:
                manifest[name] = digest(src)
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    for p in problems:
        print(p, file=sys.stderr)
    print(f"{len(srcs)} diagrams, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
