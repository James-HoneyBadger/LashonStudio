# Lashon Studio Guide

Lashon Studio is the graphical language-design workbench. It wraps the
headless `LanguageStudio` (`src/lashon/ide/studio.py`) controller in a
Tkinter shell.

```bash
lashon-ide                      # opens the bundled Aurora project
lashon-ide projects/aurora      # open a project directory
lashon-ide path/to/language.yaml prog.aur
```

Requires `tkinter` (bundled with most CPython builds) **and a graphical
display** — an X11/Wayland session on Linux, Aqua on macOS, or the Win32
desktop. Without a display `lashon-ide` exits with a message pointing at the
headless equivalents instead of raising a Tcl traceback:

```
Lashon Studio needs a graphical display (X11/Wayland on Linux,
Aqua on macOS, Win32 on Windows) and a Python build with tkinter.

Headless alternatives with the same engine:
  lashon run <file> --config <language.yaml>   run a program
  lashon validate <language.yaml>              check a language
  lashon lsp --config <language.yaml> --stdio  editor integration
  lashon-rs run <grammar.peg> <program>        native, no Python
```

On a headless server use those commands, the `LanguageStudio` controller
(`src/lashon/ide/studio.py`), or forward a display (`ssh -X`).

---

## Themes

The workbench is styled like a CRT-era machine: near-black background, one
bright phosphor accent, dim phosphor for secondary text, monospace for code.
Three palettes ship — pick one at startup:

```bash
lashon-ide projects/aurora                  # green phosphor (default)
lashon-ide projects/aurora --theme amber
lashon-ide projects/aurora --theme dark     # neutral, for long sessions
```

`LASHON_THEME=amber` does the same from the environment, and **View → Theme**
switches live: the choice is saved to `~/.config/lashon/studio.json` (or
`$XDG_CONFIG_HOME/lashon/studio.json`) and the Studio restarts into it with the
current project and saved documents. Precedence is
`--theme` → `LASHON_THEME` → saved preference → green.

The palette drives everything the window paints — editors, gutter, syntax
colours, tree selections, menus, buttons — so a theme switch is a global
change, not a coat of paint on one panel:

| Element | Treatment |
|---|---|
| Banner | Uppercase `◆ LASHON STUDIO` with a faint phosphor shadow, monospace subtitle |
| Section headers | Box-drawn rules: `── PIPELINE ─────────────` |
| Editors | Tube-black background, accent keywords, amber literals, dim comments, phosphor caret |
| Console | Timestamped boot banner (`LASHON STUDIO 5.0.0 · CRT SERIES`) then `READY.` |
| Status bar | Current state on the left, live clock on the right |

The window sizes itself to the display (up to 1440×900, never taller than the
screen) and keeps a minimum output pane of 150 px, so the console stays usable
on a small laptop screen.

