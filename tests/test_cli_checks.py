"""Tests for generics checking and not-implemented command exits."""

import sys

from parsercraft.tooling.cli import main


def _run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["parsercraft", *argv])
    return main()


def test_generics_accepts_matching_arity(tmp_path, monkeypatch, capsys):
    source = tmp_path / "generic.src"
    source.write_text(
        "class Box[T] {\n}\nbox = Box[int] ;\n",
        encoding="utf-8",
    )

    exit_code = _run(monkeypatch, "generics", str(source))

    assert exit_code == 0
    assert "Generic check passed" in capsys.readouterr().out


def test_generics_reports_arity_errors(tmp_path, monkeypatch, capsys):
    source = tmp_path / "generic.src"
    source.write_text(
        "class Box[T] {\n}\nbox = Box[int, str] ;\n",
        encoding="utf-8",
    )

    exit_code = _run(monkeypatch, "generics", str(source))

    assert exit_code == 1
    assert "expects 1 type argument(s), got 2" in capsys.readouterr().err


def test_generics_infers_arguments(tmp_path, monkeypatch, capsys):
    source = tmp_path / "generic.src"
    source.write_text(
        "def identity[T](x) {\n}\nvalue = identity[int] ;\n",
        encoding="utf-8",
    )

    exit_code = _run(monkeypatch, "generics", str(source), "--infer")

    assert exit_code == 0
    assert "T=int" in capsys.readouterr().out


def test_generics_variance_rejects_function_markers(tmp_path, monkeypatch, capsys):
    source = tmp_path / "generic.src"
    source.write_text("def identity[+T](x) {\n}\n", encoding="utf-8")

    exit_code = _run(
        monkeypatch, "generics", str(source), "--check-variance"
    )

    assert exit_code == 1
    assert "variance marker" in capsys.readouterr().err


def test_generics_missing_file(tmp_path, monkeypatch, capsys):
    exit_code = _run(monkeypatch, "generics", str(tmp_path / "nope.src"))

    assert exit_code == 1
    assert "not found" in capsys.readouterr().err


def test_unimplemented_commands_exit_two(tmp_path, monkeypatch, capsys):
    source = tmp_path / "program.src"
    source.write_text("x = 1\n", encoding="utf-8")

    for argv in (
        ("check-protocol", str(source)),
        ("package-search", "query"),
        ("package-install", "pkg@1.0.0"),
    ):
        capsys.readouterr()
        assert _run(monkeypatch, *argv) == 2
        assert "not implemented" in capsys.readouterr().err


def test_type_check_json_diagnostics(tmp_path, monkeypatch, capsys):
    import json

    config = tmp_path / "lang.yaml"
    config.write_text("name: Lang\n", encoding="utf-8")
    source = tmp_path / "program.src"
    source.write_text("x: int = 1\ny: str = 2\n", encoding="utf-8")

    exit_code = _run(
        monkeypatch, "type-check",
        "--config", str(config), "--input", str(source), "--json",
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["file"] == str(source)
    assert payload["diagnostics"][0]["code"] == "E101"
    assert payload["diagnostics"][0]["line"] == 2


def test_type_check_text_output(tmp_path, monkeypatch, capsys):
    config = tmp_path / "lang.yaml"
    config.write_text("name: Lang\n", encoding="utf-8")
    source = tmp_path / "program.src"
    source.write_text("x: int = 1\n", encoding="utf-8")

    exit_code = _run(
        monkeypatch, "type-check",
        "--config", str(config), "--input", str(source),
    )

    assert exit_code == 0
    assert "No type errors" in capsys.readouterr().out
