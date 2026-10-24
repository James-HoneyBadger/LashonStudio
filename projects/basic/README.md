# Lashon BASIC

A line-numbered BASIC dialect defined entirely by
[`grammar.peg`](grammar.peg) — no hand-written lexer or parser. Lashon
parses it and executes it.

## Dialect

Every line starts with a line number, which doubles as its `GOTO` label.

| Statement | Example |
|---|---|
| `REM` comment | `10 REM hello` |
| `LET` assignment | `20 LET X = 6 * 7` |
| Bare assignment | `30 X = X - 1` |
| `PRINT` | `40 PRINT "ANSWER", X` |
| `IF … THEN … ELSE` | `50 IF X > 0 THEN GOTO 30` |
| `GOTO` | `60 GOTO 20` |
| `WHILE … WEND` | `70 WHILE I <= 15` … `90 WEND` |
| `END` | `100 END` |

Expressions support `+ - * / %`, the comparisons `= <> < <= > >=`, string
literals, and parentheses.

## Run it

Both engines run this dialect and produce identical output:

```bash
# Rust core (no Python needed)
lashon-rs run grammar.peg samples/countdown.bas
lashon-rs codegen-c grammar.peg samples/countdown.bas --compile --run
lashon-rs lint grammar.peg --source samples/fizzbuzz.bas

# Python pipeline (CLI, Studio, REPL)
lashon run samples/countdown.bas --config language.yaml
lashon-ide projects/basic
lashon repl --grammar grammar.peg
```

`language.yaml` mirrors the grammar so the Studio can open the project. Because
Python has no `goto`, the Python backend compiles a numbered program into a
program-counter loop (`def _lashon_numbered_program(): while _pc is not None:`)
while C keeps `L10:` labels and `goto` and LLVM IR emits one basic block per
line. All three produce the same output.

Expected output:

```
$ lashon-rs run grammar.peg samples/countdown.bas
3
2
1
LIFTOFF!
```

## How it works

1. `grammar.peg` defines `program <- line+`, where `line <- NUMBER !'WEND' statement`.
   Line numbers delimit statements, so the grammar needs no newline handling.
2. `lashon-rs run` parses with the PEG engine, then executes the AST with
   the tree-walking evaluator. Line numbers are collected as labels, and
   `GOTO` rewinds the program counter to the target line.
3. The LSP and linter work on the same grammar, so diagnostics inside the
   dialect come from the same rules.

## Compiling to native code

Line numbers become labels, so both native backends understand the dialect:

```bash
lashon-rs codegen-c    grammar.peg samples/countdown.bas -o countdown.c --run
lashon-rs codegen-llvm grammar.peg samples/countdown.bas -o countdown.ll --run
```

C uses labels plus `goto`; LLVM IR uses one basic block per line number and
`br label %L30`. All three samples produce byte-identical output through the
interpreter, the generated C, and the generated LLVM IR. The Python and WASM
backends target structured languages and do not emit unstructured jumps, so
those two targets are not available for this dialect.
