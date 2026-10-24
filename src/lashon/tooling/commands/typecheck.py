"""``lashon type-check`` — heuristic type analysis with JSON output."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from lashon.config import LanguageConfig
from lashon.types.type_system import AnalysisLevel, TypeChecker

_LEVELS = {
    "lenient": AnalysisLevel.LENIENT,
    "moderate": AnalysisLevel.MODERATE,
    "strict": AnalysisLevel.STRICT,
    "very-strict": AnalysisLevel.VERY_STRICT,
}


def _diagnostic_dict(error) -> dict:
    return {
        "kind": error.kind,
        "code": error.code,
        "message": error.message,
        "line": error.line,
        "column": error.column,
        "location": error.location,
        "suggestion": error.suggestion,
    }


def cmd_type_check(args) -> int:
    """Perform static type analysis on a source file."""
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}",
              file=sys.stderr)
        return 1

    source_path = Path(args.input)
    if not source_path.exists():
        print(f"Error: Source file not found: {source_path}", file=sys.stderr)
        return 1

    try:
        config = LanguageConfig.load(config_path)
    except Exception as error:  # config loader raises several types
        print(f"Error loading config: {error}", file=sys.stderr)
        return 1

    try:
        source_path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"Error reading source file: {error}", file=sys.stderr)
        return 1

    checker = TypeChecker(
        config,
        level=_LEVELS.get(args.level, AnalysisLevel.MODERATE),
    )

    try:
        errors = checker.check_file(str(source_path))
    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"Error during type checking: {error}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 1

    if args.json:
        json.dump(
            {
                "file": str(source_path),
                "level": args.level,
                "diagnostics": [_diagnostic_dict(err) for err in errors],
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 1 if errors else 0

    print(f"Type checking: {source_path}")
    print(f"Analysis level: {args.level}")
    print("=" * 70)

    if not errors:
        print("✓ No type errors found")
        return 0

    print(f"Found {len(errors)} error(s):\n")
    for err in errors:
        print(f"[{err.kind}] {err.message}")
        if err.location:
            print(f"  Location: {err.location}")
        if err.suggestion:
            print(f"  Suggestion: {err.suggestion}")
        print()
    return 1
