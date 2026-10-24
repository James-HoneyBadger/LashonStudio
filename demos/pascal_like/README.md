# Pascal-Like Language Demo

A sample project demonstrating how to use **Lashon** to define, parse,
and compile programs written in a Pascal-inspired language.

## Project Structure

```
demos/pascal_like/
├── run_pascal.py          # Main demo — runs the full Lashon pipeline
└── samples/
    ├── hello.pas          # "Hello, World!" — basic variables and output
    ├── fibonacci.pas      # Fibonacci sequence with a WHILE loop
    ├── math_utils.pas     # Power, GCD, LCM, primality — FUNCTION blocks
    └── sort.pas           # Bubble sort with ARRAY and FOR loops
```

The language config is at:
```
configs/examples/pascal_like.yaml
```

---

## Keyword Mapping

| Python keyword | Pascal equivalent |
|---------------|-------------------|
| `if`          | `IF`              |
| `else`        | `ELSE`            |
| `elif`        | `ELSIF`           |
| `while`       | `WHILE`           |
| `for`         | `FOR`             |
| `def`         | `FUNCTION`        |
| `return`      | `RETURN`          |
| `var` / `let` | `VAR`             |
| `const`       | `CONST`           |
| `class`       | `CLASS`           |
| `try`         | `TRY`             |
| `except`      | `EXCEPT`          |
| `and`         | `AND`             |
| `or`          | `OR`              |
| `not`         | `NOT`             |
| `true`        | `TRUE`            |
| `false`       | `FALSE`           |
| `null`        | `NIL`             |

## Function Mapping

| Python function | Pascal equivalent |
|----------------|-------------------|
| `print()`      | `WriteLn()`        |
| `input()`      | `ReadLn()`         |
| `len()`        | `Length()`         |
| `int()`        | `Trunc()`          |
| `round()`      | `Round()`          |
| `str()`        | `IntToStr()`       |
| `abs()`        | `Abs()`            |

---

## Running the Demo

```bash
# From the project root
cd /home/james/Lashon
source .venv/bin/activate

# Full pipeline demo (parse → Python → C → WASM → LLVM IR)
python demos/pascal_like/run_pascal.py
```

### Expected output

```
════════════════════════════════════════════════════════════
  Pascal-Like Language — Lashon Demo
════════════════════════════════════════════════════════════

  Language : Pascal-Like Language
  Version  : 1.0
  ...

  ── Program 1 — Rectangle Geometry ──────────────────────

    width := 12 ;
    height := 8 ;
    ...

  ── Execution Results ────────────────────────────────────
    area       = 96
    diagonal_sq = 208
    height     = 8
    perimeter  = 40
    width      = 12
  ...
```

---

## Using the REPL

```bash
lashon repl configs/examples/pascal_like.yaml
```

Inside the REPL you can type Pascal-like assignments and see results
immediately:

```
> x := 10 ;
> y := x * 3 + 7 ;
> y
37
```

---

## Using the CLI

```bash
# Validate the language config
lashon validate configs/examples/pascal_like.yaml

# Show all keyword/function mappings
lashon info configs/examples/pascal_like.yaml

# Export mappings to Markdown
lashon export configs/examples/pascal_like.yaml \
    --format markdown --output pascal_mappings

# Generate C code from a source file
lashon codegen-c demos/pascal_like/samples/hello.pas \
    --output hello.c

# Generate WASM from a source file
lashon codegen-wasm demos/pascal_like/samples/fibonacci.pas \
    --output fibonacci.wat
```

---

## How It Works

1. **Grammar** — `run_pascal.py` builds a PEG grammar covering Pascal-style
   assignment statements (`IDENT := expr ;`) and arithmetic expressions.

2. **Parsing** — `PEGInterpreter` walks the grammar against your source and
   produces a `SourceAST` tree.

3. **Backends** — Four code generators consume the same AST:

   | Backend             | Class                | Output      |
   |---------------------|----------------------|-------------|
   | Python transpiler   | `PythonTranspiler`   | Python source and exec() |
   | C code generator    | `CCodeGenerator`     | ANSI C source |
   | WebAssembly         | `WasmGenerator`      | WAT text format |
   | LLVM IR             | `LLVMIRGenerator`    | LLVM SSA IR |

4. **Config** — `pascal_like.yaml` maps Python keywords to their Pascal
   equivalents so the REPL and CLI translate source files transparently.

---

## Extending the Language

To add a new Pascal keyword:

```yaml
# configs/examples/pascal_like.yaml
keywords:
  repeat: "REPEAT"
  until:  "UNTIL"
```

To add a new built-in function:

```yaml
functions:
  ord:
    name: "Ord"
    min_args: 1
    max_args: 1
    description: "Ordinal value of a character"
```

Then re-validate:

```bash
lashon validate configs/examples/pascal_like.yaml
```
