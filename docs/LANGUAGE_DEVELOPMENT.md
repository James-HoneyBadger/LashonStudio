# Language Development Guide

This is the deep guide to designing a language with ParserCraft: deciding what
the language *is*, encoding it as a PEG grammar, choosing an AST contract,
mapping semantics, testing, and shipping.

Read [QUICKSTART.md](QUICKSTART.md) first if you have not run the pipeline.
Keep [GRAMMAR_REFERENCE.md](GRAMMAR_REFERENCE.md) open while designing rules.

---

## 1. What you are actually building

A language is four artifacts:

| Artifact | ParserCraft representation |
|---|---|
| **Surface syntax** | PEG rules (`grammar.peg` / `grammar.rules`) |
| **Structure** | `SourceAST` nodes produced by the parser |
| **Meaning** | Backends (`PythonTranspiler`, `CCodeGenerator`, …) or your own evaluator |
| **Tooling** | Config metadata, Studio project, REPL, LSP, tests, packages |

Most beginners spend all their time on syntax. Successful language projects
spend most of their time on **the AST contract** and **semantics** — because
that is what every backend and tool consumes.

---

## 2. Design worksheet

Answer these before writing grammar rules.

### 2.1 Audience and purpose

- Who writes this language? Beginners, domain experts, students?
- What should feel familiar? What should feel deliberately different?
- What is the smallest program that demonstrates value?

### 2.2 Program shape

| Question | Example answers |
|---|---|
| Statements separated by? | `;`, newline, `{}` blocks |
| Blocks delimited by? | `{}`, indentation, `begin…end` |
| Comments? | `//`, `#`, `--`, `(* … *)` |
| Case sensitivity? | identifiers, keywords |
| Start rule? | `program`, `module`, `script` |

### 2.3 Expressions

- Literals: numbers, strings, booleans, lists, maps?
- Operators and precedence: arithmetic, comparison, logic, custom?
- Function calls: postfix parentheses? pipeline?
- Indexing/member access?

### 2.4 Declarations

- Variables: assignment vs declaration (`x = 1` vs `let x = 1`)?
- Functions: syntax and parameter list?
- Types/annotations? Generics?
- Modules/imports?

### 2.5 Semantics

- Evaluation strategy? (transpile to Python is the fast path)
- Scoping rules?
- Error model? (parse errors vs runtime errors)
- What does `print` mean? (builtin, library, statement?)

### 2.6 Compatibility target

Choose the primary backend early:

| Target | Best for | Constraints |
|---|---|---|
| **Python** | Prototyping, teaching, immediate execution | Must map onto Python semantics |
| **C** | Systems/embedded demonstration | Backend emits a `main()` and simple C |
| **WASM** | Browser demos | WAT output; limited runtime surface |
| **LLVM IR** | Compiler courses | SSA-style IR; simple values |
| **Custom** | Full control | You write the visitor |

The AST contract below is shaped by what the backends already understand.

---

## 3. Choose an implementation strategy

### 3.1 PEG-first (recommended)

You define the entire syntax as PEG rules. Parsing produces a real AST. This is
the path used by Aurora and the tutorials.

**Use when:** you need new syntax, functions, control flow, or precise errors.

### 3.2 Config-first

You start from `LanguageConfig`: keyword renaming, function mapping, syntax
toggles. `LanguageRuntime` translates custom keywords back to Python and the
config-driven parser handles simple statements.

**Use when:** you want a “skin” of Python/BASIC/Lisp for teaching, not new
syntax.

### 3.3 Hybrid

Use a PEG grammar for syntax and `LanguageConfig` for metadata, keyword
highlighting, builtins, presets, and the Studio. This is what Aurora does:
`language.yaml` holds keywords/settings, `grammar.peg` holds syntax.

**Recommendation:** start hybrid. It costs little and gives you the Studio and
CLI for free.

---

## 4. Build the grammar in layers

Never write the whole grammar at once. Build and test four layers in order.

### Layer 1 — atoms

```peg
program <- NUMBER
```

Verify `PEGInterpreter(grammar).parse("42")` and inspect the AST.

### Layer 2 — expressions with precedence

```peg
expr   <- term (("+" / "-") term)*
term   <- factor (("*" / "/" / "%") factor)*
factor <- NUMBER / IDENT / "(" expr ")"
```

Test associativity and parentheses **before** adding statements by checking the
AST shape:

```python
from parsercraft.parser import GrammarParser, PEGInterpreter

expr_grammar = GrammarParser().parse(
    'program <- expr\n'
    'expr <- term (("+" / "-") term)*\n'
    'term <- factor (("*" / "/" / "%") factor)*\n'
    'factor <- NUMBER / IDENT / "(" expr ")"'
)
ast = PEGInterpreter(expr_grammar).parse("2 + 3 * 4")
print(ast.pretty())        # expr[3] → term[1], Operator('+'), term[3]
```

### Layer 3 — statements

```peg
program   <- statement+
statement <- assignment / expr_stmt
assignment <- IDENT "=" expr ";"
expr_stmt  <- expr ";"
```

Now execution works end to end:

