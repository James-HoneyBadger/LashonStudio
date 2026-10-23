# Runtime Guide

ParserCraft has two runtimes:

1. **PEG runtime** — parse with a grammar, transpile the `SourceAST` to Python,
   and `exec` it. Used by `parsercraft repl --grammar`, the Studio, and every
   backend.
2. **Config runtime** — translate custom keywords/functions/operators back to
   Python and execute. Used by `parsercraft repl <config>` and `translate`.

Both execute Python, so both share the same security model (see the end of this
page).

This guide documents the REPL, standard library, FFI bridge, language runtime
singleton, and module system.

---

## REPL

### PEG REPL (grammar-based)

```bash
parsercraft repl --grammar projects/aurora/grammar.peg
# or programmatically:
python -m parsercraft.runtime.repl --config projects/aurora/language.yaml
```

Note the two entry points:

| Entry point | Flag | Reads |
|---|---|---|
| `parsercraft repl` | `--grammar FILE` | PEG text |
| `parsercraft repl` | positional config file | YAML/JSON config (config REPL) |
| `parsercraft-repl` | `--config FILE` | YAML/JSON config, via `REPL.from_config_file` |

PEG REPL commands:

| Command | Effect |
|---|---|
| `:help` | command list |
| `:ast` | pretty-print the last AST |
| `:py` | show the last generated Python |
| `:vars` | show user variables |
| `:grammar` | print every rule |
| `:load FILE` | execute a file |
| `:reset` | clear namespace and history |
| `:quit` | exit |

