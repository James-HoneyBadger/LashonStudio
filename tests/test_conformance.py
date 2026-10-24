"""Conformance corpus tests.

``tests/conformance/cases.json`` records a grammar, a program, and the exact
outcome the engine must produce. These tests:

1. pin the pure-Python engine to the recorded ASTs (regression protection), and
2. when an alternative engine is installed (the optional native backend),
   require it to produce byte-identical ASTs.

Keeping the corpus language-agnostic is what makes an alternative engine
replaceable: it only has to agree on the JSON AST, not on internals.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lashon.parser.grammar import GrammarParser, PEGInterpreter

CASES_PATH = Path(__file__).with_name("conformance") / "cases.json"
CASES = json.loads(CASES_PATH.read_text(encoding="utf-8"))


def _parse(grammar_text: str, source: str):
    grammar = GrammarParser().parse(grammar_text)
    return PEGInterpreter(grammar).parse(source)


def _by_name(name: str) -> dict:
    for case in CASES:
        if case["name"] == name:
            return case
    raise KeyError(name)


def test_corpus_is_non_trivial():
    names = [case["name"] for case in CASES]
    assert len(names) >= 8
    assert any(not case["expect"]["ok"] for case in CASES)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_python_engine_matches_recorded_ast(case):
    expect = case["expect"]
    if not expect["ok"]:
        with pytest.raises(SyntaxError) as excinfo:
            _parse(case["grammar"], case["source"])
        assert expect["error_contains"].splitlines()[0] in str(excinfo.value)
        return

    ast = _parse(case["grammar"], case["source"])
    assert ast.to_dict() == expect["ast"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_corpus_round_trips_through_json(case):
    """The AST contract is JSON, which is what an alternative engine returns."""
    expect = case["expect"]
    if not expect["ok"]:
        return
    ast = _parse(case["grammar"], case["source"])
    assert json.loads(json.dumps(ast.to_dict())) == expect["ast"]


try:  # optional dependency: a compiled accelerator
    from lashon.parser import native
except ImportError:  # pragma: no cover - not built in this checkout
    native = None


def _native_ready() -> bool:
    return native is not None and native.available()


@pytest.mark.skipif(not _native_ready(), reason="native extension not loaded")
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_native_engine_matches_python_engine(case):
    expect = case["expect"]
    grammar = GrammarParser().parse(case["grammar"])
    try:
        ast = native.parse(grammar, case["source"])
    except native.NativeParseError as error:
        assert not expect["ok"], "native rejected a valid program"
        assert expect["error_contains"].splitlines()[0] in str(error)
        return

    assert expect["ok"], "native accepted an invalid program"
    assert ast is not None
    assert ast.to_dict() == expect["ast"]
