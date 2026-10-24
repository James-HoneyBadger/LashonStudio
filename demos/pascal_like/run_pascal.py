#!/usr/bin/env python3
"""
Pascal-Like Language Demo — Lashon

Demonstrates the full Lashon pipeline using a Pascal-inspired
language defined in configs/examples/pascal_like.yaml:

  1. Load and inspect the Pascal-like language config
  2. Build a PEG grammar and parse sample Pascal-like source
  3. Transpile to Python and execute
  4. Generate C code output
  5. Generate WebAssembly (WAT) output
  6. Generate LLVM IR output
  7. Display the keyword mapping table
  8. Run a multi-program showcase
"""

import os
import sys

# Ensure lashon is importable when run directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# pylint: disable=wrong-import-position
import yaml  # noqa: E402

from lashon.parser import GrammarParser, PEGInterpreter  # noqa: E402
from lashon.codegen import (  # noqa: E402
    PythonTranspiler,
    LLVMIRGenerator,
)
from lashon.codegen.codegen_c import CCodeGenerator  # noqa: E402
from lashon.codegen.codegen_wasm import WasmGenerator  # noqa: E402
# pylint: enable=wrong-import-position


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def banner(title: str, char: str = "═") -> None:
    """Print a section banner."""
    width = max(len(title) + 4, 60)
    print(f"\n{char * width}")
    print(f"  {title}")
    print(f"{char * width}\n")


def sub_banner(title: str) -> None:
    """Print a sub-section separator."""
    print(f"  ── {title} {'─' * max(0, 54 - len(title))}")


