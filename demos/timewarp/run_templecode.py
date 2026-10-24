#!/usr/bin/env python3
"""
TempleCode Demo — Load and process the Time Warp language config.

Demonstrates the full Lashon pipeline:
  1. Load the TempleCode YAML config
  2. Build a PEG grammar from it
  3. Parse sample TempleCode source
  4. Transpile to Python and execute
  5. Generate C and LLVM IR output
"""

import os
import sys
import yaml

# Ensure lashon is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from lashon.parser import GrammarParser, PEGInterpreter, grammar_from_config
from lashon.codegen import PythonTranspiler, transpile_to_python, LLVMIRGenerator
from lashon.codegen.codegen_c import CCodeGenerator


def load_config(path: str) -> dict:
    """Load a YAML language config file."""
    with open(path) as f:
        return yaml.safe_load(f)


def banner(text: str) -> None:
    width = max(len(text) + 4, 50)
    print(f"\n{'═' * width}")
    print(f"  {text}")
    print(f"{'═' * width}\n")


def main():
    # ── 1. Load config ──────────────────────────────────────────
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "configs", "examples", "timewarp_templecode.yaml"
    )
    config = load_config(config_path)
    meta = config.get("metadata", {})

    banner(f"{meta.get('name', 'TempleCode')} — Lashon Demo")
    print(f"  Language : {meta.get('name')}")
    print(f"  Version  : {meta.get('version')}")
    print(f"  Style    : {meta.get('description', '').split('.')[0]}")
    print(f"  Extension: {meta.get('file_extension')}")
    print()

    # ── 2. Build grammar from config ────────────────────────────
    banner("Building grammar from config...")
    grammar = grammar_from_config(config)
    print(f"  Start rule : {grammar.start_rule}")
    print(f"  Rules      : {len(grammar.rules)}")
    for name in sorted(grammar.rules.keys()):
        print(f"    • {name}")
    print()

    # ── 3. Parse a simple TempleCode snippet ───────────────────
    # We use the core expression grammar (the subset that PEGInterpreter
    # can directly parse and backends can translate).
    banner("Parsing a TempleCode snippet...")

    # For demonstration, use the expression subset of the grammar
    parser = GrammarParser()
    expr_grammar = parser.parse("""
program     <- statement+
statement   <- IDENT "=" expr ";"
expr        <- term (("+" / "-") term)*
term        <- factor (("*" / "/") factor)*
factor      <- NUMBER / IDENT / "(" expr ")"
""")

    interp = PEGInterpreter(expr_grammar)

    source = "side = 80 ; angle = 90 ; perimeter = side * 4 ; area = side * side ;"
    print(f"  Source: {source}")
    print()

    ast = interp.parse(source)
    print("  AST:")
    _print_ast(ast, indent=4)
    print()

    # ── 4. Transpile to Python ──────────────────────────────────
    banner("Python transpilation...")
    transpiler = PythonTranspiler()
    py_code = transpiler.transpile(ast)
    print(f"  Generated Python:\n")
    for line in py_code.strip().split("\n"):
        print(f"    {line}")
    print()

    # Execute it
    namespace = {}
    exec(py_code, namespace)
    print("  Execution results:")
    for var in ("side", "angle", "perimeter", "area"):
        if var in namespace:
            print(f"    {var} = {namespace[var]}")
    print()

    # ── 5. Generate C code ──────────────────────────────────────
    banner("C code generation...")
    c_gen = CCodeGenerator()
    c_code = c_gen.translate_source_ast(ast)
    for line in c_code.strip().split("\n"):
        print(f"    {line}")
    print()

    # ── 6. Generate LLVM IR ─────────────────────────────────────
    banner("LLVM IR generation...")
    llvm_gen = LLVMIRGenerator()
    llvm_code = llvm_gen.translate_source_ast(ast)
    for line in llvm_code.strip().split("\n"):
        print(f"    {line}")
    print()

    # ── 7. Show keyword mapping ─────────────────────────────────
    banner("TempleCode keyword table")
    keywords = config.get("keywords", {})
    print(f"  {'TempleCode':<16} {'Maps to':<16} {'Category'}")
    print(f"  {'─' * 16} {'─' * 16} {'─' * 16}")
    for key in sorted(keywords.keys(), key=str):
        info = keywords[key]
        if isinstance(info, dict):
            custom = info.get("custom", key)
            cat = info.get("category", "")
            print(f"  {custom:<16} {key:<16} {cat}")
    print()

    # ── 8. Show built-in functions ──────────────────────────────
    banner("Built-in function library")
    funcs = config.get("builtin_functions", {})
    categories = {}
    for key, info in funcs.items():
        if isinstance(info, dict):
            name = info.get("name", key)
            desc = info.get("description", "")
            # Infer category from name
            cat = "General"
            if any(t in key for t in ("forward", "fd", "back", "bk", "left", "lt",
                                       "right", "rt", "pen", "pu", "pd", "home",
                                       "setxy", "setcolor", "hideturtle", "showturtle",
                                       "circle", "arc")):
                cat = "Turtle Graphics"
            elif any(t in key for t in ("say", "ask", "cls", "beep", "locate", "color")):
                cat = "I/O & Display"
            elif any(t in key for t in ("abs", "sqr", "int", "rnd", "sin", "cos", "tan")):
                cat = "Math"
            elif any(t in key for t in ("len", "left_str", "right_str", "mid_str",
                                         "str", "val", "chr", "asc", "upper", "lower", "instr")):
                cat = "Strings"
            elif any(t in key for t in ("score", "grade", "timer", "wait")):
                cat = "Teaching"
            categories.setdefault(cat, []).append((name, desc))

    for cat in ("I/O & Display", "Turtle Graphics", "Math", "Strings", "Teaching"):
        items = categories.get(cat, [])
        if items:
            print(f"  [{cat}]")
            for name, desc in items:
                print(f"    {name:<12} {desc}")
            print()

    banner("Done! TempleCode is ready for Time Warp IDE.")


def _print_ast(node, indent=0):
    """Pretty-print a SourceAST tree."""
    prefix = " " * indent
    if node.value is not None and not node.children:
        print(f"{prefix}{node.node_type}: {node.value!r}")
    else:
        label = node.node_type
        if node.value is not None:
            label += f" ({node.value!r})"
        print(f"{prefix}{label}")
        for child in node.children:
            _print_ast(child, indent + 2)


if __name__ == "__main__":
    main()
