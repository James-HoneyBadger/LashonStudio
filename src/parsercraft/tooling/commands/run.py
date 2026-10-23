"""``parsercraft run`` — parse a program and execute it."""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from parsercraft.codegen import transpile_and_exec, transpile_to_python
from parsercraft.parser import PEGInterpreter
from parsercraft.tooling.commands.common import load_grammar


def _json_safe(namespace: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-serialisable view of an execution namespace."""
    result: dict[str, Any] = {}
    for name, value in namespace.items():
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            result[name] = repr(value)
        else:
            result[name] = value
    return result


def _sandbox_limits() -> None:
    """Apply conservative resource limits in the child (POSIX only)."""
    try:
        import resource
    except ImportError:  # pragma: no cover - Windows
        return
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024,) * 2)


def _run_sandboxed(code: str, timeout: float) -> int:
    """Run generated Python in an isolated child process with limits."""
    with tempfile.TemporaryDirectory(prefix="parsercraft-run-") as workdir:
        script = Path(workdir) / "program.py"
        script.write_text(code, encoding="utf-8")
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        preexec = _sandbox_limits if os.name == "posix" else None
        try:
            completed = subprocess.run(
                [sys.executable, "-I", str(script)],
                cwd=workdir,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
                preexec_fn=preexec,
                check=False,
            )
        except subprocess.TimeoutExpired:
            print(
                f"Error: sandboxed program exceeded {timeout:g}s",
                file=sys.stderr,
            )
            return 124

    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)
    return completed.returncode


def cmd_run(args) -> int:
    """Parse and execute a source file."""
    source_path = Path(args.file)
    if not source_path.exists():
        print(f"Error: Source file not found: {source_path}", file=sys.stderr)
        return 1

    try:
        source = source_path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"Error reading source file: {error}", file=sys.stderr)
        return 1

    try:
        grammar = load_grammar(
            config_path=args.config,
            grammar_path=args.grammar,
            require_rules=True,
        )
        ast = PEGInterpreter(grammar).parse(source)

        if args.show_python:
            print(transpile_to_python(ast), file=sys.stderr)

        if args.sandbox:
            if args.json:
                print(
                    "Error: --json cannot be combined with --sandbox",
                    file=sys.stderr,
                )
                return 1
            code = transpile_to_python(ast)
            return _run_sandboxed(code, args.sandbox_timeout)

        if args.json:
            # Keep stdout valid JSON by sending program output to stderr.
            with contextlib.redirect_stdout(sys.stderr):
                namespace = transpile_and_exec(ast)
            json.dump({"variables": _json_safe(namespace)}, sys.stdout)
            sys.stdout.write("\n")
        else:
            transpile_and_exec(ast)

        return 0

    except (SyntaxError, ValueError, OSError, ImportError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # pylint: disable=broad-exception-caught
        print(
            f"Runtime error: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1
