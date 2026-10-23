"""Tests for ``parsercraft run``."""

import json
import sys

from parsercraft.tooling.cli import main

GRAMMAR_CONFIG = """\
grammar:
  rules:
    program: 'statement+'
    statement: 'IDENT "=" expr ";" / print_stmt'
    print_stmt: "'print' IDENT ';'"
    expr: 'term (("+" / "-") term)*'
    term: 'factor (("*" / "/") factor)*'
    factor: 'NUMBER / IDENT'
"""


def _run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["parsercraft", *argv])
    return main()


def _write(tmp_path, source):
    config = tmp_path / "lang.yaml"
    config.write_text(GRAMMAR_CONFIG, encoding="utf-8")
    program = tmp_path / "program.src"
    program.write_text(source, encoding="utf-8")
    return config, program


def test_run_executes_and_prints(tmp_path, monkeypatch, capsys):
    config, program = _write(tmp_path, "x = 21 ;\nprint x ;\n")

    exit_code = _run(
        monkeypatch, "run", str(program), "--config", str(config)
    )

    assert exit_code == 0
    assert capsys.readouterr().out == "21\n"


def test_run_json_output_is_clean(tmp_path, monkeypatch, capsys):
    config, program = _write(tmp_path, "x = 21 ;\ny = x * 2 ;\nprint y ;\n")

    exit_code = _run(
        monkeypatch, "run", str(program), "--config", str(config), "--json"
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["variables"] == {"x": 21, "y": 42}
    assert "42" in captured.err  # program output moved to stderr


def test_run_show_python(tmp_path, monkeypatch, capsys):
    config, program = _write(tmp_path, "x = 1 ;\n")

    exit_code = _run(
        monkeypatch, "run", str(program),
        "--config", str(config), "--show-python",
    )

    assert exit_code == 0
    assert "x = 1" in capsys.readouterr().err


def test_run_accepts_peg_file(tmp_path, monkeypatch, capsys):
    grammar = tmp_path / "mini.peg"
    grammar.write_text(
        'program <- statement+\nstatement <- IDENT "=" NUMBER ";"',
        encoding="utf-8",
    )
    program = tmp_path / "program.src"
    program.write_text("x = 7 ;\n", encoding="utf-8")

    exit_code = _run(
        monkeypatch, "run", str(program), "--grammar", str(grammar), "--json"
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["variables"] == {"x": 7}


def test_run_requires_a_grammar(tmp_path, monkeypatch, capsys):
    program = tmp_path / "program.src"
    program.write_text("x = 1 ;\n", encoding="utf-8")

    exit_code = _run(monkeypatch, "run", str(program))

    assert exit_code == 1
    assert "grammar is required" in capsys.readouterr().err.lower()


def test_run_reports_parse_errors(tmp_path, monkeypatch, capsys):
    config, program = _write(tmp_path, "x = ;\n")

    exit_code = _run(
        monkeypatch, "run", str(program), "--config", str(config)
    )

    assert exit_code == 1
    assert "Parse error" in capsys.readouterr().err


def test_run_missing_file(tmp_path, monkeypatch, capsys):
    exit_code = _run(monkeypatch, "run", str(tmp_path / "nope.src"))

    assert exit_code == 1
    assert "not found" in capsys.readouterr().err
