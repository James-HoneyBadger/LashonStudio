# Troubleshooting and FAQ

Symptom-first guide to the errors you are most likely to hit. Each entry says
what the message means and the smallest fix.

---

## Installation and environment

### `ModuleNotFoundError: No module named 'lashon'`

Not installed, or the wrong interpreter.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
python -c "import lashon; print(lashon.__version__)"
```

Running tests without installing also works because `pyproject.toml` sets
`pythonpath = ["src"]`:

```bash
python -m pytest -q
```

### `No module named 'yaml'`

PyYAML is a runtime dependency:

```bash
pip install "PyYAML>=6.0"
```

It is needed for YAML configs, Studio projects, `export`, `convert`, and the
`codegen-*` commands with YAML configs.

### `ModuleNotFoundError: No module named 'tkinter'`

The Studio needs Tkinter:

- Debian/Ubuntu: `sudo apt install python3-tk`
- Fedora: `sudo dnf install python3-tkinter`
- macOS/Windows python.org installers: bundled
- pyenv: rebuild after installing Tcl/Tk

### `lashon: command not found`

The console script is not on `PATH`. Either activate the venv, or use
`python -m lashon.tooling.cli`. If you used `pip install --user`, add the
user scripts directory to `PATH`.

### `error: externally-managed-environment` (PEP 668)

Use a virtual environment, or `pip install --user --break-system-packages` if you
accept the trade-off. Prefer a venv.

### Studio opens then dies on a headless machine

`_tkinter.TclError: no display name and no $DISPLAY environment variable`
means there is no X display. Run on a desktop session, forward X11, or use the
headless controller (`LanguageStudio`) instead.

---

## Configuration problems

### `Unknown preset: ...`

`--preset` values are limited to:

`python_like`, `js_like`, `minimal`, `ruby_like`, `golang_like`, `rust_like`,
`clike`, `functional`, `lisp_like`, `basic_like`.

Run `lashon list-presets` to see them with descriptions.

### `Keyword '<x>' not found` / `Function '<x>' not found`

You asked to rename or remove a mapping that does not exist. Check the exact
source spelling:

```bash
lashon info my_lang.yaml
lashon export my_lang.yaml --format markdown
```

Keyword keys are the **source** names; values are the Python targets.

### A YAML key like `true:` or `yes:` behaves strangely

YAML 1.1 parses bare `true`, `false`, `yes`, `no`, `on`, `off` as booleans.
Lashon normalises boolean keys back to their string form (`True` →
`"true"`), but the safest fix is to quote them:

```yaml
keywords:
  "true": "True"
  "false": "False"
```

### `validate` reports errors but the file looks fine

`LanguageConfig.validate()` returns hard errors only; duplicate alias warnings
are separate. Run:

```bash
lashon validate my_lang.yaml
```

and read the first error — later errors are often cascades. Common causes: an
empty `original` keyword, a duplicate alias, or an operator entry missing one
side.

### Unknown top-level fields are ignored

The loader normalises `metadata`/top-level fields and ignores unknown ones for
forward compatibility. Typos therefore do not fail loudly — validate after
editing, and check `lashon info` for what was actually loaded.

---

## Grammar problems

### `Invalid grammar line (expected 'rule <- pattern'): '...'`

A line in the grammar is not `name <- pattern`. Causes:

- A pattern continued on the next line without indentation cues. Keep each rule
  on one line, or end the previous line with a trailing operator.
- `=` used somewhere other than after the rule name.
- A stray comment marker inside a literal.

### `Unclosed group in grammar pattern`

Parentheses do not balance. Count `(` and `)` in the rule — character classes
`[...]` and literals `"..."` may contain parentheses that must be balanced too.

### `Unterminated string literal` / `Unterminated character class`

A literal or class is missing its closing `"`, `'`, or `]`. Escapes inside
literals are passed through raw; a trailing backslash escapes the closing quote.

### `Invalid grammar rule 'x': unexpected '...' in pattern`

Trailing junk after a complete pattern, e.g. `expr <- term +`. Add the operand,
or remove the operator. Strict parsing replaced silent truncation on purpose.

### `Rule 'x' is left-recursive (not allowed in PEG)`

PEG cannot handle direct left recursion:

```peg
expr <- expr "+" term / term     # rejected
```

Rewrite it iteratively:

```peg
expr <- term ("+" term)*
```

Indirect recursion through several rules is also detected.

### `Rule 'x' references undefined rule 'y'`

A rule reference has a typo or the rule was removed. `grammar.validate()`
reports every undefined reference at once. Note that built-in tokens
(`NUMBER`, `IDENT`, `STRING`, `INDENT`, `DEDENT`, ...) are allowed without
definitions; unknown ALL-CAPS names produce
`references unsupported token`.

### `Parse error at line L, column C (in rule 'r'): unexpected '...'`

The message points at the **furthest position reached**, which is usually where
the real problem is, not where the parser gave up. Check the rule it names and
the 30 characters shown.

### `Unexpected input at line L, column C: '...'`

The start rule matched a prefix but not everything. Common causes:

