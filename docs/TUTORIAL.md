# Lashon Tutorials

Eight progressive tutorials, from a five-line grammar to a packaged language.
Each tutorial can be read independently, but they build on one another.

| # | Tutorial | You will learn |
|---|---|---|
| 1 | Your first language in 15 minutes | grammar → AST → execute |
| 2 | Control flow and functions | layering a real grammar |
| 3 | Config-driven language design | presets, keyword remapping, REPL |
| 4 | Four backends | Python, C, WASM, LLVM IR |
| 5 | Build Aurora from scratch | a complete, tested language |
| 6 | Write a backend | custom code generation |
| 7 | Runtime, stdlib, FFI | semantics and native calls |
| 8 | Test, package, and ship | CI, wheel, VS Code extension |

All snippets assume `pip install -e .`. See [INSTALL.md](INSTALL.md).

---

## Tutorial 1 — Your first language in 15 minutes

### 1.1 Write the grammar

**`mini.peg`**

```peg
program   <- statement+
statement <- IDENT "=" expr ";"
expr      <- term (("+" / "-") term)*
term      <- factor (("*" / "/") factor)*
factor    <- NUMBER / IDENT / "(" expr ")"
```

### 1.2 Parse

```python
from lashon.parser import GrammarParser, PEGInterpreter

grammar = GrammarParser().parse(open("mini.peg").read())
assert grammar.validate() == []

interpreter = PEGInterpreter(grammar)
ast = interpreter.parse("x = 2 + 3 * 4 ;")
print(ast.pretty())
```

Each rule becomes an AST node; literals/operators become `Operator` children;
`NUMBER`/`IDENT` become `Number`/`Identifier` leaves.

### 1.3 Execute

```python
from lashon.codegen import transpile_and_exec, transpile_to_python

print(transpile_to_python(ast))
# x = 2 + 3 * 4

print(transpile_and_exec(ast))
# {'x': 14}
```

`transpile_and_exec` filters `__builtins__` from the returned namespace.

### 1.4 Grammar-driven REPL

```bash
lashon repl --grammar mini.peg
```

```
>>> x = 10 + 5 ;
>>> y = x * 2 ;
>>> :vars
  x = 15
  y = 30
>>> :ast
>>> :quit
```

The `--grammar` REPL uses the PEG interpreter and `:` commands. The
config-driven REPL (without `--grammar`) uses `.` commands; do not mix them.

**Checkpoint:** a parser, an AST, and an executable language.

---

## Tutorial 2 — Control flow and functions

Extend `mini.peg` into **Calc**.

### 2.1 Grammar

```peg
program       <- statement+
statement     <- function_def / if_stmt / while_stmt / return_stmt
               / print_stmt / assignment / expr_stmt
function_def  <- "fn" IDENT "(" param_list? ")" block
block         <- "{" statement* "}"
param_list    <- IDENT ("," IDENT)*
if_stmt       <- "if" comparison block ("else" block)?
while_stmt    <- "while" comparison block
return_stmt   <- "return" expr ";"
print_stmt    <- "print" expr ";"
assignment    <- IDENT "=" expr ";"
expr_stmt     <- call ";"
comparison    <- expr ("==" / "!=" / "<=" / ">=" / "<" / ">") expr
expr          <- term (("+" / "-") term)*
term          <- factor (("*" / "/" / "%") factor)*
factor        <- call / NUMBER / STRING / boolean / IDENT / "(" expr ")"
call          <- IDENT "(" arg_list? ")"
arg_list      <- expr ("," expr)*
boolean       <- "true" / "false"
```

Ordering matters: keywords before identifiers, `<=` before `<`, specific
statements before generic expressions.

### 2.2 Program

```calc
fn fib(n) {
  if n <= 1 { return n ; }
  return fib(n - 1) + fib(n - 2) ;
}

fn fact(n) {
  if n <= 1 { return 1 ; }
  return n * fact(n - 1) ;
}

print "fib(10) =" ;
print fib(10) ;
print "10! =" ;
print fact(10) ;
```

### 2.3 Run it

```python
from lashon.parser import GrammarParser, PEGInterpreter
from lashon.codegen import transpile_and_exec

grammar = GrammarParser().parse(open("calc.peg").read())
ast = PEGInterpreter(grammar).parse(open("program.calc").read())
print(transpile_and_exec(ast))
```

`print` output:

```
fib(10) =
55
10! =
3628800
```

### 2.4 Negative test

```python
from lashon.parser import GrammarParser, PEGInterpreter

calc = PEGInterpreter(GrammarParser().parse(open("calc.peg").read()))
try:
    calc.parse("fn broken( {")
except SyntaxError as error:
    print(error)
# Parse error at line 1, column 11 (in rule 'param_list'): unexpected ' {'
```

