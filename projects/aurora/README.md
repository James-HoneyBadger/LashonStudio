# Aurora

Aurora is the reference language project for **Lashon Studio**. It is a
small, complete language that demonstrates the whole pipeline:

```
grammar.peg + language.yaml  →  PEG parser  →  AST  →  Python / C / WASM / LLVM IR
```

## Layout

| File | Purpose |
|------|---------|
| `language.yaml` | Language metadata, keywords, operators, and grammar rules |
| `grammar.peg` | Canonical PEG grammar used by the Studio |
| `samples/hello.aur` | Strings and printing |
| `samples/fibonacci.aur` | Functions, recursion, conditionals |
| `samples/fizzbuzz.aur` | Loops, nested conditionals, modulo |

## Language tour

```
fn fib(n) {
  if n <= 1 { return n ; }
  return fib(n - 1) + fib(n - 2) ;
}

print fib(10) ;
```

- Values: numbers, strings, booleans
- Statements: assignment, `print`, `return`, `if`/`else`, `while`
- Functions: `fn name(a, b) { ... }`
- Operators: `+ - * / %`, comparisons `== != < <= > >=`

## Open it in the Studio

```bash
lashon-ide projects/aurora
```

The Studio loads the grammar, samples, and language metadata. Press **F5** to
run the current sample, or use **Generate** to emit Python, C, WASM, or LLVM IR.

## Run from the CLI

```bash
lashon codegen-c projects/aurora/samples/fibonacci.aur \
  --config projects/aurora/language.yaml --output /tmp/fibonacci.c
```
