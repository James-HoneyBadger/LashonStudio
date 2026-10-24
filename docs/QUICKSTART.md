# Quick Start

Get from “nothing installed” to a running custom language in about ten minutes.

> Verified against Lashon 4.0.0. For alternate installs, see
> [INSTALL.md](INSTALL.md).

---

## 1. Install

```bash
git clone https://github.com/James-HoneyBadger/LashonStudio.git
cd Lashon
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Check it:

```bash
lashon --version
# lashon 4.0.0
```

---

## 2. Define a grammar

A grammar is a set of named PEG rules. Save this as `mini.peg`:

```peg
# mini.peg — assignments and arithmetic
program   <- statement+
statement <- IDENT "=" expr ";"
expr      <- term (("+" / "-") term)*
term      <- factor (("*" / "/") factor)*
factor    <- NUMBER / IDENT / "(" expr ")"
```

**What the notation means**

| Syntax | Meaning |
|---|---|
| `name <- pattern` | define a rule |
| `a b c` | sequence |
| `a / b` | ordered choice (first match wins) |
| `a*`, `a+`, `a?` | zero-or-more, one-or-more, optional |
| `"text"` / `'text'` | literal string |
| `NUMBER`, `IDENT`, `STRING` | built-in tokens |
| `(` … `)` | grouping |

Full reference: [GRAMMAR_REFERENCE.md](GRAMMAR_REFERENCE.md).

---

## 3. Parse source

```python
from lashon.parser import GrammarParser, PEGInterpreter

grammar = GrammarParser().parse(open("mini.peg").read())
interpreter = PEGInterpreter(grammar)

ast = interpreter.parse("x = 2 + 3 * 4 ;")
print(ast.pretty())
```

Output:

```
program[1]
  statement[4]
    Identifier('x')
    Operator('=')
    expr[3]
      term[1]
        factor[1]
          Number(2)
      Operator('+')
      term[3]
        factor[1]
          Number(3)
        Operator('*')
        factor[1]
          Number(4)
    Operator(';')
```

The parser is a packrat parser: each `(rule, position)` pair is memoized, so
parsing is linear in the input size. It skips whitespace and `//` comments by
default.

---

## 4. Execute it

Lashon ships a Python transpiler. It understands the AST shapes produced
by the built-in tokens and common PEG patterns:

```python
from lashon.codegen import transpile_and_exec

result = transpile_and_exec(ast)
print(result)
# {'x': 14}
```

`transpile_and_exec` returns only program-visible names; `__builtins__` is
filtered out.

Want to see the intermediate Python?

```python
from lashon.codegen import transpile_to_python

print(transpile_to_python(ast))
# x = 2 + 3 * 4
```

---

## 5. Emit other targets

```python
from lashon.codegen import CCodeGenerator, WasmGenerator, LLVMIRGenerator

print(CCodeGenerator().translate_source_ast(ast))     # ANSI C
print(WasmGenerator().translate_source_ast(ast).to_wat())  # WAT
print(LLVMIRGenerator().translate_source_ast(ast))    # LLVM IR
```

`PythonTranspiler` also exposes the common backend method:

```python
from lashon.codegen import PythonTranspiler

print(PythonTranspiler().translate_source_ast(ast))
```

Every backend implements `translate_source_ast(ast) -> str` (the WASM backend
returns a `WasmModule`; call `.to_wat()`).

---

## 6. Add control flow

Extend the grammar:

```peg
program       <- statement+
statement     <- if_stmt / while_stmt / assignment
if_stmt       <- "if" comparison block ("else" block)?
while_stmt    <- "while" comparison block
block         <- "{" statement* "}"
assignment    <- IDENT "=" expr ";"
comparison    <- expr ("==" / "!=" / "<" / ">" / "<=" / ">=") expr
expr          <- term (("+" / "-") term)*
term          <- factor (("*" / "/" / "%") factor)*
factor        <- call / NUMBER / STRING / IDENT / "(" expr ")"
call          <- IDENT "(" arg_list? ")"
arg_list      <- expr ("," expr)*
```

