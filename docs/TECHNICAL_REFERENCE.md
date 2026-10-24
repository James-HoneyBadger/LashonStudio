# Lashon — Technical Reference

API reference for `lashon` 5.0.0. Signatures are copied from the installed
package; examples are executed while writing this reference.

- Task-oriented usage: [USER_GUIDE.md](USER_GUIDE.md)
- Internals: [ARCHITECTURE.md](ARCHITECTURE.md)
- Grammar notation: [GRAMMAR_REFERENCE.md](GRAMMAR_REFERENCE.md)
- Backends: [CODEGEN_GUIDE.md](CODEGEN_GUIDE.md)

---

## Conventions

- `lashon` is importable after `pip install -e .`; tests use
  `pythonpath = ["src"]`.
- Type hints are shown as reported by `inspect.signature`.
- "Stable" means covered by tests and intended for use. "Experimental" means the
  API exists but behaviour may be incomplete (documented per class).
- Positions (`line`, `column`) are **1-based** unless an API says otherwise.

---

## Module map

| Package | Public exports |
|---|---|
| `lashon.parser` | `GrammarParser`, `GrammarBuilder`, `Grammar`, `GrammarRule`, `PEGNode`, `PEGNodeType`, `PEGInterpreter`, `SourceAST`, `IncrementalParser`, `grammar_from_config`, `Lexer`, `Parser`, `ParserGenerator`, `Token`, `TokenType`, `ASTNode`, `generate_parser` |
| `lashon.codegen` | `PythonTranspiler`, `TranspileOptions`, `transpile_to_python`, `transpile_and_exec`, `CCodeGenerator`, `CType`, `WasmGenerator`, `WasmModule`, `WasmType`, `WasmOp`, `LLVMIRGenerator` |
| `lashon.config` | `LanguageConfig`, `LanguageValidator`, `IdentifierValidator`, `KeywordMapping`, `FunctionConfig`, `OperatorConfig`, `SyntaxOptions`, `ParsingConfig`, `list_presets` |
| `lashon.runtime` | `REPL`, `StdLib`, `StdModule`, `StdFunction`, `StdConstant`, `FFIBridge`, `FFIBinding`, `LanguageRuntime`, `ModuleManager`, `ModuleLoader` (dataclasses `Module`, `ModuleImport`, `ModuleExport` live in `lashon.runtime.module_system`) |
| `lashon.tooling` | `ErrorLocalizer`, `ErrorMessage` (plus `lsp`, `debug`, `test_framework` submodules) |
| `lashon.types` | `Type`, `TypeKind`, `TypeChecker`, `TypeEnvironment`, `Protocol`, `ProtocolChecker`, `GenericType`, `TypeParameter`, `GenericChecker`, `GenericsTypeChecker`, `ProtocolTypeChecker`, `TypeNarrowingPass`, `ProtocolBinding`, `ProtocolTypeIntegration`, `TypeCompatibilityResult` |
| `lashon.ide` | `LashonIDE` (Studio shim), `CodeEditor`, `LineNumbers`, `Project`, `ProjectManager`; `LanguageStudio`/`StudioProject` live in `lashon.ide.studio` |
| `lashon.packaging` | `PackageRegistry`, `Package`, `DocumentationGenerator`; `Version` in `lashon.packaging.package_registry` |

---

## lashon.parser

### `GrammarParser`

```python
class GrammarParser:
    def parse(self, grammar_text: str, grammar_name: str = "custom") -> Grammar
```

Parses PEG text. Raises `ValueError` for malformed rules and `SyntaxError` from
nested parsers. `Grammar.validate()` reports semantic problems (undefined
references, left recursion, unsupported tokens).

```python
from lashon.parser import GrammarParser

grammar = GrammarParser().parse(
    'program <- statement+\n'
    'statement <- IDENT "=" NUMBER ";"'
)
print(grammar.start_rule)      # program
print(list(grammar.rules))     # ['program', 'statement']
```

### `Grammar`

```python
class Grammar(
    name: str = "custom",
    rules: Dict[str, GrammarRule] = {},
    start_rule: str = "program",
    skip_whitespace: bool = True,
    comment_patterns: List[str] = ["//.*", r"/\*[\s\S]*?\*/"],
):
    def add_rule(self, name: str, pattern: PEGNode, **kwargs) -> None
    def get_rule(self, name: str) -> Optional[GrammarRule]
    def validate(self) -> List[str]
```

`comment_patterns` are regular expressions matched at the current position;
empty matches are ignored so zero-width patterns cannot loop.

### `GrammarRule`

```python
@dataclass
class GrammarRule:
    name: str
    pattern: PEGNode
    description: str = ""
    is_fragment: bool = False   # produce no AST node; splice children
    node_type: str = ""         # AST node_type (defaults to name)
```

