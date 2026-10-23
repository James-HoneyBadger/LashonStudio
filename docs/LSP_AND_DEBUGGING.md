# LSP and Debugging

ParserCraft includes a language server (completions, hover, symbols,
formatting), refactoring/formatting engines, a Debug Adapter Protocol handler,
and a localized error catalog. This page documents what each piece actually
does, including the gaps.

---

## Language server

### Starting it

```bash
parsercraft lsp --config my_lang.yaml --stdio
```

| Flag | Meaning |
|---|---|
| `--config`, `-c` | language config file (required) |
| `--port`, `-p` | socket port (default 8080) |
| `--stdio` | use stdin/stdout JSON-RPC |

**Transport status:** `--stdio` is implemented via `LSPServer.run_stdio()`. The
`--port` socket mode is accepted but **not implemented**; the process exits
without serving.

### Protocol coverage

`run_stdio` implements a JSON-RPC loop for:

- `initialize`, `initialized`, `shutdown`, `exit`
- `textDocument/didOpen`, `didChange`, `didClose` (each publishes
  `textDocument/publishDiagnostics`)
- `textDocument/completion`, `hover`, `documentSymbol`, `formatting`,
  `signatureHelp`

Unknown requests receive a JSON-RPC `-32601` error; unknown notifications are
ignored. The analysis functions below are also callable directly, which is how
the Studio and tests use them.

| Capability | API | Status |
|---|---|---|
| initialize | `initialize(root_path=None)` → server capabilities dict | ✅ |
| didOpen | `handle_did_open(uri, content)` | ✅ |
| didChange | `handle_did_change(uri, changes, version)` | ✅ |
| didClose | `handle_did_close(uri)` | ✅ |
| completion | `completions(uri, position)` → `list[dict]` | ✅ |
| hover | `hover(uri, position)` → `dict \| None` | ✅ |
| signature help | `signature_help(uri, position)` | ✅ |
| document symbols | `document_symbols(uri)` | ✅ |
| formatting | `format_document(uri)` → `list[dict]` | ✅ |
| diagnostics | `diagnostics(uri)` + publish notifications | ✅ |
| rename/extract/inline | `RefactoringEngine` (not wired to stdio) | programmatic only |
| semantic highlighting | `SemanticHighlighter` | programmatic only |

### Programmatic use

```python
from parsercraft.config import LanguageConfig
from parsercraft.tooling.lsp import LSPServer
from parsercraft.tooling.lsp.lsp_server import Position

server = LSPServer(LanguageConfig.load("my_lang.yaml"))
server.initialize(root_path=".")

uri = "file:///program.src"
server.handle_did_open(uri, 'x = 1 ;\nprint x ;\n')

items = server.completions(uri, Position(line=1, character=6))
print([item["label"] for item in items])

info = server.hover(uri, Position(line=0, character=0))   # word at cursor
symbols = server.document_symbols(uri)
edits = server.format_document(uri)

server.handle_did_change(uri, [{"text": 'x = 2 ;\n'}], version=2)
server.handle_did_close(uri)
```

Behaviour notes:

- `hover` resolves the **word at the cursor** (not just the character under it)
  and returns `None` outside a word or for negative/out-of-range positions.
- Positions are zero-based LSP offsets; ParserCraft AST positions are 1-based,
  so conversions happen inside the server.
- Completions draw from keywords, functions, and operators in the loaded config.

### Refactoring engine

```python
from parsercraft.tooling.lsp.lsp_advanced import RefactoringEngine, CodeFormatter

refactor = RefactoringEngine()
refactor.build_symbol_table(source)
edits = refactor.rename("old", "new", source)          # list[TextEdit]
edits = refactor.extract_function(source, "name", ["a"], 3, 7)
edits = refactor.extract_variable(source, 4, 2, 4, 9, "value")
edits = refactor.inline_variable(source, "value", 5)
actions = refactor.generate_code_actions(diagnostics)
```

`TextEdit` carries `line`, `start_col`, `end_col`, and `new_text`; apply edits
from the end of the file backwards so offsets stay valid. The CLI
`refactor-rename` command applies them for you.

### Formatter

```python
from parsercraft.tooling.lsp.lsp_advanced import CodeFormatter

CodeFormatter(tab_size=4).format(source)
```

The formatter normalises indentation and whitespace only; it is not a full
pretty-printer. `parsercraft format` exposes it on the command line.

### Semantic highlighting

`SemanticHighlighter` maps words to `SemanticToken`s with `TokenType` and
`TokenModifier` values. It is used by the Studio's editor and available for
editor integrations, but is not advertised over stdio.

---

## Debug adapter

`Debugger` models breakpoints, frames, variables, and stepping. It is a
**controller**, not a process launcher: you tell it when the program hits a
line, and it evaluates conditions against the frame values you register.

```python
from parsercraft.tooling.debug import Debugger
from parsercraft.tooling.debug.debug_adapter import Variable

debugger = Debugger("program.src")
debugger.start()                                  # state = RUNNING, current_frame = 0

frame = debugger.current_frame
debugger.add_variable(frame, Variable("i", 3, "int"))

bp = debugger.set_breakpoint("program.src", line=4, condition="i > 2")
hit = debugger.hit_breakpoint("program.src", 4)   # Breakpoint or None

print(debugger.get_stack_trace())                 # frames you append yourself
print(debugger.get_variables(frame))              # [Variable(name='i', value=3, ...)]
print(debugger.evaluate_expression("i + 1", frame))   # '4'
print(debugger.evaluate_expression("__import__('os')", frame))   # None

debugger.step_over()
debugger.pause()
debugger.continue_execution()
debugger.remove_breakpoint(bp.id)
```

