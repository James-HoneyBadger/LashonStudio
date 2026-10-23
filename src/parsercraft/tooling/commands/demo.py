"""``parsercraft demo`` — a zero-setup guided tour of the pipeline."""

from __future__ import annotations

import contextlib
import io
import sys

from parsercraft.codegen import (
    CCodeGenerator,
    LLVMIRGenerator,
    PythonTranspiler,
    WasmGenerator,
    transpile_and_exec,
)
from parsercraft.parser import GrammarParser, PEGInterpreter

GRAMMAR = """\
program    <- statement+
statement  <- assignment / print_stmt
assignment <- IDENT "=" expr ";"
print_stmt <- "print" expr ";"
expr       <- term (("+" / "-") term)*
term       <- factor (("*" / "/") factor)*
factor     <- NUMBER / IDENT / "(" expr ")"
"""

SOURCE = """\
x = 2 + 3 * 4 ;
area = (x + 6) / 2 ;
print area ;
"""


def cmd_demo(args) -> int:
    """Run a guided parse → inspect → generate → execute tour."""
    stage = 1

    def heading(title: str) -> None:
        nonlocal stage
        print()
        print(f"[{stage}] {title}")
        print("-" * 60)
        stage += 1

    heading("Grammar")
    print(GRAMMAR.rstrip())

    heading("Source")
    print(SOURCE.rstrip())

    grammar = GrammarParser().parse(GRAMMAR)
    ast = PEGInterpreter(grammar).parse(SOURCE)

    heading("AST")
    print(ast.pretty())

    heading("Python")
    python_code = PythonTranspiler().translate_source_ast(ast)
    print(python_code)

    if not args.no_backends:
        heading("C")
        print(CCodeGenerator().translate_source_ast(ast))

        heading("WebAssembly (WAT)")
        print(WasmGenerator().translate_source_ast(ast).to_wat())

        heading("LLVM IR")
        print(LLVMIRGenerator().translate_source_ast(ast))

    heading("Execution")
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        namespace = transpile_and_exec(ast)
    sys.stdout.write(buffer.getvalue())
    print(f"variables: {namespace}")

    print()
    print("Next: parsercraft init \"My Lang\" --directory ./languages")
    return 0
