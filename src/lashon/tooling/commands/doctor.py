"""``lashon doctor`` — environment and toolchain diagnostics."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


def _check(name: str, status: str, detail: str, fix: str = "") -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, "fix": fix}


def _check_python() -> dict[str, Any]:
    if sys.version_info >= (3, 10):
        return _check(
            "Python",
            "ok",
            f"{sys.version.split()[0]} ({sys.executable})",
        )
    return _check(
        "Python",
        "error",
        sys.version.split()[0],
        "Install Python 3.10 or newer.",
    )


def _check_module(module: str, label: str, required: bool) -> dict[str, Any]:
    if importlib.util.find_spec(module) is not None:
        return _check(label, "ok", "installed")
    return _check(
        label,
        "error" if required else "warn",
        "not installed",
        f"pip install {module}",
    )


def _check_tkinter() -> dict[str, Any]:
    if importlib.util.find_spec("tkinter") is None:
        return _check(
            "Tkinter",
            "warn",
            "not installed",
            "Install python3-tk (Debian/Ubuntu) or python3-tkinter (Fedora).",
        )
    try:
        import tkinter as tk

        root = tk.Tk()
        root.destroy()
    except Exception as error:  # pylint: disable=broad-exception-caught
        return _check(
            "Display",
            "warn",
            f"Tk cannot open a window: {error}",
            "Run a desktop session or use the CLI/LanguageStudio headlessly.",
        )
    return _check("Tkinter", "ok", "available with a display")


def _check_entry_point(name: str, required: bool) -> dict[str, Any]:
    path = shutil.which(name)
    if not path:
        sibling = Path(sys.executable).parent / name
        if sibling.exists():
            path = str(sibling)
    if path:
        return _check(name, "ok", path)
    return _check(
        name,
        "error" if required else "warn",
        "not on PATH",
        'Activate the virtualenv or reinstall with pip install -e ".[dev]".',
    )


def _check_tool(name: str, required: bool) -> dict[str, Any]:
    path = shutil.which(name)
    if path:
        return _check(name, "ok", path)
    return _check(
        name,
        "error" if required else "warn",
        "not found",
        f"Install {name} to enable that backend.",
    )


def _check_wasmtime() -> dict[str, Any]:
    if importlib.util.find_spec("wasmtime") is not None:
        return _check("wasmtime", "ok", "installed")
    return _check(
        "wasmtime",
        "warn",
        "not installed",
        'pip install -e ".[dev]" to run WASM execution tests.',
    )


def _check_writable(label: str, path: Path) -> dict[str, Any]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".lashon-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as error:
        return _check(label, "error", f"{path}: {error}", "Choose a writable directory.")
    return _check(label, "ok", str(path))


def collect_checks() -> list[dict[str, Any]]:
    checks = [
        _check_python(),
        _check_module("yaml", "PyYAML", required=True),
        _check_entry_point("lashon", required=True),
        _check_entry_point("lashon-ide", required=False),
        _check_entry_point("lashon-repl", required=False),
        _check_tkinter(),
        _check_tool("gcc", required=False),
        _check_tool("clang", required=False),
        _check_wasmtime(),
        _check_writable("Working directory", Path.cwd()),
        _check_writable(
            "Config directory",
            Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
            / "lashon",
        ),
    ]
    return checks


def cmd_doctor(args) -> int:
    """Report environment readiness for Lashon."""
    checks = collect_checks()
    failures = [c for c in checks if c["status"] == "error"]
    warnings = [c for c in checks if c["status"] == "warn"]

    if args.json:
        json.dump(
            {
                "ok": not failures,
                "checks": checks,
                "errors": len(failures),
                "warnings": len(warnings),
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        symbols = {"ok": "✓", "warn": "!", "error": "✗"}
        for check in checks:
            symbol = symbols[check["status"]]
            print(f"{symbol} {check['name']:<20} {check['detail']}")
            if check["status"] != "ok" and check["fix"]:
                print(f"    fix: {check['fix']}")
        print()
        if failures:
            print(f"{len(failures)} blocking issue(s), {len(warnings)} warning(s)")
        elif warnings:
            print(f"Ready with {len(warnings)} warning(s)")
        else:
            print("Everything looks ready.")

    if failures:
        return 1
    if args.strict and warnings:
        return 1
    return 0
