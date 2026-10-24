"""Tests for line-numbered (BASIC-style) programs on the Python pipeline.

The Rust core has always evaluated these; the Python backend used to emit each
line number as a bare statement and choke on ``IF … THEN GOTO``. The transpiler
now turns a numbered program into a program-counter loop, so every front end
(CLI, Studio, REPL) runs the same program the same way.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from lashon.codegen import transpile_and_exec, transpile_to_python
from lashon.parser import GrammarParser, PEGInterpreter
from lashon.tooling.cli import main

BASIC_ROOT = Path(__file__).resolve().parent.parent / "projects" / "basic"
SAMPLES = sorted((BASIC_ROOT / "samples").glob("*.bas"))

EXPECTED = {
    "hello": "HELLO, BASIC!\nTHE ANSWER IS 42",
    "countdown": "3\n2\n1\nLIFTOFF!",
    "fizzbuzz": None,
}


def _grammar():
    return GrammarParser().parse(
        (BASIC_ROOT / "grammar.peg").read_text(encoding="utf-8")
    )


def _run_source(source: str) -> dict:
    ast = PEGInterpreter(_grammar()).parse(source)
    return transpile_and_exec(ast)


def _run_cli(monkeypatch, *argv) -> int:
    monkeypatch.setattr(sys, "argv", ["lashon", *argv])
    return main()


def test_samples_are_discovered():
    assert [p.stem for p in SAMPLES] == ["countdown", "fizzbuzz", "hello"]


def test_numbered_program_becomes_a_program_counter_loop():
    ast = PEGInterpreter(_grammar()).parse(
        (BASIC_ROOT / "samples" / "countdown.bas").read_text(encoding="utf-8")
    )
    code = transpile_to_python(ast)

    assert "def _lashon_numbered_program():" in code
    assert "while _pc is not None:" in code
    assert "_pc = 30" in code
    assert "\n10\n" not in code, "line numbers must not become statements"
    # No bare `if` without a body: the failure mode this replaced.
    compile(code, "<numbered>", "exec")


def test_goto_loop_terminates_and_keeps_variables():
    namespace = _run_source(
        "10 LET X = 3\n"
        "20 PRINT X\n"
        "30 LET X = X - 1\n"
        "40 IF X > 0 THEN GOTO 20\n"
        "50 PRINT \"done\"\n"
    )
    assert namespace["X"] == 0


def test_while_wend_runs_its_lines():
    namespace = _run_source(
        "10 LET I = 0\n"
        "20 WHILE I < 3\n"
        "30 PRINT I\n"
        "40 LET I = I + 1\n"
        "50 WEND\n"
    )
    assert namespace["I"] == 3


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda p: p.stem)
def test_every_sample_runs_through_the_python_pipeline(sample, monkeypatch,
                                                       capsys):
    exit_code = _run_cli(
        monkeypatch, "run", str(sample), "--config",
        str(BASIC_ROOT / "language.yaml"),
    )
    assert exit_code == 0
    output = capsys.readouterr().out.strip()
    assert output
    expected = EXPECTED.get(sample.stem)
    if expected is not None:
        assert output == expected


def test_json_reports_the_final_variables(monkeypatch, capsys):
    exit_code = _run_cli(
        monkeypatch, "run", str(BASIC_ROOT / "samples" / "countdown.bas"),
        "--config", str(BASIC_ROOT / "language.yaml"), "--json",
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["variables"]["X"] == 0
