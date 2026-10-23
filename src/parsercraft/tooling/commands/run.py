"""``parsercraft run`` — parse a program and execute it."""

from __future__ import annotations

import contextlib
import json
import sys
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
