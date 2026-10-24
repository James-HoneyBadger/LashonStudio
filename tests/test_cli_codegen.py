"""Tests for the code-generation CLI commands."""

import sys

from lashon.tooling.cli import main

GRAMMAR_CONFIG = """\
grammar:
  rules:
    program: "statement+"
    statement: 'IDENT "=" NUMBER ";"'
"""

SOURCE = "x = 42 ;\n"


def _write_inputs(tmp_path):
    config = tmp_path / "lang.yaml"
    config.write_text(GRAMMAR_CONFIG, encoding="utf-8")
    source = tmp_path / "program.src"
    source.write_text(SOURCE, encoding="utf-8")
    return config, source


def _run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["lashon", *argv])
    return main()


def test_codegen_c_uses_input_program(tmp_path, monkeypatch):
    config, source = _write_inputs(tmp_path)
    output = tmp_path / "program.c"

    exit_code = _run(
        monkeypatch, "codegen-c", str(source),
        "--config", str(config), "--output", str(output),
    )

    assert exit_code == 0
    generated = output.read_text(encoding="utf-8")
    assert "int main" in generated
    assert "int x = 42;" in generated


def test_codegen_wasm_uses_input_program(tmp_path, monkeypatch):
    config, source = _write_inputs(tmp_path)
    output = tmp_path / "program.wat"

    exit_code = _run(
        monkeypatch, "codegen-wasm", str(source),
        "--config", str(config), "--output", str(output),
    )

    assert exit_code == 0
    assert output.read_text(encoding="utf-8").startswith("(module")


def test_codegen_llvm_uses_input_program(tmp_path, monkeypatch):
    config, source = _write_inputs(tmp_path)
    output = tmp_path / "program.ll"

    exit_code = _run(
        monkeypatch, "codegen-llvm", str(source),
        "--config", str(config), "--output", str(output),
    )

    assert exit_code == 0
    assert "LLVM IR" in output.read_text(encoding="utf-8")


def test_codegen_requires_a_grammar_section(tmp_path, monkeypatch, capsys):
    config = tmp_path / "empty.yaml"
    config.write_text("name: NoGrammar\n", encoding="utf-8")
    source = tmp_path / "program.src"
    source.write_text(SOURCE, encoding="utf-8")
    output = tmp_path / "program.c"

    exit_code = _run(
        monkeypatch, "codegen-c", str(source),
        "--config", str(config), "--output", str(output),
    )

    assert exit_code == 1
    assert "grammar.rules" in capsys.readouterr().out
