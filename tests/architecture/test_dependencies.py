"""Enforce the dependency rule: domain <- ports <- application <- adapters, wired only in bootstrap."""

import ast
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[2] / "src" / "decksmith"

RULES = {
    # layer: prefixes it must NOT import
    "domain": (
        "decksmith.ports",
        "decksmith.application",
        "decksmith.adapters",
        "decksmith.bootstrap",
        "decksmith.interfaces",
        "langgraph",
        "mlflow",
        "duckdb",
        "pptx",
        "httpx",
        "openai",
        "fastapi",
    ),
    "ports": (
        "decksmith.application",
        "decksmith.adapters",
        "decksmith.bootstrap",
        "decksmith.interfaces",
        "langgraph",
        "mlflow",
        "duckdb",
        "pptx",
        "httpx",
        "openai",
        "fastapi",
    ),
    "application": (
        "decksmith.adapters",
        "decksmith.bootstrap",
        "decksmith.interfaces",
        "duckdb",
        "pptx",
        "httpx",
        "openai",
        "fastapi",
        "mlflow",
    ),
    "adapters": ("decksmith.application", "decksmith.bootstrap", "decksmith.interfaces"),
}


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("layer", sorted(RULES))
def test_layer_dependencies(layer: str) -> None:
    violations = [
        f"{f.relative_to(PKG)} imports {name}"
        for f in (PKG / layer).rglob("*.py")
        for name in _imports(f)
        if name.startswith(RULES[layer])
    ]
    assert not violations, "\n".join(violations)


def test_only_bootstrap_imports_adapters() -> None:
    offenders = [
        str(f.relative_to(PKG))
        for f in PKG.rglob("*.py")
        if not f.is_relative_to(PKG / "adapters")
        and f.name != "bootstrap.py"
        and any(n.startswith("decksmith.adapters") for n in _imports(f))
    ]
    assert not offenders


def test_local_and_databricks_adapters_independent() -> None:
    for side, other in (("local", "databricks"), ("databricks", "local")):
        for f in (PKG / "adapters" / side).rglob("*.py"):
            assert not any(n.startswith(f"decksmith.adapters.{other}") for n in _imports(f)), f
