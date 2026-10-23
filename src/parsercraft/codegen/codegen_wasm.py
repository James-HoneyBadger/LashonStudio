#!/usr/bin/env python3
"""
WebAssembly (WASM) Backend for ParserCraft

Translates a SourceAST (produced by the PEG grammar engine) into WebAssembly
Text Format (WAT) for web deployment or WASM runtime execution.

Features:
    - SourceAST → WAT generation for top-level assignments, expressions, and
      calls inside the generated ``main`` function
    - WASM type mapping: i32, i64, f32, f64
    - Module/function import/export registration
    - WasmModule builder with to_wat() serialisation

Current limitation: user-defined function bodies (``fn``/``function_def``),
branches, loops, and print statements are not translated into WAT yet, so
output for such programs is incomplete. The class API (``generate_if``,
``generate_loop``, ``generate_binary_op``) can be used to build instructions
manually.

Primary API:
    from parsercraft.codegen.codegen_wasm import WasmGenerator

    gen = WasmGenerator()
    module = gen.translate_source_ast(ast)  # SourceAST from grammar engine
    wat_text = module.to_wat()

    # Lower-level entry point with optional config:
    module = gen.generate_from_ast(ast, config)

WASM Types:
    - i32: 32-bit integer
    - i64: 64-bit integer
    - f32: 32-bit float
    - f64: 64-bit float
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class WasmType(Enum):
    """WebAssembly primitive types."""

    I32 = "i32"  # 32-bit integer
    I64 = "i64"  # 64-bit integer
    F32 = "f32"  # 32-bit float
    F64 = "f64"  # 64-bit float


class WasmOp(Enum):
    """Common WebAssembly operations."""

    # Arithmetic
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div_s"  # signed division
    REM = "rem_s"  # signed remainder

    # Logic
    AND = "and"
    OR = "or"
    XOR = "xor"
    SHL = "shl"
    SHR_U = "shr_u"  # unsigned shift right

    # Comparison
    EQ = "eq"
    NE = "ne"
    LT_S = "lt_s"  # signed less than
    GT_S = "gt_s"  # signed greater than
    LE_S = "le_s"  # signed less than or equal
    GE_S = "ge_s"  # signed greater than or equal

    # Memory
    LOAD = "load"
    STORE = "store"

    # Control flow
    BR = "br"  # branch
    BR_IF = "br_if"  # branch if
    IF = "if"
    ELSE = "else"
    END = "end"
    LOOP = "loop"
    BLOCK = "block"
    RETURN = "return"
    CALL = "call"


@dataclass
class WasmLocal:
    """Local variable in WASM function."""

    name: str
    wasm_type: WasmType
    mutable: bool = True

    def to_wat(self) -> str:
        """Convert to WAT format."""
        return f"(local ${self.name} {self.wasm_type.value})"


@dataclass
class WasmFunction:
    """WebAssembly function."""

    name: str
    params: List[Tuple[str, WasmType]] = field(default_factory=list)
    return_type: Optional[WasmType] = None
    locals: List[WasmLocal] = field(default_factory=list)
    body: List[str] = field(default_factory=list)  # WAT instructions
    is_export: bool = False

    def to_wat(self) -> str:
        """Convert to WAT format."""
        lines = []

        # Function signature
        func_sig = f"(func ${self.name}"

        # Parameters
        for param_name, param_type in self.params:
            func_sig += f" (param ${param_name} {param_type.value})"

        # Return type
        if self.return_type:
            func_sig += f" (result {self.return_type.value})"

        # Export if needed
        if self.is_export:
            lines.append(f"(export \"{self.name}\" (func ${self.name}))")

        lines.append(func_sig)

        # Locals
        for local in self.locals:
            lines.append(f"  {local.to_wat()}")

        # Body
        for instruction in self.body:
            lines.append(f"  {instruction}")

        lines.append(")")

        return "\n".join(lines)


@dataclass
class WasmImport:
    """Imported function from JavaScript."""

    module: str
    name: str
    params: List[Tuple[str, WasmType]] = field(default_factory=list)
    return_type: Optional[WasmType] = None

    def to_wat(self) -> str:
        """Convert to WAT format."""
        sig = f"(func ${self.name}"

        for param_name, param_type in self.params:
            sig += f" (param ${param_name} {param_type.value})"

        if self.return_type:
            sig += f" (result {self.return_type.value})"

        sig += ")"

        return f'(import "{self.module}" "{self.name}" {sig})'


class WasmModule:
    """WebAssembly module builder."""

    def __init__(self, name: str = "module"):
        self.name = name
        self.functions: Dict[str, WasmFunction] = {}
        self.imports: Dict[str, WasmImport] = {}
        self.memory_size = 256  # Pages (256 * 64KB = 16MB)
        self.data_segment: Dict[int, bytes] = {}  # address -> data

    def add_function(self, func: WasmFunction) -> None:
        """Add function to module."""
        self.functions[func.name] = func

    def add_import(self, imp: WasmImport) -> None:
        """Add imported function."""
        self.imports[imp.name] = imp

    def add_data(self, address: int, data: bytes) -> None:
        """Add data segment."""
        self.data_segment[address] = data

    def set_memory_size(self, pages: int) -> None:
        """Set memory size in pages (64KB each)."""
        self.memory_size = pages

    def to_wat(self) -> str:
        """Convert module to WAT format."""
        lines = [f"(module ${self.name}"]

        # Imports must precede memory and function definitions.
        for imp in self.imports.values():
            lines.append(f"  {imp.to_wat()}")

        # Memory (exported so hosts can read string data)
        lines.append(f"  (memory {self.memory_size})")
        lines.append('  (export "memory" (memory 0))')

        # Functions
        for func in self.functions.values():
            for line in func.to_wat().split("\n"):
                lines.append(
                    f"  {line}"
                    if line and not line.startswith("(export")
                    else line
                )

        # Data segments
        for address, data in self.data_segment.items():
            escaped = "".join(
                chr(byte)
                if 32 <= byte < 127 and byte not in (34, 92)
                else f"\\{byte:02x}"
                for byte in data
            )
            lines.append(f'  (data (i32.const {address}) "{escaped}")')

        lines.append(")")

        return "\n".join(lines)

    def save(self, filename: str) -> None:
        """Save module as WAT file."""
        with open(filename, "w", encoding="utf-8") as f:
            f.write(self.to_wat())


class WasmGenerator:
    """Generates WebAssembly from custom language AST."""

    def __init__(self) -> None:
        self.module = WasmModule()
        self.type_mapping = {
            "int": WasmType.I32,
            "float": WasmType.F32,
            "bool": WasmType.I32,
        }
        self.var_count = 0
        self._locals: List[WasmLocal] = []
        self._instructions: List[str] = []
        self._local_index: Dict[str, int] = {}

    def translate_type(self, lang_type: str) -> WasmType:
        """Translate language type to WASM type."""
        return self.type_mapping.get(lang_type, WasmType.I32)

    def gen_temp_var(self) -> str:
        """Generate unique temporary variable name."""
        self.var_count += 1
        return f"$temp{self.var_count}"

    def generate_from_ast(self, ast: Any, _config: Any = None) -> WasmModule:
        """Generate WASM module from AST."""
        # This is a framework — actual AST traversal depends on
        # language definition
        # For now, show structure of how it would work

        # Add memory
        self.module.set_memory_size(256)

        # Process function definitions from AST
        if hasattr(ast, "functions"):
            for func_def in ast.functions:
                wasm_func = self._generate_function(func_def)
                if wasm_func:
                    self.module.add_function(wasm_func)

        # Add standard library imports
        self._add_stdlib_imports()

        return self.module

    def _generate_function(self, func_def: Any) -> Optional[WasmFunction]:
        """Generate WASM function from function definition."""
        if not hasattr(func_def, "name"):
            return None

        # Map parameters
        params = []
        if hasattr(func_def, "params"):
            for param in func_def.params:
                param_type = self.translate_type(getattr(param, "type", "int"))
                params.append((getattr(param, "name", "arg"), param_type))

        # Map return type
        return_type = None
        if hasattr(func_def, "return_type"):
            return_type = self.translate_type(func_def.return_type)

        # Generate body
        body = []
        if hasattr(func_def, "body"):
            body = self._generate_body(func_def.body)

        func = WasmFunction(
            name=func_def.name,
            params=params,
            return_type=return_type,
            body=body,
            is_export=getattr(func_def, "is_export", False),
        )

        return func

    def _generate_body(self, statements: List[Any]) -> List[str]:
        """Generate WASM instructions from statements."""
        instructions = []

        for stmt in statements:
            if hasattr(stmt, "type"):
                if stmt.type == "return":
                    # Return statement
                    instructions.append("return")
                elif stmt.type == "assignment":
                    # Variable assignment
                    instructions.append(f"(local.set ${stmt.target} ...)")
                elif stmt.type == "call":
                    # Function call
                    instructions.append(f"(call ${stmt.name})")

        return instructions

    def _add_stdlib_imports(self) -> None:
        """Add standard library imports for console output, math, etc."""
        # Console.log for debugging
        self.module.add_import(
            WasmImport(
                module="console",
                name="__log_i32",
                params=[("value", WasmType.I32)],
            )
        )

        self.module.add_import(
            WasmImport(
                module="console",
                name="__log_str",
                params=[("ptr", WasmType.I32), ("len", WasmType.I32)],
            )
        )

        # Math operations (if not using native WASM instructions)
        self.module.add_import(
            WasmImport(
                module="math",
                name="__sqrt",
                params=[("value", WasmType.F64)],
                return_type=WasmType.F64,
            )
        )

    def generate_binary_op(
        self, op: str, left_type: WasmType, _right_type: WasmType
    ) -> str:
        """Generate WASM for binary operation."""
        # Map operator to WASM instruction
        op_map = {
            "+": WasmOp.ADD,
            "-": WasmOp.SUB,
            "*": WasmOp.MUL,
            "/": WasmOp.DIV,
            "==": WasmOp.EQ,
            "<": WasmOp.LT_S,
            ">": WasmOp.GT_S,
        }

        if op not in op_map:
            return f"(unreachable) ;; unknown op: {op}"

        wasm_op = op_map[op]
        type_prefix = "i32" if left_type == WasmType.I32 else "f32"

        return f"({type_prefix}.{wasm_op.value})"

    def generate_memory_load(
        self, address: int, wasm_type: WasmType, offset: int = 0
    ) -> str:
        """Generate memory load instruction."""
        # size_map = {WasmType.I32: 32, WasmType.I64: 64,
        #              WasmType.F32: 32, WasmType.F64: 64}
        # size = size_map.get(wasm_type, 32)

        return (
            f"({wasm_type.value}.load offset={offset} (i32.const {address}))"
        )

    def generate_memory_store(
        self, address: int, wasm_type: WasmType, offset: int = 0
    ) -> str:
        """Generate memory store instruction."""
        return (
            f"({wasm_type.value}.store offset={offset} (i32.const {address}))"
        )

    def generate_loop(self, condition: str, body: List[str]) -> List[str]:
        """Generate WASM loop."""
        instructions = ["(block $break", "(loop $continue"]

        # Add condition check
        instructions.append(condition)
        instructions.append("(br_if $break)")

        # Add body
        instructions.extend(body)

        # Continue loop
        instructions.append("(br $continue)")
        instructions.append(")")
        instructions.append(")")

        return instructions

    def generate_if(
        self,
        condition: str,
        then_body: List[str],
        else_body: Optional[List[str]] = None,
    ) -> List[str]:
        """Generate WASM if statement."""
        instructions = ["(if", condition]

        instructions.append("(then")
        instructions.extend(then_body)
        instructions.append(")")

        if else_body:
            instructions.append("(else")
            instructions.extend(else_body)
            instructions.append(")")

        instructions.append(")")

        return instructions

    # -------------------------------------------------------------------
    # SourceAST translation (from grammar engine)
    # -------------------------------------------------------------------

    def translate_source_ast(self, ast: Any) -> WasmModule:
        """Translate a SourceAST tree into a WASM module.

        Supports the documented subset: integer functions and calls,
        assignments, ``if``/``else``, ``while``, returns, and prints.
        Strings are stored in memory and printed through the imported
        ``console.logStr(ptr, len)`` host function.
        """
        from parsercraft.codegen.common import (
            inline_assignment,
            meaningful_children,
            split_chain,
        )

        self._inline_assignment = inline_assignment
        self._meaningful_children = meaningful_children
        self._split_chain = split_chain

        self.module = WasmModule()
        self.module.set_memory_size(256)
        self._functions = []
        self._strings: Dict[str, int] = {}
        self._next_data = 0
        self._label_counter = 0

        top_level: List[Any] = []
        function_nodes: List[Any] = []
        for child in ast.children:
            function = self._function_def(child)
            if function is not None:
                function_nodes.append(function)
            else:
                top_level.append(child)

        self._function_names = {
            self._function_name(function) for function in function_nodes
        }
        for function in function_nodes:
            self._compile_function(function)

        self._instructions = []
        self._locals = []
        self._local_names = set()
        self._param_names = set()
        for statement in top_level:
            self._emit_statement(statement)

        for function in self._functions:
            self.module.add_function(function)

        main = WasmFunction(
            name="main",
            return_type=WasmType.I32,
            locals=self._locals,
            body=self._instructions + ["i32.const 0"],
            is_export=True,
        )
        self.module.add_function(main)
        self._add_stdlib_imports()
        return self.module

    def _function_name(self, node: Any) -> str:
        for child in self._meaningful_children(node):
            if child.node_type in ("Identifier", "IDENT"):
                return str(child.value)
        return ""

    def _function_def(self, node: Any) -> Optional[Any]:
        """Return a function definition node, unwrapping statement wrappers."""
        if node.node_type in ("function_def", "FunctionDef"):
            return node
        if node.node_type in ("statement", "Statement"):
            children = [
                child for child in node.children
                if child.node_type in ("function_def", "FunctionDef")
            ]
            if len(children) == 1:
                return children[0]
        return None

    # -- function compilation --------------------------------------------

    def _compile_function(self, node: Any) -> None:
        meaningful = self._meaningful_children(node)
        name = ""
        params: List[str] = []
        body_nodes: List[Any] = []

        for child in meaningful:
            if child.node_type in ("Identifier", "IDENT") and not name:
                name = str(child.value)
            elif child.node_type == "param_list":
                params = [
                    str(param.value)
                    for param in child.children
                    if param.node_type in ("Identifier", "IDENT")
                ]
            elif child.node_type in ("block", "Block"):
                body_nodes = list(child.children)
            elif child.node_type not in ("Operator",):
                body_nodes.append(child)

        if not name:
            return

        self._instructions = []
        self._locals = []
        self._local_names = set()
        self._param_names = set(params)
        for statement in body_nodes:
            self._emit_statement(statement)

        self._functions.append(
            WasmFunction(
                name=name,
                params=[(param, WasmType.I32) for param in params],
                return_type=WasmType.I32,
                locals=self._locals,
                body=self._instructions + ["i32.const 0"],
            )
        )

    def _ensure_local(self, name: str) -> None:
        if name in self._local_names or name in self._param_names:
            return
        self._locals.append(WasmLocal(name, WasmType.I32))
        self._local_names.add(name)

    # -- statements ------------------------------------------------------

    def _emit_statement(self, node: Any) -> None:
        nt = node.node_type

        if nt in ("program", "Program", "Module", "block", "Block"):
            for child in node.children:
                self._emit_statement(child)
            return

        if nt in ("statement", "Statement"):
            if self._function_def(node) is not None:
                return
            pair = self._inline_assignment(node)
            if pair is not None:
                target, value = pair
                self._emit_assignment(target, value)
            else:
                for child in node.children:
                    self._emit_statement(child)
            return

        if nt in ("assignment", "Assignment"):
            meaningful = self._meaningful_children(node)
            if len(meaningful) >= 2:
                self._emit_assignment(meaningful[0], meaningful[1])
            return

        if nt in ("function_def", "FunctionDef"):
            # Nested definitions are not supported; ignore rather than
            # emitting their bodies into the caller.
            return

        if nt in ("if_stmt", "IfStmt"):
            children = [c for c in node.children if c.node_type != "Operator"]
            if not children:
                return
            self._emit_expression(children[0])
            self._instructions.append("if")
            blocks = [
                c for c in children[1:]
                if c.node_type in ("block", "Block")
            ]
            then_nodes = blocks[0].children if blocks else children[1:]
            for child in then_nodes:
                self._emit_statement(child)
            if len(blocks) > 1:
                self._instructions.append("else")
                for child in blocks[1].children:
                    self._emit_statement(child)
            self._instructions.append("end")
            return

        if nt in ("while_stmt", "WhileStmt"):
            children = [c for c in node.children if c.node_type != "Operator"]
            if not children:
                return
            self._label_counter += 1
            exit_label = f"while_exit_{self._label_counter}"
            loop_label = f"while_loop_{self._label_counter}"
            self._instructions.append(f"block ${exit_label}")
            self._instructions.append(f"loop ${loop_label}")
            self._emit_expression(children[0])
            self._instructions.append("i32.eqz")
            self._instructions.append(f"br_if ${exit_label}")
            body = children[1:]
            for child in body:
                self._emit_statement(child)
            self._instructions.append(f"br ${loop_label}")
            self._instructions.append("end")
            self._instructions.append("end")
            return

        if nt in ("return_stmt", "ReturnStmt"):
            meaningful = [c for c in node.children if c.node_type != "Operator"]
            if meaningful:
                self._emit_expression(meaningful[0])
            else:
                self._instructions.append("i32.const 0")
            self._instructions.append("return")
            return

        if nt in ("print_stmt", "PrintStmt"):
            for child in [c for c in node.children if c.node_type != "Operator"]:
                text = self._string_literal(child)
                if text is not None:
                    address = self._allocate_string(text)
                    self._instructions.append(f"i32.const {address}")
                    self._instructions.append(
                        f"i32.const {len(text.encode('utf-8'))}"
                    )
                    self._instructions.append("call $__log_str")
                else:
                    self._emit_expression(child)
                    self._instructions.append("call $__log_i32")
            return

        if nt in ("expr_stmt", "ExprStmt"):
            meaningful = [c for c in node.children if c.node_type != "Operator"]
            if meaningful:
                self._emit_expression(meaningful[0])
                self._instructions.append("drop")
            return

        # Transparent fallback: walk children.
        for child in node.children:
            self._emit_statement(child)

    def _emit_assignment(self, target: Any, value: Any) -> None:
        name = self._source_expr_name(target)
        self._ensure_local(name)
        self._emit_expression(value)
        self._instructions.append(f"local.set ${name}")

    # -- expressions -----------------------------------------------------

    def _emit_expression(self, node: Any) -> None:
        nt = node.node_type

        if nt == "Number":
            value = node.value
            if isinstance(value, float):
                value = int(value)
            self._instructions.append(f"i32.const {int(value)}")
            return

        if nt == "String":
            text = str(node.value)
            address = self._allocate_string(text)
            self._instructions.append(f"i32.const {address}")
            return

        if nt in ("boolean", "Boolean", "bool", "Bool"):
            value = str(node.value).strip().lower()
            self._instructions.append(
                "i32.const 0" if value in ("false", "0") else "i32.const 1"
            )
            return

        if nt in ("Identifier", "IDENT"):
            name = str(node.value)
            self._ensure_local(name)
            self._instructions.append(f"local.get ${name}")
            return

        if nt == "Operator":
            return

        if nt in ("call", "Call", "FunctionCall"):
            children = [c for c in node.children if c.node_type != "Operator"]
            if not children:
                self._instructions.append("i32.const 0")
                return
            for argument in children[1:]:
                self._emit_expression(argument)
            name = self._source_expr_name(children[0])
            if name not in self._function_names:
                raise ValueError(
                    f"WASM backend cannot resolve function '{name}'. "
                    "Define it in the same source file; external builtins are "
                    "not available yet."
                )
            self._instructions.append(f"call ${name}")
            return

        if nt in (
            "expr", "Expr", "comparison", "addition", "multiplication",
            "term", "Comparison",
        ):
            operands, operators = self._split_chain(node)
            if not operands:
                self._instructions.append("i32.const 0")
                return
            self._emit_expression(operands[0])
            for index, operator in enumerate(operators):
                if index + 1 >= len(operands):
                    break
                self._emit_expression(operands[index + 1])
                instruction = self._binary_instruction(str(operator.value))
                if instruction:
                    self._instructions.append(instruction)
                else:
                    self._instructions.append("drop")
                    self._instructions.append("drop")
                    self._instructions.append("i32.const 0")
            return

        if nt in ("factor", "primary", "Primary"):
            meaningful = [
                c for c in node.children if c.node_type != "Operator"
            ]
            if meaningful:
                self._emit_expression(meaningful[0])
            else:
                self._instructions.append("i32.const 0")
            return

        if node.value is not None:
            self._instructions.append(f"i32.const {int(node.value)}")
            return

        meaningful = [c for c in node.children if c.node_type != "Operator"]
        if meaningful:
            self._emit_expression(meaningful[0])
        else:
            self._instructions.append("i32.const 0")

    def _binary_instruction(self, operator: str) -> Optional[str]:
        return {
            "+": "i32.add",
            "-": "i32.sub",
            "*": "i32.mul",
            "/": "i32.div_s",
            "%": "i32.rem_s",
            "==": "i32.eq",
            "!=": "i32.ne",
            "<": "i32.lt_s",
            ">": "i32.gt_s",
            "<=": "i32.le_s",
            ">=": "i32.ge_s",
            "&&": "i32.and",
            "and": "i32.and",
            "||": "i32.or",
            "or": "i32.or",
        }.get(operator)

    def _string_literal(self, node: Any) -> Optional[str]:
        if node.node_type == "String":
            return str(node.value)
        if node.node_type in (
            "expr", "Expr", "term", "factor", "primary", "Primary",
        ):
            meaningful = [c for c in node.children if c.node_type != "Operator"]
            if len(meaningful) == 1:
                return self._string_literal(meaningful[0])
        return None

    def _allocate_string(self, text: str) -> int:
        if text in self._strings:
            return self._strings[text]
        data = text.encode("utf-8")
        address = self._next_data
        self.module.add_data(address, data)
        self._strings[text] = address
        self._next_data += len(data) + 1
        return address

    def _source_expr_name(self, node: Any) -> str:
        """Extract name string from an identifier-type node."""
        if node.node_type in ("Identifier", "IDENT"):
            return str(node.value)
        if node.value is not None:
            return str(node.value)
        return "unknown"
