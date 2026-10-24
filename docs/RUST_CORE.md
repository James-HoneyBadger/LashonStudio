# Rust core

ParserCraft's engine also exists as a Rust workspace. It is not a wrapper: the
grammar parser, the PEG engine, the four code generators, the evaluator, the
language server, and the debug adapter are all implemented in Rust and run
without a Python interpreter.

```bash
cargo build --workspace --release     # target/release/parsercraft-rs
parsercraft-rs run projects/basic/grammar.peg projects/basic/samples/fizzbuzz.bas
```

---

## Workspace layout

```
Cargo.toml                     workspace
crates/parsercraft-core/       grammar · engine · ast · eval · backends/{c,python,wasm,llvm}
crates/parsercraft-cli/        parsercraft-rs binary: commands, lsp, dap
```

`parsercraft-core` has no I/O dependencies. PyO3 bindings live behind the
optional `python` feature, so plain binaries link without `libpython`.

---

## What runs on Rust

| Capability | Entry point |
|---|---|
| Parse PEG text notation | `parse_peg_text` |
| Match source, build an AST | `parse_to_ast`, `parse_document` |
| Execute a program | `eval::run_program`, `parsercraft-rs run` |
| Emit C | `backends::c`, `parsercraft-rs codegen-c` |
| Emit Python | `backends::python`, `parsercraft-rs codegen-py` |
| Emit WebAssembly | `backends::wasm`, `parsercraft-rs codegen-wasm` |
| Emit LLVM IR | `backends::llvm`, `parsercraft-rs codegen-llvm` |
| Language server (stdio) | `parsercraft-rs lsp` |
| Debug adapter (stdio) | `parsercraft-rs dap` |
| Validate / lint / scaffold / demo | `parsercraft-rs validate`, `lint`, `init`, `demo` |

Still Python: language configs (YAML), the Tkinter Studio, editor packaging,
and the `config`/`format`/`package-*` CLI verbs.

---

## How the two engines stay honest

Two independent implementations can drift. Three mechanisms prevent it:

1. **Conformance corpus** — `tests/conformance/cases.json` records a grammar, a
   program, and the exact AST (or error position). Both engines must match it.
2. **Differential execution** — for every backend, the test suite compiles the
   generated artifact and compares its stdout with the reference pipeline:
   - C → `cc`, compared with the Python transpiler's output
   - Python → CPython, compared with the transpiler
   - WASM → wasmtime, compared with the Python generator
   - LLVM IR → `clang`, compared with the Python generator
   - Interpreter → compared with the Python transpiler
3. **Wire tests** — the LSP and DAP servers are driven over their real
   protocols by `tests/test_rust_cli.py`, including a breakpoint hit and a
   diagnostic position computed from the Python engine's own error message.

```bash
cargo test --workspace
python -m pytest tests/test_rust_cli.py tests/test_conformance.py -q
```

---

## Python bindings

The extension is optional. Build and install it, then the Python API can use
the Rust engine:

```bash
scripts/build_native.sh
```

```python
from parsercraft.parser import PEGInterpreter
PEGInterpreter(grammar, backend="auto")    # Rust when built and in scope
PEGInterpreter(grammar, backend="native")  # require it
```

`native.supports()` detects grammars outside the native subset (custom comment
patterns, semantic actions) and falls back to the Python engine.

---

## Line-numbered languages

Unstructured jumps are a good test of a backend, because each target expresses
them differently:

| Target | `GOTO 30` |
|---|---|
| Interpreter | moves the program counter to the line-30 label |
| C | `goto L30;` with `L30:` labels |
| LLVM IR | one basic block per line, `br label %L30` |
| Python / WASM | not supported — neither has an unstructured jump |

`projects/basic` exercises this end to end; all three executable paths produce
byte-identical output.

---

## Performance

Reference machine, Aurora grammar, 2,000 lines (35 KB):

| Measurement | Result |
|---|---|
| Python engine, full parse | ~110-125 ms (~300 KB/s) |
| Rust engine, match + JSON | ~24 ms (~1.4 MB/s) |
| Rust engine, end to end via PyO3 | ~61-69 ms (~520 KB/s) |

`benchmarks/parse_bench.py` reproduces these numbers. The end-to-end gap is
`SourceAST` construction in Python, which is why the Rust evaluator (no
materialisation) is the fast path for execution.

---

## See also

- [ARCHITECTURE.md](ARCHITECTURE.md) — layering and package map.
- [CLI_REFERENCE.md](CLI_REFERENCE.md#rust-front-end-parsercraft-rs) — every command.
- [CODEGEN_GUIDE.md](CODEGEN_GUIDE.md) — backend details.