The reported rule is the furthest one reached, which is often *deeper* than the
construct you were editing — use the line/column and rule name together.

**Checkpoint:** Calc has the same shape as Aurora.

---

## Tutorial 3 — Config-driven language design

A config-driven language keeps Python/BASIC-like semantics and changes
vocabulary. No PEG grammar is required.

### 3.1 Start from a preset

```python
from lashon.config import LanguageConfig, list_presets

print(list_presets())
# ['python_like', 'js_like', 'minimal', 'ruby_like', 'golang_like',
#  'rust_like', 'clike', 'functional', 'lisp_like', 'basic_like']

config = LanguageConfig.from_preset("python_like")
print(config.name)          # Python-like
print(config.keywords["if"]) # KeywordMapping(original='if', custom='if', ...)
```

### 3.2 Customise keywords and functions

```python
config.name = "Espanol"
config.rename_keyword("if", "si")
config.rename_keyword("else", "sino")
config.rename_keyword("while", "mientras")
config.rename_function("print", "imprimir")
config.save("espanol.yaml")
```

`add_function("imprimir", "print")` is an alias: it keeps the original
`print` function and exposes it under the new name.

### 3.3 Validate and inspect

```bash
lashon validate espanol.yaml
lashon info espanol.yaml
lashon export espanol.yaml --format markdown --output espanol.md
```

`validate` exits 0 for valid configs and prints warnings for duplicate keyword
aliases.

### 3.4 Runtime translation

```python
from lashon.runtime.language_runtime import LanguageRuntime

LanguageRuntime.load_config(config=config)
print(LanguageRuntime.translate_keyword("si"))        # if
print(LanguageRuntime.translate_function("imprimir")) # builtin.print
```

### 3.5 Config-driven REPL

```bash
lashon repl espanol.yaml
```

```
>>> x = 5
>>> print(x)
5
>>> .vars
Variables:
  x = 5
>>> .exit
```

This REPL translates custom keywords to Python and executes. It is not a PEG
interpreter; use `--grammar` or the Studio for grammar-driven execution.

**Checkpoint:** localise and reskin a language in minutes.

---

## Tutorial 4 — Four backends

Using the Calc AST from Tutorial 2:

```python
from lashon.codegen import (
    PythonTranspiler, CCodeGenerator, WasmGenerator, LLVMIRGenerator,
)

python_code = PythonTranspiler().translate_source_ast(ast)
c_code      = CCodeGenerator().translate_source_ast(ast)
wat         = WasmGenerator().translate_source_ast(ast).to_wat()
llvm_ir     = LLVMIRGenerator().translate_source_ast(ast)
```

What each backend gives you:

| Backend | Output | Notes |
|---|---|---|
| Python | runnable source | most complete semantics |
| C | ANSI C with `main()` | source emitter, not an optimizing compiler |
| WASM | WAT (`(module …)`) | `main` export, minimal imports |
| LLVM IR | textual SSA IR | compile with `clang`/`llc` |

Compile the IR if you like:

```bash
clang output.ll -o program
./program
```

### CLI equivalents

The CLI reads the grammar from the **config file**, not from `calc.peg`, so put
the rules in `calc.yaml`:

```yaml
name: Calc
grammar:
  start: program
  comments: ["//.*"]
  rules:
    program: statement+
    statement: function_def / if_stmt / while_stmt / return_stmt / print_stmt / assignment / expr_stmt
    function_def: '"fn" IDENT "(" param_list? ")" block'
    block: '"{" statement* "}"'
    param_list: 'IDENT ("," IDENT)*'
    if_stmt: '"if" comparison block ("else" block)?'
    while_stmt: '"while" comparison block'
    return_stmt: '"return" expr ";"'
    print_stmt: '"print" expr ";"'
    assignment: 'IDENT "=" expr ";"'
    expr_stmt: 'call ";"'
    comparison: 'expr ("==" / "!=" / "<=" / ">=" / "<" / ">") expr'
    expr: 'term (("+" / "-") term)*'
    term: 'factor (("*" / "/" / "%") factor)*'
    factor: 'call / NUMBER / STRING / boolean / IDENT / "(" expr ")"'
    call: 'IDENT "(" arg_list? ")"'
    arg_list: 'expr ("," expr)*'
    boolean: '"true" / "false"'
```

```bash
lashon codegen-c    program.calc --config calc.yaml --output program.c
lashon codegen-wasm  program.calc --config calc.yaml --output program.wat
lashon codegen-llvm  program.calc --config calc.yaml --output program.ll
```

Quote each YAML value so PEG operators (`*`, `?`, `"`) stay strings. Details and
fidelity caveats: [CODEGEN_GUIDE.md](CODEGEN_GUIDE.md).

**Checkpoint:** one AST, four targets.

---

## Tutorial 5 — Build Aurora from scratch

