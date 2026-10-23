#!/usr/bin/env python3
"""
AST Integration for Code Generators

Bridges Phase 4 code generators (C, WASM) with the existing AST system.
Provides adapters to convert language AST nodes to code generation targets.

Features:
    - AST to C code translation
    - AST to WASM bytecode translation
    - Type inference from AST nodes
    - Symbol table building from AST
    - Control flow analysis

Usage:
    from parsercraft.ast_integration import ASTToCGenerator, ASTToWasmGenerator
    
    c_gen = ASTToCGenerator()
    c_code = c_gen.translate(ast, config)
    
    wasm_gen = ASTToWasmGenerator()
    wasm_module = wasm_gen.translate(ast, config)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from parsercraft.codegen.codegen_c import CCodeGenerator, CFunction, CType, CVariable
from parsercraft.codegen.codegen_wasm import WasmFunction, WasmGenerator, WasmModule, WasmType


@dataclass
class ASTNode:
    """Represents a generic AST node."""

    node_type: str
    value: Any = None
    children: List[ASTNode] = None
    attributes: Dict[str, Any] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.attributes is None:
            self.attributes = {}


@dataclass
class TypeInfo:
    """Type information extracted from AST."""

    base_type: str
    is_pointer: bool = False
    is_const: bool = False
    array_size: Optional[int] = None
    generic_params: List[str] = None

    def __post_init__(self):
        if self.generic_params is None:
            self.generic_params = []


class ASTVisitor:
    """Base visitor for AST traversal."""

    def visit(self, node: ASTNode) -> Any:
        """Visit an AST node."""
        method_name = f"visit_{node.node_type}"

        if hasattr(self, method_name):
            return getattr(self, method_name)(node)
        else:
            return self.visit_generic(node)

    def visit_generic(self, node: ASTNode) -> Any:
        """Default visitor for unknown node types."""
        for child in node.children:
            self.visit(child)
        return None


class SymbolTable:
    """Symbol table for tracking declared symbols."""

    def __init__(self):
        self.scopes: List[Dict[str, TypeInfo]] = [{}]  # Stack of scopes
        self.functions: Dict[str, Tuple[List[str], str]] = {}  # name -> (params, return_type)
        self.global_scope = self.scopes[0]

    def push_scope(self) -> None:
        """Enter a new scope (function, block, etc.)."""
        self.scopes.append({})

    def pop_scope(self) -> None:
        """Exit the current scope."""
        if len(self.scopes) > 1:
            self.scopes.pop()

    def declare(self, name: str, type_info: TypeInfo) -> None:
        """Declare a symbol in the current scope."""
        self.scopes[-1][name] = type_info

    def lookup(self, name: str) -> Optional[TypeInfo]:
        """Look up a symbol in any scope (closest first)."""
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def declare_function(self, name: str, params: List[str], return_type: str) -> None:
        """Declare a function."""
        self.functions[name] = (params, return_type)

    def lookup_function(self, name: str) -> Optional[Tuple[List[str], str]]:
        """Look up a function."""
        return self.functions.get(name)


class ASTToCGenerator(ASTVisitor):
    """Converts AST to C code."""

    def __init__(self, config: Any = None):
        self.generator = CCodeGenerator()
        self.symbol_table = SymbolTable()
        self.config = config
        self.current_function: Optional[str] = None

    def translate(self, ast: ASTNode, config: Any = None) -> str:
        """Translate AST to C code."""
        if config:
            self.config = config

        # First pass: collect symbols
        self._collect_symbols(ast)

        # Second pass: generate code
        self.visit(ast)

        # Generate final output
        return self.generator.generate_header() + "\n" + self.generator.generate_implementations()

    def _collect_symbols(self, node: ASTNode) -> None:
        """First pass: collect function and variable declarations."""
        if node.node_type == "function":
            func_name = node.attributes.get("name", "unknown")
            params = node.attributes.get("params", [])
            return_type = node.attributes.get("return_type", "int")
            self.symbol_table.declare_function(func_name, params, return_type)

        for child in node.children:
            self._collect_symbols(child)

    def visit_program(self, node: ASTNode) -> None:
        """Visit program node (root)."""
        for child in node.children:
            self.visit(child)

    def visit_function(self, node: ASTNode) -> None:
        """Visit function definition."""
        func_name = node.attributes.get("name", "unknown_func")
        # return_type = node.attributes.get("return_type", "int")
        params = node.attributes.get("params", [])

        self.current_function = func_name
        self.symbol_table.push_scope()

        # Add parameters to symbol table
        for param_name in params:
            self.symbol_table.declare(param_name, TypeInfo("int"))

        # Generate function
        func = CFunction(name=func_name, return_type=CType.INT)

        # Add parameter declarations
        for param_name in params:
            func.params.append((param_name, CType.INT))

        # Visit function body
        for child in node.children:
            self.visit(child)

        self.generator.functions[func_name] = func
        self.symbol_table.pop_scope()
        self.current_function = None

    def visit_variable_declaration(self, node: ASTNode) -> None:
        """Visit variable declaration."""
        var_name = node.attributes.get("name", "var")
        var_type = node.attributes.get("type", "int")
        value = node.attributes.get("value")

        type_info = TypeInfo(var_type)
        self.symbol_table.declare(var_name, type_info)

        # Add to global variables if at top level, otherwise generate local declaration
        c_type_str = self.generator.translate_type(var_type)
        c_var = CVariable(name=var_name, c_type=c_type_str, initial_value=value)
        self.generator.globals.append(c_var)

    def visit_assignment(self, node: ASTNode) -> None:
        """Visit assignment statement."""
        target = node.attributes.get("target", "var")
        value = node.attributes.get("value", "0")

        # Generate assignment instruction
        instruction = f"(local.set ${target} {value})"
        if self.current_function and self.current_function in self.generator.functions:
            self.generator.functions[self.current_function].body.append(instruction)

    def visit_if(self, node: ASTNode) -> None:
        """Visit if statement."""
        # condition = node.attributes.get("condition", "true")

        # Then branch
        then_body = []
        for child in node.children:
            if child.node_type == "then_block":
                for stmt in child.children:
                    then_body.append(f"// {stmt.node_type}")

        # Else branch
        else_body = []
        for child in node.children:
            if child.node_type == "else_block":
                for stmt in child.children:
                    else_body.append(f"// {stmt.node_type}")

    def visit_return(self, node: ASTNode) -> None:
        """Visit return statement."""
        value = node.attributes.get("value", "0")

        if self.current_function and self.current_function in self.generator.functions:
            self.generator.functions[self.current_function].body.append(f"return {value};")


class ASTToWasmGenerator(ASTVisitor):
    """Converts AST to WebAssembly."""

    def __init__(self, config: Any = None):
        self.generator = WasmGenerator()
        self.module = WasmModule()
        self.symbol_table = SymbolTable()
        self.config = config
        self.current_function: Optional[str] = None

    def translate(self, ast: ASTNode, config: Any = None) -> WasmModule:
        """Translate AST to WASM module."""
        if config:
            self.config = config

        # First pass: collect symbols
        self._collect_symbols(ast)

        # Second pass: generate code
        self.visit(ast)

        return self.module

    def _collect_symbols(self, node: ASTNode) -> None:
        """First pass: collect declarations."""
        if node.node_type == "function":
            func_name = node.attributes.get("name", "unknown")
            params = node.attributes.get("params", [])
            return_type = node.attributes.get("return_type", "i32")
            self.symbol_table.declare_function(func_name, params, return_type)

        for child in node.children:
            self._collect_symbols(child)

    def visit_program(self, node: ASTNode) -> None:
        """Visit program node."""
        for child in node.children:
            self.visit(child)

    def visit_function(self, node: ASTNode) -> None:
        """Visit function definition."""
        func_name = node.attributes.get("name", "unknown")
        return_type = node.attributes.get("return_type", "i32")
        params = node.attributes.get("params", [])

        self.current_function = func_name
        self.symbol_table.push_scope()

        # Map return type
        wasm_return = self._translate_type(return_type)

        # Create WASM function
        wasm_func = WasmFunction(
            name=func_name,
            return_type=wasm_return,
            params=[(p, WasmType.I32) for p in params],
        )

        # Add to module
        self.module.add_function(wasm_func)

        # Visit function body
        for child in node.children:
            self.visit(child)

        self.symbol_table.pop_scope()
        self.current_function = None

    def visit_return(self, node: ASTNode) -> None:
        """Visit return statement."""
        # value = node.attributes.get("value", "0")

        if self.current_function and self.current_function in {f.name for f in self.module.functions.values()}:
            func = self.module.functions[self.current_function]
            func.body.append("return")

    def _translate_type(self, lang_type: str) -> WasmType:
        """Translate language type to WASM type."""
        type_map = {
            "int": WasmType.I32,
            "i32": WasmType.I32,
            "i64": WasmType.I64,
            "float": WasmType.F32,
            "f32": WasmType.F32,
            "f64": WasmType.F64,
            "bool": WasmType.I32,
        }
        return type_map.get(lang_type, WasmType.I32)


class TypeInferencePass(ASTVisitor):
    """Infers types from AST nodes."""

    def __init__(self):
        self.type_map: Dict[str, TypeInfo] = {}
        self.constraints: List[Tuple[str, str]] = []

    def infer(self, node: ASTNode) -> Dict[str, TypeInfo]:
        """Infer types from AST."""
        self.visit(node)
        return self.type_map

    def visit_literal(self, node: ASTNode) -> TypeInfo:
        """Infer type from literal."""
        value = node.attributes.get("value")

        if isinstance(value, int):
            return TypeInfo("int")
        elif isinstance(value, float):
            return TypeInfo("float")
        elif isinstance(value, bool):
            return TypeInfo("bool")
        elif isinstance(value, str):
            return TypeInfo("string")
        else:
            return TypeInfo("any")

    def visit_binary_op(self, node: ASTNode) -> TypeInfo:
        """Infer type from binary operation."""
        op = node.attributes.get("operator", "+")

        # Infer left and right operand types
        left_type = None
        # right_type = None

        for child in node.children:
            if child.attributes.get("position") == "left":
                left_type = self.visit(child)
            elif child.attributes.get("position") == "right":
                self.visit(child)

        # Apply operator typing rules
        if op in ["+", "-", "*", "/"]:
            if left_type and left_type.base_type in ["int", "float"]:
                return left_type
            return TypeInfo("int")

        elif op in ["<", ">", "<=", ">=", "==", "!="]:
            return TypeInfo("bool")

        return TypeInfo("any")


class ControlFlowAnalyzer(ASTVisitor):
    """Analyzes control flow in AST."""

    def __init__(self):
        self.branches: List[str] = []
        self.loops: List[str] = []
        self.returns: List[str] = []

    def analyze(self, node: ASTNode) -> Dict[str, Any]:
        """Analyze control flow."""
        self.visit(node)
        return {
            "branches": self.branches,
            "loops": self.loops,
            "returns": self.returns,
        }

    def visit_if(self, node: ASTNode) -> None:
        """Visit if statement."""
        self.branches.append("if")
        for child in node.children:
            self.visit(child)

    def visit_while(self, node: ASTNode) -> None:
        """Visit while loop."""
        self.loops.append("while")
        for child in node.children:
            self.visit(child)

    def visit_for(self, node: ASTNode) -> None:
        """Visit for loop."""
        self.loops.append("for")
        for child in node.children:
            self.visit(child)

    def visit_return(self, node: ASTNode) -> None:
        """Visit return statement."""
        self.returns.append("return")