```python
from parsercraft.codegen import transpile_and_exec

grammar = GrammarParser().parse(
    'program <- statement+\n'
    'statement <- assignment\n'
    'assignment <- IDENT "=" expr ";"\n'
    'expr <- term (("+" / "-") term)*\n'
    'term <- factor (("*" / "/") factor)*\n'
    'factor <- NUMBER / IDENT / "(" expr ")"'
)
run = lambda src: transpile_and_exec(PEGInterpreter(grammar).parse(src))
assert run("x = 2 + 3 * 4 ;")["x"] == 14
assert run("x = (2 + 3) * 4 ;")["x"] == 20
```

### Layer 4 — structure

Add functions, `if`/`else`, `while`, blocks. Add one construct at a time and run
the sample suite after each addition.

### Ordering rules of thumb

1. Keywords before identifiers in choices.
2. Specific statement forms before generic expressions.
3. Longer operators before their prefixes (`<=` before `<`).
4. Put the most common constructs first for performance and clarity.

---

## 5. Define the AST contract

The AST is the public interface between parsing and every consumer. Decide it
deliberately.

### 5.1 Node naming

A rule named `assignment` produces nodes with `node_type="assignment"`. Backend
handlers dispatch on that name. The Python transpiler recognizes both
`snake_case` rule names and capitalized variants:

```
program / Program / Module
statement / Statement
assignment / Assignment
function_def / FunctionDef
if_stmt / IfStmt
while_stmt / WhileStmt
for_stmt / ForStmt
return_stmt / ReturnStmt
call / Call / FunctionCall
expr / Expr
expression wrappers: expr, comparison, addition, multiplication, term, factor
literals: Number, String, Boolean/boolean
identifiers: Identifier, IDENT
```

If you invent `when_clause`, you must teach the backend what it means.

### 5.2 Inline assignment shape

A rule like:

```peg
statement <- IDENT "=" expr ";"
```

produces:

```
statement[
  Identifier('x'),
  Operator('='),
  expr[...],
  Operator(';')
]
```

All four backends detect this pattern. You do **not** need a separate
`assignment` rule for simple assignment.

### 5.3 Operator nodes

Literals and character classes inside sequences become `Operator` children with
`value` set to the matched text. Backends use these for operators and
punctuation, and filter structural ones (`;`, `,`, `{`, `}`) as needed.

### 5.4 Contract table

Document your own AST shapes in a table like this (Aurora does this in
`projects/aurora/README.md`):

| Rule | Children | Meaning |
|---|---|---|
| `program` | `statement+` | top level |
| `assignment` | `IDENT, Operator('='), expr, Operator(';')` | assignment |
| `if_stmt` | `Operator('if'), comparison, block, [Operator('else'), block]` | conditional |
| `call` | `IDENT, Operator('('), arg_list?, Operator(')')` | call |

When a backend produces surprising output, compare the AST against this table
first.

---

## 6. Map semantics

### 6.1 Python backend (fastest)

`PythonTranspiler` emits Python source and optionally executes it. It handles:

- assignments (including inline `IDENT = expr ;`),
- arithmetic/comparison chains,
- calls and argument lists,
- list/dict literals,
- function definitions, `if`/`else`, `while`, `for`,
- `return`, `print`, imports,
- boolean rules (`boolean <- "true" / "false"`),
- BASIC/TempleCode statements (`SAY`, `ASK`, `LET`, `REPEAT`, turtle commands).

Options:

```python
from parsercraft.codegen import PythonTranspiler, TranspileOptions

opts = TranspileOptions(
    keyword_map={"when": "if"},
    function_map={"shout": "print"},
    indent_str="    ",
    wrap_in_main=True,
)
print(PythonTranspiler(opts).transpile(ast))
```

### 6.2 C / WASM / LLVM

These backends are source emitters, not optimizing compilers. They understand
the same core shapes (assignment, expressions, calls, functions, control flow)
but each has a deliberately small runtime model. See
[CODEGEN_GUIDE.md](CODEGEN_GUIDE.md) for what each emits and its limits.

### 6.3 Custom semantics

If your language is not Python-shaped, write your own visitor:

```python
from parsercraft.parser import SourceAST

def evaluate(node: SourceAST, env: dict):
    if node.node_type == "Number":
        return node.value
    if node.node_type == "Identifier":
        return env[node.value]
    if node.node_type == "Operator" and node.value == "+":
        ...
```

Use `SourceAST.to_dict()` for serialization or `node.pretty()` for debugging.

---

## 7. Testing a language

A language without tests is a demo. Use four layers.

### 7.1 Grammar validation

```python
grammar = GrammarParser().parse(open("grammar.peg").read())
assert grammar.validate() == []
```

### 7.2 Positive programs

Keep a `samples/` directory and run every file through every backend you claim
to support:

```python
from pathlib import Path
from parsercraft.ide.studio import LanguageStudio

studio = LanguageStudio()
studio.open_project("projects/aurora")
assert studio.validate_grammar().ok

for sample in Path("projects/aurora/samples").glob("*.aur"):
    result = studio.run(sample.read_text())
    assert result.ok, (sample, result.error)

    for backend, generated in studio.generate_all(sample.read_text()).items():
        assert generated.ok, (sample, backend, generated.error)
        assert generated.text.strip()
```

