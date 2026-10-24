"""
lashon.parser — PEG grammar engine and AST construction.

This subpackage provides everything needed to define a grammar and parse
source code into an abstract syntax tree (SourceAST).

Primary classes
---------------
GrammarParser
    Parse PEG text notation (``rule <- pattern``) into a Grammar object::

        grammar = GrammarParser().parse(
            'program   <- statement+\\n'
            'statement <- IDENT "=" expr ";\"\\n'
            'expr      <- NUMBER / IDENT'
        )

GrammarBuilder
    Fluent Python API for constructing grammars without text notation::

        g = GrammarBuilder()
        g.rule("stmt").set_pattern(
            GrammarBuilder.seq(
                GrammarBuilder.ref("IDENT"),
                GrammarBuilder.lit("="),
                GrammarBuilder.ref("NUMBER"),
                GrammarBuilder.lit(";"),
            )
        )
        grammar = g.build()

PEGInterpreter
    Execute a grammar against source text to produce a SourceAST.
    Uses packrat memoization for guaranteed O(n) parse time::

        ast = PEGInterpreter(grammar).parse("x = 42 ;")

SourceAST
    Dataclass representing a node in the abstract syntax tree.
    Fields: node_type (str), value (Any), children (list), line, column.

IncrementalParser
    Re-parse only changed regions of source text.  Suitable for real-time
    use in editors and language servers.

Built-in tokens
---------------
The parser recognises three built-in token names in grammar rules:

- ``NUMBER``  — integer or float literal.
- ``IDENT``   — identifier (letters, digits, underscore).
- ``STRING``  — double- or single-quoted string literal.

See the TECHNICAL_REFERENCE.md for complete API documentation.
"""

from .grammar import (
    Grammar,
    GrammarBuilder,
    GrammarParser,
    GrammarRule,
    PEGInterpreter,
    PEGNode,
    PEGNodeType,
    SourceAST,
    grammar_from_config,
)
from .incremental import IncrementalParser
from .parser_generator import (
    ASTNode,
    Lexer,
    Parser,
    ParserGenerator,
    Token,
    TokenType,
    generate_parser,
)

__all__ = [
    "Lexer",
    "Parser",
    "ParserGenerator",
    "Token",
    "TokenType",
    "ASTNode",
    "generate_parser",
    "Grammar",
    "GrammarBuilder",
    "GrammarParser",
    "GrammarRule",
    "PEGInterpreter",
    "PEGNode",
    "PEGNodeType",
    "SourceAST",
    "grammar_from_config",
    "IncrementalParser",
]
