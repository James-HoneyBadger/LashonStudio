# Code Generation Guide

ParserCraft turns one `SourceAST` into several target languages. Every backend
implements `translate_source_ast(ast)`; the semantics they preserve differ, and
this guide is explicit about where each one stops.

```python
from parsercraft.parser import GrammarParser, PEGInterpreter
from parsercraft.codegen import PythonTranspiler, CCodeGenerator
from parsercraft.codegen import WasmGenerator, LLVMIRGenerator

grammar = GrammarParser().parse(peg_text)
ast = PEGInterpreter(grammar).parse(source_code)

python_src = PythonTranspiler().translate_source_ast(ast)
c_src = CCodeGenerator().translate_source_ast(ast)
wat = WasmGenerator().translate_source_ast(ast).to_wat()
llvm_ir = LLVMIRGenerator().translate_source_ast(ast)
```

---

## Backend maturity

| Backend | Entry point | Returns | Status |
|---|---|---|---|
| Python | `PythonTranspiler`, `transpile_to_python`, `transpile_and_exec` | `str` / `dict` | **Complete** for the documented node set |
| C | `CCodeGenerator` | `str` | **Complete** for the documented node set; integer-typed |
| LLVM IR | `LLVMIRGenerator` | `str` | **Complete** for the documented node set; verifies with `clang` |
| WebAssembly | `WasmGenerator` | `WasmModule` | **Complete** for the documented integer subset (functions, calls, control flow, prints) |

All three Aurora samples are translated by the Python, C, LLVM, and WASM
backends and execute successfully (WASM is verified with `wasmtime` in the
test suite when available).

---

## The AST contract

Backends receive a `SourceAST` tree. Node handling is by `node_type`; names are
lower-case rule names from your grammar (with common CamelCase aliases also
accepted).

| `node_type` | Meaning | Typical children |
|---|---|---|
| `program` | compilation unit | statements |
| `statement` | transparent wrapper | tokens + expression |
| `assignment` | `x = expr ;` | `Identifier`, `Operator('=')`, expr |
| `function_def` | `fn name(params) { ... }` | `Identifier`, `param_list`, `block` |
| `param_list` | parameters | `Identifier` list |
| `block` | `{ ... }` | statements (no brace tokens) |
| `if_stmt` | `if cond block (else block)?` | condition, `block`, `block` |
| `while_stmt` | `while cond block` | condition, `block` |
| `return_stmt` | `return expr ;` | expr |
| `print_stmt` | `print expr ;` | expr |
| `expr_stmt` | expression statement | call or expr |
| `call` | `name(args)` | `Identifier`, arguments |
| `expr` / `term` / `factor` | operator chains | operands and `Operator` nodes |
| `comparison` | relational expression | operands and `Operator` |
| `Number` | numeric literal | `value` |
| `String` | string literal | `value` |
| `Identifier` / `IDENT` | identifier | `value` |
| `Operator` | punctuation/operator | `value` |

**Inline assignments.** When a grammar writes `statement <- IDENT "=" expr ";"`
without an `assignment` rule, the `statement` node contains the tokens
directly. All backends detect this shape, so both styles work.

**Positions.** `node.line` and `node.column` are 1-based, which is what error
messages and the Studio cursor pane report.

---

## Python backend

### API

```python
from parsercraft.codegen import PythonTranspiler, TranspileOptions

options = TranspileOptions(indent_str="    ")
transpiler = PythonTranspiler(options)
code = transpiler.translate_source_ast(ast)   # alias of transpile()
expr = transpiler.transpile_expression(ast)   # single expression → str
```

### `TranspileOptions`

| Field | Default | Effect |
|---|---|---|
| `indent_str` | `"    "` | indentation unit |
| `keyword_map` | `{}` | custom keyword → Python keyword |
| `function_map` | `{}` | custom function → Python callable name |
| `operator_map` | `{}` | custom operator → Python operator |
| `inject_runtime` | `False` | prepend helper code when the program needs it (for example turtle colour support) |
| `source_maps` | `False` | reserved; currently has no effect on output |
| `wrap_in_main` | `False` | indent the program under `if __name__ == "__main__":` |