### `PEGNode` / `PEGNodeType`

```python
@dataclass
class PEGNode:
    node_type: PEGNodeType
    value: Any = None
    children: List[PEGNode] = []
    action: Optional[str] = None
    label: Optional[str] = None
```

`PEGNodeType`: `SEQUENCE`, `ORDERED_CHOICE`, `ZERO_OR_MORE`, `ONE_OR_MORE`,
`OPTIONAL`, `AND_PREDICATE`, `NOT_PREDICATE`, `LITERAL`, `CHAR_CLASS`,
`ANY_CHAR`, `RULE_REF`, `TOKEN_REF`, `ACTION`.

### `GrammarBuilder`

```python
class GrammarBuilder:
    def __init__(self, name: str = "custom")
    # fluent
    def rule(self, name: str, description: str = "") -> GrammarBuilder
    def set_pattern(self, pattern: PEGNode) -> GrammarBuilder
    def start(self, rule_name: str) -> GrammarBuilder
    def build(self) -> Grammar
    # static combinators
    def seq(*items: PEGNode) -> PEGNode
    def choice(*items: PEGNode) -> PEGNode
    def star(item: PEGNode) -> PEGNode
    def plus(item: PEGNode) -> PEGNode
    def opt(item: PEGNode) -> PEGNode
    def and_pred(item: PEGNode) -> PEGNode
    def not_pred(item: PEGNode) -> PEGNode
    def ref(rule_name: str) -> PEGNode
    def token(token_type: str) -> PEGNode
    def lit(text: str) -> PEGNode
    def char_class(pattern: str) -> PEGNode
    def any_char() -> PEGNode
    def ident() -> PEGNode
    def number() -> PEGNode
    def string() -> PEGNode
```

```python
from lashon.parser import GrammarBuilder as B

grammar = (
    B("mini")
    .rule("program").set_pattern(B.plus(B.ref("statement")))
    .rule("statement").set_pattern(B.seq(B.ident(), B.lit("="), B.ref("expr"), B.lit(";")))
    .rule("expr").set_pattern(B.choice(B.number(), B.ident()))
    .start("program")
    .build()
)
```

### `PEGInterpreter`

```python
class PEGInterpreter:
    def __init__(self, grammar: Grammar)
    def parse(self, source: str) -> SourceAST
    def parse_rule(self, rule_name: str, source: str) -> SourceAST
```

- `parse` requires full consumption (trailing whitespace allowed) and raises
  `SyntaxError("Parse error at line L, column C (in rule 'r'): ...")` or
  `SyntaxError("Unexpected input at line L, column C: ...")`.
- `parse_rule` parses `source` as one instance of `rule_name`; unknown rules
  raise `ValueError`.
- Memoisation is per-call (`self.memo` is cleared on each parse).

### `SourceAST`

```python
class SourceAST:
    def __init__(
        self,
        node_type: str,
        value: Any = None,
        children: List[SourceAST] = [],
        line: int = 0,
        column: int = 0,
        source_text: str = "",
    )
    def pretty(self, indent: int = 0) -> str
    def to_dict(self) -> Dict[str, Any]
```

Common `node_type` values: `program`, `statement`, `assignment`,
`function_def`, `param_list`, `block`, `if_stmt`, `while_stmt`, `return_stmt`,
`print_stmt`, `expr_stmt`, `call`, `expr`, `term`, `factor`, `comparison`,
`Number`, `String`, `Identifier`/`IDENT`, `Operator`.

### `IncrementalParser`

```python
class IncrementalParser:
    def __init__(self, grammar: Grammar, debounce_ms: int = 50)
    def parse(self, source: str) -> SourceAST
    def apply_edit(self, offset: int, old_len: int, new_text: str) -> SourceAST
    def apply_edits(self, edits: List[Tuple[int, int, str]]) -> SourceAST
    def invalidate(self) -> None
    def reset(self) -> None
    @property
    def ast(self) -> Optional[SourceAST]
    @property
    def source(self) -> str
    @property
    def stats(self) -> Dict[str, Any]
```

`stats` keys: `total_parses`, `incremental`, `full_reparse`, `last_parse_ms`.
Edits at region boundaries fall back to a full parse; parse failures keep the
previous AST.

### `grammar_from_config`

```python
def grammar_from_config(config_dict: Dict[str, Any]) -> Grammar
```

Builds a `Grammar` from a raw config dict's `grammar.rules`, `start`,
`skip_whitespace`, and `comments`. Returns the default grammar when
`grammar.rules` is missing. Note that `LanguageConfig` deliberately does not
model the grammar section — pass the raw YAML/JSON dict.

