# Architecture

ParserCraft is a Python framework for defining languages with PEG grammars,
parsing source into an AST, and generating output for several targets. This
page describes how the pieces fit together so you can extend them safely.

Version 4.0.0, ~20,800 lines of library code, 322 tests.

---

## Pipeline

```
language.yaml / grammar.peg
        │
        ├── LanguageConfig ──────────────► config-driven runtime
        │        (keywords, functions, operators, syntax options)
        │
        └── GrammarParser ──► Grammar (rules of PEGNode)
                                  │
source text ──────────────────────┤
                                  ▼
                          PEGInterpreter
                          (packrat matching, memoised)
                                  │
                                  ▼
                             SourceAST
                                  │
        ┌─────────────┬───────────┼───────────┬─────────────┐
        ▼             ▼           ▼           ▼             ▼
   PythonTranspiler  CCode      Wasm       LLVM IR      your backend
        │          Generator   Generator   Generator
        ▼
   exec() → namespace / stdout
```

Two paths share the AST: **PEG** (grammar → AST → backend) and **config**
(keyword translation → Python). The Studio and CLI use both; backends only need
the PEG path.

---

## Package map

| Path | Responsibility |
|---|---|
| `config/language_config.py` | `LanguageConfig` model, YAML/JSON loading, normalization, `validate()`, `validation_warnings()` |
| `config/language_validator.py` | schema/identifier validation helpers |
| `config/identifier_validator.py` | identifier rules per language style |
| `config/visual_config_editor.py` | Tkinter keyword/function editor (used from the legacy IDE) |
| `parser/grammar.py` | `GrammarParser`, `Grammar`, `GrammarRule`, `PEGNode`, `PEGInterpreter`, `grammar_from_config`, default grammar |
| `parser/incremental.py` | `IncrementalParser` — region-based re-parse with full-parse fallback |
| `parser/parser_generator.py` | tokenizer/parser scaffolding generation |
| `parser/ast_integration.py` | adapters that feed ASTs to the C/WASM generators |
| `codegen/common.py` | Shared AST traversal (`meaningful_children`, `split_chain`, `inline_assignment`, operator sets) |
| `codegen/python_transpiler.py` | `PythonTranspiler`, `TranspileOptions`, `transpile_to_python`, `transpile_and_exec` |
| `codegen/codegen_c.py` | `CCodeGenerator` (AST → C) |
| `codegen/codegen_wasm.py` | `WasmGenerator`, `WasmModule`, WAT serialization |
| `codegen/llvm_ir.py` | `LLVMIRGenerator` (AST → SSA IR text) |
| `runtime/repl.py` | PEG REPL (`REPL`), `parsercraft-repl` entry point |
| `runtime/language_runtime.py` | `LanguageRuntime` singleton, keyword/function mapping, feature flags |
| `runtime/stdlib.py` | `StdLib`, `StdModule`, builtins and module tables |
| `runtime/ffi.py` | `FFIBridge` (ctypes + Python bindings) |
| `runtime/module_system.py` | `ModuleManager`, import/export parsing, dependency graph |
| `runtime/interpreter_generator.py` | packages an interpreter for CodeEx |
| `tooling/cli.py` | `main()`, every `parsercraft` subcommand, config-driven REPL |
| `tooling/commands/codegen.py` | `codegen-c/wasm/llvm` implementations |
| `tooling/lsp/lsp_server.py` | `LSPServer`, `DocumentManager`, stdio loop |
| `tooling/lsp/lsp_advanced.py` | refactoring, formatting, semantic highlighting |
| `tooling/lsp/lsp_integration.py` | feature integration layer |
| `tooling/debug/debug_adapter.py` | `Debugger`, `DebugAdapter`, safe expression evaluator |
| `tooling/error_localization.py` | `ErrorLocalizer` and the English catalog |
| `tooling/test_framework.py` | `LanguageTestRunner` and test case model |
| `types/type_system.py` | `Type`, `TypeKind`, `TypeEnvironment`, `TypeChecker` |
| `types/type_system_generics.py` | `GenericChecker`, `GenericsTypeChecker`, `TypeNarrowingPass`, `Variance` |
| `types/generics.py` | generic type/parameter models |
| `types/protocols.py` | `Protocol`, `StructuralType`, `ProtocolChecker` |
| `types/protocol_type_integration.py` | protocol bridging into the checker |
| `packaging/vscode_integration.py` | VS Code extension generation |
| `packaging/documentation_generator.py` | Markdown/HTML language reference |
| `packaging/package_registry.py` | `Package`, `Version`, `VersionConstraint`, `PackageRegistry` |
| `ide/studio.py` | headless `LanguageStudio`, `StudioProject` |
| `ide/studio_app.py` | Tkinter Studio UI |
| `ide/app.py` | compatibility shim (`ParserCraftIDE`) |
| `ide/editor.py`, `ide/project.py` | editor widget and project files |

---

## Grammar internals

### Grammar parsing

`GrammarParser.parse(text)` reads `rule <- pattern` definitions (also accepts
`=`), supports comments (`#`, `//`), and builds `PEGNode` trees with node types
`SEQUENCE`, `ORDERED_CHOICE`, `ZERO_OR_MORE`, `ONE_OR_MORE`, `OPTIONAL`,
`AND_PREDICATE`, `NOT_PREDICATE`, `LITERAL`, `CHAR_CLASS`, `ANY_CHAR`,
`RULE_REF`, `TOKEN_REF`, `ACTION`.

The parser is strict: trailing junk, unclosed groups, and unterminated literals
raise `ValueError`/`SyntaxError` rather than silently truncating. Semantic
actions (`{ ... }`) are rejected.