The CLI and REPL build these maps from `LanguageConfig.keywords`,
`LanguageConfig.builtin_functions`, and `LanguageConfig.operators`.

### Execution helpers

```python
from parsercraft.codegen import transpile_and_exec

namespace = transpile_and_exec(ast)                      # {'x': 42}
namespace = transpile_and_exec(ast, globals_dict={"pi": 3.14159})
```

`transpile_and_exec` filters dunder keys (notably `__builtins__`) so the returned
dict contains only program-defined names plus the supplied globals.

### Behaviour notes

- `=` and `:=` are both treated as assignment.
- Structural punctuation (`;`, `,`, `(`, `)`, `{`, `}`, `[`, `]`, `:`) is
  filtered out of expression, print, list, dict, parameter, and argument lists.
- Boolean rule names such as `true_literal`/`false_literal` are normalised to
  `True`/`False`.
- Lambda-mapped function calls are parenthesised so precedence stays correct.
- Config-driven comparisons rewrite the custom `=` operator without touching
  `==`, `<=`, `>=`, `!=`, or `:=` (BASIC/Pascal style).

### Verified example

Aurora's recursive Fibonacci sample transpiles to:

```python
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)
print('fib(10) =')
print(fib(10))
```

and `transpile_and_exec` returns `{'fib': <function fib>, 'fact': <function fact>}`
with `55` and `3628800` printed.

---

## C backend

### API

```python
from parsercraft.codegen import CCodeGenerator

gen = CCodeGenerator(config=None)
c_source = gen.translate_source_ast(ast)
```

Lower-level builders (`gen_assignment`, `gen_if`, `gen_loop`, `gen_while`,
`gen_printf`, `gen_function_call`, `gen_variable_declare`, `add_include`) are
available for programmatic construction, and `generate(ast_dict, path)`
supports the legacy dictionary AST.

### Emitted structure

```
// Auto-generated C code from ParserCraft

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Forward declarations
int fib(int n);

int fib(int n) { ... }

int main(int argc, char** argv) {
    ...
    return 0;
}
```

### Supported nodes

`program`, `block`, `statement`, `assignment`, `function_def`, `if_stmt`
(including `else`), `while_stmt`, `return_stmt`, `expr_stmt`, `print_stmt`,
`call`, `expr`/`term`/`factor`/`comparison` chains, `Number`, `String`,
`Identifier`, `Operator`.

### Semantics

- Functions are emitted with `int` return type and `int` parameters, and are
  forward-declared before use (recursion works).
- A variable is declared the first time it is assigned in a scope
  (`int i = 1;`); later assignments emit plain `i = i + 1;`.
- `print "text";` → `printf("%s\n", "text");`; `print expr;` →
  `printf("%d\n", expr);`.
- `if/else`, `while`, and nested blocks are emitted with real braces.
- String literals are passed through verbatim; escape sequences are your
  grammar's responsibility.

### Verified example

Aurora FizzBuzz compiles and runs:

```console
$ parsercraft codegen-c projects/aurora/samples/fizzbuzz.aur \
    --config projects/aurora/language.yaml --output fizzbuzz.c \
    --source-map
$ gcc -std=c99 fizzbuzz.c -o fizzbuzz && ./fizzbuzz
1
2
Fizz
...
FizzBuzz
```

`--source-map` emits `#line N "<file>"` directives before each statement, so
compiler diagnostics (and debuggers) point at your language's source lines
instead of the generated C. The `CCodeGenerator(source_map=True,
source_file="prog.aur")` API does the same from Python.

### Line-numbered languages

Line numbers become C labels and `GOTO` becomes `goto`; the LLVM backend uses
one basic block per line and `br label %L30`. A BASIC-style dialect therefore
compiles as well as runs:

```bash
parsercraft-rs codegen-c projects/basic/grammar.peg \
    projects/basic/samples/countdown.bas -o countdown.c --run
```

### Limitations

- Integer-only type inference: every expression is `int` unless it is a string
  literal. Floating point is emitted but printed with `%d`.
- No arrays, structs, pointers, strings as values, `for` loops, `break`, or
  `continue`.
- Indentation of nested statements is cosmetic, not pretty-printed.
- No runtime library: anything beyond `printf`/arithmetic must be included by
  the host program.

---

## LLVM IR backend

### API

```python
from parsercraft.codegen import LLVMIRGenerator

gen = LLVMIRGenerator()
ir_text = gen.translate_source_ast(ast)
gen.save("out.ll")
```

Compile with `clang out.ll -o program` (or `llc` + a linker).

### Emitted structure

- SSA registers (`%1`, `%2`, ...) and one `alloca` per local variable, with
  explicit `load`/`store` for mutability.
- Format strings in `@.fmt.N`, string literals in `@.str.N`.
- `declare i32 @printf(ptr, ...)` plus one `printf` call per print statement.
- `define i32 @name(i32 %param)` per function, with an `entry` block.
- `if`/`else` and `while` become labelled basic blocks with `br` terminators.
- Comparisons produce `i1`; conditions are used directly by `br i1`, and
  `return` zero-extends an `i1` to `i32` for integer functions.

### Supported nodes

`program`, `block`, `statement`, `assignment`, `function_def`, `if_stmt`,
`while_stmt`, `return_stmt`, `expr_stmt`, `print_stmt`, `call`,
binary/comparison chains, `Number`, `String`, `Identifier`, `Operator`.

### Verified end to end

All three Aurora samples compile with `clang` and produce the same output as the
Python backend, including mutually recursive `fib`/`fact` calls and FizzBuzz's
nested conditionals and loop.

```console
$ parsercraft codegen-llvm projects/aurora/samples/fizzbuzz.aur \
    --config projects/aurora/language.yaml --output fizzbuzz.ll
$ clang fizzbuzz.ll -o fizzbuzz && ./fizzbuzz
1
2
Fizz
...
FizzBuzz
```

(`clang` may warn about overriding the module target triple; that is expected.)

### Limitations

- Values are `i32` (or `double` for float literals); mixed arithmetic is not
  promoted, and function signatures are integer-only.
- Locals live in `alloca` slots rather than being promoted through `mem2reg`;
  run `opt -passes=mem2reg` if you want clean SSA input.
- No arrays, structs, globals written by the program, `for` loops, or string
  concatenation.
- Undefined identifiers emit `; WARNING: undefined variable 'name'` and use
  `0`, so unknown names do not fail compilation but change behaviour.
- Calls to functions not defined in the module need a matching `declare`; add
  it with a custom backend or a pass over the output.

---

## WASM backend

### API

```python
from parsercraft.codegen import WasmGenerator

module = WasmGenerator().translate_source_ast(ast)   # returns WasmModule
module.to_wat()                                       # WAT text
module.save("out.wat")
```

Note the return type: unlike the other backends, `translate_source_ast` returns
a `WasmModule`, not a string.

### What is emitted

```wat
(module $module
  (import "console" "__log_i32" (func $__log_i32 (param $value i32)))
  (import "console" "__log_str" (func $__log_str (param $ptr i32) (param $len i32)))
  (import "math" "__sqrt" (func $__sqrt (param $value f64) (result f64)))
  (memory 256)
  (export "memory" (memory 0))
  (func $fib (param $n i32) (result i32)
    local.get $n
    i32.const 1
    i32.le_s
    if
    local.get $n
    return
    end
    ...
  )
  (export "main" (func $main))
  (func $main (result i32)
    i32.const 0          ;; string address
    i32.const 9          ;; byte length
    call $__log_str
    ...
  )
  (data (i32.const 0) "fib(10) =")
)
```