Aurora is the bundled reference language: 18 rules, three samples, four
backends.

### 5.1 Scaffold

Studio: **New**, choose a folder, name the language. Or:

```python
from lashon.ide.studio import LanguageStudio

studio = LanguageStudio()
project = studio.new_project("Aurora", ".")
print(project.root)
```

```
aurora/
  language.yaml
  grammar.peg
  samples/hello.aur
  README.md
```

### 5.2 Grammar

Replace `grammar.peg`:

```peg
program       <- statement+
statement     <- function_def / if_stmt / while_stmt / return_stmt
               / print_stmt / assignment / expr_stmt
function_def  <- "fn" IDENT "(" param_list? ")" block
block         <- "{" statement* "}"
param_list    <- IDENT ("," IDENT)*
if_stmt       <- "if" comparison block ("else" block)?
while_stmt    <- "while" comparison block
return_stmt   <- "return" expr ";"
print_stmt    <- "print" expr ";"
assignment    <- IDENT "=" expr ";"
expr_stmt     <- call ";"
comparison    <- expr ("==" / "!=" / "<=" / ">=" / "<" / ">") expr
expr          <- term (("+" / "-") term)*
term          <- factor (("*" / "/" / "%") factor)*
factor        <- call / NUMBER / STRING / boolean / IDENT / "(" expr ")"
call          <- IDENT "(" arg_list? ")"
arg_list      <- expr ("," expr)*
boolean       <- "true" / "false"
```

### 5.3 Language metadata

`language.yaml`:

```yaml
name: Aurora
version: "1.0.0"
description: "A small, expressive teaching language built with Lashon."
author: "Lashon Studio"

keywords:
  if: "if"
  else: "else"
  while: "while"
  fn: "fn"
  return: "return"
  print: "print"
  "true": "true"
  "false": "false"

syntax_options:
  single_line_comment: "//"
  require_semicolons: true
  statement_terminator: ";"

grammar:
  start: program
  skip_whitespace: true
  comments:
    - "//.*"
  rules:
    # keep in sync with grammar.peg; the Studio does this on save
```

### 5.4 Samples

`hello.aur`:

```aurora
// Aurora — hello world
print "Hello, Aurora!" ;
```

`fibonacci.aur`:

```aurora
fn fib(n) {
  if n <= 1 { return n ; }
  return fib(n - 1) + fib(n - 2) ;
}

fn fact(n) {
  if n <= 1 { return 1 ; }
  return n * fact(n - 1) ;
}

print "fib(10) =" ;
print fib(10) ;
print "10! =" ;
print fact(10) ;
```

`fizzbuzz.aur`:

```aurora
fn fizzbuzz(limit) {
  i = 1 ;
  while i <= limit {
    if i % 15 == 0 { print "FizzBuzz" ; }
    else {
      if i % 3 == 0 { print "Fizz" ; }
      else {
        if i % 5 == 0 { print "Buzz" ; }
        else { print i ; }
      }
    }
    i = i + 1 ;
  }
}

fizzbuzz(15) ;
```

### 5.5 Validate and run

```python
studio.open_project("aurora")
print(studio.validate_grammar().text)   # Grammar OK — 18 rules
print(studio.run().text)                # Hello from Aurora!
```

Studio: **F5** runs, **F6** shows the AST, **F7** generates all backends.

### 5.6 Generate all targets

```python
from pathlib import Path

source = Path("aurora/samples/fibonacci.aur").read_text()
results = studio.generate_all(source)
print({name: (r.ok, len(r.text)) for name, r in results.items()})
# {'python': (True, ...), 'c': (True, ...), 'wasm': (True, ...), 'llvm': (True, ...)}
```

### 5.7 CLI

```bash
lashon validate projects/aurora/language.yaml
lashon codegen-c projects/aurora/samples/fibonacci.aur \
  --config projects/aurora/language.yaml --output /tmp/fib.c
```

**Checkpoint:** a complete language project.

---

## Tutorial 6 — Write a backend

A backend only needs `translate_source_ast(ast) -> str`.

```python
from lashon.parser import SourceAST

class OutlineBackend:
    """Emit an indented outline of the AST."""

    def translate_source_ast(self, ast: SourceAST) -> str:
        lines: list[str] = []

        def visit(node: SourceAST, depth: int) -> None:
            label = node.node_type
            if node.value is not None:
                label += f" = {node.value!r}"
            lines.append("  " * depth + label)
            for child in node.children:
                visit(child, depth + 1)

        visit(ast, 0)
        return "\n".join(lines)
```

Use it:

```python
from lashon.parser import GrammarParser, PEGInterpreter

grammar = GrammarParser().parse(
    'program <- statement+\n'
    'statement <- IDENT "=" NUMBER ";"'
)
ast = PEGInterpreter(grammar).parse("x = 42 ;")
print(OutlineBackend().translate_source_ast(ast))
```

