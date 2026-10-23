"""Tests for ``parsercraft init``."""

import sys

from parsercraft.ide.studio import LanguageStudio
from parsercraft.tooling.cli import main


def _run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["parsercraft", *argv])
    return main()


def test_init_creates_a_runnable_project(tmp_path, monkeypatch, capsys):
    exit_code = _run(
        monkeypatch, "init", "Tiny Lang", "--directory", str(tmp_path)
    )

    assert exit_code == 0
    root = tmp_path / "tiny-lang"
    for relative in (
        "language.yaml",
        "grammar.peg",
        "samples/hello.aur",
        "README.md",
        "tests/test_tiny_lang.py",
    ):
        assert (root / relative).is_file(), relative

    studio = LanguageStudio()
    project = studio.open_project(root)
    assert studio.validate_grammar().ok
    assert studio.run(
        project.sample_path.read_text(encoding="utf-8")
    ).ok
    assert "Created Tiny Lang" in capsys.readouterr().out


def test_init_refuses_to_overwrite(tmp_path, monkeypatch, capsys):
    assert _run(
        monkeypatch, "init", "Tiny", "--directory", str(tmp_path)
    ) == 0
    capsys.readouterr()

    exit_code = _run(
        monkeypatch, "init", "Tiny", "--directory", str(tmp_path)
    )

    assert exit_code == 1
    assert "already exists" in capsys.readouterr().err


def test_init_force_overwrites(tmp_path, monkeypatch):
    assert _run(
        monkeypatch, "init", "Tiny", "--directory", str(tmp_path)
    ) == 0
    (tmp_path / "tiny" / "samples" / "hello.aur").write_text(
        "broken", encoding="utf-8"
    )

    assert _run(
        monkeypatch, "init", "Tiny", "--directory", str(tmp_path), "--force"
    ) == 0
    assert "Hello from Tiny!" in (
        tmp_path / "tiny" / "samples" / "hello.aur"
    ).read_text(encoding="utf-8")


def test_init_rejects_missing_parent(tmp_path, monkeypatch, capsys):
    exit_code = _run(
        monkeypatch, "init", "Tiny", "--directory", str(tmp_path / "missing")
    )

    assert exit_code == 1
    assert "not found" in capsys.readouterr().err


def test_init_calculator_template(tmp_path, monkeypatch):
    assert _run(
        monkeypatch,
        "init", "Calc", "--directory", str(tmp_path),
        "--template", "calculator",
    ) == 0

    root = tmp_path / "calc"
    sample = (root / "samples" / "calc.aur").read_text(encoding="utf-8")
    assert "width * height" in sample

    studio = LanguageStudio()
    studio.open_project(root)
    assert studio.validate_grammar().ok
    assert studio.run(sample).ok
    assert all(r.ok for r in studio.generate_all(sample).values())


def test_init_minimal_template(tmp_path, monkeypatch):
    assert _run(
        monkeypatch,
        "init", "Mini", "--directory", str(tmp_path),
        "--template", "minimal",
    ) == 0

    studio = LanguageStudio()
    studio.open_project(tmp_path / "mini")
    assert studio.validate_grammar().ok
    assert "print" in (tmp_path / "mini" / "grammar.peg").read_text()


def test_init_with_vscode_and_ci(tmp_path, monkeypatch):
    assert _run(
        monkeypatch,
        "init", "Scaffold", "--directory", str(tmp_path),
        "--with-vscode", "--with-ci",
    ) == 0

    root = tmp_path / "scaffold"
    launch = (root / ".vscode" / "launch.json").read_text(encoding="utf-8")
    assert "parsercraft.tooling.cli" in launch
    assert (root / ".vscode" / "settings.json").is_file()

    workflow = (
        root / ".github" / "workflows" / "language.yml"
    ).read_text(encoding="utf-8")
    assert "parsercraft lint" in workflow
    assert "parsercraft run" in workflow
