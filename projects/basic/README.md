# ParserCraft BASIC

A line-numbered BASIC dialect defined entirely by
[`grammar.peg`](grammar.peg) — no hand-written lexer or parser. ParserCraft
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

```bash
parsercraft-rs run grammar.peg samples/hello.bas
parsercraft-rs run grammar.peg samples/countdown.bas
parsercraft-rs run grammar.peg samples/fizzbuzz.bas
parsercraft-rs lint grammar.peg --source samples/fizzbuzz.bas
parsercraft-rs ast grammar.peg samples/hello.bas
```

Expected output:

```
$ parsercraft-rs run grammar.peg samples/countdown.bas
3
2
1
LIFTOFF!
```

## How it works

1. `grammar.peg` defines `program <- line+`, where `line <- NUMBER !'WEND' statement`.
   Line numbers delimit statements, so the grammar needs no newline handling.
2. `parsercraft-rs run` parses with the PEG engine, then executes the AST with
   the tree-walking evaluator. Line numbers are collected as labels, and
   `GOTO` rewinds the program counter to the target line.
3. The LSP and linter work on the same grammar, so diagnostics inside the
   dialect come from the same rules.

Line-numbered control flow is interpreted by the Rust core; the Python
transpiler and the C/WASM/LLVM backends target structured languages and do not
support `GOTO,` so this dialect is run — not transpiled.