## 1. Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ ◆ LASHON STUDIO                design a grammar · parse · run …     │
│ [＋ New] [⌂ Open] [▣ Save] │ [✓ Validate] [◈ Parse] [▶ Run] [⇩ Gen] │
├──────────────┬──────────────────────────────────────────────────────┤
│ ── PROJECT ─ │  Source │ grammar.peg │ language.yaml                 │
│ ◆ Aurora     │                                                      │
│  ⚙ lang.yaml │        syntax-highlighted editors                    │
│  λ grammar   │                                                      │
│  ▸ samples   ├──────────────────────────────────────────────────────┤
│   • hello    │  Console │ Variables │ Python │ C │ WASM │ LLVM │ AST │
│   • fibonacci│                                                      │
│   • fizzbuzz │  Console │ Variables │ … │ Problems │ AST            │
│ ── PIPELINE  │        output / tree views / problem list            │
│ ✓ Grammar    │                                                      │
│ ○ Parse      │                                                      │
│ ○ Run        │                                                      │
├──────────────┴──────────────────────────────────────────────────────┤
│ Grammar OK — 3.2 ms               rules 18 · samples 3 · Ln 4 · 20:30│
└─────────────────────────────────────────────────────────────────────┘
```

| Pane | Purpose |
|---|---|
| **Project tree** | Language config, grammar, and every sample program |
| **Source editor** | Programs in your language |
| **Grammar editor** | PEG rules; validation runs 800 ms after typing stops |
| **Language editor** | YAML: metadata, keywords, operators, syntax options |
| **Console** | Timestamped output, timings, errors, backend summaries |
| **Canvas** | Live drawing surface: turtle statements paint here after every run |
| **Variables** | Namespace after a run |
| **Python / C / WASM / LLVM IR** | Generated output |
| **Pipeline** | Live status for Grammar → Parse → Run → Python/C/WASM/LLVM: `○` idle, `✓` passed, `✗` failed |
| **Problems** | Errors and warnings; double-click a row to jump to the code |
| **AST** | Expandable syntax tree |

### The Canvas tab

Anything the program draws lands on the **Canvas** tab, between Console and
Variables. The Studio repaints it after each run, switches to it when the
program actually drew something, and logs a summary such as
`canvas: 37 strokes, 89×77 units`. Text-only programs stay on the Console, and
an empty canvas shows a hint naming the statements that would fill it
(`FORWARD`, `LEFT`, `SETXY`, `CIRCLE`, `PENUP`, `CLS`…).

Drawing is a runtime feature, not a code-generation one, so it works for any
grammar that uses the turtle statement names. `projects/logo` is the worked
example; [GRAPHICS.md](GRAPHICS.md) documents the vocabulary and the export
formats (SVG, ASCII, JSON).

Failed parses and grammar validation open the **Problems** tab automatically.
The offending line is underlined in the editor with a red squiggle, and
selecting a problem moves the caret to its position in the right editor
(source or grammar).

---

## 2. First run

On startup the Studio tries to open the bundled Aurora project. You should see:

- title `Lashon Studio — Aurora`,
- `hello.aur` in the source tab,
- the project tree populated,
- `Grammar OK — 18 rules` in the status bar.

Press **F5**. The console shows:

```
[14:39:02] ▶ Running program…
[14:39:02] Hello, Aurora!
[14:39:02] Designed in Lashon Studio.
[14:39:02] Finished in 0.9 ms
```

The Python tab contains the transpiled program; the Variables tab shows the
namespace; the AST tab is populated.

---

## 3. Shortcuts

| Action | Keys |
|---|---|
| New project | `Ctrl+N` |
| Open project | `Ctrl+O` |
| Save project | `Ctrl+S` |
| Validate grammar | `Ctrl+Shift+V` |
| Parse + show AST | `F6` |
| Run program | `F5` |
| Generate all backends | `F7` |
| Undo / redo | `Ctrl+Z` / `Ctrl+Y` |
| Cut / copy / paste | `Ctrl+X` / `Ctrl+C` / `Ctrl+V` |
| Command palette | `Ctrl+Shift+P` |
| Quick open (project files) | `Ctrl+P` |
| Shortcut cheat sheet | `F1` |

The command palette lists every action with its accelerator and filters as you
type — press `Enter` to run the highlighted entry, `Esc` to dismiss. Quick open
filters the project's files the same way and loads the chosen sample.

---

## 4. Project format

A Studio project is a directory:

```
my-language/
├── language.yaml      # metadata, keywords, syntax options, grammar.rules
├── grammar.peg        # canonical editable grammar
├── samples/
│   ├── hello.my
│   └── demo.my
└── README.md
```

`language.yaml` is a normal Lashon language config, so the CLI can read it:

```yaml
name: Aurora
version: "1.0.0"
description: "A teaching language"
author: "You"

keywords:
  if: "if"
  while: "while"
  fn: "fn"
  print: "print"
  "true": "true"
  "false": "false"

syntax_options:
  single_line_comment: "//"
  require_semicolons: true

grammar:
  start: program
  skip_whitespace: true
  comments:
    - "//.*"
  rules:
    program: statement+
    statement: 'IDENT "=" expr ";"'
    expr: term (("+" / "-") term)*
    term: factor (("*" / "/") factor)*
    factor: NUMBER / IDENT / "(" expr ")"
