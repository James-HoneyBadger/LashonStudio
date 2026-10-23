# ParserCraft Studio Guide

ParserCraft Studio is the graphical language-design workbench. It wraps the
headless `LanguageStudio` (`src/parsercraft/ide/studio.py`) controller in a
Tkinter shell.

```bash
parsercraft-ide                      # opens the bundled Aurora project
parsercraft-ide projects/aurora      # open a project directory
parsercraft-ide path/to/language.yaml prog.aur
```

Requires `tkinter` (bundled with most CPython builds). On headless machines use
the `LanguageStudio` API or the CLI instead.

---

## 1. Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ ◆ ParserCraft Studio            Design a grammar · parse · run …     │
│ [＋ New] [⌂ Open] [▣ Save] │ [✓ Validate] [◈ Parse] [▶ Run] [⇩ Gen] │
├──────────────┬──────────────────────────────────────────────────────┤
│ PROJECT      │  Source │ grammar.peg │ language.yaml               │
│ ◆ Aurora     │                                                      │
│  ⚙ lang.yaml │        syntax-highlighted editors                    │
│  λ grammar   │                                                      │
│  ▸ samples   ├──────────────────────────────────────────────────────┤
│   • hello    │  Console │ Variables │ Python │ C │ WASM │ LLVM │ AST │
│   • fibonacci│                                                      │
│   • fizzbuzz │        output / tree views                           │
├──────────────┴──────────────────────────────────────────────────────┤
│ Grammar OK — 3.2 ms               rules 18 · samples 3 · Ln 4, Col 9│
└─────────────────────────────────────────────────────────────────────┘
```

| Pane | Purpose |
|---|---|
| **Project tree** | Language config, grammar, and every sample program |
| **Source editor** | Programs in your language |
| **Grammar editor** | PEG rules; validation runs 800 ms after typing stops |
| **Language editor** | YAML: metadata, keywords, operators, syntax options |
| **Console** | Timestamped output, timings, errors, backend summaries |
| **Variables** | Namespace after a run |
| **Python / C / WASM / LLVM IR** | Generated output |
| **AST** | Expandable syntax tree |

---

## 2. First run

On startup the Studio tries to open the bundled Aurora project. You should see:

- title `ParserCraft Studio — Aurora`,
- `hello.aur` in the source tab,
- the project tree populated,
- `Grammar OK — 18 rules` in the status bar.

Press **F5**. The console shows:

```
[14:39:02] ▶ Running program…
[14:39:02] Hello, Aurora!
[14:39:02] Designed in ParserCraft Studio.
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

`language.yaml` is a normal ParserCraft language config, so the CLI can read it:

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
from parsercraft.ide.studio import LanguageStudio

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