- Functions are emitted as `(func $name (param …) (result i32))`, with
  parameters and lazily declared locals.
- Assignments become `local.set`; identifiers and parameters use `local.get`.
- Expression chains emit operands then `i32.add/sub/mul/div_s/rem_s`,
  `i32.eq/ne/lt_s/gt_s/le_s/ge_s`, and `i32.and/or`.
- `if`/`else` and `while` use structured WAT (`block`/`loop`/`br_if`).
- Calls push arguments then `call $name`.
- `print` of a string allocates a data segment and calls
  `console.logStr(ptr, len)`; other expressions call `console.log(i32)`.
- Module memory is exported as `memory` so hosts can read string data.

### Host contract

A WASM host must provide:

```js
const imports = {
  console: {
    __log_i32: (value) => console.log(value),
    __log_str: (ptr, len) => console.log(readString(ptr, len)),
  },
  math: { __sqrt: Math.sqrt },
};
```

With Python:

```python
import wasmtime

engine = wasmtime.Engine()
store = wasmtime.Store(engine)
module = wasmtime.Module(engine, wasmtime.wat2wasm(wat_text))
# imports: log_i32, log_str (access_caller=True), sqrt -- see tests/test_codegen.py
instance = wasmtime.Instance(store, module, imports)
instance.exports(store)["main"](store)
```

### Limitations

- Values are `i32`; float literals are truncated, and `double` operations are
  not modelled.
- No globals, arrays, structs, pointers, `for` loops, or `break`/`continue`.
- Calls to functions not defined in the same source raise
  `ValueError("WASM backend cannot resolve function ...")`; external builtins
  are not available yet.
- Strings are only printed; string values and concatenation are unsupported.

---

## Writing a custom backend

1. Create a class in `src/parsercraft/codegen/` with
   `translate_source_ast(self, ast) -> str`.
2. Dispatch on `node.node_type`, walking `node.children` in order.
3. Skip `Operator` nodes when you need meaningful children, except where the
   operator itself is the payload (`=`, `+`, comparisons).
4. For expression nodes, handle `expr`/`term`/`factor`/`comparison` chains by
   separating operands from operators.
5. Handle inline assignments in `statement` nodes (see the AST contract).
6. Export the class from `codegen/__init__.py` and add a `codegen-<name>` CLI
   command if the backend should be reachable from the shell.
7. Add golden tests that assert both structure and, where a toolchain is
   available, execution.

```python
class MyBackend:
    """Minimal backend: count statements."""

    def translate_source_ast(self, ast):
        lines = []
        self._visit(ast, lines)
        return "\n".join(lines)

    def _visit(self, node, lines):
        nt = node.node_type
        if nt == "program":
            for child in node.children:
                self._visit(child, lines)
        elif nt == "assignment":
            name = next(c for c in node.children if c.node_type in {"Identifier", "IDENT"})
            lines.append(f"SET {name.value}")
        else:
            for child in node.children:
                self._visit(child, lines)
```

### Testing backends

- Structural assertions (`assert "printf" in out`) catch regressions cheaply.
- Compile-and-run tests (`gcc`, `clang`) catch semantic breakage; mark them with
  `pytest.mark.skipif(shutil.which("clang") is None, ...)` so CI without a
  toolchain stays green.
- Compare outputs against the Python backend on the same AST — it is the
  reference implementation.

See `tests/test_codegen.py` for the existing suite, including
`TestBackendControlFlow`, which exercises functions, `if/else`, `while`,
recursion, string formatting, and comparison typing across C and LLVM.

---

## See also

- [GRAMMAR_REFERENCE.md](GRAMMAR_REFERENCE.md) — how AST nodes are produced.
- [LANGUAGE_DEVELOPMENT.md](LANGUAGE_DEVELOPMENT.md) — designing semantics before
  choosing a backend.
- [CLI_REFERENCE.md](CLI_REFERENCE.md#code-generation) — `codegen-*` commands.