Output:

```
program
  statement
    Identifier = 'x'
    Operator = '='
    Number = 42
    Operator = ';'
```

### Backend rules of thumb

1. Accept any `SourceAST`-shaped tree.
2. Dispatch on `node_type`; provide a wrapper fallback.
3. Filter structural operators (`;`, `,`, `{`, `}`).
4. Never mutate the AST.
5. Test every sample through the backend.

---

## Tutorial 7 — Runtime, stdlib, FFI

### 7.1 Standard library

```python
from lashon.runtime.stdlib import StdLib

stdlib = StdLib()
stdlib.register_builtins()          # required

ns = {}
stdlib.inject(ns)                   # print, len, range, int, ...
print(ns["len"]("hello"))           # 5

stdlib.inject_module("math", ns, ["sqrt"])
print(ns["sqrt"](9))                # 3.0

math_ns = {}
stdlib.inject_module("math", math_ns)
print(math_ns["math"].sqrt(16))     # 4.0
```

Modules: `io`, `math`, `string`, `collections`, `system`, `random`. Full symbol
tables: [RUNTIME_GUIDE.md](RUNTIME_GUIDE.md#standard-library).

### 7.2 Custom module

```python
from lashon.runtime.stdlib import StdLib, StdModule

lib = StdLib()
lib.register_builtins()

mod = StdModule("aurora")
mod.add_function(
    "shout",
    lambda text: str(text).upper() + "!",
    params=[("text", "string")],
    returns="string",
    doc="Uppercase and add an exclamation mark.",
)
lib.add_module(mod)

ns = {}
lib.inject_module("aurora", ns, ["shout"])
print(ns["shout"]("hello"))  # HELLO!
```

### 7.3 Python FFI

```python
from lashon.runtime.ffi import FFIBridge

ffi = FFIBridge()
ffi.register_python("greet", lambda name: f"Hello, {name}!")
print(ffi.call("greet", "World"))   # Hello, World!

ns = {}
ffi.inject(ns)
print(ns["greet"]("Ada"))           # Hello, Ada!
```

### 7.4 C FFI

```python
ffi.load_library("m", "/usr/lib/libm.so.6")
ffi.bind("sqrt", "m", arg_types=["double"], return_type="double")
print(ffi.call("sqrt", 144.0))      # 12.0
```

FFI executes native code and `transpile_and_exec` executes Python. Run only
trusted programs. See [RUNTIME_GUIDE.md](RUNTIME_GUIDE.md#security-model).

---

## Tutorial 8 — Test, package, and ship

### 8.1 Test the language

```python
from pathlib import Path
from lashon.ide.studio import LanguageStudio

def test_language():
    studio = LanguageStudio()
    studio.open_project("projects/aurora")
    assert studio.validate_grammar().ok

    for sample in Path("projects/aurora/samples").glob("*.aur"):
        source = sample.read_text()
        assert studio.run(source).ok, sample
        for backend, output in studio.generate_all(source).items():
            assert output.ok, (sample, backend, output.error)
```

```bash
python -m pytest -q
```

### 8.2 Build a wheel

```bash
python -m build          # or: pip wheel . --no-deps -w dist/
```

Package data (grammar, samples) is controlled by
`[tool.setuptools.package-data]` and `MANIFEST.in`; see
[PACKAGING.md](PACKAGING.md).

### 8.3 Generate a VS Code extension

```bash
lashon extension --config projects/aurora/language.yaml \
  --output ./aurora-vscode --publisher my-org --version 1.0.0
cd aurora-vscode
npm install -g @vscode/vsce
vsce package
```

### 8.4 Publish package metadata

```python
from lashon.packaging import Package, PackageRegistry
from lashon.packaging.package_registry import Version

registry = PackageRegistry()
registry.register_package(Package("aurora", Version.parse("1.0.0")))
print(registry.resolve("aurora", "^1.0.0"))   # aurora@1.0.0
```

The `package-search` / `package-install` CLI commands are placeholders until a
remote registry exists; use the Python API.

### 8.5 Version and document

- Bump `version` in `language.yaml`.
- Update `CHANGELOG.md`.
- Keep a project `README.md` with a language tour.
- Re-run positive and negative tests.

**Checkpoint:** a shippable language.

---

## Where next

- [LANGUAGE_DEVELOPMENT.md](LANGUAGE_DEVELOPMENT.md) — design method.
- [GRAMMAR_REFERENCE.md](GRAMMAR_REFERENCE.md) — every PEG construct.
- [CODEGEN_GUIDE.md](CODEGEN_GUIDE.md) — backend details.
- [STUDIO_GUIDE.md](STUDIO_GUIDE.md) — GUI walkthrough.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — when something breaks.
