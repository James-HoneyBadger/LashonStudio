"""``lashon init`` — scaffold a new language project."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from lashon.ide.studio import LanguageStudio

_PROJECT_TEST = '''"""Tests for the {name} language project."""

from pathlib import Path

from lashon.ide.studio import LanguageStudio

PROJECT = Path(__file__).resolve().parents[1]


def test_grammar_validates():
    studio = LanguageStudio()
    studio.open_project(PROJECT)
    assert studio.validate_grammar().ok


def test_sample_runs():
    studio = LanguageStudio()
    project = studio.open_project(PROJECT)
    source = project.sample_path.read_text(encoding="utf-8")
    result = studio.run(source)
    assert result.ok, result.error


def test_all_backends_generate():
    studio = LanguageStudio()
    project = studio.open_project(PROJECT)
    source = project.sample_path.read_text(encoding="utf-8")
    for backend, result in studio.generate_all(source).items():
        assert result.ok, (backend, result.error)
'''


_TEMPLATES: dict[str, dict[str, Any]] = {
    "aurora": {
        "description": "Full language: functions, control flow, and calls.",
        "rules": {
            "program": "statement+",
            "statement": (
                "function_def / if_stmt / while_stmt / return_stmt / "
                "print_stmt / assignment / expr_stmt"
            ),
            "function_def": "'fn' IDENT '(' param_list? ')' block",
            "block": "'{' statement* '}'",
            "param_list": "IDENT (',' IDENT)*",
            "if_stmt": "'if' comparison block ('else' block)?",
            "while_stmt": "'while' comparison block",
            "return_stmt": "'return' expr ';'",
            "print_stmt": "'print' expr ';'",
            "assignment": "IDENT '=' expr ';'",
            "expr_stmt": "call ';'",
            "comparison": "expr ('==' / '!=' / '<=' / '>=' / '<' / '>') expr",
            "expr": "term (('+' / '-') term)*",
            "term": "factor (('*' / '/' / '%') factor)*",
            "factor": (
                "call / NUMBER / STRING / boolean / IDENT / '(' expr ')'"
            ),
            "call": "IDENT '(' arg_list? ')'",
            "arg_list": "expr (',' expr)*",
            "boolean": "'true' / 'false'",
        },
        "samples": [
            (
                "hello.aur",
                """// Welcome to {name}
print "Hello from {name}!" ;
""",
            ),
            (
                "fizzbuzz.aur",
                """// FizzBuzz in {name}
i = 1 ;
while i < 16 {{
    if i % 15 == 0 {{
        print "FizzBuzz" ;
    }} else {{
        if i % 3 == 0 {{
            print "Fizz" ;
        }} else {{
            if i % 5 == 0 {{
                print "Buzz" ;
            }} else {{
                print i ;
            }}
        }}
    }}
    i = i + 1 ;
}}
""",
            ),
        ],
    },
    "calculator": {
        "description": "Expression evaluator with print and variables.",
        "rules": {
            "program": "statement+",
            "statement": "print_stmt / assignment / expr_stmt",
            "print_stmt": "'print' expr ';'",
            "assignment": "IDENT '=' expr ';'",
            "expr_stmt": "expr ';'",
            "expr": "term (('+' / '-') term)*",
            "term": "factor (('*' / '/' / '%') factor)*",
            "factor": "NUMBER / IDENT / '(' expr ')'",
        },
        "samples": [
            (
                "calc.aur",
                """// Try arithmetic in {name}
width = 12 ;
height = 7 ;
print width * height ;
print (width + height) * 2 ;
print 10 % 3 ;
""",
            )
        ],
    },
    "minimal": {
        "description": "Smallest useful grammar: assignments and print.",
        "rules": {
            "program": "statement+",
            "statement": "print_stmt / assignment",
            "print_stmt": "'print' expr ';'",
            "assignment": "IDENT '=' expr ';'",
            "expr": "term (('+' / '-') term)*",
            "term": "factor (('*' / '/') factor)*",
            "factor": "NUMBER / STRING / IDENT / '(' expr ')'",
        },
        "samples": [
            (
                "hello.lang",
                """print "Hello from {name}!" ;
