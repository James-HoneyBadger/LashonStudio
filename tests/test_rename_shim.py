"""The deprecated ``parsercraft`` alias still exposes the public API."""

from __future__ import annotations

import importlib

import pytest


def _fresh():
    """Import the shim, reloading it so the deprecation warning fires again."""
    module = importlib.import_module("parsercraft")
    with pytest.warns(DeprecationWarning, match="renamed to 'lashon'"):
        importlib.reload(module)
    return module


def test_import_warns_and_reexports():
    module = _fresh()
    import lashon

    assert module.__version__ == lashon.__version__
    assert module.LanguageConfig is lashon.LanguageConfig
    assert module.LanguageRuntime is lashon.LanguageRuntime


def test_submodule_imports_are_aliased():
    _fresh()
    from parsercraft.parser import GrammarParser, PEGInterpreter

    from lashon.parser import GrammarParser as NewParser
    from lashon.parser import PEGInterpreter as NewInterpreter

    assert GrammarParser is NewParser
    assert PEGInterpreter is NewInterpreter


def test_deep_submodule_imports_and_use():
    _fresh()
    from parsercraft.parser.grammar import GrammarParser

    grammar = GrammarParser().parse("program <- IDENT\n")
    assert grammar.start_rule == "program"


def test_unknown_attribute_raises():
    module = _fresh()
    with pytest.raises(AttributeError):
        _ = module.definitely_not_a_real_attribute


def test_version_is_5_0_0():
    import lashon

    assert lashon.__version__ == "5.0.0"
