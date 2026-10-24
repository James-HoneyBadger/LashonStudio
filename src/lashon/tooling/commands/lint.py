"""``lashon lint`` — config, grammar, and type checks in one command."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from lashon.config import LanguageConfig
from lashon.parser import GrammarParser
from lashon.tooling.commands.common import CONFIG_LOAD_ERRORS, load_raw_config
from lashon.types import TypeChecker


def cmd_lint(args) -> int:
    """Run configuration, grammar, and optional type checks."""
    config_path = Path(args.config)
    if config_path.suffix == ".peg":
        print(
            "Error: lint expects a language config (YAML/JSON). "
            "For a .peg grammar use: lashon-rs lint <grammar.peg> "
            "[--source FILE]",
            file=sys.stderr,
        )
        return 1
    if not config_path.exists():
        print(f"Error: File not found: {config_path}", file=sys.stderr)
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    grammar_rules = 0

    try:
        config = LanguageConfig.load(config_path)
    except CONFIG_LOAD_ERRORS as error:
        print(f"Error loading config: {error}", file=sys.stderr)
        return 1

    errors.extend(config.validate())
    warnings.extend(config.validation_warnings())

    try:
        raw = load_raw_config(config_path)
        grammar_data = raw.get("grammar") or {}
        if grammar_data.get("rules"):
            grammar = GrammarParser().parse(
                "\n".join(
                    f"{name} <- {pattern}"
                    for name, pattern in grammar_data["rules"].items()
                )
            )
            grammar.start_rule = grammar_data.get("start", "program")
            grammar.skip_whitespace = grammar_data.get(
                "skip_whitespace", True
            )
            grammar.comment_patterns = grammar_data.get("comments") or []
            errors.extend(grammar.validate())
            grammar_rules = len(grammar.rules)
        else:
            warnings.append("no grammar.rules section; grammar not checked")
    except (ValueError, SyntaxError) as error:
        errors.append(f"grammar: {error}")

    type_errors = 0
    if args.input:
        source = Path(args.input)
        if not source.exists():
            errors.append(f"source file not found: {source}")
        else:
            checker = TypeChecker(config)
            findings = checker.check_file(str(source))
            type_errors = len(findings)
            errors.extend(
                f"{finding.code}: {finding.message} (line {finding.line})"
                for finding in findings
            )

    if args.json:
        json.dump(
            {
                "ok": not errors,
                "errors": errors,
                "warnings": warnings,
                "grammar_rules": grammar_rules,
                "type_errors": type_errors,
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        print(f"Linting: {config_path}")
        print("=" * 70)
        print(f"  Grammar rules: {grammar_rules}")
        if args.input:
            print(f"  Source: {args.input}")
            print(f"  Type findings: {type_errors}")
        for warning in warnings:
            print(f"  ! {warning}")
        for error in errors:
            print(f"  ✗ {error}")
        if not errors:
            print("✓ No problems found")

    return 1 if errors else 0