- Missing statement terminator (`;`) that the grammar requires.
- A statement rule that does not include a newly added construct.
- Trailing tokens after the last statement.

### The parser hangs or spins

Zero-width comment patterns used to loop forever; the matcher now requires
`m.end() > 0`. If you still see a hang, check for a pattern that can match empty
text (for example `.*` inside a rule used with `*`), and simplify the grammar.
`re.error` in a comment pattern raises
`Invalid comment pattern '...': ...`.

### `INDENT`/`DEDENT` validation errors

These tokens are recognised but not supported by the interpreter. Use braces,
`end` keywords, or explicit terminators instead of layout-sensitive rules.

### Semantic actions `{ ... }` are rejected

Lashon does not execute grammar actions. Put semantics in the backend or
post-process the AST yourself.

---

## Transpiler and runtime problems

### Generated Python raises `SyntaxError`

Print the generated code to see what the transpiler produced:

```python
print(PythonTranspiler().translate_source_ast(ast))
```

Typical causes:

- A grammar rule name that collides with a Python keyword (`class`, `lambda`)
  without a `keyword_map` entry.
- Punctuation included in expressions because the grammar emits it as a
  non-structural operator (for example `->`).
- A `print` rule with multiple arguments where the grammar nests them
  differently than expected.

### `exec` result is empty or missing variables

`transpile_and_exec` returns only non-dunder names. If your program assigns
nothing, the dict is empty. Also note that assignments inside functions are
local to those functions.

### Variables disappear between REPL lines

The PEG REPL keeps a namespace, but `:reset` clears it. The config REPL clears
on `.clear`. If a line fails to parse, the previous namespace is kept.

### A custom keyword still executes as Python

Config REPL translation is textual and ordered; a keyword that is also valid
Python may shadow a mapping if it appears in an unexpected position. Use
`.debug` to print the translated line before execution.

### `NameError` for a builtin in the REPL

`StdLib` is opt-in for embedding:

```python
stdlib = StdLib(); stdlib.register_builtins(); stdlib.inject(namespace)
```

The config REPL (`lashon repl config.yaml`) runs with a restricted
`SAFE_BUILTINS` set — `abs`, `all`, `any`, `bool`, `enumerate`, `filter`,
`float`, `int`, `len`, `list`, `map`, `max`, `min`, `print`, `range`, `round`,
`sorted`, `str`, `sum`, `tuple`, `zip`, plus `pi` and `e` — not the full
`StdLib` modules and not `open`/`input`. The PEG REPL uses the plain Python namespace plus whatever you inject.

---

## Backend problems

### C output does not compile

- Ensure `gcc -std=c99` (or newer).
- Unknown identifiers default to `int`; declare them first.
- Strings are emitted verbatim — escape quotes and newlines in your grammar if
  the source can contain them.
- `%d` is used for expressions and `%s` for literals; printing a `double`
  prints as an integer (documented limitation).
- Functions are emitted as `int name(int param)`; there are no pointers,
  structs, or arrays.

### C program loops forever

Likely a loop variable that is never updated, or a `while` condition using a
value the body does not change. Inspect the generated C (the Studio C pane or
`lashon codegen-c`), since indentation there is cosmetic and can hide a
dropped statement.

### LLVM IR fails to verify

- `warning: overriding the module target triple` is harmless.
- `; WARNING: undefined variable 'x'` in the output means the identifier was
  never assigned/declared; it is replaced with `0`, which can produce invalid
  arithmetic in unusual positions.
- Calls to external functions need a `declare`; only `printf` is declared
  automatically.
- Values are `i32` unless the literal is a float; mixed float/int arithmetic is
  not promoted.

Run `opt -passes=verify` or `llc` to see the precise error.

### WASM output fails validation or cannot find a function

Calling a function that is not defined in the same source raises
`ValueError("WASM backend cannot resolve function ...")`; define it locally or
extend the backend with imports. Float values are truncated to `i32`. String
printing requires the host to provide `console.__log_str` and export/read
memory.

### `translate_source_ast` returns an object, not a string (WASM)

`WasmGenerator` returns `WasmModule`; call `.to_wat()` (or `.save(path)`) to get
text. The other three backends return strings.

---

## Studio problems

### The Studio starts but shows an empty project

On startup the Studio loads the Aurora sample if it can find it. If not, use
**Samples → Open Aurora Reference Project** (or the **Aurora sample** toolbar
button, or `LanguageStudio().open_sample_project()`). A new project starts from
the starter rules in `ide/studio.py`; the Grammar tab shows the generated PEG.

### Saving fails with `Grammar validation failed: ...`