### Tokenizer/parser generator helpers

```python
class Lexer:
    def __init__(self, config: LanguageConfig)
    def tokenize(self, source: str) -> List[Token]

class Parser:
    def __init__(self, config: LanguageConfig, tokens: List[Token])
    def parse(self) -> ASTNode

class ParserGenerator:
    def __init__(self, config: LanguageConfig)
    def parse(self, source: str) -> Tuple[List[Token], ASTNode]
    def generate_parser_code(self) -> str
    def visualize_tokens(self, tokens: List[Token]) -> str
    def visualize_ast(self, ast: ASTNode, indent: int = 0) -> str
    def ast_to_json(self, ast: ASTNode) -> str

def generate_parser(config: LanguageConfig) -> ParserGenerator
```

These are config-driven (keyword-based) and independent of the PEG engine.

---

## lashon.codegen

### `PythonTranspiler`

```python
class PythonTranspiler:
    def __init__(self, options: Optional[TranspileOptions] = None)
    def translate_source_ast(self, ast: SourceAST) -> str
    def transpile(self, ast: SourceAST) -> str            # alias
    def transpile_expression(self, ast: SourceAST) -> str
```

### `TranspileOptions`

| Field | Type | Default |
|---|---|---|
| `indent_str` | `str` | `"    "` |
| `keyword_map` | `Dict[str,str]` | `{}` |
| `function_map` | `Dict[str,str]` | `{}` |
| `operator_map` | `Dict[str,str]` | `{}` |
| `inject_runtime` | `bool` | `False` |
| `source_maps` | `bool` | `False` (reserved, no effect) |
| `wrap_in_main` | `bool` | `False` |

### Module functions

```python
def transpile_to_python(
    ast: SourceAST,
    keyword_map: Optional[Dict[str, str]] = None,
    function_map: Optional[Dict[str, str]] = None,
) -> str

def transpile_and_exec(
    ast: SourceAST,
    keyword_map: Optional[Dict[str, str]] = None,
    function_map: Optional[Dict[str, str]] = None,
    globals_dict: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]
```

`transpile_and_exec` returns the namespace minus dunder keys.

### `CCodeGenerator`

```python
class CCodeGenerator:
    def __init__(self, config: Any = None)
    def translate_source_ast(self, ast: Any) -> str
    def generate(self, _ast: Dict[str, Any], output_file: str = "output.c") -> str

    # string builders
    def add_include(self, header: str) -> None
    def indent(self) -> str
    def gen_temp_var(self, _c_type: str = "int") -> str
    def gen_assignment(self, target: str, value: str) -> str
    def gen_binary_op(self, left: str, op: str, right: str) -> str
    def gen_function_call(self, func_name: str, args: List[str]) -> str
    def gen_if(self, condition: str, true_body: List[str],
               false_body: Optional[List[str]] = None) -> str
    def gen_loop(self, init: str, condition: str, increment: str,
                 body: List[str]) -> str
    def gen_while(self, condition: str, body: List[str]) -> str
    def gen_printf(self, format_str: str, args: Optional[List[str]] = None) -> str
    def gen_return(self, value: Optional[str] = None) -> str
    def gen_variable_declare(self, name: str, c_type: str,
                             value: Optional[str] = None) -> str
    def generate_header(self) -> str
    def generate_implementations(self) -> str
    def generate_main(self) -> str
    def translate_type(self, lang_type: str) -> str
```

### `WasmGenerator`

```python
class WasmGenerator:
    def __init__(self) -> None
    def translate_source_ast(self, ast: Any) -> WasmModule
    def generate_from_ast(self, ast: Any, _config: Any = None) -> WasmModule
    def translate_type(self, lang_type: str) -> WasmType
    def generate_binary_op(self, op: str, left_type: WasmType,
                           _right_type: WasmType) -> str
    def generate_if(self, condition: str, then_body: List[str],
                    else_body: Optional[List[str]] = None) -> List[str]
    def generate_loop(self, condition: str, body: List[str]) -> List[str]
    def generate_memory_load(self, address: int, wasm_type: WasmType,
                             offset: int = 0) -> str
    def generate_memory_store(self, address: int, wasm_type: WasmType,
                              offset: int = 0) -> str
    def gen_temp_var(self) -> str
```

`WasmModule.to_wat()` returns WAT text; `WasmModule.save(path)` writes it.
AST translation emits functions, locals, calls, `if`/`else`, `while`,
returns, and integer/string prints using the documented host imports.

### `LLVMIRGenerator`

```python
class LLVMIRGenerator:
    def __init__(self)
    def translate_source_ast(self, ast: Any) -> str
    def save(self, filename: str) -> None
```

