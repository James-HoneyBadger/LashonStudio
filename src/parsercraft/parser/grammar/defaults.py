"""Built-in default grammar used when no grammar is supplied."""

from __future__ import annotations

from .model import Grammar
from .peg_parser import GrammarParser


def _default_grammar() -> Grammar:
    """Create a default grammar suitable for Python-like languages."""
    peg_text = """
program     <- statement*
statement   <- function_def / if_stmt / while_stmt / for_stmt / return_stmt / assignment / expr_stmt
function_def <- 'def' IDENT '(' param_list? ')' ':' block
param_list  <- IDENT (',' IDENT)*
if_stmt     <- 'if' expr ':' block ('elif' expr ':' block)* ('else' ':' block)?
while_stmt  <- 'while' expr ':' block
for_stmt    <- 'for' IDENT 'in' expr ':' block
return_stmt <- 'return' expr?
assignment  <- IDENT '=' expr
expr_stmt   <- expr
block       <- statement+
expr        <- comparison
comparison  <- addition (('==' / '!=' / '<=' / '>=' / '<' / '>') addition)*
addition    <- multiplication (('+' / '-') multiplication)*
multiplication <- unary (('*' / '/' / '%') unary)*
unary       <- ('-' / '!') unary / call
call        <- primary ('(' arg_list? ')')*
arg_list    <- expr (',' expr)*
primary     <- NUMBER / STRING / IDENT / '(' expr ')' / list_literal
list_literal <- '[' (expr (',' expr)*)? ']'
"""
    parser = GrammarParser()
    return parser.parse(peg_text.strip(), "default")
