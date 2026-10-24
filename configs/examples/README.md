# Turing-Complete Language Examples

This directory contains sample Language Construction Set configurations that define Turing-complete programming languages with different paradigms and computational models.

## What Makes These Turing-Complete?

All these languages are Turing-complete because they include:
1. **Conditional branching** (if/then/else)
2. **Loops or recursion** (while/for or recursive functions)
3. **Variables/memory** (storage and retrieval)
4. **Arithmetic operations** (computation)

These four features are sufficient to simulate a Turing machine and compute any computable function.

## Language Configurations

### 1. BASIC-Like Language (`basic_like.yaml`)
**Paradigm**: Imperative, procedural  
**Inspired by**: BASIC, QBasic

**Key Features:**
- Line-numbered programming style
- `LET`, `PRINT`, `INPUT` commands
- `GOSUB` for subroutines
- `DIM` for arrays
- 1-based array indexing
- `REM` for comments
- Classic BASIC operators (`<>` for not-equal)

**Example syntax:**
```basic
LET x = 10
IF x > 5 THEN PRINT "Greater"
FOR i = 1 TO 10 STEP 2
    PRINT i
NEXT
```

### 2. LISP-Like Language (`lisp_like.yaml`)
**Paradigm**: Functional, S-expression based  
**Inspired by**: Lisp, Scheme

**Key Features:**
- S-expression syntax
- `lambda` for anonymous functions
- `car`, `cdr`, `cons` for list operations
- `map`, `filter`, `fold` higher-order functions
- Pattern matching with `cond`
- Recursion-preferred over loops
- Semicolon comments

**Example syntax:**
```lisp
(define factorial
  (lambda (n)
    (if (= n 0)
        1
        (* n (factorial (- n 1))))))
```

### 3. Forth-Like Language (`forth_like.yaml`)
**Paradigm**: Stack-based, postfix notation  
**Inspired by**: Forth

**Key Features:**
- Reverse Polish Notation (RPN)
- Stack manipulation: `DUP`, `DROP`, `SWAP`, `OVER`, `ROT`
- Postfix operators
- Colon definitions (`:` to define, `;` to end)
- Direct memory access (`@` fetch, `!` store)
- `BEGIN...UNTIL` loops

**Example syntax:**
```forth
: square DUP * ;
: sum-of-squares square SWAP square + ;
5 3 sum-of-squares .
```

### 4. Pascal-Like Language (`pascal_like.yaml`)
**Paradigm**: Structured, imperative  
**Inspired by**: Pascal, Delphi

**Key Features:**
- Strong typing with `VAR`, `TYPE`, `CONST`
- `BEGIN...END` blocks
- `PROCEDURE` and `FUNCTION` declarations
- `:=` for assignment
- `CASE` statements
- `ARRAY OF` syntax
- Semicolon statement separator

**Example syntax:**
```pascal
FUNCTION Fibonacci(n: Integer): Integer;
BEGIN
    IF n <= 1 THEN
        Fibonacci := n
    ELSE
        Fibonacci := Fibonacci(n-1) + Fibonacci(n-2);
END;
```

### 5. Ruby-Like Language (`ruby_like.yaml`)
**Paradigm**: Object-oriented, dynamic  
**Inspired by**: Ruby

**Key Features:**
- Object-oriented with `class`, `self`, `super`
- Blocks with `do...end`
- Iterators: `each`, `map`, `select`, `reduce`
- `unless` (negative `if`)
- `next` instead of `continue`
- Symbol coercion: `to_i`, `to_s`, `to_f`
- `begin...rescue...ensure` exception handling

**Example syntax:**
```ruby
def factorial(n)
  return 1 if n <= 1
  n * factorial(n - 1)
end

[1,2,3,4,5].map { |x| x * 2 }
```

### 6. Functional ML-Like Language (`functional_ml.yaml`)
**Paradigm**: Functional, statically typed (conceptually)  
**Inspired by**: OCaml, F#, Standard ML

**Key Features:**
- Pattern matching with `match...with`
- Algebraic data types
- `let rec` for recursive functions
- List operations: `::` (cons), `@` (append)
- Higher-order functions: `List.map`, `List.fold_left`
- Option types: `Some`, `None`
- Double semicolon `;;` statement separator