Emits SSA IR with `alloca` locals, i1 comparisons, `printf` calls, function
definitions, and calls. Undefined identifiers produce comments and the constant
`0`.

---

## lashon.config

### `LanguageConfig`

```python
class LanguageConfig:
    def __init__(
        self,
        name: str = "Custom Language",
        version: str = "3.0.0",
        description: str = "A customizable programming language",
        author: str = "",
        target_interpreter: str = "python",
        keyword_mappings: dict[str, KeywordMapping] = {},
        builtin_functions: dict[str, FunctionConfig] = {},
        operators: dict[str, OperatorConfig] = {},
        syntax_options: SyntaxOptions = SyntaxOptions(),
        parsing_config: ParsingConfig = ParsingConfig(),
        debug_mode: bool = False,
        strict_mode: bool = False,
        compatibility_mode: str = "standard",
    )
```

Class/classmethod-style API:

```python
LanguageConfig.load(filepath) -> LanguageConfig
LanguageConfig.from_dict(data) -> LanguageConfig
LanguageConfig.from_json(text) -> LanguageConfig
LanguageConfig.from_preset(name) -> LanguageConfig
LanguageConfig.load_preset(name) -> LanguageConfig     # alias-ish
```

Instance API:

| Method | Effect |
|---|---|
| `add_keyword(name, category="custom", description="")` | add keyword mapping |
| `rename_keyword(original, new_name)` | change the custom spelling |
| `remove_keyword(name)` / `delete_keyword(keyword)` | remove |
| `add_function(name, alias_or_arity=None, implementation=None, description="", min_args=-1, max_args=-1)` | add function mapping |
| `rename_function(original, new_name)` / `remove_function(name)` / `delete_function(function_name)` | edit functions |
| `delete_operator(operator_symbol)` | remove operator |
| `set_comment_style(single_line="//", multi_start=None, multi_end=None)` | comments |
| `set_array_indexing(start_index, allow_fractional=True)` | indexing rules |
| `enable_feature(feature, enabled=True)` | feature flag (raises `ValueError` for unknown features) |
| `disable_satirical_keywords()` | turn off joke keywords |
| `merge(other, prefer_other=True)` | merge configs |
| `clone()` | deep copy |
| `update(updates, merge=True)` | dict-style update |
| `validate()` | hard errors (`list[str]`) |
| `validation_warnings()` | non-fatal warnings (duplicate aliases) |
| `export_mapping_table(filepath=None)` | human-readable mapping table |
| `to_dict()`, `to_json()`, `to_yaml()` | serialise |
| `save(filepath, fmt="auto")` | write YAML/JSON |

`save` picks format from the extension when `fmt="auto"`.

### Config dataclasses

```python
@dataclass
class KeywordMapping:    original: str; custom: str; category: str; description: str
@dataclass
class FunctionConfig:    name: str; arity: int; implementation: str; description: str
                         enabled: bool; min_args: int; max_args: int; alias: str
@dataclass
class OperatorConfig:    symbol: str; precedence: int; associativity: str; enabled: bool
```

`SyntaxOptions` fields: `array_start_index`, `allow_fractional_indexing`,
`flexible_quoting`, `string_interpolation`, `interpolation_symbol`,
`single_line_comment`, `multi_line_comment_start`, `multi_line_comment_end`,
`require_semicolons`, `statement_terminator`, `three_valued_logic`,
`probabilistic_variables`, `temporal_variables`, `enable_satirical_keywords`,
`enable_quantum_features`, `enable_time_travel`, `enable_gaslighting`.

`ParsingConfig` fields: delimiters and separators for blocks, lists, tuples,
dicts, statements, parameters, key/value pairs, strings, escapes,
member/index/call access, `if`/`else`/`elif` keywords, function parameter
syntax, return type separator, class inheritance/body, import syntax, and
`allow_custom_operators`/`allow_operator_overloading`.

### `LanguageValidator`

```python
class LanguageValidator:
    def __init__(self, config: LanguageConfig)
    def validate_all(self) -> List[ValidationIssue]
    def check_completeness(self) -> None
    def check_keyword_conflicts(self) -> None
    def check_function_conflicts(self) -> None
    def check_operator_precedence(self) -> None
    def check_naming_conventions(self) -> None
    def check_reserved_words(self) -> None
    def check_syntax_ambiguities(self) -> None
    def get_issues_by_severity(self, severity: str) -> List[ValidationIssue]
    def get_issues_by_category(self, category: str) -> List[ValidationIssue]
    def has_errors(self) -> bool
    def has_warnings(self) -> bool
    def generate_report(self) -> str
```

### `IdentifierValidator`

