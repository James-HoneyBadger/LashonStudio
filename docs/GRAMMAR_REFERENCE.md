# Grammar Reference

Lashon grammars are parsing expression grammars (PEGs) written in a small
text notation. This document defines the notation, its runtime semantics, the
AST it produces, and the traps worth knowing.

- Grammar text is parsed by `GrammarParser`.
- Grammars can also be built programmatically with `GrammarBuilder`.
- A `LanguageConfig` YAML file embeds rules under `grammar.rules`; see
  [LANGUAGE_CONFIG](#10-embedding-in-language-config).

---

## 1. A complete grammar

```peg
# comments use # or //
program       <- statement+
statement     <- function_def / if_stmt / while_stmt / assignment / expr_stmt
function_def  <- "fn" IDENT "(" param_list? ")" block
block         <- "{" statement* "}"
param_list    <- IDENT ("," IDENT)*
if_stmt       <- "if" comparison block ("else" block)?
while_stmt    <- "while" comparison block
assignment    <- IDENT "=" expr ";"
expr_stmt     <- call ";"
comparison    <- expr ("==" / "!=" / "<=" / ">=" / "<" / ">") expr
expr          <- term (("+" / "-") term)*
term          <- factor (("*" / "/" / "%") factor)*
factor        <- call / NUMBER / STRING / boolean / IDENT / "(" expr ")"
call          <- IDENT "(" arg_list? ")"
arg_list      <- expr ("," expr)*
boolean       <- "true" / "false"
```

Rules may span lines. A continuation line is indented (or starts with `|`) and
does not contain `<-`:

```peg
expr <- term
        (("+" / "-") term)*
```

Blank lines and lines starting with `#` or `//` are ignored.

---

## 2. Notation

| Construct | Syntax | Example |
|---|---|---|
| Rule definition | `name <- pattern` | `program <- statement+` |
| Sequence | juxtaposition | `"if" expr block` |
| Ordered choice | `/` (or `\|`) | `NUMBER / IDENT` |
| Zero or more | `*` | `statement*` |
| One or more | `+` | `statement+` |
| Optional | `?` | `param_list?` |
| And-predicate | `&pattern` | `&NUMBER NUMBER` |
| Not-predicate | `!pattern` | `!"x" .` |
| Literal | `"text"` or `'text'` | `"if"` |
| Character class | `[regex-class]` | `[a-zA-Z0-9_]` |
| Any character | `.` | `.` |
| Group | `( pattern )` | `("+" / "-") term` |
| Rule reference | `name` | `expr` |
| Built-in token | uppercase name | `NUMBER`, `IDENT`, `STRING` |
| Named capture | `@name:pattern` | reserved — parsed but ignored |
| Semantic action | `{ name }` | not supported — rejected |

### Reserved syntax

- **Named captures** (`@name:pattern`) are parsed and store a `label` on the
  PEG node, but the interpreter does not expose labels in the AST. Do not rely
  on them.
- **Semantic actions** (`{ ... }`) are rejected by the grammar parser. Handle
  semantics in a backend or after parsing instead.

---

## 3. Matching semantics

### 3.1 Ordered choice

`a / b / c` tries `a`, then `b`, then `c`. The first success wins; PEG does not
backtrack into an earlier alternative if a later part of the sequence fails.
Order alternatives from most specific to most general.

```peg
# Correct: keyword statement before generic assignment
statement <- print_stmt / assignment

# Wrong: assignment may consume the leading IDENT first
statement <- assignment / print_stmt
```

### 3.2 Repetition and zero-width matches

`*` and `+` stop when the inner pattern fails **or matches zero characters**.
This guarantees termination, but it also means a pattern that can match empty
will not advance:

```peg
# "item?" can succeed without consuming input; the loop stops immediately.
program <- item?*
```

Use a pattern that consumes input in the repeated clause.

### 3.3 Whitespace and comments

By default, `skip_whitespace=True` and the interpreter skips ` \t\r\n` before
rules, literals, and tokens. `Grammar.comment_patterns` defaults to:

```python
["//.*", r"/\*[\s\S]*?\*/"]
```

Comments are regular expressions matched at the current position, repeatedly.
A zero-width regex is ignored (guarded). Invalid regexes raise `ValueError`.

Disable both with:

```python
grammar.skip_whitespace = False
```

This also disables comment skipping.

### 3.4 Keyword boundaries

Alphabetic literals get an implicit word-boundary check: `"if"` matches `if`
but not the prefix of `ifx`. Non-alphabetic literals (operators, punctuation)
do not get this check.

### 3.5 Predicates

- `&p` succeeds if `p` matches, without consuming input.
- `!p` succeeds if `p` fails, without consuming input.

```peg
# A statement that does not start with "end"
statement <- !"end" IDENT "=" NUMBER ";"
```

### 3.6 Literal escapes

Literal values are stored **raw**. `"\n"` in grammar text is a backslash
followed by `n`, not a newline. Escape sequences are not decoded. If you need a
newline literal, use a character class or a built-in token instead.

### 3.7 Character classes

The text between `[` and `]` is passed to Python's `re` as a character class.
`[a-zA-Z0-9_]` works as expected. Matched characters are exposed as AST
`Operator` nodes when they are part of a sequence (see §5).

---

## 4. Built-in tokens

| Token | Matches | AST node |
|---|---|---|
| `NUMBER` | `[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?` | `Number` with `int` or `float` value |
| `IDENT` | `[a-zA-Z_]\w*` | `Identifier` with string value |
| `STRING` | single- or double-quoted, backslash-aware | `String` with raw body (escapes preserved) |
| `NEWLINE` | `\n` or `\r\n` | no node (consumes) |
| `EOF` | only at end (after whitespace) | no node |

`INDENT` and `DEDENT` are recognised by the grammar reader but **not
implemented**. A grammar that references them fails validation.

You cannot override built-in tokens: a rule named `NUMBER`, `IDENT`, `STRING`,
`NEWLINE`, or `EOF` is parsed, but references to that name always resolve to the
built-in token. Validation does not warn about this shadowing — use a different
rule name if you need custom lexing.

---

## 5. AST production rules

Every non-fragment rule produces a `SourceAST`:

```python
SourceAST(
    node_type=rule.node_type or rule.name,
    value=...,          # scalar result, if any
    children=[...],     # child nodes
    line=1, column=1,   # 1-based, start of the match
    source_text="...",  # exact matched source
)
```

Rules for assembling children:

| Match result | AST effect |
|---|---|
| A single `SourceAST` | becomes the only child |
| A list of `SourceAST` | becomes `children` |
| A scalar (string/number) | becomes `value` |
| A sequence of raw strings | each non-blank string becomes an `Operator` child |

Consequences:

- `IDENT "=" expr ";"` under a rule named `statement` yields
  `statement[Identifier, Operator('='), expr, Operator(';')]`.
- A literal-only rule such as `boolean <- "true" / "false"` produces a
  `boolean` node with `value="true"` (not a `Boolean` node).
- Character classes inside sequences appear as `Operator` nodes.
- `is_fragment=True` rules (available through `GrammarBuilder`/`add_rule`) do
  not create a node; their children are spliced into the parent.

Source positions are attached to every rule node and every token node.

---

## 6. Fragment rules and custom node types

```python
from lashon.parser import GrammarBuilder, PEGNode, PEGNodeType

b = GrammarBuilder("Tiny")
b.rule("program").set_pattern(b.plus(b.ref("statement")))
b.rule("statement").set_pattern(
    b.seq(b.ref("IDENT"), b.lit("="), b.ref("NUMBER"), b.lit(";"))
)
grammar = b.build()
```

To make a rule invisible in the AST, add it with `is_fragment=True`:

```python
from lashon.parser import PEGNode, PEGNodeType

grammar.add_rule(
    "comma",
    PEGNode(PEGNodeType.LITERAL, ","),
    is_fragment=True,
)
```

To emit a different node type, set `node_type`:

```python
grammar.add_rule("assign", pattern, node_type="assignment")
```

Backend handlers dispatch on `SourceAST.node_type`, so custom node types need a
backend that understands them.

---

## 7. Validation

```python
grammar = GrammarParser().parse(text)
errors = grammar.validate()
```

Validation reports:

- references to undefined rules,
- unsupported tokens (`INDENT`, `DEDENT`),
- a missing start rule,
- direct or first-position left recursion.

Left-recursive rules are illegal in PEG:

```peg
# Rejected
expr <- expr "+" term / term
```

Rewrite with repetition:

```peg
expr <- term ("+" term)*
```

Validation is structural. It does **not** execute the grammar. Left recursion
through predicates is not detected.

`GrammarParser.parse` also rejects malformed text: trailing junk, unclosed
groups, unterminated literals/classes, and lines that are not rule definitions.

---

## 8. Error reporting

A parse failure raises `SyntaxError` with the furthest position reached:

```text
Parse error at line 3, column 12 (in rule 'factor'): unexpected 'END'
```

`PEGInterpreter` also rejects unconsumed trailing input:

```text
Unexpected input at line 1, column 8: '...'
```

For localised messages, see
[ErrorLocalizer](LSP_AND_DEBUGGING.md#localized-errors).

---

## 9. GrammarBuilder reference

| Call | Result |
|---|---|
| `GrammarBuilder(name="custom")` | new builder |
| `.rule(name, description="")` | start/select a rule |
| `.set_pattern(node)` | assign the current rule's pattern |
| `.start(rule_name)` | set the start rule |
| `.seq(*nodes)` | sequence |
| `.choice(*nodes)` | ordered choice |
| `.star(node)` / `.plus(node)` / `.opt(node)` | repetition |
| `.lit(text)` | literal |
| `.ref(rule_name)` | rule reference |
| `.token("NUMBER")` | built-in token reference |
| `.ident()` / `.number()` / `.string()` | token shorthands |
| `.char_class("a-z")` | character class |
| `.any_char()` | any character |
| `.and_pred(node)` / `.not_pred(node)` | predicates |
| `.build()` | validate and return a `Grammar` |

---

## 10. Embedding in language config

```yaml
grammar:
  start: program
  skip_whitespace: true
  comments:
    - "//.*"
    - "/\\*[\\s\\S]*?\\*/"
  rules:
    program: statement+
    statement: 'IDENT "=" expr ";"'
    expr: term (("+" / "-") term)*
    term: factor (("*" / "/") factor)*
    factor: NUMBER / IDENT / "(" expr ")"
```

```python
import yaml
from lashon.parser import grammar_from_config, PEGInterpreter

config = yaml.safe_load(open("language.yaml"))
grammar = grammar_from_config(config)
ast = PEGInterpreter(grammar).parse("x = 1 + 2 ;")
```

Rules in YAML are strings. Keep each rule on a single line; use the
`grammar.peg` file when you want multi-line, human-formatted rules.

The config-driven Studio writes both `grammar.peg` and `grammar.rules`; see
[STUDIO_GUIDE.md](STUDIO_GUIDE.md).

---

## 11. Common patterns

### Expression precedence

```peg
expr   <- term (("+" / "-") term)*
term   <- factor (("*" / "/") factor)*
factor <- NUMBER / IDENT / "(" expr ")"
```

### Blocks

```peg
block <- "{" statement* "}"
```

For indentation-sensitive languages, model indentation explicitly with
`NEWLINE` and an external pre-pass, or use explicit terminators. `INDENT` /
`DEDENT` are not implemented.

### Function definitions and calls

```peg
function_def <- "fn" IDENT "(" param_list? ")" block
param_list   <- IDENT ("," IDENT)*
call         <- IDENT "(" arg_list? ")"
arg_list     <- expr ("," expr)*
```

### Lists and dictionaries

```peg
list_literal <- "[" (expr ("," expr)*)? "]"
dict_literal <- "{" (STRING ":" expr ("," STRING ":" expr)*)? "}"
```

### Inline assignment

```peg
statement <- IDENT "=" expr ";"
```

Backends detect this shape (`[IDENT, Operator('='), expr, Operator(';')]`)
without a separate `assignment` rule.

---

## 12. Pitfalls checklist

- [ ] Alternatives ordered most-specific first.
- [ ] No left recursion.
- [ ] Every rule reachable from the start rule is defined.
- [ ] Repetition clauses always consume when they succeed.
- [ ] Keywords before identifiers in choices.
- [ ] Comments do not appear inside literals unexpectedly.
- [ ] Literal escapes are raw.
- [ ] Unsupported tokens are not used.
- [ ] Grammar validates: `grammar.validate() == []`.
- [ ] Test with valid and invalid programs (see
      [LANGUAGE_DEVELOPMENT.md](LANGUAGE_DEVELOPMENT.md#7-testing-a-language)).
