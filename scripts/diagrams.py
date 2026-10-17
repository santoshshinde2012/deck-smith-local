"""Check and render every Mermaid diagram in the docs, in GitHub's light and dark themes.

One semantic palette is used everywhere (see ``PALETTE``). Nodes carry explicit fill, stroke and
text colours, so they look the same in both themes. Diagrams set no ``%%{init}%%`` theme, so
edges, edge labels and subgraph titles follow GitHub's light or dark theme automatically. A diagram
may appear in more than one file (the README repeats the hexagonal view), but every copy with the
same name must be identical.

    python scripts/diagrams.py                     # check palette + render each diagram in both themes
    python scripts/diagrams.py --svg docs/diagrams # also write light-theme SVGs of named diagrams
    python scripts/diagrams.py --png out/arch --only hexagonal   # PNG previews (light and dark)

Rendering needs mermaid-cli: ``MMDC`` is the command (default ``mmdc``, for example
``MMDC="npx -y @mermaid-js/mermaid-cli@11"``) and ``PUPPETEER_CONFIG`` an optional browser config.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ["README.md", "ARCHITECTURE.md", *sorted(str(p.relative_to(ROOT)) for p in (ROOT / "docs").glob("*.md"))]

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
THEMES = {"light": ("default", "#FFFFFF"), "dark": ("dark", "#0D1117")}  # GitHub's page backgrounds

BLOCK = re.compile(r"```mermaid\n(.*?)```", re.S)


def blocks() -> list[tuple[str, int, str, str]]:
    """(file, line, name, source) for every mermaid block."""
    found = []
    for rel in DOCS:
        text = (ROOT / rel).read_text()
        for m in BLOCK.finditer(text):
            src = m.group(1)
            name = re.search(r"^%% diagram: (\S+)", src, re.M)
            found.append((rel, text[: m.start()].count("\n") + 1, name.group(1) if name else "", src))
    return found


def check_palette(rel: str, line: int, src: str) -> list[str]:
    problems = []
    if "%%{init" in src:
        problems.append("sets an init theme; leave theming to GitHub so dark mode works")
    for m in re.finditer(r"^\s*classDef (\S+) (.*)$", src, re.M):
        name = m.group(1)
        if name not in CLASSDEFS:
            problems.append(f"classDef {name!r} is not in the palette")
        elif m.group(0).strip() != CLASSDEFS[name]:
            want = CLASSDEFS[name]
            problems.append(f"classDef {name!r} differs from the palette:\n    {m.group(0).strip()}\n    {want}")
    used = set(re.findall(r":::(\w+)", src)) | set(re.findall(r"^\s*class\s.*\s(\w+)\s*$", src, re.M))
    for name in sorted(used - set(re.findall(r"^\s*classDef (\S+)", src, re.M))):
        problems.append(f"uses class {name!r} without defining it")
    for m in re.finditer(r"^\s*style (\S+) (.*)$", src, re.M):
        if m.group(2).strip() != GROUP_STYLE:
            problems.append(f"style {m.group(1)} should be the shared group style: {GROUP_STYLE}")
    return [f"{rel}:{line}: {p}" for p in problems]


def render(src: str, out: Path, theme: str, scale: int = 1) -> str | None:
    mmdc = shlex.split(os.environ.get("MMDC", "mmdc"))
    mermaid_theme, background = THEMES[theme]
    with tempfile.NamedTemporaryFile("w", suffix=".mmd", delete=False) as f:
        f.write(src)
    cmd = [*mmdc, "-q", "-i", f.name, "-o", str(out), "-t", mermaid_theme, "-b", background, "-s", str(scale)]
    if os.environ.get("PUPPETEER_CONFIG"):
        cmd += ["-p", os.environ["PUPPETEER_CONFIG"]]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    os.unlink(f.name)
    if result.returncode != 0:
        return (result.stderr or result.stdout).strip().splitlines()[-1]
    if out.suffix == ".svg" and "Syntax error" in out.read_text():
        return "Syntax error in rendered SVG"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--svg", type=Path, help="write light-theme SVGs of named diagrams here")
    ap.add_argument("--png", type=Path, help="write light and dark PNG previews here")
    ap.add_argument("--only", help="limit --svg/--png to one diagram name")
    ap.add_argument("--no-render", action="store_true", help="check the palette only")
    args = ap.parse_args()

    found = blocks()
    if args.only and args.only not in {n for _, _, n, _ in found}:
        print(f"no diagram named {args.only!r}", file=sys.stderr)
        return 1
    problems = [p for rel, line, _, src in found for p in check_palette(rel, line, src)]
    sources: dict[str, str] = {}
    for rel, line, name, src in found:
        if name and sources.setdefault(name, src) != src:
            problems.append(f"{rel}:{line}: diagram {name!r} differs from another copy with the same name")
    if not args.no_render:
        with tempfile.TemporaryDirectory() as tmp:
            for rel, line, name, src in found:
                for theme in THEMES:
                    err = render(src, Path(tmp) / "d.svg", theme)
                    status = "ok" if err is None else f"FAIL: {err}"
                    print(f"{rel}:{line} {name or '-':<22} {theme:<5} {status}")
                    if err:
                        problems.append(f"{rel}:{line}: {theme} render failed: {err}")
    for name, src in sources.items():
        if args.only and name != args.only:
            continue
        if args.svg:
            args.svg.mkdir(parents=True, exist_ok=True)
            err = render(src, args.svg / f"{name}.svg", "light")
            problems += [f"{name}: svg failed: {err}"] if err else []
        if args.png:
            args.png.mkdir(parents=True, exist_ok=True)
            for theme in THEMES:
                err = render(src, args.png / f"{name}-{theme}.png", theme, scale=2)
                problems += [f"{name}: {theme} png failed: {err}"] if err else []
    for p in problems:
        print(p, file=sys.stderr)
    print(f"{len(found)} diagrams, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