```python
class IdentifierValidator:
    def is_valid_identifier(name: str) -> bool
    def is_python_reserved(name: str) -> bool
    def is_valid_length(name: str, min_len: int = 1, max_len: int = 255) -> bool
    def detect_naming_style(name: str) -> str | None
    def suggest_name(invalid_name: str, style: str = "snake_case") -> str
    def validate_identifier(
        name: str,
        reserved_set: set[str] | None = None,
        allow_reserved: bool = False,
        min_length: int = 1,
        max_length: int = 255,
        allow_symbols: bool = False,
    ) -> Tuple[bool, List[str]]
```

### Presets

`python_like`, `js_like`, `minimal`, `ruby_like`, `golang_like`, `rust_like`,
`clike`, `functional`, `lisp_like`, `basic_like`.

---

## lashon.runtime

### `REPL`

```python
class REPL:
    def __init__(self, grammar: Optional[Grammar] = None,
                 transpile_options: Optional[TranspileOptions] = None,
                 prompt: str = ">>> ", continue_prompt: str = "... ")
    def run(self) -> None
    def eval_line(self, source: str) -> str
    def eval_lines(self, sources: list[str]) -> dict[str, Any]
```

`eval_line` returns captured stdout/stderr; `eval_lines` returns the filtered
namespace.

### `StdLib`

```python
class StdLib:
    def register_builtins(self) -> None
    def add_builtin(self, name: str, value: Any) -> None
    def add_module(self, module: StdModule) -> None
    def get_module(self, name: str) -> Optional[StdModule]
    def list_modules(self) -> List[str]
    def list_builtins(self) -> List[str]
    def inject(self, namespace: Dict[str, Any]) -> Dict[str, Any]
    def inject_module(self, module_name: str, namespace: Dict[str, Any],
                      symbols: Optional[List[str]] = None) -> Dict[str, Any]
```

