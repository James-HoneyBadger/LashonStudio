"""PEG grammar engine.

Split into focused modules so the model, the text parser, the interpreter, and
the builder can evolve (and be reviewed) independently::

    model.py         Grammar · GrammarRule · PEGNode
    peg_parser.py    GrammarParser  (text notation → Grammar)
    interpreter.py   PEGInterpreter (source → SourceAST)
    builder.py       GrammarBuilder · grammar_from_config
    defaults.py      the built-in fallback grammar
"""

from __future__ import annotations

from lashon.ast import SourceAST

from .builder import GrammarBuilder, grammar_from_config
from .interpreter import ParseResult, PEGInterpreter
from .model import (
    SUPPORTED_TOKENS,
    Grammar,
    GrammarRule,
    PEGNode,
    PEGNodeType,
)
from .peg_parser import GrammarParser

__all__ = [
    "SUPPORTED_TOKENS",
    "Grammar",
    "GrammarBuilder",
    "GrammarParser",
    "GrammarRule",
    "PEGInterpreter",
    "PEGNode",
    "PEGNodeType",
    "ParseResult",
    "SourceAST",
    "grammar_from_config",
]