### Matching

`PEGInterpreter` holds:

- `source`, `line_starts` for position → line/column conversion
- `memo: {(rule_name, pos): ParseResult}` for packrat memoisation
- `max_pos`, `max_rule` to produce "furthest failure" messages

`_match_rule(name, pos)` skips ignored text (`skip_whitespace`, comment
patterns) unless the rule is a built-in token, consults the memo, matches the
pattern, and — for non-fragment rules — builds a `SourceAST`:

- a single child result becomes `children=[child]`
- a scalar becomes `value`
- raw strings become `Operator` child nodes
- fragments splice their children into the parent

`parse()` requires the whole input to be consumed (trailing whitespace aside) and
reports `Unexpected input at line L, column C`. `parse_rule()` parses a single
rule at offset 0; `IncrementalParser` uses it for region re-parsing and records
whether each edit was incremental or fell back.

### AST shape

`SourceAST` fields: `node_type`, `value`, `children`, `line`, `column`,
`source_text`. Rule nodes use `rule.node_type or rule.name`, which is why a rule
named `expr` yields `node_type == "expr"` unless overridden with
`node_type=...` in a fragment.

Positions are 1-based.

---

## Backend dispatch

All backends expose `translate_source_ast(ast)`. They dispatch on
`node.node_type` with aliases (`expression`/`Expr`, `function_def`/`FunctionDef`,
...). The practical contract:

1. Walk `children` in order.
2. Skip structural `Operator` tokens (`;`, `,`, braces, parens) unless the
   operator is meaningful.
3. Handle inline assignments in `statement` nodes.
4. Keep a notion of declaration/definition rather than re-declaring on every
   assignment.

C and LLVM share `codegen/common.py` for child filtering and operator-chain
splitting; new backends should use it instead of copying structural-operator
sets.

See [CODEGEN_GUIDE.md](CODEGEN_GUIDE.md) for per-backend node coverage and known
gaps (notably WASM).

---

## Studio architecture

The GUI is split so that everything except rendering is testable headlessly:

```
studio_app.py (Tkinter view)  ──calls──►  studio.py (LanguageStudio)
                                             │
                                             ├── GrammarParser / PEGInterpreter
                                             ├── PythonTranspiler / transpile_and_exec
                                             ├── CCodeGenerator / WasmGenerator / LLVMIRGenerator
                                             └── StudioProject (language.yaml + grammar.peg + samples/)
```

- `LanguageStudio.validate_grammar()`, `.parse()`, `.run()`, `.transpile()`,
  `.generate()`, and `.generate_all()` return `StudioResult` objects with
  `ok`, `text`, `error`, `diagnostics`, `elapsed_ms`, `value`, `supported`,
  and `warnings` (`generate_all()` returns a `{target: StudioResult}` dict).
  `supported=False` marks deliberately partial output such as WASM.
- `StudioProject.from_path()` and `.save()` read and write the project.
  `save()` parses and validates the grammar first, then writes `grammar.peg` and
  syncs its rules into `language.yaml` (raising `ValueError` if the grammar is
  invalid).
- `LanguageStudio.sample_project_path()` resolves the bundled Aurora project;
  `open_sample_project()` loads a copy.

The view layer owns tabs, highlighting, and keyboard shortcuts only. Tests in
`tests/test_studio.py` exercise the controller; `tests/test_studio_gui.py` checks
the widgets when a display is available.

---

## Error handling strategy

| Layer | Behaviour |
|---|---|
| Grammar parse | `SyntaxError`/`ValueError` with line/column and rule context |
| Interpreter | raises `SyntaxError` with furthest-failure position; stale ASTs are kept by `IncrementalParser` during edits |
| Transpiler | emits Python; runtime failures surface from `exec` |
| C/LLVM | unknown identifiers become warnings/`0` (LLVM) or ints (C) rather than hard failures |
| CLI | catches config/IO errors, prints a message, returns exit code 1 |
| Studio | converts failures into `StudioResult` diagnostics instead of tracebacks |
| Type checker | returns `TypeError` records; never raises for mismatches |

---

## Extension points

| Want to… | Do this |
|---|---|
| Add a backend | new class in `codegen/`, `translate_source_ast`, export in `codegen/__init__.py`, add CLI command |
| Add a CLI command | function in `tooling/cli.py`, register a subparser in `main()` |
| Add a stdlib module | build a `StdModule`, `stdlib.add_module(...)` |
| Bind native code | `FFIBridge.bind` / `register_python` |
| Add diagnostics | extend `ErrorLocalizer` catalog or `TypeChecker` |
| Customize grammar nodes | use fragments with `node_type=...` |
| Add sample projects | put a directory under `projects/` and mirror it into `parsercraft/ide/samples/` if it should ship |

---

## Testing strategy

- `tests/` covers grammar, transpiler, codegen, REPL, stdlib/FFI/errors,
  incremental parsing, integration, types, modules, LSP, packaging, IDE project,
  debug adapter, config validation, and the Studio.
- `pytest` uses `pythonpath = ["src"]`, so no install is required to run tests.
- Codegen tests include structural assertions plus compile/run checks where
  toolchains exist.
- Run `python -m pytest -q` and `ruff check src tests` before committing.

---

## See also

- [LANGUAGE_DEVELOPMENT.md](LANGUAGE_DEVELOPMENT.md) — designing a language.
- [CODEGEN_GUIDE.md](CODEGEN_GUIDE.md) — backend details.
- [STUDIO_GUIDE.md](STUDIO_GUIDE.md) — the Studio from a user's perspective.
- [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md) — API signatures.
