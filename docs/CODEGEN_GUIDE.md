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
| WebAssembly | `WasmGenerator` | `WasmModule` | **Experimental** — scaffolding, memory, imports, and top-level `main` body only |

The Aurora sample (`projects/aurora`) is translated by the Python, C, and LLVM
backends and executed successfully; the WASM backend emits a module whose
`main` does not yet contain user function bodies.

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
    --config projects/aurora/language.yaml --output fizzbuzz.c
$ gcc -std=c99 fizzbuzz.c -o fizzbuzz && ./fizzbuzz
1
2
Fizz
...
FizzBuzz
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

### What is emitted today

```wat
(module $module
  (memory 256)
  (import "console" "log" (func $log (param $value i32)))
  (import "math" "sqrt" (func $sqrt (param $value f64) (result f64)))
  (export "main" (func $main))
  (func $main (result i32)
    (i32.const 0)))
```

- Module scaffolding, 256 pages of memory, and standard imports.
- Top-level assignments become `local`s with `local.set`; arithmetic chains
  emit `i32.add`/`sub`/`mul`/`div_s`/`rem_s` and comparison instructions.
- Top-level calls emit `(call $name)` with argument expressions pushed first.
- Expressions are exposed through `_emit_source_expr`, and reusable builders
  (`generate_binary_op`, `generate_if`, `generate_loop`,
  `generate_memory_load/store`, `translate_type`) are public.

### What is not emitted yet

- Function definitions and their bodies (`fn`/`function_def`).
- `if`, `while`, `return`, and print statements.
- Strings, floats beyond literal emission, and any runtime/console output.

Because user functions are not emitted, a program that calls one produces WAT
referencing an undefined function. Treat WASM output as a **structural
skeleton** to extend, not as a deployable build. The Studio's WASM pane shows
exactly this output; do not mistake it for a working module.

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