**Example syntax:**
```ocaml
let rec length lst =
  match lst with
  | [] -> 0
  | head :: tail -> 1 + length tail

let rec map f lst =
  match lst with
  | [] -> []
  | h :: t -> (f h) :: (map f t)
```

## Turing Completeness Proof Elements

Each language demonstrates Turing completeness through:

### 1. Conditional Execution
- **BASIC**: `IF...THEN...ELSE`
- **LISP**: `(if condition then else)`
- **Forth**: `IF...THEN...ELSE`
- **Pascal**: `IF...THEN...ELSE`
- **Ruby**: `if...elsif...else`
- **ML**: `if...then...else` and pattern matching

### 2. Iteration/Recursion
- **BASIC**: `FOR...NEXT`, `WHILE`
- **LISP**: `lambda` + recursion, `while`
- **Forth**: `BEGIN...UNTIL`, `DO...LOOP`
- **Pascal**: `FOR...TO`, `WHILE...DO`, `REPEAT...UNTIL`
- **Ruby**: `for`, `while`, `until`, `.each`
- **ML**: `let rec` recursive functions, `for`

### 3. Memory/Variables
- **BASIC**: `LET`, `DIM` (arrays)
- **LISP**: `let`, `define`, lists
- **Forth**: Stack + `VARIABLE`, `@`, `!`
- **Pascal**: `VAR`, `ARRAY`, pointers
- **Ruby**: Variables, instance variables, arrays
- **ML**: `let` bindings, lists, refs

### 4. Computation
- All languages support: `+`, `-`, `*`, `/`
- Comparison operators: `=`, `<`, `>`
- Logical operators: `AND`, `OR`, `NOT`

## Using These Configurations

### Load in the IDE
```bash
lashon-ide
# Then: File → Open and select a config, or use the Config panel
```

### Load Programmatically
```python
from lashon.config import LanguageConfig
from lashon.runtime import LanguageRuntime

# Load a configuration
config = LanguageConfig.load("configs/examples/lisp_like.yaml")
LanguageRuntime.load_config(config)

# Get info
print(LanguageRuntime.get_info())
```

### Validate Configuration
```bash
lashon validate configs/examples/forth_like.yaml
```

### Create Custom Variant
Start from any preset as a base:
```bash
lashon create --preset ruby_like --output my_custom.yaml
lashon edit my_custom.yaml          # opens in $EDITOR
```

## Computational Models

| Language | Model | Execution | Memory Model |
|----------|-------|-----------|--------------|
| BASIC-like | Imperative | Sequential | Variables, arrays |
| LISP-like | Functional | Expression evaluation | Lists, cons cells |
| Forth-like | Stack-based | Postfix/RPN | Stack + heap |
| Pascal-like | Structured | Block-based | Typed variables |
| Ruby-like | OO/Imperative | Method dispatch | Objects, closures |
| ML-like | Functional | Pattern matching | Immutable bindings |

## Extending These Languages

Each configuration can be extended with:
- Additional keywords
- Custom operators
- New built-in functions
- Modified syntax rules
- Different comment styles

Example:
```bash
# Create a variant and open it for editing
lashon create --preset basic_like --output my_basic.yaml
lashon edit my_basic.yaml

# Validate after editing
lashon validate my_basic.yaml
```

## Theoretical Background

### Church-Turing Thesis
All these languages can compute the same set of functions as a Turing machine, meaning they can:
- Compute any computable function
- Simulate any other Turing-complete system
- Solve the same class of problems

### Minimal Requirements
The simplest Turing-complete language needs only:
1. One register/variable
2. Increment/decrement operations
3. Conditional jump
4. Loop construct

All configurations here exceed these minimal requirements significantly.

## Educational Use

These configurations are useful for:
- **Language design studies**: Compare paradigms
- **Compiler courses**: Implement different execution models
- **Programming language theory**: Study expressiveness
- **Pedagogy**: Teach concepts in familiar syntax

## Performance Considerations

Note: These are language **definitions**, not implementations. Actual performance depends on:
- Interpreter/compiler implementation
- Optimization strategies
- Runtime environment
- Memory management approach

## References

- Turing, A.M. (1936). "On Computable Numbers"
- Church, A. (1936). "An Unsolvable Problem of Elementary Number Theory"
- Böhm, C. & Jacopini, G. (1966). "Flow Diagrams, Turing Machines and Languages with Only Two Formation Rules"

## License

These configuration files are examples for educational purposes. Adapt freely for your projects.