answer = 6 * 7 ;
print answer ;
""",
            )
        ],
    },
}


def _apply_template(project, template: str) -> None:
    """Rewrite a freshly scaffolded project to match ``template``."""
    from lashon.ide.studio import rules_to_peg

    spec = _TEMPLATES[template]
    rules = spec["rules"]
    project.grammar_text = rules_to_peg(rules)
    project.config["grammar"]["rules"] = dict(rules)
    for stale in (project.root / "samples").iterdir():
        if stale.is_file():
            stale.unlink()
    sample_path = None
    for filename, text in spec["samples"]:
        path = project.root / "samples" / filename
        path.write_text(text.format(name=project.name), encoding="utf-8")
        sample_path = sample_path or path
    assert sample_path is not None
    project.sample_path = sample_path
    project.save()


def _write_vscode_files(project) -> None:
    """Emit a launch configuration for the bundled VS Code client."""
    vscode_dir = project.root / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    launch = {
        "version": "0.2.0",
        "configurations": [
            {
                "name": f"Run {project.name} sample",
                "type": "python",
                "request": "launch",
                "module": "lashon.tooling.cli",
                "args": [
                    "run",
                    "${workspaceFolder}/samples/"
                    + project.sample_path.name,
                    "--config",
                    "${workspaceFolder}/language.yaml",
                ],
                "console": "integratedTerminal",
            }
        ],
    }
    (vscode_dir / "launch.json").write_text(
        json.dumps(launch, indent=2) + "\n", encoding="utf-8"
    )
    (vscode_dir / "settings.json").write_text(
        json.dumps(
            {
                "files.associations": {
                    f"*{project.sample_path.suffix}": "plaintext"
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_ci_workflow(project) -> None:
    """Emit a GitHub Actions workflow that validates the language."""
    workflow_dir = project.root / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    (workflow_dir / "language.yml").write_text(
        f"""name: {project.name}

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install lashon pytest
      - run: lashon lint language.yaml
      - run: lashon validate language.yaml --grammar
      - run: lashon run samples/{project.sample_path.name} --config language.yaml
      - run: python -m pytest tests -q
""",
        encoding="utf-8",
    )


def _project_slug(name: str) -> str:
    slug = "".join(
        ch.lower() if ch.isalnum() else "-" for ch in name
    ).strip("-")
    return slug or "my-language"


def cmd_init(args) -> int:
    """Create a language project with config, grammar, sample, and tests."""
    if any(separator in args.name for separator in ("/", "\\", os.sep)):
        print(
            f"Error: '{args.name}' looks like a path. Pass the language name "
            "and the parent directory separately:\n"
            f"  lashon init my-lang --directory {Path(args.name).parent}",
            file=sys.stderr,
        )
        return 1

    parent = Path(args.directory).expanduser()
    if not parent.exists():
        print(f"Error: Directory not found: {parent}", file=sys.stderr)
        return 1

    root = parent.resolve() / _project_slug(args.name)
    if root.exists() and any(root.iterdir()) and not args.force:
        print(
            f"Error: {root} already exists and is not empty "
            "(use --force to overwrite)",
            file=sys.stderr,
        )
        return 1

    try:
        studio = LanguageStudio()
        project = studio.new_project(args.name, parent)
    except (OSError, ValueError) as error:
        print(f"Error creating project: {error}", file=sys.stderr)
        return 1

    template = getattr(args, "template", "aurora")
    try:
        _apply_template(project, template)
    except (KeyError, OSError) as error:
        print(f"Error applying template: {error}", file=sys.stderr)
        return 1

    if getattr(args, "with_vscode", False):
        _write_vscode_files(project)
    if getattr(args, "with_ci", False):
        _write_ci_workflow(project)

    tests_dir = project.root / "tests"
    tests_dir.mkdir(exist_ok=True)
    module = _project_slug(args.name).replace("-", "_")
    (tests_dir / f"test_{module}.py").write_text(
        _PROJECT_TEST.format(name=args.name),
        encoding="utf-8",
    )

    print(f"✓ Created {project.root} — {args.name} (template: {template})")
    print(f"  {project.config_path.name}  language configuration + grammar")
    print(f"  {project.sample_path.name}  first sample program")
    print("  tests/                    grammar, run, and backend checks")
    if getattr(args, "with_vscode", False):
        print("  .vscode/                  run configuration for VS Code")
    if getattr(args, "with_ci", False):
        print("  .github/workflows/        continuous integration")
    print()
    print("Next steps:")
    print(f"  lashon-ide {project.root}")
    print(
        f"  lashon run {project.sample_path} "
        f"--config {project.config_path}"
    )
    print(f"  python -m pytest {tests_dir} -q")
    return 0