### 7.3 Negative programs

Assert that invalid input fails at the right place:

```python
result = studio.parse("x = ;")
assert not result.ok
assert "Parse error" in result.error
```

### 7.4 Golden output

For deterministic programs, assert exact output:

```python
lines = studio.run(open("samples/fizzbuzz.aur").read()).text.splitlines()
assert len(lines) == 15
assert lines[-1] == "FizzBuzz"
```

### 7.5 Incremental edits (editors)

```python
from parsercraft.parser import GrammarParser
from parsercraft.parser.incremental import IncrementalParser

parser = IncrementalParser(GrammarParser().parse(grammar_text))
parser.parse("x = 10 ; y = 20 ;")
parser.apply_edit(offset=4, old_len=2, new_text="99")
assert parser.stats["incremental"] == 1
```

---

## 8. Errors and diagnostics

### Parse errors

`PEGInterpreter` raises `SyntaxError` with the furthest position and rule. Do
not replace this with a generic “invalid program”; the rule name is often the
most useful debugging clue.

### Friendly messages

```python
from parsercraft.tooling import ErrorLocalizer

loc = ErrorLocalizer()
print(loc.format_with_context(
    "E001",
    source="x = ;",
    line=1, col=5,
    got=";", expected="expression",
))
```

```
error[E001]: Unexpected token ';', expected 'expression'
 --> <input>:1:5
     |
   1 | x = ;
           ^ here
```

Use catalogued codes (`E001`, `E020`, ...). An unknown code renders as
`[code]`.

Register custom messages with `loc.register_error(...)` or load translation
files with `load_translations_file(...)`. Only `en` ships by default.

### Studio / LSP

The Studio surfaces errors in the console and status bar. The LSP analyzer
exposes the same diagnostics programmatically; see
[LSP_AND_DEBUGGING.md](LSP_AND_DEBUGGING.md).

---

## 9. Performance

- The parser is packrat-memoized: O(n) rule/position pairs.
- Avoid rules that can match empty inside `*`/`+`; repetition stops to prevent
  loops, which can silently hide bugs.
- Memoization is per parse; `IncrementalParser` reuses the interpreter but
  re-parses the affected statement.
- Prefer `Grammar.validate()` once at startup, not per parse.
- For large inputs, node creation dominates. Use `is_fragment=True` for
  helper rules that should not appear in the AST, but keep punctuation that
  backends rely on.

---

## 10. Evolving a language

1. **Version the config.** Increment `version` in `language.yaml`; record
   changes in `CHANGELOG.md`.
2. **Add, don’t mutate.** Introduce new keywords/rules; keep old ones working.
3. **Alias deliberately.** Multiple originals may map to one custom keyword
   (e.g. `function` and `lambda` → `fun`). `LanguageConfig.validation_warnings()`
   reports aliases; reverse translation uses the last mapping.
4. **Deprecate in layers.** Warn in docs, then in the REPL, then remove.
5. **Test migrations.** Keep one sample per historical feature until removal.

---

## 11. Case study: Aurora

Aurora (`projects/aurora`) is an 18-rule language with functions, recursion,
conditionals, loops, strings, numbers, booleans, and comments. Its design:

| Decision | Choice | Why |
|---|---|---|
| Blocks | `{}` | unambiguous, easy to parse |
| Statements | `;` terminated | simple error recovery |
| Functions | `fn name(a, b) { … }` | familiar, no annotations |
| Booleans | literal rule `boolean` | demonstrates literal rules |
| Primary backend | Python | fastest path to execution |
| Metadata | `language.yaml` | Studio + CLI reuse |

Run it:

```bash
parsercraft-ide projects/aurora
```

The full build is in
[TUTORIAL.md § Tutorial 5](TUTORIAL.md).

---

## 12. Anti-patterns

| Anti-pattern | Consequence | Fix |
|---|---|---|
| Left recursion | parse failure/validation error | rewrite with repetition |
| Keyword after identifier in a choice | keywords parsed as identifiers | reorder alternatives |
| Empty-match repetition | silent non-progress | make the clause consume |
| One giant rule | unreadable, poor errors | split into named rules |
| Relying on literal escapes | `"\n"` is a backslash + n | use tokens/classes |
| Backend-specific AST hacks | other backends break | fix the shared AST shape |
| No negative tests | errors surface to users | add invalid-program tests |
| Ignoring `validate()` | undefined rules fail at runtime | validate at startup |

---

## 13. Production checklist

- [ ] Grammar validates with no errors.
- [ ] Every rule is documented with its AST shape.
- [ ] Samples cover literals, expressions, statements, structure, and errors.
- [ ] All claimed backends produce non-empty output for every sample.
- [ ] Negative tests assert failure messages.
- [ ] `language.yaml` describes metadata, keywords, operators, and comments.
- [ ] Studio project opens and validates.
- [ ] README explains how to run the language.
- [ ] Version and changelog are current.
- [ ] Packaging (wheel/extension) includes the grammar and samples.
