# Type System

ParserCraft ships a small, dependency-free type model plus a line-oriented
checker and separate generic/protocol/narrowing helpers. It is a **heuristic
analyzer**, not a full type checker: it recognises simple annotations and
literals, records function signatures you give it, and reports obvious
mismatches. Use it for editor feedback and quick sanity checks, not as a proof
of type safety.

Everything lives in `parsercraft.types`:

```python
from parsercraft.types import (
    Type, TypeKind, TypeEnvironment, TypeChecker, AnalysisLevel,
    GenericChecker, GenericsTypeChecker, GenericType, TypeParameter,
    Protocol, ProtocolChecker, ProtocolTypeChecker, ProtocolTypeIntegration,
    TypeNarrowingPass, TypeCompatibilityResult,
)
```

---

## `Type` and `TypeKind`

```python
from parsercraft.types import Type, TypeKind

Type.int()                          # int
Type.float()                        # float
Type.str()                          # str
Type.bool()                         # bool
Type.list(Type.int())               # list[int]
Type.dict(Type.str(), Type.int())   # dict[str, int]
Type.union(Type.int(), Type.str())  # (int | str)
Type(kind=TypeKind.INT, nullable=True)   # int?
```

`Type` is a dataclass: `kind`, `name`, `type_args`, `nullable`, `metadata`.

`TypeKind` values: `UNKNOWN`, `NONE`, `BOOL`, `INT`, `FLOAT`, `STR`, `LIST`,
`DICT`, `TUPLE`, `SET`, `CALLABLE`, `CLASS`, `UNION`, `OPTIONAL`, `GENERIC`,
`ANY`.

`str(type)` renders `list[int]`, `(int | str)`, `int?`, or the kind name.

### Compatibility rules

`source.is_compatible_with(target)` returns `True` when:

1. Either side is `ANY`.
2. Kinds are equal — and when both have `type_args`, every pair is compatible.
3. The pair is `{INT, FLOAT}` (numeric widening in both directions).
4. Either side is `OPTIONAL` — compatibility is checked against its inner type
   (an empty `OPTIONAL` is compatible with anything).

Everything else is `False`; there is no subtyping graph and no class hierarchy.

```python
assert Type.int().is_compatible_with(Type.float())
assert Type.str().is_compatible_with(Type.union(Type.str(), Type.int()))
assert not Type.str().is_compatible_with(Type.int())
```

---

## Environment

`TypeEnvironment` holds variables, function signatures, and class types, with an
optional parent for nested scopes.

```python
from parsercraft.types import TypeEnvironment, Type

env = TypeEnvironment()
env.define_variable("count", Type.int())

child = env.create_child_scope()
child.define_variable("count", Type.float())      # shadows parent
env.get_variable_type("count")                    # int
child.get_variable_type("count")                  # float
env.get_variable_type("missing")                  # None
```

`define_function(name, TypeSignature)` and `get_function_signature(name)` cover
calls; `create_child_scope()` is the only scoping primitive (no block analysis).

---

## `TypeChecker`

```python
from parsercraft.types import TypeChecker, AnalysisLevel
from parsercraft.config import LanguageConfig

checker = TypeChecker(LanguageConfig.load("my_lang.yaml"), AnalysisLevel.STRICT)
errors = checker.check_file("program.src")
print(checker.get_type_error_summary())
```

### Analysis levels

`LENIENT`, `MODERATE` (default), `STRICT`, `VERY_STRICT`. The CLI maps
`--level lenient|moderate|strict|very-strict` onto these. Levels are recorded on
the checker; they do not currently change which rules run.

### What `check_file` does

For each line:

- Skips blanks and `#` comments.
- Treats a non-empty right-hand side of `=` as an assignment (lines beginning
  with `if`/`when` are skipped).
- Splits the target on `:` for an annotation and infers the source type.
- On mismatch, records error `E101` with the real line number and file path.

```text
x: int = 1        # ok
y: str = 2        # [E101] Type mismatch: cannot assign int to str at program.src
z = y             # infers z: str
```

### Expression inference

`check_expression(expr, env)` handles:

| Input | Result |
|---|---|
| identifier (`count`) | registered type, else `UNKNOWN` |
| call (`f(...)`) | the registered signature's return type, else literal inference |
| integer (`42`) | `int` |
| float (`3.14`) | `float` |
| string (`"hi"` / `'hi'`) | `str` |
| `true`/`false`/`True`/`False` | `bool` |
| list literal (`[1]`) | `list[any]` |
| dict literal (`{1: 2}`) | `dict[any, any]` |
| anything else | `UNKNOWN` |

Numeric literals are recognised as literals, not as variable names.

### Checking a specific assignment

```python
from parsercraft.types import TypeChecker, TypeEnvironment
from parsercraft.config import LanguageConfig

env = TypeEnvironment()
checker = TypeChecker(LanguageConfig())
ok = checker.check_assignment("total: float", "3", env,
                              line=7, location="program.src")
```

`check_function_definition(name, params, return_type, env)` registers a
signature from `(name, annotation)` pairs; the file checker does not parse
function definitions itself.

### Error format

`check_file` returns `TypeError` records (`kind`, `code`, `message`, `location`,
`line`, `column`, `suggestion`). `get_type_error_summary()` prints them grouped
as `Errors (n)` / `Warnings (n)`.

### Limits

- Line-oriented: multi-line expressions, nested blocks, and function bodies are
  not analysed.
- No control-flow or return-path analysis, no inference of expression types
  beyond literals and registered signatures.
- No generics, unions, or optional unwrapping during checking — those types are
  modelled, but the checker does not enforce them deeply.