`StudioProject.save()` validates the grammar before writing. Fix the listed
grammar errors (see [Grammar problems](#grammar-problems)); nothing is written
when validation fails.

### Edits to `language.yaml` are overwritten

Saving from the Studio writes `grammar.peg` **and** replaces
`language.yaml`'s `grammar.rules` with the editor content. Edit the grammar in
one place — preferably the Studio's Grammar tab — and keep hand edits to the
YAML outside `grammar.rules`.

### Run does nothing / console stays empty

- Check the Console tab for `StudioResult.error`.
- Programs need a `print`-style statement to produce output; assignments only
  populate the Variables pane.
- If the grammar has no start rule named `program`, set `grammar.start` in the
  YAML.

### Syntax highlighting looks wrong

Highlighting is regex-based. A keyword that is a prefix of an identifier
(`if`/`iffy`) is handled, but unusual delimiters can confuse it. It has no
effect on parsing.

---

## Tooling problems

### LSP client connects but gets no diagnostics

Check that the client sends `textDocument/didOpen` first: diagnostics are
published from open/change notifications, and hover/symbol/format requests need
an open document. The stdio loop serves initialize/shutdown, document
open/change/close, completion, hover, symbols, formatting, and signature help;
rename/extract/inline are still Python-API only.

### `lsp --port` exits immediately

Socket transport is not implemented and exits with code 2. Use `--stdio`.

### Breakpoints never fire in `debug-launch`

- Launch with `--config` (or `--grammar`) so the source can be parsed; otherwise
  the server reports a debuggee error.
- Breakpoint lines are language source lines (1-based), not generated Python
  lines.
- The adapter serves one client on the selected port; confirm the editor points
  at `tcp://127.0.0.1:<port>` and sends `setBreakpoints` before
  `configurationDone`.
- Only line breakpoints are implemented (no conditions/hit counts).

### `Debugger` breakpoint conditions never fire

- Register variables on `debugger.current_frame`; conditions are evaluated
  against that frame's variables.
- Conditions use the safe evaluator (no calls); invalid conditions set
  `verified=False`.

### `refactor-rename` finds no occurrences

`build_symbol_table` runs first, so the old name must appear as an identifier in
the file. Names inside strings/comments are not renamed.

### `format` changes nothing

The formatter only normalises indentation/whitespace. It does not reflow lines
or rename anything.

---

## Type checker problems

### Everything is "unknown"

The checker is line-oriented and only understands:

- `name: type = value` annotations
- plain `name = value` with literal/registered-signature sources

Function bodies, multi-line expressions, and calls to unknown functions produce
`unknown`. See [TYPE_SYSTEM.md](TYPE_SYSTEM.md).

### False "Type mismatch" on numbers

`int` and `float` are compatible in both directions, so numeric mismatches
should not appear. If they do, check that the annotation is spelled as a known
type name (`int`, `float`, `str`, `bool`, `list`, `dict`, `tuple`, `set`,
`any`).

### `generics` reports nothing or misses violations

The CLI scanner only understands declaration syntax (`class Box[T]`,
`def identity[T]`) and instantiation arity. It does not parse the language's own
grammar. Use `GenericChecker`/`GenericsTypeChecker` for programmatic checks.

### `check-protocol` exits 2

Protocol conformance is not wired to the CLI; it needs a language-specific type
model. Use `ProtocolChecker.register_protocol` /
`conforms_to_protocol` directly.

---

## Performance

| Symptom | Likely cause | Fix |
|---|---|---|
| Parse is slow on big files | packrat memo table grows with input | reuse one interpreter, clear between documents (`parse` does), or use `IncrementalParser` |
| Re-parse after every keystroke is slow | full re-parse on each edit | `IncrementalParser.apply_edit` re-parses regions; check `stats["incremental"]` |
| Large grammar validate is slow | left-recursion check is per rule | it is bounded by rule count; cache the compiled `Grammar` |
| Studio feels sluggish | regenerating all four backends | use `generate(target)` for one backend |

`IncrementalParser.stats` reports `total_parses`, `incremental`, `full_reparse`,
and `last_parse_ms` — use it to confirm the fast path is actually taken.

---

## FAQ

**Can Lashon parse Python/C/JavaScript?** Not as shipped. The grammar engine
is general, but you would need to write (or generate) the grammar; PEG cannot
handle left recursion, so expression grammars must be written iteratively.

**Do I need a grammar to use a language config?** No. Keyword/function/operator
mapping works without `grammar.rules` (config REPL, `translate`, `batch`). Code
generation and the PEG REPL do need a grammar.

**Are the backends equivalent?** Python is the reference. C and LLVM execute the
documented node set. WASM is integer-only (see above). None implement full language
semantics beyond what the AST encodes — your grammar decides what exists.

**Is there a sandbox?** No. Generated code runs with full Python privileges; FFI
calls native code. See
[RUNTIME_GUIDE.md](RUNTIME_GUIDE.md#security-model).

**Why 456 tests?** The suite covers each layer plus regressions for issues found
during review. Run `python -m pytest -q`; all should pass.

**Where do I report bugs?** Open an issue at
`https://github.com/James-HoneyBadger/LashonStudioStudio/issues` with the grammar, a
minimal source file, the command, and the full message.

---

## See also

- [INSTALL.md](INSTALL.md) — supported versions and platform notes.
- [GRAMMAR_REFERENCE.md](GRAMMAR_REFERENCE.md) — precise grammar semantics.
- [CLI_REFERENCE.md](CLI_REFERENCE.md) — flags and command status.
- [STUDIO_GUIDE.md](STUDIO_GUIDE.md) — Studio workflow.
