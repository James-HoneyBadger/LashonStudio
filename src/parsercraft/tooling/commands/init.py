"""``parsercraft init`` — scaffold a new language project."""

from __future__ import annotations

import sys
from pathlib import Path

from parsercraft.ide.studio import LanguageStudio

_PROJECT_TEST = '''"""Tests for the {name} language project."""

from pathlib import Path

from parsercraft.ide.studio import LanguageStudio

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


def _project_slug(name: str) -> str:
    slug = "".join(
        ch.lower() if ch.isalnum() else "-" for ch in name
    ).strip("-")
    return slug or "my-language"


def cmd_init(args) -> int:
    """Create a language project with config, grammar, sample, and tests."""
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

    tests_dir = project.root / "tests"
    tests_dir.mkdir(exist_ok=True)
    module = _project_slug(args.name).replace("-", "_")
    (tests_dir / f"test_{module}.py").write_text(
        _PROJECT_TEST.format(name=args.name),
        encoding="utf-8",
    )

    print(f"✓ Created {args.name} in {project.root}")
    print(f"  {project.config_path.name}  language configuration + grammar")
    print(f"  {project.sample_path.name}  first sample program")
    print("  tests/                    grammar, run, and backend checks")
    print()
    print("Next steps:")
    print(f"  parsercraft-ide {project.root}")
    print(
        f"  parsercraft run {project.sample_path} "
        f"--config {project.config_path}"
    )
    print(f"  python -m pytest {tests_dir} -q")
    return 0