```

### Save semantics

`Ctrl+S`:

1. parses the YAML editor into the project config,
2. parses and validates `grammar.peg`,
3. converts the grammar back into `grammar.rules` (one rule per line),
4. writes `language.yaml` and `grammar.peg`.

If the grammar is invalid, nothing is written and the error is shown in the
console. Saving is deliberately conservative: the CLI and Studio must agree.

---

## 5. Workflow

### Create a language

1. **New** → choose a parent directory → enter a name.
2. The Studio scaffolds a working starter language (functions, `if`, `while`,
   `print`, numbers, strings, booleans).
3. Edit `grammar.peg`.
4. Edit samples or write a program in the source tab.
5. **F5** to run.

### Open an existing config

**Open** chooses a directory; use **File → Open Language Config…** for a single
`.yaml`/`.json` file. Configs without a `grammar.peg` use `grammar.rules` from
YAML.

### Iterate on syntax

- Grammar edits trigger validation automatically. The status bar turns green
  (`Grammar OK`) or red (`Grammar error`).
- Parse errors appear in the console with rule and position.
- Use **F6** to inspect the AST when a backend output looks wrong.

### Generate targets

**F7** fills all four backend tabs. Failures are shown per tab as comments, and
the console lists which backends failed.

---

## 6. Headless controller

Everything the GUI does is available without Tkinter:

```python
from lashon.ide.studio import LanguageStudio

studio = LanguageStudio()
project = studio.open_project("projects/aurora")

print(project.summary())
# {'name': 'Aurora', 'version': '1.0.0', 'root': '...', 'rules': 18,
#  'keywords': 8, 'samples': 3}

result = studio.validate_grammar()
assert result.ok
print(result.text)          # Grammar OK — 18 rules

source = project.sample_path.read_text()
print(studio.run(source).text)

for backend, output in studio.generate_all(source).items():
    print(backend, output.ok, len(output.text))
```

### API summary

| Member | Returns |
|---|---|
| `open_project(path)` | `StudioProject` |
| `open_sample_project()` | bundled Aurora project |
| `new_project(name, parent)` | scaffolded `StudioProject` |
| `save_project()` | writes YAML + grammar, validates first |
| `validate_grammar(text=None)` | `StudioResult` (`value` = `Grammar`) |
| `parse(source=None)` | `StudioResult` (`value` = `SourceAST`) |
| `transpile(source=None)` | `StudioResult` (`value` = Python source) |
| `run(source=None)` | `StudioResult` (`value` = namespace) |
| `generate(backend, source=None)` | `StudioResult` (`value` = code) |
| `generate_all(source=None)` | `dict[str, StudioResult]` |
| `ast_tree(ast)` | nested dicts for a Treeview |
| `highlight_keywords()` | keyword list for editors |

`StudioResult` fields: `ok`, `text`, `error`, `diagnostics`, `elapsed_ms`,
`value`, `supported`, `warnings`. Failures are data, not exceptions.
`supported=False` marks deliberately partial output; all bundled backends
currently report `True`.

---

## 7. Language editor

The YAML editor is the source of truth for metadata and keywords. Changes are
applied when you validate, run, save, or generate. Useful fields:

| Field | Effect |
|---|---|
| `name`, `version`, `description`, `author` | project metadata |
| `keywords` | mapping of original → custom names (string shorthand supported) |
| `builtin_functions` / `functions` | built-in function metadata |
| `operators` | precedence/associativity for tooling |
| `syntax_options` | comments, terminators, indexing, feature toggles |
| `grammar.start` | start rule |
| `grammar.comments` | regex comment patterns |
| `grammar.skip_whitespace` | whitespace/comment policy |

Unknown keys are preserved in the file but ignored by the loader.

---

## 8. Keyword highlighting

The source editor highlights:

- keywords from `language.yaml` and literal keywords found in the grammar,
- strings, numbers, comments (`//`, `#`), and operators,
- function names before `(`,
- the grammar editor highlights `IDENT`, `NUMBER`, `STRING`, `NEWLINE`, `EOF`.

When keywords change, re-validate (`Ctrl+Shift+V`) to refresh highlighting.

---

## 9. Limitations

- One project per window; no multi-root workspace.
- Grammar validation is structural, not semantic.
- Backends are source emitters; the Studio does not invoke C/WASM/LLVM toolchains.
- Very large programs may slow the syntax highlighter; it re-tags the whole
  buffer on modification.
- The Studio is not a full IDE: no file rename, search across project, or
  version-control integration.
- GUI tests are skipped on machines without a display.

---

## 10. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Window does not open | `tkinter` missing or no display; use the CLI/controller |
| “Grammar invalid” after editing | fix the rule reported in the console |
| Save refuses | grammar must validate before writing |
| Generated C/WASM/LLVM looks sparse | the backends are minimal; inspect the AST and backend docs |
| Keywords not highlighted | re-validate after changing `language.yaml` |
| Sample will not run | check the console for the parse position and rule |

More: [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
