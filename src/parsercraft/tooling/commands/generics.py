"""``parsercraft generics`` — check generic declarations and instantiations."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from parsercraft.types import GenericsTypeChecker

_DECL = re.compile(
    r"^\s*(class|def|fn|func)\s+(\w+)\s*\[([^\]]*)\]"
)
_INST = re.compile(r"\b(\w+)\s*\[([^\]]+)\]")
_IDENT = re.compile(r"^[A-Za-z_]\w*$")


def _split_params(text: str) -> list[tuple[str, str]]:
    """Return ``(name, variance)`` pairs from ``+T, -U`` syntax."""
    params: list[tuple[str, str]] = []
    for raw in text.split(","):
        item = raw.strip()
        if not item:
            continue
        variance = "invariant"
        if item[0] in "+-":
            variance = "covariant" if item[0] == "+" else "contravariant"
            item = item[1:].strip()
        params.append((item, variance))
    return params


def cmd_generics(args) -> int:
    """Validate generic declarations and instantiation arity."""
    path = Path(args.file)
    if not path.exists():
        print(f"Error: Source file not found: {path}", file=sys.stderr)
        return 1

    try:
        source = path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"Error reading source file: {error}", file=sys.stderr)
        return 1

    checker = GenericsTypeChecker()
    declared: dict[str, list[str]] = {}
    errors: list[str] = []
    inferences: list[str] = []

    for number, line in enumerate(source.splitlines(), 1):
        declaration = _DECL.match(line)
        if declaration:
            kind, name, params_text = declaration.groups()
            params = _split_params(params_text)
            names = [param for param, _ in params]
            if not names:
                errors.append(f"{number}: {name} declares no type parameters")
                continue
            for param, _variance in params:
                if not _IDENT.match(param):
                    errors.append(
                        f"{number}: invalid type parameter '{param}'"
                    )
                elif param in names[names.index(param) + 1:]:
                    errors.append(f"{number}: duplicate type parameter '{param}'")
            if args.check_variance:
                for param, variance in params:
                    if variance != "invariant" and kind != "class":
                        errors.append(
                            f"{number}: variance marker on function parameter "
                            f"'{param}' has no effect"
                        )
            declared[name] = names
            if kind == "class":
                checker.check_generic_class(name, names, None)
            else:
                checker.check_generic_function(name, names, None)
            continue

        for match in _INST.finditer(line):
            name, args_text = match.groups()
            if name not in declared:
                continue
            supplied = [item.strip() for item in args_text.split(",") if item.strip()]
            expected = declared[name]
            if len(supplied) != len(expected):
                errors.append(
                    f"{number}: {name} expects {len(expected)} type "
                    f"argument(s), got {len(supplied)}"
                )
            elif args.infer:
                pairs = ", ".join(
                    f"{param}={value}"
                    for param, value in zip(expected, supplied)
                )
                inferences.append(f"{number}: {name}[{args_text}] -> {pairs}")

    if args.infer and inferences:
        print("Inferred type arguments:")
        for line in inferences:
            print(f"  {line}")

    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        print(
            f"Generic check failed with {len(errors)} error(s)",
            file=sys.stderr,
        )
        return 1

    print(f"✓ Generic check passed: {path}")
    if declared:
        print(
            "  Declarations: "
            + ", ".join(
                f"{name}[{', '.join(params)}]"
                for name, params in declared.items()
            )
        )
    return 0
