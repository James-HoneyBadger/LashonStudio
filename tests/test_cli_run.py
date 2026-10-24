"""Tests for ``lashon run``."""

import json
import sys

from lashon.tooling.cli import main

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
    monkeypatch.setattr(sys, "argv", ["lashon", *argv])
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


def test_run_sandbox_executes_in_child(tmp_path, monkeypatch, capsys):
    config, program = _write(tmp_path, "x = 21 ;\nprint x ;\n")

    exit_code = _run(
        monkeypatch, "run", str(program),
        "--config", str(config), "--sandbox",
    )

    assert exit_code == 0
    assert capsys.readouterr().out == "21\n"


def test_run_sandbox_rejects_json(tmp_path, monkeypatch, capsys):
    config, program = _write(tmp_path, "x = 1 ;\n")

    exit_code = _run(
        monkeypatch, "run", str(program),
        "--config", str(config), "--sandbox", "--json",
    )

    assert exit_code == 1
    assert "--json" in capsys.readouterr().err


def test_run_sandbox_times_out(tmp_path, monkeypatch, capsys):
    config, program = _write(
        tmp_path, "i = 0 ;\nwhile i < 3 {\n  i = i ;\n}\n"
    )
    config.write_text(
        "grammar:\n"
        "  rules:\n"
        "    program: 'statement+'\n"
        "    statement: 'while_stmt / assignment / print_stmt'\n"
        "    while_stmt: \"'while' comparison block\"\n"
        "    block: \"'{' statement* '}'\"\n"
        "    comparison: 'expr (\"<\" / \">\") expr'\n"
        "    assignment: 'IDENT \"=\" expr \";\"'\n"
        "    print_stmt: \"'print' IDENT ';'\"\n"
        "    expr: 'term ((\"+\" / \"-\") term)*'\n"
        "    term: 'factor ((\"*\" / \"/\") factor)*'\n"
        "    factor: 'NUMBER / IDENT'\n",
        encoding="utf-8",
    )

    exit_code = _run(
        monkeypatch, "run", str(program),
        "--config", str(config), "--sandbox",
        "--sandbox-timeout", "0.5",
    )

    assert exit_code == 124
    assert "exceeded" in capsys.readouterr().err
