"""Tests for the optional native PEG backend.

Skipped when the extension is not built; ``scripts/build_native.sh`` builds it.
The conformance suite (``tests/test_conformance.py``) additionally requires the
native backend to agree with the Python engine on the recorded corpus.
"""

from __future__ import annotations

import pytest

from parsercraft.parser import GrammarParser, PEGInterpreter, native

GRAMMAR = """
program  <- statement+
statement <- print_stmt / assignment
print_stmt <- 'print' expr ';'
assignment <- IDENT '=' expr ';'
expr     <- term (('+' / '-') term)*
term     <- NUMBER / IDENT
""".strip()

SOURCE = 'x = 1 ;\nprint x + 2 ;\n'

requires_native = pytest.mark.skipif(
    not native.available(), reason="native extension not built"
)


@pytest.fixture
def grammar():
    return GrammarParser().parse(GRAMMAR)


def test_backend_probe_is_consistent():
    assert native.backend() in {"python", "native"}
    assert native.available() == (native.backend() == "native")
    assert native.version() is None or isinstance(native.version(), str)


def test_python_backend_is_the_default(grammar):
    interpreter = PEGInterpreter(grammar)
    assert interpreter.backend == "python"
    interpreter.parse(SOURCE)


def test_auto_backend_matches_python(grammar):
    python_ast = PEGInterpreter(grammar).parse(SOURCE)
    auto_ast = PEGInterpreter(grammar, backend="auto").parse(SOURCE)
    assert auto_ast.to_dict() == python_ast.to_dict()


def test_auto_falls_back_for_unsupported_grammar():
    """An out-of-scope grammar must silently use the Python engine."""
    grammar = GrammarParser().parse(
        "program <- statement+\nstatement <- IDENT '=' NUMBER ';'\n"
    )
    grammar.comment_patterns = ["#.*"]  # not understood natively
    assert not native.supports(grammar)

    interpreter = PEGInterpreter(grammar, backend="auto")
    ast = interpreter.parse("x = 1 ;\n")
    assert ast.children[0].node_type == "statement"


@requires_native
def test_native_backend_produces_identical_ast(grammar):
    python_ast = PEGInterpreter(grammar).parse(SOURCE)
    native_ast = PEGInterpreter(grammar, backend="native").parse(SOURCE)
    assert native_ast.to_dict() == python_ast.to_dict()


@requires_native
def test_native_backend_reports_syntax_errors(grammar):
    with pytest.raises(native.NativeParseError) as excinfo:
        PEGInterpreter(grammar, backend="native").parse("x = ;\n")
    assert "line 1" in str(excinfo.value)


@requires_native
def test_native_supports_reports_capability(grammar):
    assert native.supports(grammar)


def test_missing_native_backend_raises_when_required(grammar, monkeypatch):
    monkeypatch.setattr(native, "available", lambda: False)
    interpreter = PEGInterpreter(grammar, backend="native")
    with pytest.raises(RuntimeError, match="not built"):
        interpreter.parse(SOURCE)