Then rebuild the interpreter and run:

```python
from lashon.parser import GrammarParser, PEGInterpreter
from lashon.codegen import transpile_and_exec

grammar = GrammarParser().parse(open("mini.peg").read())   # updated file
interpreter = PEGInterpreter(grammar)

source = """
i = 0 ;
sum = 0 ;
while i < 5 {
  i = i + 1 ;
  sum = sum + i ;
}
"""
ast = interpreter.parse(source)
print(transpile_and_exec(ast))
# {'i': 5, 'sum': 15}
```

The numbers in `pretty()` output are child counts, not positions — use
`node.line`/`node.column` for source locations.

If a construct does not transpile the way you expect, inspect the AST first —
the AST *is* the contract between parsing and code generation. See
[CODEGEN_GUIDE.md](CODEGEN_GUIDE.md).

---

## 6.5 Scaffold a project

The same workflow, generated for you:

```bash
lashon init "My Lang" --directory ./languages
cd languages/my-lang
python -m pytest tests -q
lashon run samples/hello.aur --config language.yaml
```

`init` writes `language.yaml`, `grammar.peg`, a sample, a README, and tests that
validate the grammar, run the sample, and generate every backend.

## 7. Use the Studio

```bash
lashon-ide projects/aurora
```

The Studio opens the Aurora reference language with:

- a project tree (config, grammar, samples),
- source / grammar / language editors,
- a console and variable inspector,
- Python, C, WASM, and LLVM IR panes,
- an expandable AST tree.

Press **F5** to run the current sample, **F6** for the AST, **F7** to generate
all backends. Full walkthrough: [STUDIO_GUIDE.md](STUDIO_GUIDE.md).

---

## 8. Use the CLI

```bash
# Validate a language config (grammar + metadata)
lashon validate projects/aurora/language.yaml

# Run a program through a config that contains a PEG grammar
lashon repl projects/aurora/language.yaml

# Generate targets
lashon codegen-c    projects/aurora/samples/fibonacci.aur \
  --config projects/aurora/language.yaml --output /tmp/fib.c
lashon codegen-wasm  projects/aurora/samples/fibonacci.aur \
  --config projects/aurora/language.yaml --output /tmp/fib.wat
lashon codegen-llvm  projects/aurora/samples/fibonacci.aur \
  --config projects/aurora/language.yaml --output /tmp/fib.ll
```

Unlike the codegen commands, the config-driven REPL works from keywords alone;
for grammar-driven execution use the Python API or the Studio.

Every command and flag: [CLI_REFERENCE.md](CLI_REFERENCE.md).

---

## 9. Where to go next

| Goal | Document |
|---|---|
| Learn the whole platform step by step | [TUTORIAL.md](TUTORIAL.md) |
| Design a real language | [LANGUAGE_DEVELOPMENT.md](LANGUAGE_DEVELOPMENT.md) |
| Understand grammar semantics | [GRAMMAR_REFERENCE.md](GRAMMAR_REFERENCE.md) |
| Build a backend | [CODEGEN_GUIDE.md](CODEGEN_GUIDE.md) |
| Add a runtime/stdlib/FFI | [RUNTIME_GUIDE.md](RUNTIME_GUIDE.md) |
| Ship a VS Code extension | [PACKAGING.md](PACKAGING.md) |
| Something is broken | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |

---

## The two-minute conceptual model

```
grammar text ──GrammarParser──► Grammar (rules + PEG tree)
                                     │
source text ──PEGInterpreter─────────┘
                    │
                    ▼
                 SourceAST
                    │
     ┌──────────────┼──────────────┬──────────────┐
     ▼              ▼              ▼              ▼
  Python            C             WASM           LLVM
```

- **Grammar** is data: rules, start rule, whitespace/comment policy.
- **SourceAST** is a uniform tree: `node_type`, optional `value`, `children`,
  plus source positions.
- **Backends** are visitors over that tree. The same AST feeds all four.
- **Studio** is a GUI over the same headless controller the tests use.

That is the entire architecture. Everything else is tooling around it.
