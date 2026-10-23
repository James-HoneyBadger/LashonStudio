#!/usr/bin/env python3
"""
C Code Generator Backend for ParserCraft

Translates a SourceAST (produced by the PEG grammar engine) into C source
code ready for compilation with gcc/clang.

Features:
    - SourceAST → C translation (assignments, control flow, functions)
    - Typed variable declarations via CType/CVariable
    - Generates a standalone main() with stdio includes
    - Language-name annotation in the file header comment
    - Inline assignment pattern detection (IDENT "=" expr ";")

Usage:
    from parsercraft.codegen.codegen_c import CCodeGenerator

    gen = CCodeGenerator()
    c_code = gen.translate_source_ast(ast)  # SourceAST from grammar engine

    # Optionally write to file:
    # gen.generate(ast, "output.c")

    # Compile with:
    # gcc output.c -o program
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from parsercraft.codegen.common import meaningful_children, split_chain


class CType(Enum):
    """C type mappings."""

    BOOL = "bool"
    INT = "int"
    FLOAT = "double"
    STR = "const char*"
    VOID = "void"
    ANY = "void*"
    LIST = "vector_t*"
    DICT = "map_t*"


@dataclass
class CVariable:
    """Represents a C variable."""

    name: str
    c_type: str
    is_pointer: bool = False
    is_const: bool = False
    initial_value: Optional[str] = None

    def declaration(self) -> str:
        """Generate C declaration."""
        prefix = "const " if self.is_const else ""
        suffix = "*" if self.is_pointer else ""
        if self.initial_value:
            decl = (
                f"{prefix}{self.c_type}{suffix} {self.name}"
            )
            return f"{decl} = {self.initial_value};"
        return f"{prefix}{self.c_type}{suffix} {self.name};"


@dataclass
class CFunction:
    """Represents a C function."""

    name: str
    return_type: str
    parameters: Dict[str, str] = field(default_factory=dict)  # name -> type
    body: List[str] = field(default_factory=list)
    is_static: bool = False
    is_inline: bool = False

    def signature(self) -> str:
        """Generate function signature."""
        params = ", ".join(f"{typ} {name}" for name,
                           typ in self.parameters.items())
        prefix = "static " if self.is_static else ""
        inline = "inline " if self.is_inline else ""
        return f"{prefix}{inline}{self.return_type} {self.name}({params})"

    def definition(self) -> str:
        """Generate complete function definition."""
        sig = self.signature()
        body = "\n    ".join(self.body) if self.body else "return;"
        return f"{sig} {{\n    {body}\n}}"


class CCodeGenerator:
    """Generates C code from custom language AST."""

    def __init__(
        self,
        config: Any = None,
        source_map: bool = False,
        source_file: str = "<source>",
    ):
        self.config = config
        self.source_map = source_map
        self.source_file = source_file
        self._last_source_line = 0
        self.functions: List[CFunction] = []
        self.globals: List[CVariable] = []
        self.includes: Set[str] = {"<stdio.h>", "<stdlib.h>", "<string.h>"}
        self.indent_level = 0
        self.var_counter = 0
        self._body_lines: List[str] = []

    def add_include(self, header: str) -> None:
        """Add include directive."""
        if not header.startswith("<") and not header.startswith('"'):
            header = f'"{header}"'
        self.includes.add(header)

    def gen_temp_var(self, _c_type: str = "int") -> str:
        """Generate unique temporary variable."""
        var_name = f"__tmp_{self.var_counter}"
        self.var_counter += 1
        return var_name

    def indent(self) -> str:
        """Get current indentation."""
        return "    " * self.indent_level

    def generate_header(self) -> str:
        """Generate C header section."""
        lines = []

        # Includes
        for include in sorted(self.includes):
            lines.append(f"#include {include}")

        lines.append("")
        lines.append("// Forward declarations")
        for func in self.functions:
            lines.append(f"{func.signature()};")

        lines.append("")
        lines.append("// Global variables")
        for var in self.globals:
            lines.append(var.declaration())

        return "\n".join(lines)

    def generate_implementations(self) -> str:
        """Generate function implementations."""
        implementations = []
        for func in self.functions:
            implementations.append(func.definition())
            implementations.append("")
        return "\n".join(implementations)

    def generate_main(self) -> str:
        """Generate main function."""
        return """int main(int argc, char** argv) {
    // Program entry point
    return 0;
}
"""

    def generate(
        self, _ast: Dict[str, Any], output_file: str = "output.c"
    ) -> str:
        """Generate complete C program."""
        lang_name = self.config.name if self.config else 'Unknown'
        code_parts = [
            "// Auto-generated C code from ParserCraft",
            f"// Original language: {lang_name}",
            "",
            self.generate_header(),
            "",
            self.generate_implementations(),
            "",
            self.generate_main(),
        ]

        full_code = "\n".join(code_parts)

        # Write to file if specified
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(full_code)

        return full_code

    def translate_type(self, lang_type: str) -> str:
        """Translate language type to C type."""
        type_map = {
            "bool": CType.BOOL.value,
            "int": CType.INT.value,
            "float": CType.FLOAT.value,
            "str": CType.STR.value,
            "string": CType.STR.value,
            "list": CType.LIST.value,
            "dict": CType.DICT.value,
            "void": CType.VOID.value,
        }
        return type_map.get(lang_type, CType.ANY.value)

    def gen_function_call(self, func_name: str, args: List[str]) -> str:
        """Generate C function call."""
        args_str = ", ".join(args)
        return f"{func_name}({args_str})"

    def gen_variable_declare(
            self, name: str, c_type: str,
            value: Optional[str] = None) -> str:
        """Generate variable declaration."""
        var = CVariable(name, c_type, initial_value=value)
        return var.declaration()

    def gen_return(self, value: Optional[str] = None) -> str:
        """Generate return statement."""
        if value:
            return f"{self.indent()}return {value};"
        return f"{self.indent()}return;"

    def gen_if(
            self, condition: str, true_body: List[str],
            false_body: Optional[List[str]] = None) -> str:
        """Generate if statement."""
        lines = [f"{self.indent()}if ({condition}) {{"]
        self.indent_level += 1
        for stmt in true_body:
            lines.append(stmt)
        self.indent_level -= 1

        if false_body:
            lines.append(f"{self.indent()}}} else {{")
            self.indent_level += 1
            for stmt in false_body:
                lines.append(stmt)
            self.indent_level -= 1

        lines.append(f"{self.indent()}}}")
        return "\n".join(lines)

    def gen_loop(
            self, init: str, condition: str,
            increment: str, body: List[str]) -> str:
        """Generate for loop."""
        lines = [f"{self.indent()}for ({init}; {condition}; {increment}) {{"]
        self.indent_level += 1
        for stmt in body:
            lines.append(stmt)
        self.indent_level -= 1
        lines.append(f"{self.indent()}}}")
        return "\n".join(lines)

    def gen_while(self, condition: str, body: List[str]) -> str:
        """Generate while loop."""
        lines = [f"{self.indent()}while ({condition}) {{"]
        self.indent_level += 1
        for stmt in body:
            lines.append(stmt)
        self.indent_level -= 1
        lines.append(f"{self.indent()}}}")
        return "\n".join(lines)

    def gen_binary_op(self, left: str, op: str, right: str) -> str:
        """Generate binary operation."""
        return f"({left} {op} {right})"

    def gen_assignment(self, target: str, value: str) -> str:
        """Generate assignment statement."""
        return f"{self.indent()}{target} = {value};"

    def gen_printf(self, format_str: str,
                   args: Optional[List[str]] = None) -> str:
        """Generate printf call."""
        args_str = f", {', '.join(args)}" if args else ""
        return f'{self.indent()}printf("{format_str}"{args_str});'

    # -------------------------------------------------------------------
    # SourceAST translation (from grammar engine)
    # -------------------------------------------------------------------

    def translate_source_ast(self, ast: Any) -> str:
        """Translate a SourceAST tree into C source code.

        Works with SourceAST nodes produced by the PEG grammar engine.
        """
        self.functions = []
        self.globals = []
        self.includes = {"<stdio.h>", "<stdlib.h>", "<string.h>"}
        self._body_lines = []
        self._declared = set()
        self._last_source_line = 0
        self.indent_level = 1  # Inside main()

        self._visit_source_node(ast)

        # Build output
        parts = [
            "// Auto-generated C code from ParserCraft",
            "",
            self.generate_header(),
            "",
            self.generate_implementations(),
            "",
            "int main(int argc, char** argv) {",
        ]
        for line in self._body_lines:
            parts.append(f"    {line}")
        parts.append("    return 0;")
        parts.append("}")
        return "\n".join(parts)

    _SOURCE_MAP_NODES = frozenset({
        "statement",
        "Statement",
        "assignment",
        "Assignment",
        "print_stmt",
        "return_stmt",
        "if_stmt",
        "while_stmt",
        "expr_stmt",
    })

    def _maybe_source_map(self, node: Any) -> None:
        """Emit a ``#line`` directive when the source line changes."""
        if not self.source_map:
            return
        line = getattr(node, "line", 0)
        if not line or line == self._last_source_line:
            return
        self._last_source_line = line
        self._body_lines.append(f'#line {line} "{self.source_file}"')

    def _visit_source_node(self, node: Any) -> None:
        """Visit a SourceAST node and generate C statements."""
        nt = node.node_type
        if nt in self._SOURCE_MAP_NODES:
            self._maybe_source_map(node)

        if nt in ("program", "Program", "Module"):
            for child in node.children:
                self._visit_source_node(child)

        elif nt in ("statement", "Statement"):
            # Detect inline assignment: IDENT '=' expr ';'
            ops = [c for c in node.children if c.node_type == "Operator"]
            if any(o.value == "=" for o in ops):
                meaningful = [
                    c for c in node.children
                    if not (c.node_type == "Operator"
                            and c.value in ("=", ";"))]
                if len(meaningful) >= 2:
                    target = self._source_expr(meaningful[0])
                    value = self._source_expr(meaningful[1])
                    c_type = self._infer_c_type(meaningful[1])
                    self._body_lines.append(f"{c_type} {target} = {value};")
            else:
                for child in node.children:
                    self._visit_source_node(child)

        elif nt in ("block", "Block"):
            for child in node.children:
                self._visit_source_node(child)

        elif nt in ("assignment", "Assignment"):
            meaningful = meaningful_children(node)
            if len(meaningful) >= 2:
                target = self._source_expr(meaningful[0])
                value = self._source_expr(meaningful[1])
                if target in self._declared:
                    self._body_lines.append(f"{target} = {value};")
                else:
                    c_type = self._infer_c_type(meaningful[1])
                    self._body_lines.append(f"{c_type} {target} = {value};")
                    self._declared.add(target)

        elif nt in ("function_def", "FunctionDef"):
            meaningful = [
                c for c in node.children if c.node_type != "Operator"]
            name = ""
            params_str = ""
            body_nodes = []
            for child in meaningful:
                if child.node_type in ("Identifier", "IDENT") and not name:
                    name = str(child.value)
                elif child.node_type == "param_list":
                    params_str = ", ".join(
                        f"int {self._source_expr(p)}" for p in child.children)
                elif child.node_type in ("block", "Block"):
                    body_nodes = child.children
                else:
                    body_nodes.append(child)

            if params_str:
                params_dict = {
                    p.strip().split()[-1]: p.strip().rsplit(" ", 1)[0]
                    for p in params_str.split(",") if p.strip()
                }
            else:
                params_dict = {}
            func = CFunction(
                name=name, return_type="int", parameters=params_dict)
            saved = self._body_lines
            saved_declared = self._declared
            self._body_lines = []
            self._declared = set(params_dict)
            for child in body_nodes:
                self._visit_source_node(child)
            func.body = self._body_lines
            self._body_lines = saved
            self._declared = saved_declared
            self.functions.append(func)

        elif nt in ("if_stmt", "IfStmt"):
            children = [c for c in node.children if c.node_type != "Operator"]
            if children:
                cond = self._source_expr(children[0])
                blocks = [
                    c for c in children[1:]
                    if c.node_type in ("block", "Block")
                ]
                self._body_lines.append(f"if ({cond}) {{")
                if blocks:
                    for stmt in blocks[0].children:
                        self._visit_source_node(stmt)
                for block in blocks[1:]:
                    self._body_lines.append("} else {")
                    for stmt in block.children:
                        self._visit_source_node(stmt)
                self._body_lines.append("}")

        elif nt in ("while_stmt", "WhileStmt"):
            children = [c for c in node.children if c.node_type != "Operator"]
            if children:
                cond = self._source_expr(children[0])
                self._body_lines.append(f"while ({cond}) {{")
                if len(children) > 1:
                    for child in children[1:]:
                        self._visit_source_node(child)
                self._body_lines.append("}")

        elif nt in ("return_stmt", "ReturnStmt"):
            meaningful = [
                c for c in node.children if c.node_type != "Operator"]
            if meaningful:
                val = self._source_expr(meaningful[0])
                self._body_lines.append(f"return {val};")
            else:
                self._body_lines.append("return;")

        elif nt in ("expr_stmt", "ExprStmt"):
            meaningful = [
                c for c in node.children if c.node_type != "Operator"]
            if meaningful:
                expr = self._source_expr(meaningful[0])
                self._body_lines.append(f"{expr};")

        elif nt in ("print_stmt", "PrintStmt"):
            args = [c for c in node.children if c.node_type != "Operator"]
            if args:
                fmts = []
                vals = []
                for a in args:
                    val = self._source_expr(a)
                    fmts.append("%s" if val.startswith('"') else "%d")
                    vals.append(val)
                fmt = " ".join(fmts) + "\\n"
                args_str = ", ".join(vals)
                self._body_lines.append(f'printf("{fmt}", {args_str});')

    def _source_expr(self, node: Any) -> str:
        """Convert a SourceAST expression to a C expression string."""
        nt = node.node_type

        if nt == "Number":
            val = node.value
            if isinstance(val, float):
                return str(val)
            return str(int(val))

        if nt == "String":
            return f'"{node.value}"'

        if nt in ("Identifier", "IDENT"):
            return str(node.value)

        if nt == "Operator":
            return str(node.value)

        if nt in (
                "expr", "Expr", "comparison",
                "addition", "multiplication", "term"):
            operands, operators = split_chain(node)
            parts: list[str] = []
            for index, operand in enumerate(operands):
                parts.append(self._source_expr(operand))
                if index < len(operators):
                    parts.append(str(operators[index].value))
            return " ".join(parts) if parts else ""

        if nt in ("factor", "primary"):
            meaningful = [
                c for c in node.children if c.node_type != "Operator"]
            if meaningful:
                return self._source_expr(meaningful[0])

        if nt in ("call", "Call", "FunctionCall"):
            children = [c for c in node.children if c.node_type != "Operator"]
            if children:
                func = self._source_expr(children[0])
                args = ", ".join(self._source_expr(c) for c in children[1:])
                return f"{func}({args})"

        # Fallback
        if node.value is not None:
            return str(node.value)
        if node.children:
            meaningful = [
                c for c in node.children if c.node_type != "Operator"]
            if meaningful:
                return self._source_expr(meaningful[0])
        return "0"

    def _infer_c_type(self, node: Any) -> str:
        """Infer C type from a SourceAST expression node."""
        nt = node.node_type
        if nt == "Number":
            if isinstance(node.value, float):
                return "double"
            return "int"
        if nt == "String":
            return "const char*"
        return "int"  # Default