- Annotations are recognised only as `name: type` inside an assignment line.

---

## Generics

Two layers exist:

### `GenericChecker` (constraint checks)

```python
from parsercraft.types import GenericChecker, GenericType, TypeParameter
from parsercraft.types.type_system_generics import GenericClass, GenericFunction

checker = GenericChecker()

bound = TypeParameter("T", constraint="Comparable")
checker.check_constraint(bound, "int")                  # True

identity = GenericFunction(
    name="identity",
    type_parameters=[TypeParameter("T")],
    parameter_types={"value": "T"},
    return_type="T",
)
checker.infer_type_arguments(identity, {"T": "int"})    # dict or None

box = GenericClass(name="Box", type_parameters=[TypeParameter("T")])
checker.validate_generic_class(box)                     # list of problems

checker.check_generic_assignment(
    GenericType("Box", arguments=["int"]),
    GenericType("Box", arguments=["float"]),
)
```

`check_generic_assignment` currently compares the raw `GenericType` objects; it
does not enforce variance, so treat its result as a structural name check.

### `GenericsTypeChecker` (file-level)

```python
from parsercraft.types import GenericsTypeChecker
from parsercraft.types.type_system_generics import Variance

checker = GenericsTypeChecker(config)
checker.check_file("program.src")                        # list of messages
checker.check_generic_class("Box", ["T"], class_def)     # list of problems
checker.check_generic_function("map", ["T", "U"], func_def)
checker.check_generic_instantiation("Box", ["int"])      # (ok, messages)
checker.check_variance("Box", position=0, variance=Variance.COVARIANT)
checker.infer_type_arguments("identity", [Type.int()])   # (inferred, messages)
```

Generic classes and functions must be registered with the checker before
instantiation/variance checks succeed; unknown names return
`(False, ['Unknown generic: ...'])`.

`GenericType(name, parameters, arguments)` describes a generic; `TypeParameter`
carries `constraint`, `bound`, `variance`, and `default`. Variance values:
`INVARIANT`, `COVARIANT`, `CONTRAVARIANT` (from
`parsercraft.types.type_system_generics`).

`parsercraft generics FILE` scans `class Name[T]` / `def Name[T]` declarations
and `Name[...]` instantiations for duplicate/empty parameters and arity
mismatches. `--infer` prints parameter bindings; `--check-variance` flags
variance markers on functions. It is a lightweight source checker, not a
replacement for the classes below.

---

## Protocols (structural typing)

```python
from parsercraft.types import Protocol, ProtocolChecker
from parsercraft.types.protocols import StructuralType, MethodSignature

printable = Protocol(
    name="Printable",
    methods={"print": MethodSignature("print", "void")},
)

doc = StructuralType(methods={"print": MethodSignature("print", "void")})

checker = ProtocolChecker()
checker.register_protocol(printable)
checker.conforms_to_protocol(doc, printable)        # True
checker.find_matching_protocols(doc)                # ['Printable']
checker.structural_compatible(doc, other_struct)    # structural match
checker.extract_structural_type(source_text)        # StructuralType
checker.check_protocol_composition(["Printable", "Comparable"])
```

`MethodSignature(name, return_type, parameter_types, is_optional)` and
`PropertyDef(name, type_, is_readonly, is_optional)` describe members.
`Protocol` also supports `extends` and `get_all_methods()`/`get_all_properties()`
for inheritance.

`ProtocolTypeChecker` and `ProtocolTypeIntegration` bridge protocols into the
main checker; the `parsercraft check-protocol` CLI command is a placeholder.

---

## Narrowing

`TypeNarrowingPass` tracks per-variable narrowings:

```python
from parsercraft.types import TypeNarrowingPass

pass_ = TypeNarrowingPass()
pass_.narrow_by_isinstance("value", "int")
pass_.get_narrowed_type("value")          # int

pass_.narrow_by_truthiness("value")       # truthy narrowing
pass_.narrow_by_comparison("value", "!=", None)   # clears nullable
```

Narrowing is recorded, not applied to the environment automatically. Behaviour
details:

- `narrow_by_isinstance` maps a type name to a `Type` and stores it.
- `narrow_by_comparison` only adjusts variables that are already narrowed:
  `== None`/`is None` sets `nullable=True`; `!= None`/`is not None` sets
  `nullable=False`; any comparison against a non-`None` value clears
  `nullable` on `OPTIONAL`/`NONE` types.
- `narrow_by_truthiness` applies the same nullable-clearing rule.

---

## Using types with languages

1. Generate Python with `PythonTranspiler` — type annotations in your source can
   be preserved as Python annotations by your grammar and codegen choices.
2. Run `parsercraft type-check --config lang.yaml --input program.src` for a
   quick report.
3. For editor integration, call `TypeChecker.check_file`/`check_expression`
   from your LSP analyzer and surface `TypeError.message` as diagnostics.
4. For real guarantees, rely on the Python runtime plus your own tests; treat
   this checker as advisory.

```python
from parsercraft.types import TypeChecker, AnalysisLevel

def diagnostics_for(path: str, config) -> list[str]:
    checker = TypeChecker(config, AnalysisLevel.STRICT)
    return [f"{e.line}: {e.message}" for e in checker.check_file(path)]
```

---

## See also

- [CLI_REFERENCE.md](CLI_REFERENCE.md#type-and-protocol-analysis) — `type-check`,
  `generics`, `check-protocol`.
- [LSP_AND_DEBUGGING.md](LSP_AND_DEBUGGING.md) — surfacing diagnostics in an
  editor.
- [LANGUAGE_DEVELOPMENT.md](LANGUAGE_DEVELOPMENT.md) — where types fit in a
  language design.