Input ending in `\`, `{`, or `:` continues on the next line. A missing trailing
`;` is added automatically.

```python
from parsercraft.runtime import REPL
from parsercraft.parser import GrammarParser

grammar = GrammarParser().parse(open("projects/aurora/grammar.peg").read())
repl = REPL(grammar=grammar)

repl.eval_line("fn twice(x) { return x * 2 ; }")
print(repl.eval_line("print twice(21) ;"))     # "42\n"
namespace = repl.eval_lines(["a = 1 ;", "b = a + 2 ;"])   # {'a': 1, 'b': 3}
```

`eval_line` captures stdout/stderr and returns it as a string — ideal for tests
and embedding. `eval_lines` returns the filtered namespace (names starting with
`_` and `__builtins__` removed).

### Config REPL (keyword translation)

```bash
parsercraft repl configs/examples/pascal_like.yaml
```

Commands use a dot prefix:

| Command | Effect |
|---|---|
| `.help` | command list |
| `.info` | language name/version |
| `.keywords` | custom keywords |
| `.functions` | custom function mappings |
| `.vars` | current variables |
| `.clear` | clear variables |
| `.debug` | toggle debug mode (prints translation details) |
| `.exit` | exit |

Lines are translated with `LanguageRuntime` mappings before execution, so
`print` may be `escribir`, `if` may be `si`, and so on.

---

## Standard library

`StdLib` is opt-in: call `register_builtins()` before injecting, otherwise the
namespace receives nothing.

```python
from parsercraft.runtime import StdLib

stdlib = StdLib()
stdlib.register_builtins()

namespace = {}
stdlib.inject(namespace)                      # builtins only
stdlib.inject_module("math", namespace)       # whole module (sqrt, PI, ...)
stdlib.inject_module("math", namespace, ["sqrt"])   # selected symbols
```

### Builtins

`print`, `input`, `len`, `range`, `int`, `float`, `str`, `bool`, `list`, `dict`,
`type`, `abs`, `min`, `max`, `sum`, `enumerate`, `zip`, `map`, `filter`,
`sorted`, `reversed`, `round`, `isinstance`, `hasattr`, `getattr`, `setattr`.

### Modules

| Module | Functions | Constants |
|---|---|---|
| `io` | `print`, `input`, `read_file`, `write_file` | — |
| `math` | `abs`, `acos`, `asin`, `atan`, `atan2`, `ceil`, `cos`, `floor`, `gcd`, `log`, `log10`, `pow`, `sin`, `sqrt`, `tan` | `E`, `INF`, `PI`, `TAU` |
| `string` | `chr`, `endswith`, `find`, `format`, `join`, `lower`, `ord`, `replace`, `split`, `startswith`, `strip`, `upper` | — |
| `collections` | `append`, `contains`, `count`, `flatten`, `index`, `length`, `pop`, `reverse`, `sort`, `unique`, `zip_lists` | — |
| `system` | `cwd`, `env`, `exit`, `sleep`, `time` | — |
| `random` | `choice`, `randint`, `random`, `sample`, `seed`, `shuffle` | — |

### Extending

```python
from parsercraft.runtime import StdLib
from parsercraft.runtime.stdlib import StdModule

stdlib = StdLib()
stdlib.register_builtins()
stdlib.add_builtin("shout", lambda text: text.upper() + "!")

geo = StdModule(name="geo", doc="Geometry helpers")
geo.add_function("area", lambda r: 3.14159 * r * r,
                 params=[("r", "float")], returns="float")
geo.add_constant("PHI", 1.6180339887)
stdlib.add_module(geo)

namespace = {}
stdlib.inject_module("geo", namespace)
```

`StdFunction` accepts `params`, `returns`, `doc`, and `pure`; `pure=False` marks
functions with side effects for documentation and tooling.

---

## FFI bridge

`FFIBridge` binds C library functions (via `ctypes`) and Python callables into a
namespace.

### C functions

```python
from parsercraft.runtime import FFIBridge

ffi = FFIBridge()
ffi.load_library("c", "libc.so.6")           # name → shared object path
ffi.bind("atoi", "c", "atoi", ["char_p"], "int")

print(ffi.call("atoi", b"42"))               # 42
```

`load_library(name, path=None)` accepts a name alone (ctypes resolution) or an
explicit path. `bind(name, library, native_name=None, arg_types=None,
return_type="int", doc="")` requires the library to be loaded first.

Available type names (`CTYPE_MAP`):

`void`, `int`, `int8`, `int16`, `int32`, `int64`, `uint`, `uint8`, `uint16`,
`uint32`, `uint64`, `float`, `double`, `char`, `char_p`, `wchar_p`, `bool`,
`size_t`, `pointer`.

### Python functions

```python
ffi.register_python("double_it", lambda x: x * 2, doc="Double a number")
ffi.import_python_module("math", functions=["sqrt"], prefix="py_")
```

`import_python_module(module_name, functions=None, prefix="")` returns the list
of created bindings; omit `functions` to import every public callable.

### Injecting and inspecting

```python
namespace = {}
ffi.inject(namespace)          # every binding as a plain callable
print(ffi.describe())
print(ffi.list_bindings(), ffi.list_libraries())
ffi.unload_library("c")
```

`describe()` prints a signature table, for example:

```
FFI Bindings:
  atoi(char_p) -> int  [c:c]
  double_it() -> void  [python:native]
```

### Making FFI visible to a language

```python
from parsercraft.runtime import StdLib, FFIBridge

stdlib = StdLib(); stdlib.register_builtins()
ffi = FFIBridge(); ffi.load_library("c", "libc.so.6")
ffi.bind("atoi", "c", "atoi", ["char_p"], "int")

namespace = {}
stdlib.inject(namespace)
ffi.inject(namespace)

from parsercraft.codegen import transpile_and_exec
transpile_and_exec(ast, globals_dict=namespace)
```

---

## Language runtime (config-driven)

`LanguageRuntime` is a singleton holding the active `LanguageConfig` and its
keyword/function mappings.

```python
from parsercraft.config import LanguageConfig
from parsercraft.runtime import LanguageRuntime

LanguageRuntime.load_config(config_file="my_lang.yaml")
# or: LanguageRuntime.load_config(config=LanguageConfig.load("my_lang.yaml"))

LanguageRuntime.translate_keyword("escribir")   # 'print'
LanguageRuntime.translate_function("longitud")  # 'len'
LanguageRuntime.get_custom_keywords()           # ('escribir', 'si', ...)
LanguageRuntime.get_custom_functions()          # ['longitud', ...] (custom names)
LanguageRuntime.get_info()
LanguageRuntime.is_feature_enabled("semicolons")
LanguageRuntime.should_enforce_semicolons()
LanguageRuntime.get_array_start_index()         # 0 or 1 for 1-based languages
LanguageRuntime.get_comment_syntax()            # ('//', '/*', '*/')
LanguageRuntime.reset()
```

`load_config` prints a one-line confirmation, including whether satirical
keywords are enabled. Reset before loading a different language in long-lived
processes (the Studio does this per run).

Feature flags live under `syntax_options` in the YAML; see
[LANGUAGE_DEVELOPMENT.md](USER_GUIDE.md#create-a-language-configuration).

---

## Module system

`ModuleManager` discovers multi-file programs, extracts imports/exports, and
resolves dependencies.

```python
from parsercraft.runtime import ModuleManager
from parsercraft.config import LanguageConfig

manager = ModuleManager(
    config=LanguageConfig.load("my_lang.yaml"),
    search_paths=["modules", "lib"],
    enable_caching=True,
)

module = manager.load_module("utils")
if module:
    print(module.name, module.version, list(module.exports))

resolved = manager.resolve_dependencies("main")     # load order
graph = manager.load_with_dependencies("main")      # {'main': Module, ...}
cycles = manager.detect_circular_dependencies()     # [(from, to), ...]
manager.export_dependency_graph("deps.json")
print(manager.get_module_info("utils"))
```

### Discovery

`_find_module` looks for `<name>` with extensions `.teach`, `.lang`, `.script`,
`.txt` (and no extension) in the configured search paths.

### File syntax

```text
#@ version: 1.2.0
#@ author: Jane Doe
#@ description: String utilities

import math
import math as m
import {sin, cos} from math
import utils version "^1.0.0"

export function shout(text)
export const GREETING = "hello"
export class Point
```

| Construct | Meaning |
|---|---|
| `import mod` | dependency, referenced by `mod` |
| `import mod as alias` | dependency with alias |
| `import {a, b} from mod` | selected exports |
| `import mod version "constraint"` | version requirement |
| `export function\|const\|class name` | public export (kind recorded) |
| `#@ key: value` | metadata (`version`, `author`, `description`, others stored in `metadata`) |

`Module.hash` is a 12-character SHA-256 prefix of the content, useful for cache
invalidation. Imports declared inside functions are also detected because
parsing is line-based, not AST-based.

### Limits

- The parser is line-oriented: `import` must begin a line, and `export` is
  found anywhere in a line.
- No wildcard `import *`; no re-exports.
- Visibility defaults to public; `protected`/`private` exist on
  `ModuleExport` but are not parsed from source.
- Version constraints are stored and reported, not enforced during resolution.

---

## Security model

ParserCraft executes generated Python, so **any source you run has full Python
privileges**:

- `transpile_and_exec`, the REPL, and the Studio's Run button all call `exec`.
- `StdLib.system` exposes `exit`, `sleep`, `env`, `cwd`.
- `FFIBridge` calls native code through `ctypes` — a crash or memory bug in the
  native library can take down the interpreter.
- The CLI's `lsp`, `format`, and `refactor-rename` commands read files you point
  them at; they do not sandbox paths.

Treat language files as code, not data, and only run trusted input. ParserCraft
does not attempt a capability sandbox. If you need isolation, run the generated
Python in a subprocess with OS-level restrictions.

---

## See also

- [CLI_REFERENCE.md](CLI_REFERENCE.md#execution) — `repl`, `batch`, `translate`.
- [TYPE_SYSTEM.md](TYPE_SYSTEM.md) — static analysis of runtime values.
- [LSP_AND_DEBUGGING.md](LSP_AND_DEBUGGING.md) — debugging the runtime.
- [STUDIO_GUIDE.md](STUDIO_GUIDE.md) — the same runtime inside the GUI.
