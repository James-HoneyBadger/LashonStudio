# Lashon — User Guide

Task-oriented guide to building and running languages with Lashon 4.0.0.
For exhaustive references, follow the links to the dedicated pages.

- New here? Start with [QUICKSTART.md](QUICKSTART.md).
- Designing a language? Read [LANGUAGE_DEVELOPMENT.md](LANGUAGE_DEVELOPMENT.md).
- Need a flag or command? See [CLI_REFERENCE.md](CLI_REFERENCE.md).
- Stuck? Use [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## Contents

1. [Two ways to use Lashon](#two-ways-to-use-lashon)
2. [Install and verify](#install-and-verify)
3. [Create a language configuration](#create-a-language-configuration)
4. [Map keywords, functions, and operators](#map-keywords-functions-and-operators)
5. [Define a grammar](#define-a-grammar)
6. [Execute programs](#execute-programs)
7. [Generate other targets](#generate-other-targets)
8. [Use the REPL](#use-the-repl)
9. [Use the Studio](#use-the-studio)
10. [Modules, types, and tooling](#modules-types-and-tooling)
11. [Ship your language](#ship-your-language)
12. [Limits and security](#limits-and-security)

---

## Two ways to use Lashon

| Approach | You provide | You get | Typical use |
|---|---|---|---|
| **Grammar (PEG)** | `grammar.peg` rules | `SourceAST` → Python/C/WASM/LLVM | real languages with syntax |
| **Config only** | keyword/function/operator maps | textual translation to Python | localized Python, teaching, quick wins |

They compose: a language config can hold both keyword mappings (for the config
REPL) and a `grammar.rules` section (for parsing and codegen). `projects/aurora`
does exactly that.

---

## Install and verify

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

lashon --version          # lashon 4.0.0
python -m pytest -q            # 368 passed
```

Platform notes live in [INSTALL.md](INSTALL.md).

---

## Create a language configuration

Start a complete project (config + grammar + sample + tests):

```bash
lashon init "My Lang" --directory ./languages
cd languages/my-lang && python -m pytest tests -q
```

Or create a single config from a preset:

```bash
lashon create --preset python_like --output my_lang.yaml
lashon validate my_lang.yaml
lashon info my_lang.yaml
```

Presets: `python_like`, `js_like`, `minimal`, `ruby_like`, `golang_like`,
`rust_like`, `clike`, `functional`, `lisp_like`, `basic_like`.

Minimal shape:

```yaml
name: MyLang
version: "0.1.0"
description: "A tiny language"
author: "you"

keywords:
  print: "print"
  if: "if"
  else: "else"
  while: "while"
  "true": "True"
  "false": "False"

functions:
  length: "len"
  show: "print"

operators:
  equals: "=="

syntax_options:
  single_line_comment: "//"
  require_semicolons: true
```

Loading and saving from Python:

```python
from lashon.config import LanguageConfig

config = LanguageConfig.load("my_lang.yaml")   # or .json
config.save("copy.yaml")
print(config.name, config.version)
```

`LanguageConfig.validate()` returns hard errors; `validation_warnings()` reports
duplicate alias warnings. The CLI prints both and exits 0 when there are no hard
errors. Full schema: [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md#languageconfig).

---

## Map keywords, functions, and operators

Keys are **your** words; values are the Python targets.

```yaml
keywords:
  escribir: "print"
  si: "if"
  sino: "else"
  mientras: "while"

functions:
  longitud: "len"
```

```bash
lashon translate --config espanol.yaml --input programa.txt
```

Programmatic edits:

```python
from lashon.config import LanguageConfig

config = LanguageConfig.load("my_lang.yaml")
config.rename_keyword("print", "escribir")
config.add_function("longitud", "len")
config.remove_keyword("escribir")
config.save("my_lang.yaml")
```

Unknown names raise `ValueError("Keyword 'x' not found")`; invalid identifiers
raise with the validator's warning as the message.

---

## Define a grammar

Keep grammar text in `grammar.peg` (or under `grammar.rules` in YAML):

```peg
program     <- statement+
statement   <- assignment / print_stmt
assignment  <- IDENT "=" expr ";"
print_stmt  <- "print" expr ";"
expr        <- term (("+" / "-") term)*
term        <- factor (("*" / "/") factor)*
factor      <- NUMBER / IDENT / "(" expr ")"
```

```python
from lashon.parser import GrammarParser, PEGInterpreter

grammar = GrammarParser().parse(open("grammar.peg").read())
ast = PEGInterpreter(grammar).parse("x = 21 * 2 ; print x ;")

print(ast.pretty())
for node in ast.children:
    print(node.node_type, node.line, node.column)
```

Rules you should know:

- `<-` defines a rule (`=` is accepted too).
- `"literal"`, `'literal'`, `[a-z0-9_]`, `.`, `rule`, `TOKEN`.
- `a / b` ordered choice (`|` works as an alias).
- `p*`, `p+`, `p?`, `&p`, `!p`, `( … )`.
- Comments: `#` and `//`.
- Left recursion is rejected — rewrite it with repetition.
- Built-in tokens: `NUMBER`, `IDENT`, `STRING`, `NEWLINE`, `EOF`. `INDENT` and
  `DEDENT` parse as tokens but validation rejects them as unsupported.

Semantics and pitfalls: [GRAMMAR_REFERENCE.md](GRAMMAR_REFERENCE.md).

---

## Execute programs

```python
from lashon.codegen import PythonTranspiler, transpile_and_exec

print(PythonTranspiler().translate_source_ast(ast))

namespace = transpile_and_exec(ast)          # {'x': 42}
print(namespace)
```

Options:

```python
from lashon.codegen import PythonTranspiler, TranspileOptions

transpiler = PythonTranspiler(TranspileOptions(
    indent_str="  ",
    keyword_map={"print": "print"},
    function_map={"show": "print"},
    wrap_in_main=True,
))
print(transpiler.transpile(ast))
```

`transpile_and_exec` filters dunder keys, so the returned dict contains only
your names (plus anything passed via `globals_dict`).

---

## Generate other targets

```bash
lashon codegen-c    program.src --config my_lang.yaml --output out.c
lashon codegen-llvm program.src --config my_lang.yaml --output out.ll
lashon codegen-wasm program.src --config my_lang.yaml --output out.wat
```

```bash
gcc -std=c99 out.c -o program && ./program
clang out.ll -o program && ./program
```

C, LLVM, and WASM handle functions, `if/else`, `while`, recursion, calls, and
printing for the documented AST nodes (WASM is integer-only and needs host
`console` imports). Details and fidelity notes:
[CODEGEN_GUIDE.md](CODEGEN_GUIDE.md).

From Python:

```python
from lashon.codegen import CCodeGenerator, LLVMIRGenerator, WasmGenerator

c_src = CCodeGenerator().translate_source_ast(ast)
ir = LLVMIRGenerator().translate_source_ast(ast)
wat = WasmGenerator().translate_source_ast(ast).to_wat()   # returns WasmModule
```

---

## Use the REPL

Grammar REPL:

```bash
lashon repl --grammar grammar.peg
```

```text
>>> fn twice(x) { return x * 2 ; }
>>> print twice(21) ;
42
>>> :ast
>>> :py
>>> :quit
```

Config REPL:

```bash
lashon repl espanol.yaml
```

```text
>>> escribir "hola"
hola
>>> .keywords
>>> .exit
```

Command sets differ (`:` for grammar, `.` for config):

| Grammar REPL | Config REPL | Effect |
|---|---|---|
| `:ast` / `:py` | — | show the AST or generated Python |
| `:doc RULE` | — | print a rule's pattern |
| `:backends` | — | C / WASM / LLVM line counts for the last AST |
| `:load FILE` / `:save FILE` | `.save FILE` | read or write a source file |
| `:time` | `.time` | toggle per-line timing |
| `:vars` / `:reset` | `.vars` / `.clear` | inspect or clear the namespace |

Both REPLs keep history between sessions, and the grammar REPL completes
commands, rule names, and common builtins with `Tab`. Programmatic use:

```python
from lashon.runtime import REPL
from lashon.parser import GrammarParser

repl = REPL(grammar=GrammarParser().parse(open("grammar.peg").read()))
repl.eval_line('print "hi" ;')            # 'hi\n'
ns = repl.eval_lines(["a = 1 ;", "b = a + 1 ;"])
```

Full REPL, stdlib, and FFI details: [RUNTIME_GUIDE.md](RUNTIME_GUIDE.md).

---

## Use the Studio

```bash
lashon-ide                          # opens the Aurora sample when available
lashon-ide projects/aurora          # open a project
```

Layout: project tree on the left, Source / Grammar / Language tabs in the middle,
Console / Variables / Python / C / WASM / LLVM IR / AST tabs on the right.

Everyday actions:

| Action | Shortcut |
|---|---|
| Run | `F5` |
| Parse only | `F6` |
| Generate all backends | `F7` |
| Save project | `Ctrl+S` |
| Open project | `Ctrl+O` |
| New project | `Ctrl+N` |

Saving writes `grammar.peg` and syncs its rules into `language.yaml` after
validating the grammar. Manual: [STUDIO_GUIDE.md](STUDIO_GUIDE.md).

---

## Modules, types, and tooling

**Modules**

```bash
lashon module-info utils --module-dir ./modules
lashon module-deps main --module-dir ./modules
lashon module-cycles --module-dir ./modules
```

```python
from lashon.runtime import ModuleManager
from lashon.config import LanguageConfig

manager = ModuleManager(LanguageConfig.load("my_lang.yaml"), search_paths=["modules"])
module = manager.load_module("utils")
print(list(module.exports), manager.resolve_dependencies("utils"))
```

Syntax and limits: [RUNTIME_GUIDE.md](RUNTIME_GUIDE.md#module-system).

**Types**

```bash
lashon type-check --config my_lang.yaml --input program.src --level strict
```

The checker is line-oriented and heuristic; it understands `name: type = value`
and literal inference. See [TYPE_SYSTEM.md](TYPE_SYSTEM.md).

**Editor and debugger**

```bash
lashon lsp --config my_lang.yaml --stdio     # stdio subset
lashon format program.src --in-place
lashon refactor-rename program.src old new
```

See [LSP_AND_DEBUGGING.md](LSP_AND_DEBUGGING.md) for capabilities and the DAP
controller.

---

## Ship your language

1. Copy the shape of `projects/aurora`: `language.yaml`, `grammar.peg`,
   `samples/`, README.
2. Generate a reference: `DocumentationGenerator().save_markdown(config, "REFERENCE.md")`.
3. Generate a VS Code extension:
   `lashon extension --config language.yaml --output ./my-lang-vscode`.
4. Decide how users run it: `lashon-ide`, `lashon repl`, or a
   generated backend plus your own toolchain.

Packaging details, including what the extension generator does *not* produce:
[PACKAGING.md](PACKAGING.md).

---

## Limits and security

- **Execution is unsandboxed.** Transpiled code runs through `exec`; FFI calls
  native libraries through `ctypes`. Only run trusted source.
- **WASM codegen is incomplete** (see above).
- **C/LLVM are integer-typed** unless values are float literals; no arrays,
  structs, or pointers.
- **LSP stdio** serves `initialize`, `shutdown`, `exit`, and completion; other
  features are programmatic.
- **Placeholders:** `generics`, `check-protocol`, `package-search`,
  `package-install`, and `test-run` report success without performing analysis.
- **The type checker is advisory**, not a proof of safety.

---

## Command cheat sheet

| Goal | Command |
|---|---|
| Scaffold project | `lashon init "My Lang" -d ./languages` |
| Create config | `lashon create --preset python_like -o lang.yaml` |
| Validate | `lashon validate lang.yaml` |
| Inspect | `lashon info lang.yaml` |
| Grammar REPL | `lashon repl --grammar g.peg` |
| Config REPL | `lashon repl lang.yaml` |
| Run a program | `lashon run prog.src -g g.peg` |
| Run a script | `lashon batch lang.yaml --script prog.txt --show-vars` |
| Emit C | `lashon codegen-c prog.src -c lang.yaml -o prog.c` |
| Emit LLVM | `lashon codegen-llvm prog.src -c lang.yaml -o prog.ll` |
| Emit WAT | `lashon codegen-wasm prog.src -c lang.yaml -o prog.wat` |
| Type check | `lashon type-check -c lang.yaml -i prog.src` |
| LSP | `lashon lsp -c lang.yaml --stdio` |
| Extension | `lashon extension -c lang.yaml -o ./ext` |
| Studio | `lashon-ide projects/aurora` |
| Browser playground | `lashon play projects/aurora --open` |
| Guided demo | `lashon demo` |
| Environment check | `lashon doctor` |
| CI lint | `lashon lint lang.yaml --source prog.src` |
| Change one setting | `lashon config set lang.yaml grammar.start program` |
| Re-run on save | `lashon run prog.src -c lang.yaml --watch` |

Every command and flag: [CLI_REFERENCE.md](CLI_REFERENCE.md).