Conditions evaluate against the variables registered for `current_frame`.
Register values on that frame (not an arbitrary id) or conditions will not see
them.

### Breakpoints

`Breakpoint` fields: `id`, `source_path`, `line`, `column`, `condition`,
`hit_condition`, `log_message`, `verified`, `message`.

- `condition` is evaluated with a **safe AST evaluator** when the line is hit.
- If a condition raises or is invalid, the breakpoint is marked
  `verified=False` with `message="Invalid condition: ..."` and skipped.
- `hit_condition` and `log_message` are stored for adapter use; they are not
  interpreted by `hit_breakpoint`.

### Safe expression evaluation

`evaluate_expression` parses the expression and evaluates only:

- literals, names, boolean operators, comparisons, unary/binary arithmetic
- list/tuple/dict/set literals, subscripts

Calls, attribute access, comprehensions, lambdas, and assignments are rejected.
Failures return `None` rather than raising.

### Debug Adapter Protocol handler

```python
from parsercraft.tooling.debug import DebugAdapter

adapter = DebugAdapter(debugger)
```

`DebugAdapter` translates DAP-shaped requests/responses on top of `Debugger`.
The `parsercraft debug-launch` command exits 2 with guidance: it does **not**
open a DAP socket or execute the program. To debug a real run, drive `Debugger`
from your own runner (or the generated Python) and call `hit_breakpoint` at each
line.

### Verified behaviour

- Breakpoint conditions use the same whitelist as `evaluate_expression`.
- A condition such as `i > 2` is evaluated against the current frame's
  variables; a malformed condition disables the breakpoint instead of raising.
- Stepping methods update the debugger state but do not advance a program by
  themselves.

---

## Localized errors

`ErrorLocalizer` formats catalogued diagnostics with optional source context.

```python
from parsercraft.tooling import ErrorLocalizer

localizer = ErrorLocalizer()                 # locale="en"
localizer.format("E001", got=";", expected=")")

localizer.format_with_context(
    "E001", source="print (1 + ;", line=1, col=14, filename="program.src",
    got=";", expected=")",
)
```

Output:

```
error[E001]: Unexpected token ';', expected ')'
 --> program.src:1:14
     |
   1 | print (1 + ;
                    ^ here
```

The caret line is fixed-width (it does not yet align under the exact column);
use `line`/`col` in the header for precise navigation.

### Behaviour

- `format(code, **kwargs)` fills `{placeholders}` from the catalog. If a
  placeholder is missing, the **raw template** is returned (no exception).
- Unknown codes return `[CODE]`.
- `format_with_context` adds the `error[CODE]:` prefix, file/line/column, and a
  caret line; it also prefixes the severity.
- `register_error(code, severity, template, category="custom")` adds entries at
  runtime.
- `load_translations(dict, locale=None)` and `load_translations_file(...)`
  register locale strings; `set_locale(...)` switches.
- Only `en` ships. `ErrorLocalizer("es")` falls back to the English catalog.
- `list_codes()` and `get_severity(code)` expose the catalog.

### Catalog

| Code | Severity | Template |
|---|---|---|
| `E001` | error | Unexpected token '{got}', expected '{expected}' |
| `E002` | error | Unterminated string literal |
| `E003` | error | Invalid number format: '{text}' |
| `E004` | error | Unexpected end of input |
| `E005` | error | Mismatched bracket: '{bracket}' |
| `E010` | error | Undefined variable: '{name}' |
| `E011` | error | Variable '{name}' already defined |
| `E012` | error | Cannot assign to '{name}' |
| `E013` | error | Undefined function: '{name}' |
| `E014` | error | Module '{name}' not found |
| `E020` | error | Type mismatch: expected '{expected}', got '{got}' |
| `E021` | error | Cannot apply operator '{op}' to types '{left}' and '{right}' |
| `E022` | error | Wrong number of arguments: expected {expected}, got {got} |
| `E023` | error | Cannot convert '{from_type}' to '{to_type}' |
| `E030` | error | Grammar rule '{rule}' is undefined |
| `E031` | error | Left recursion detected in rule '{rule}' |
| `E032` | error | Duplicate rule definition: '{rule}' |
| `W001` | warning | Variable '{name}' defined but never used |
| `W002` | warning | Unreachable code after return statement |
| `W003` | warning | Shadowing variable '{name}' from outer scope |
| `W004` | warning | Division by zero |
| `H001` | hint | Did you mean '{suggestion}'? |
| `H002` | hint | Consider using '{alternative}' instead |

---

## Wiring a real editor

1. Start `parsercraft lsp --config lang.yaml --stdio` from your extension and
   complete the `initialize` handshake.
2. For capabilities not yet served over stdio, run a small Python bridge (call
   `LSPServer` directly and forward results) or use the programmatic API from
   your extension's Node/Python host.
3. Generate a TextMate grammar and language configuration with
   `parsercraft extension --config lang.yaml`; see
   [PACKAGING.md](PACKAGING.md#vs-code-extension).
4. Surface `TypeChecker` results as diagnostics (see
   [TYPE_SYSTEM.md](TYPE_SYSTEM.md)).
5. Use `ErrorLocalizer` for message text so codes stay stable across locales.

---

## See also

- [CLI_REFERENCE.md](CLI_REFERENCE.md#editor-and-developer-tooling) — `lsp`,
  `format`, `refactor-rename`, `debug-launch`.
- [STUDIO_GUIDE.md](STUDIO_GUIDE.md) — the Studio reuses these analyzers.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — LSP handshake problems.