def load_config(path: str) -> dict:
    """Load a YAML language config file."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def print_ast(node, indent: int = 0) -> None:
    """Pretty-print a SourceAST tree."""
    prefix = " " * indent
    if node.value is not None and not node.children:
        print(f"{prefix}{node.node_type}: {node.value!r}")
    else:
        label = node.node_type
        if node.value is not None:
            label += f"  ({node.value!r})"
        print(f"{prefix}{label}")
        for child in node.children:
            print_ast(child, indent + 2)


def build_core_grammar() -> object:
    """
    Build the core expression grammar understood by PEGInterpreter.

    This handles Pascal-style programs composed of assignment statements,
    arithmetic expressions, and parenthesised sub-expressions.
    """
    parser = GrammarParser()
    return parser.parse(
        "program     <- statement+\n"
        "statement   <- IDENT \":=\" expr \";\"\n"
        "expr        <- term   ((\"+\" / \"-\") term)*\n"
        "term        <- factor ((\"*\" / \"/\") factor)*\n"
        "factor      <- NUMBER / IDENT / \"(\" expr \")\"\n"
    )


def parse_and_run(
    description: str,
    pascal_source: str,
    grammar,
    show_ast: bool = True,
    show_c: bool = True,
    show_wasm: bool = True,
    show_llvm: bool = True,
) -> dict:
    """Parse pascal_source, transpile to Python, execute, and show codegen."""
    banner(description)

    # ── Source listing ──────────────────────────────────────────────────────
    sub_banner("Pascal-Like Source")
    for line in pascal_source.strip().splitlines():
        print(f"    {line}")
    print()

    # ── Parse ───────────────────────────────────────────────────────────────
    sub_banner("Parsing with PEGInterpreter")
    interp = PEGInterpreter(grammar)
    ast = interp.parse(pascal_source)
    print("  ✓ Parse successful\n")

    if show_ast:
        sub_banner("Abstract Syntax Tree")
        print_ast(ast, indent=4)
        print()

    # ── Python transpilation + execution ────────────────────────────────────
    sub_banner("Python Transpilation")
    transpiler = PythonTranspiler()
    py_code = transpiler.transpile(ast)
    print("  Generated Python:")
    for line in py_code.strip().splitlines():
        print(f"    {line}")
    print()

    namespace: dict = {}
    exec(py_code, namespace)  # noqa: S102  # pylint: disable=exec-used

    sub_banner("Execution Results")
    for var, val in sorted(
        (k, v) for k, v in namespace.items() if not k.startswith("__")
    ):
        print(f"    {var} = {val}")
    print()

    # ── C code generation ───────────────────────────────────────────────────
    if show_c:
        sub_banner("C Code Generation")
        c_gen = CCodeGenerator()
        c_code = c_gen.translate_source_ast(ast)
        for line in c_code.strip().splitlines():
            print(f"    {line}")
        print()

    # ── WASM generation ─────────────────────────────────────────────────────
    if show_wasm:
        sub_banner("WebAssembly (WAT) Generation")
        wasm_gen = WasmGenerator()
        wasm_module = wasm_gen.translate_source_ast(ast)
        wat = wasm_module.to_wat()
        for line in wat.strip().splitlines()[:20]:   # first 20 lines
            print(f"    {line}")
        if wat.count("\n") > 20:
            print("    ...")
        print()

    # ── LLVM IR generation ──────────────────────────────────────────────────
    if show_llvm:
        sub_banner("LLVM IR Generation")
        llvm_gen = LLVMIRGenerator()
        llvm_code = llvm_gen.translate_source_ast(ast)
        for line in llvm_code.strip().splitlines():
            print(f"    {line}")
        print()

    return namespace


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the Pascal-like language demo pipeline."""
    config_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "configs", "examples", "pascal_like.yaml",
    )

    # ── 1. Load and inspect config ──────────────────────────────────────────
    banner("Pascal-Like Language — Lashon Demo", char="╔")
    config = load_config(config_path)
    meta = config.get("metadata", config)       # YAML may lack 'metadata' key

    lang_name = (
        meta.get("name") if isinstance(meta, dict)
        else config.get("name", "Pascal-Like")
    )
    lang_version = (
        meta.get("version") if isinstance(meta, dict)
        else config.get("version", "1.0")
    )
    lang_desc = (
        meta.get("description") if isinstance(meta, dict)
        else config.get("description", "")
    )

    print(f"  Language : {lang_name}")
    print(f"  Version  : {lang_version}")
    print(f"  Style    : {lang_desc}")
    print(f"  Config   : {os.path.relpath(config_path)}")
    print()

    # ── 2. Keyword mapping table ────────────────────────────────────────────
    banner("Keyword Mapping Table")
    keywords = config.get("keywords", {})
    print(f"  {'Python keyword':<18} {'Pascal equivalent':<18} description")
    print(f"  {'─' * 17}  {'─' * 17}  {'─' * 20}")
    for py_kw, pascal_kw in sorted(
        keywords.items(), key=lambda kv: str(kv[0])
    ):
        if isinstance(pascal_kw, dict):
            custom = pascal_kw.get("custom", pascal_kw)
            desc = pascal_kw.get("description", "")
        else:
            custom = pascal_kw
            desc = ""
        py_kw_str = str(py_kw) if py_kw is not None else "null"
        print(f"  {py_kw_str:<18} {custom:<18} {desc}")
    print()

    # ── 3. Function mapping table ───────────────────────────────────────────
    banner("Built-in Function Mapping")
    functions = config.get("functions", {})
    if functions:
        print(
            f"  {'Python function':<18} "
            f"{'Pascal equivalent':<18} description"
        )
        sep = f"  {'─' * 17}  {'─' * 17}  {'─' * 20}"
        print(sep)
        for py_fn, info in sorted(
            functions.items(), key=lambda kv: str(kv[0])
        ):
            if isinstance(info, dict):
                pascal_name = info.get("name", py_fn)
                desc = info.get("description", "")
            else:
                pascal_name = info
                desc = ""
            py_fn_str = str(py_fn) if py_fn is not None else "null"
            print(f"  {py_fn_str:<18} {pascal_name:<18} {desc}")
    else:
        print("  (no function mappings defined)")
    print()

    # ── Build grammar once, reuse for all demos ─────────────────────────────
    grammar = build_core_grammar()

    # ── 4. Program 1 — Area and perimeter of a rectangle ───────────────────
    rect_source = (
        "width := 12 ;\n"
        "height := 8 ;\n"
        "perimeter := (width + height) * 2 ;\n"
        "area := width * height ;\n"
        "diagonal_sq := width * width + height * height ;\n"
    )
    rect_vars = parse_and_run(
        "Program 1 — Rectangle Geometry",
        rect_source,
        grammar,
    )
    print(
        f"  Sanity check — perimeter expected 40,"
        f" got {rect_vars.get('perimeter')}"
    )
    print(
        f"  Sanity check — area expected 96,"
        f" got {rect_vars.get('area')}"
    )
    print()

    # ── 5. Program 2 — Fibonacci recurrence (unrolled) ─────────────────────
    fib_source = (
        "f0 := 0 ;\n"
        "f1 := 1 ;\n"
        "f2 := f0 + f1 ;\n"
        "f3 := f1 + f2 ;\n"
        "f4 := f2 + f3 ;\n"
        "f5 := f3 + f4 ;\n"
        "f6 := f4 + f5 ;\n"
        "f7 := f5 + f6 ;\n"
        "f8 := f6 + f7 ;\n"
        "f9 := f7 + f8 ;\n"
        "f10 := f8 + f9 ;\n"
    )
    fib_vars = parse_and_run(
        "Program 2 — Fibonacci Sequence (unrolled)",
        fib_source,
        grammar,
        show_c=False,
        show_wasm=False,
        show_llvm=False,
    )
    fib_sequence = [fib_vars.get(f"f{i}") for i in range(11)]
    print(f"  Fibonacci[0..10] = {fib_sequence}")
    print()

    # ── 6. Program 3 — Statistics (sum, mean, variance) ────────────────────
    stats_source = (
        "a := 4 ;\n"
        "b := 7 ;\n"
        "c := 13 ;\n"
        "d := 2 ;\n"
        "e := 9 ;\n"
        "n := 5 ;\n"
        "total := a + b + c + d + e ;\n"
        "mean := total / n ;\n"
        "sq_a := (a - mean) * (a - mean) ;\n"
        "sq_b := (b - mean) * (b - mean) ;\n"
        "sq_c := (c - mean) * (c - mean) ;\n"
        "sq_d := (d - mean) * (d - mean) ;\n"
        "sq_e := (e - mean) * (e - mean) ;\n"
        "variance := (sq_a + sq_b + sq_c + sq_d + sq_e) / n ;\n"
    )
    stats_vars = parse_and_run(
        "Program 3 — Basic Statistics",
        stats_source,
        grammar,
        show_c=True,
        show_wasm=False,
        show_llvm=True,
    )
    print(
        f"  total={stats_vars.get('total')}, "
        f"mean={stats_vars.get('mean')}, "
        f"variance={stats_vars.get('variance')}"
    )
    print()

    # ── 7. Program 4 — Unit conversions ────────────────────────────────────
    convert_source = (
        "celsius := 100 ;\n"
        "fahrenheit := celsius * 9 / 5 + 32 ;\n"
        "kelvin := celsius + 273 ;\n"
        "miles := 26 ;\n"
        "km := miles * 16 / 10 ;\n"
        "pounds := 70 ;\n"
        "kg := pounds * 45 / 100 ;\n"
    )
    parse_and_run(
        "Program 4 — Unit Conversions",
        convert_source,
        grammar,
        show_ast=False,
        show_c=False,
        show_wasm=True,
        show_llvm=False,
    )

    # ── 8. Summary ──────────────────────────────────────────────────────────
    banner("Demo Complete", char="╚")
    print("  All four Pascal-like programs were:")
    print("    ✓ Parsed with PEGInterpreter")
    print("    ✓ Transpiled to Python and executed")
    print("    ✓ Compiled to C source")
    print("    ✓ Compiled to WebAssembly (WAT)")
    print("    ✓ Compiled to LLVM IR")
    print()
    print("  Next steps:")
    print("    • Edit demos/pascal_like/samples/*.pas "
          "to try your own programs")
    print("    • Run:  lashon repl "
          "configs/examples/pascal_like.yaml")
    print("    • Run:  lashon validate configs/examples/pascal_like.yaml")
    print()


if __name__ == "__main__":
    main()
