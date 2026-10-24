"""Architecture contracts.

These tests encode the dependency rule the package layout is supposed to
follow, so a refactor cannot quietly reintroduce a cycle or drag a GUI or
socket dependency into the parsing core.

Layers (lower may be imported by higher, never the reverse)::

    core      lashon.ast · config · parser · codegen · types
    app       lashon.runtime
    adapters  lashon.tooling · ide · packaging
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "src" / "lashon"

CORE = {"ast", "config", "parser", "codegen", "types"}
APP = {"runtime"}
ADAPTERS = {"tooling", "ide", "packaging"}
LAYER = {
    **{name: "core" for name in CORE},
    **{name: "app" for name in APP},
    **{name: "adapters" for name in ADAPTERS},
}

#: Adapter-to-adapter edges that are deliberately allowed. Each target must be
#: a headless module (no Tk import), which the separate Tk check enforces.
ALLOWED_ADAPTER_EDGES = {
    ("tooling", "ide"),
    ("tooling", "packaging"),
}

#: Libraries that only belong to a specific layer.
FORBIDDEN = {
    "core": {"tkinter", "socket", "http", "webbrowser", "argparse"},
    # Console entry points (``lashon-repl``) legitimately parse argv.
    "app": {"tkinter"},
    "adapters": set(),
}

#: The parsing core must stay format-agnostic; YAML belongs to the loaders.
YAML_FORBIDDEN_PACKAGES = {"parser", "codegen", "ast", "types"}


def _package_of(path: Path) -> str:
    """Return the layer-facing package name for a module.

    Root-level modules (``lashon/ast.py``) are their own package so the
    contracts treat them like the small core packages they are.
    """
    parts = path.relative_to(PACKAGE_ROOT).parts
    if len(parts) == 1:
        return path.stem
    return parts[0]


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(PACKAGE_ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(["lashon", *parts])


def _resolve_relative(module: str, node: ast.ImportFrom) -> str:
    """Turn ``from ..x import y`` into an absolute module path."""
    if node.level == 0:
        return node.module or ""
    parts = module.split(".")
    base = parts[: max(len(parts) - node.level, 0)]
    if node.module:
        base += node.module.split(".")
    return ".".join(base)


def iter_imports(path: Path):
    """Yield ``(imported_module, line)`` for every import in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module = _module_name(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            yield _resolve_relative(module, node), node.lineno


def all_modules():
    return sorted(
        path
        for path in PACKAGE_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _target_package(imported: str) -> str | None:
    parts = imported.split(".")
    if parts[0] != "lashon" or len(parts) < 2:
        return None
    return parts[1]


def _violations(predicate):
    found = []
    for path in all_modules():
        source = _package_of(path)
        for imported, line in iter_imports(path):
            if predicate(source, imported):
                found.append(
                    f"{path.relative_to(PACKAGE_ROOT.parent.parent)}:{line} "
                    f"{source} -> {imported}"
                )
    return found


def test_core_never_imports_app_or_adapters():
    def bad(source, imported):
        target = _target_package(imported)
        return (
            LAYER.get(source) == "core"
            and target is not None
            and LAYER.get(target) in {"app", "adapters"}
        )

    violations = _violations(bad)
    assert not violations, (
        "core must not depend on runtime/adapters:\n" + "\n".join(violations)
    )


def test_app_never_imports_adapters():
    def bad(source, imported):
        target = _target_package(imported)
        return (
            LAYER.get(source) == "app"
            and target is not None
            and LAYER.get(target) == "adapters"
        )

    violations = _violations(bad)
    assert not violations, (
        "runtime must not depend on adapters:\n" + "\n".join(violations)
    )


def test_adapters_do_not_depend_on_each_other():
    def bad(source, imported):
        target = _target_package(imported)
        if target is None or LAYER.get(source) != "adapters":
            return False
        if LAYER.get(target) != "adapters" or target == source:
            return False
        return (source, target) not in ALLOWED_ADAPTER_EDGES

    violations = _violations(bad)
    assert not violations, (
        "adapters may not import each other:\n" + "\n".join(violations)
    )


def test_tooling_never_imports_tk_modules_directly():
    """The CLI and LSP must stay usable on a headless machine."""
    tk_modules = {
        "lashon.ide.studio_app",
        "lashon.ide.app",
        "lashon.ide.editor",
    }

    def bad(_source, imported):
        return imported in tk_modules

    violations = [
        entry
        for entry in _violations(bad)
        if entry.startswith("src/lashon/tooling")
    ]
    assert not violations, (
        "tooling must not import Tk widgets:\n" + "\n".join(violations)
    )


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_avoids_foreign_libraries(layer):
    forbidden = FORBIDDEN[layer]

    def bad(source, imported):
        if LAYER.get(source) != layer:
            return False
        return imported.split(".")[0] in forbidden

    violations = _violations(bad)
    assert not violations, (
        f"{layer} may not import {sorted(forbidden)}:\n" + "\n".join(violations)
    )


def test_parsing_core_stays_format_agnostic():
    """Only loader/CLI layers may know about YAML."""
    violations = []
    for path in all_modules():
        if _package_of(path) not in YAML_FORBIDDEN_PACKAGES:
            continue
        for imported, line in iter_imports(path):
            if imported.split(".")[0] == "yaml":
                relative = path.relative_to(PACKAGE_ROOT).as_posix()
                violations.append(f"src/lashon/{relative}:{line} imports yaml")
    assert not violations, "\n".join(violations)


def test_no_import_cycles_between_top_level_packages():
    graph: dict[str, set[str]] = defaultdict(set)
    for path in all_modules():
        source = _package_of(path)
        if source == "<root>":
            continue
        for imported, _line in iter_imports(path):
            target = _target_package(imported)
            if target and target != source:
                graph[source].add(target)

    cycles = []
    for start in graph:
        stack = [(start, [start])]
        while stack:
            node, trail = stack.pop()
            for neighbour in graph.get(node, ()):
                if neighbour == start:
                    cycles.append(" -> ".join(trail + [start]))
                elif neighbour not in trail and len(trail) < 6:
                    stack.append((neighbour, trail + [neighbour]))
    assert not cycles, "import cycles detected:\n" + "\n".join(sorted(set(cycles)))


def test_public_packages_declare_all():
    for name in sorted(CORE | APP | ADAPTERS):
        init = PACKAGE_ROOT / name / "__init__.py"
        if not init.is_file():  # single-module core packages (lashon/ast.py)
            init = PACKAGE_ROOT / f"{name}.py"
        tree = ast.parse(init.read_text(encoding="utf-8"))
        declared = any(
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            )
            for node in tree.body
        )
        assert declared, f"lashon/{name}/__init__.py should declare __all__"