`inject` adds builtins only; call `register_builtins()` first. Module and symbol
tables: [RUNTIME_GUIDE.md](RUNTIME_GUIDE.md#standard-library).

### `FFIBridge`

```python
class FFIBridge:
    def load_library(self, name: str, path: Optional[str] = None) -> FFILibrary
    def unload_library(self, name: str) -> None
    def bind(self, name: str, library: str, native_name: Optional[str] = None,
             arg_types: Optional[List[str]] = None, return_type: str = "int",
             doc: str = "") -> FFIBinding
    def register_python(self, name: str, func: Callable, doc: str = "") -> FFIBinding
    def import_python_module(self, module_name: str,
                             functions: Optional[List[str]] = None,
                             prefix: str = "") -> List[FFIBinding]
    def call(self, name: str, *args: Any) -> Any
    def get_binding(self, name: str) -> Optional[FFIBinding]
    def list_bindings(self) -> List[str]
    def list_libraries(self) -> List[str]
    def inject(self, namespace: Dict[str, Any]) -> Dict[str, Any]
    def describe(self) -> str
```

`bind` raises `KeyError` if the library was not loaded. Type names come from
`lashon.runtime.ffi.CTYPE_MAP`.

### `LanguageRuntime`

Singleton (classmethod API):

```python
LanguageRuntime.load_config(config=None, config_file=None) -> None
LanguageRuntime.translate_keyword(text) -> str
LanguageRuntime.translate_function(name) -> str
LanguageRuntime.get_custom_keywords() -> list[str]
LanguageRuntime.get_custom_functions() -> list[str]
LanguageRuntime.get_info() -> str
LanguageRuntime.is_feature_enabled(feature) -> bool
LanguageRuntime.should_enforce_semicolons() -> bool
LanguageRuntime.get_array_start_index() -> int
LanguageRuntime.get_comment_syntax() -> tuple[str, Optional[str], Optional[str]]
LanguageRuntime.reset() -> None
LanguageRuntime.get_instance() -> LanguageRuntime
```

`get_custom_functions()` returns the custom names (not the Python targets).
`load_config` prints a confirmation line.

### `ModuleManager`

```python
class ModuleManager:
    def __init__(self, config: Any, search_paths: Optional[List[str]] = None,
                 enable_caching: bool = True)
    def load_module(self, module_name: str,
                    search_relative_to: Optional[Path] = None) -> Optional[Module]
    def load_with_dependencies(self, module_name: str) -> Dict[str, Module]
    def resolve_dependencies(self, module_name: str) -> List[str]
    def detect_circular_dependencies(self) -> List[Tuple[str, str]]
    def get_module_info(self, module_name: str) -> Dict[str, Any]
    def export_dependency_graph(self, output_file: str) -> None
```

`Module` exposes `name`, `version`, `author`, `description`, `dependencies`,
`exports`, `metadata`, `hash`, plus `get_exports()`.
`ModuleImport` carries `module_name`, `alias`, `selected`, `version_constraint`,
`optional`. `ModuleExport` carries `name`, `kind`, `visibility`, `type_hint`,
`documentation`, `defined_at`, `metadata`.

---

## lashon.tooling

### `ErrorLocalizer`

```python
class ErrorLocalizer:
    def __init__(self, locale: str = "en")
    def format(self, code: str, **kwargs: Any) -> str
    def format_with_context(self, code: str, source: str = "", line: int = 0,
                            col: int = 0, filename: str = "<input>",
                            **kwargs: Any) -> str
    def register_error(self, code: str, severity: str, template: str,
                       category: str = "custom") -> None
    def set_locale(self, locale: str) -> None
    def load_translations(self, translations: Dict[str, str],
                          locale: Optional[str] = None) -> None
    def load_translations_file(self, path: str,
                               locale: Optional[str] = None) -> None
    def available_locales(self) -> List[str]
    def list_codes(self, category: Optional[str] = None) -> List[str]
    def get_severity(self, code: str) -> str
```

Catalog and behaviour: [LSP_AND_DEBUGGING.md](LSP_AND_DEBUGGING.md#localized-errors).

### LSP

```python
class LSPServer:
    def __init__(self, config: LanguageConfig)
    def initialize(self, root_path: Optional[str] = None) -> dict
    def handle_did_open(self, uri: str, content: str) -> None
    def handle_did_change(self, uri: str, changes: list[dict], version: int) -> None
    def handle_did_close(self, uri: str) -> None
    def completions(self, uri: str, position: Position) -> list[dict]
    def hover(self, uri: str, position: Position) -> Optional[dict]
    def signature_help(self, uri: str, position: Position) -> Optional[dict]
    def document_symbols(self, uri: str) -> list[dict]
    def format_document(self, uri: str) -> list[dict]
    def run_stdio(self) -> None
```

`Position` comes from `lashon.tooling.lsp.lsp_server`. Stdio serves a
subset — see [LSP_AND_DEBUGGING.md](LSP_AND_DEBUGGING.md#protocol-coverage).

### Debugging

```python
class Debugger:
    def __init__(self, program_path: str)
    def start(self) -> None
    def set_breakpoint(self, source_path: str, line: int, column: int = 1,
                       condition: Optional[str] = None) -> Breakpoint
    def remove_breakpoint(self, bp_id: int) -> bool
    def hit_breakpoint(self, source_path: str, line: int) -> Optional[Breakpoint]
    def evaluate_expression(self, expression: str, frame_id: int) -> Optional[str]
    def get_stack_trace(self) -> List[StackFrame]
    def get_variables(self, frame_id: int) -> List[Variable]
    def add_variable(self, frame_id: int, var: Variable) -> None
    def step_over(self) -> None
    def pause(self) -> None
    def continue_execution(self) -> None
```

`Variable(name, value, var_type, indexed_variables=None, named_variables=None,
memory_reference=None)`. `DebugAdapter(debugger)` exposes DAP-shaped handling.

### Test framework

`lashon.tooling.test_framework` provides `TestCase` and
`LanguageTestRunner`; `lashon test` uses it with a YAML/JSON case file, and
`test-run` is a placeholder.

---

## lashon.types

### `Type` / `TypeKind`

```python
@dataclass
class Type:
    kind: TypeKind
    name: str = ""
    type_args: List[Type] = []
    nullable: bool = False
    metadata: Dict[str, Any] = {}

    def is_compatible_with(self, other: Type) -> bool
    @staticmethod
    def int() -> Type
    @staticmethod
    def float() -> Type
    @staticmethod
    def str() -> Type
    @staticmethod
    def bool() -> Type
    @staticmethod
    def list(element_type: Type) -> Type
    @staticmethod
    def dict(key_type: Type, value_type: Type) -> Type
    @staticmethod
    def optional(inner: Type) -> Type
    @staticmethod
    def union(*types: Type) -> Type
```

`TypeKind`: `UNKNOWN`, `NONE`, `BOOL`, `INT`, `FLOAT`, `STR`, `LIST`, `DICT`,
`TUPLE`, `SET`, `CALLABLE`, `CLASS`, `UNION`, `OPTIONAL`, `GENERIC`, `ANY`.

### `TypeEnvironment`

```python
class TypeEnvironment:
    def __init__(self, variables: Dict[str, Type] = {},
                 functions: Dict[str, TypeSignature] = {},
                 classes: Dict[str, ClassType] = {},
                 parent: Optional["TypeEnvironment"] = None)
    def define_variable(self, name: str, type_: Type) -> None
    def get_variable_type(self, name: str) -> Optional[Type]
    def define_function(self, name: str, signature: TypeSignature) -> None
    def get_function_signature(self, name: str) -> Optional[TypeSignature]
    def create_child_scope(self) -> "TypeEnvironment"
```

### `TypeChecker`

```python
class TypeChecker:
    def __init__(self, language_config: Any,
                 level: AnalysisLevel = AnalysisLevel.MODERATE)
    def check_file(self, file_path: str) -> List[TypeError]
    def check_expression(self, expr: str, environment: TypeEnvironment) -> Type
    def check_assignment(self, target: str, source: str,
                         environment: TypeEnvironment,
                         line: int = 0, location: str = "") -> bool
    def check_function_definition(self, func_name: str,
                                  params: List[Tuple[str, Optional[str]]],
                                  return_type_str: Optional[str],
                                  environment: TypeEnvironment) -> None
    def get_type_error_summary(self) -> str
```

`AnalysisLevel`: `LENIENT`, `MODERATE`, `STRICT`, `VERY_STRICT`. Behaviour and
limits: [TYPE_SYSTEM.md](TYPE_SYSTEM.md).

### Generics, protocols, narrowing

```python
class GenericChecker:
    def check_constraint(self, type_param: TypeParameter, concrete_type: str) -> bool
    def infer_type_arguments(self, generic_func: GenericFunction,
                             actual_args: Dict[str, str]) -> Optional[Dict[str, str]]
    def validate_generic_class(self, generic_class: GenericClass) -> List[str]
    def check_generic_assignment(self, source: GenericType,
                                 target: GenericType) -> bool

class GenericsTypeChecker:
    def __init__(self, config: Any = None)
    def check_file(self, file_path: str) -> List[str]
    def check_generic_class(self, class_name: str, type_params: List[str],
                            class_def: Any) -> List[str]
    def check_generic_function(self, func_name: str, type_params: List[str],
                               func_def: Any) -> List[str]
    def check_generic_instantiation(self, generic_name: str,
                                    type_args: List[str]) -> Tuple[bool, List[str]]
    def check_variance(self, generic_name: str, position: int,
                       variance: Variance) -> Tuple[bool, str]
    def infer_type_arguments(self, generic_name: str,
                             actual_args: List[Type]) -> Tuple[List[str], List[str]]

class ProtocolChecker:
    def register_protocol(self, protocol: Protocol) -> None
    def conforms_to_protocol(self, struct_type: StructuralType | Dict[str, Any],
                             protocol: Protocol) -> bool
    def structural_compatible(self, source_type: StructuralType,
                              target_type: StructuralType) -> bool
    def find_matching_protocols(self, struct_type: StructuralType) -> List[str]
    def extract_structural_type(self, source: str) -> StructuralType
    def check_protocol_composition(self, protocol_names: List[str]) -> List[str]

class TypeNarrowingPass:
    def narrow_by_isinstance(self, var_name: str, type_name: str) -> None
    def narrow_by_comparison(self, var_name: str, op: str, value: Any) -> None
    def narrow_by_truthiness(self, var_name: str) -> None
    def get_narrowed_type(self, var_name: str) -> Optional[Type]
```

`GenericType(name, parameters, arguments)`, `TypeParameter(name, constraint=None,
bound=None, variance=Variance.INVARIANT, default=None)`, `Protocol(name,
methods={}, properties={}, extends=[], is_generic=False)`,
`StructuralType(methods={}, properties={})`,
`MethodSignature(name, return_type, parameter_types=[], is_optional=False)`,
`PropertyDef(name, type_, is_readonly=False, is_optional=False)`.

---

## lashon.ide

### `LanguageStudio` (headless controller)

```python
class LanguageStudio:
    def __init__(self, project: Optional[StudioProject] = None)
    def new_project(self, name: str, parent_dir: str | Path) -> StudioProject
    def open_project(self, path: str | Path) -> StudioProject
    def open_sample_project(self) -> StudioProject
    @staticmethod
    def sample_project_path() -> Optional[Path]
    def save_project(self) -> None
    def set_config(self, config: Dict[str, Any]) -> None
    def set_grammar_text(self, text: str) -> None
    def invalidate_grammar(self) -> None
    def validate_grammar(self, text: Optional[str] = None) -> StudioResult
    def parse(self, source: Optional[str] = None) -> StudioResult
    def transpile(self, source: Optional[str] = None) -> StudioResult
    def run(self, source: Optional[str] = None) -> StudioResult
    def generate(self, backend: str, source: Optional[str] = None) -> StudioResult
    def generate_all(self, source: Optional[str] = None) -> Dict[str, StudioResult]
    def ast_tree(self, ast: SourceAST) -> List[dict]
    def highlight_keywords(self) -> List[str]
```

### `StudioProject`, `StudioResult`, `Diagnostic`

```python
class StudioProject:
    def __init__(self, name: str, root: Path, config_path: Path,
                 config: Dict[str, Any], grammar_text: str,
                 sample_path: Optional[Path] = None)
    @classmethod
    def from_path(cls, path: str | Path) -> "StudioProject"
    def language_config(self) -> LanguageConfig
    def sample_files(self) -> List[Path]
    def summary(self) -> Dict[str, Any]
    def save(self) -> None

@dataclass
class StudioResult:
    ok: bool
    text: str = ""
    error: str = ""
    diagnostics: List[Diagnostic] = []
    elapsed_ms: float = 0.0
    value: Any = None
    supported: bool = True
    warnings: List[str] = []

@dataclass
class Diagnostic:
    severity: str
    message: str
```

Helpers: `rules_to_peg(rules) -> str`, `peg_to_rules(text) -> Dict[str, str]`.

### Studio GUI and legacy classes

`LashonIDE(project=None, source=None)` is the Tkinter application exported
by `lashon.ide` (implementation in `lashon.ide.studio_app`).

```python
class Project:
    def __init__(self, name="Untitled Language", root_dir="", config_path="",
                 source_files=[], config={}, grammar_text="")
    def add_source_file(self, path: str, content: str = "") -> ProjectFile
    def get_keywords(self) -> List[str]
    def save(self, path: Optional[str] = None) -> None

class ProjectManager:
    def __init__(self, workspace_dir: str = "")
    def create_project(self, name: str, directory: str,
                       preset: str = "python_like") -> Project
    def open_project(self, path: str) -> Project
```

`CodeEditor(parent, keywords=None, colors=None, **kwargs)` adds
`set_text/get_text/highlight_syntax/mark_error/clear_errors/set_keywords/
on_change` over `tk.Text`; `LineNumbers(parent, text_widget)` provides `redraw()`.

---

## lashon.packaging

### `Package`, `Version`, `VersionConstraint`

```python
@dataclass
class Package:
    name: str
    version: Version
    description: str = ""
    author: str = ""
    license: str = "MIT"
    dependencies: Dict[str, str] = {}
    dev_dependencies: Dict[str, str] = {}
    path: Optional[Path] = None
    published_at: Optional[datetime] = None
    integrity: Optional[str] = None
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Package"
    def to_dict(self) -> Dict[str, Any]

class Version:
    @staticmethod
    def parse(version_str: str) -> "Version"
    # attributes: major, minor, patch, prerelease, metadata

class VersionConstraint:
    @staticmethod
    def parse(constraint_str: str) -> "VersionConstraint"
    def satisfies(self, version: Version) -> bool
```

### `PackageRegistry`

```python
class PackageRegistry:
    def register_package(self, package: Package) -> None
    def register_local(self, directory: Path | str) -> None
    def resolve(self, name: str, constraint: str) -> Optional[Package]
    def resolve_dependencies(self, package: Package,
                             include_dev: bool = False) -> Dict[str, Package]
    def check_conflicts(self, resolved: Dict[str, Package]) -> List[str]
    def create_lock_file(self, resolved: Dict[str, Package]) -> Dict[str, Any]
    def load_lock_file(self, lock_file: Path | str) -> Dict[str, Package]
```

### `DocumentationGenerator` and extension generation

```python
class DocumentationGenerator:
    def generate_markdown(config: LanguageConfig) -> str
    def generate_html(config: LanguageConfig) -> str
    def save_markdown(config: LanguageConfig, filepath: str) -> None
    def save_html(config: LanguageConfig, filepath: str) -> None

def generate_vscode_extension(
    config: LanguageConfig,
    output_dir: str = ".vscode-ext",
    publisher: str = "lashon",
    version: str = "0.0.1",
) -> None

def generate_simple_grammar(config: LanguageConfig,
                            output_file: str = "grammar.txt") -> None
```

Generated file list and follow-up steps:
[PACKAGING.md](PACKAGING.md#vs-code-extension).

---

## Compatibility notes

| Area | Guarantee |
|---|---|
| `SourceAST` shape | rule nodes carry `node_type`, `children`, `line`, `column`, `source_text`; scalars use `value` |
| Backends | `translate_source_ast(ast)` exists on all four; WASM returns `WasmModule` |
| Config | YAML/JSON load, `validate`, `save` are stable; unknown fields are ignored |
| REPL | `REPL.eval_line`/`eval_lines` are the stable embedding API |
| CLI | commands and flags are additive; placeholders documented in [CLI_REFERENCE.md](CLI_REFERENCE.md) |
| Internals | `_`-prefixed members may change without notice |
