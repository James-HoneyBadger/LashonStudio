"""
AST-to-Python Transpiler for ParserCraft

Translates a SourceAST (from the PEG grammar engine) into executable Python
source code. This is the fastest path to running programs written in custom
languages: parse with the grammar engine, transpile to Python, exec().

Supports:
    - Variable declarations/assignments
    - Function definitions and calls
    - Control flow (if/elif/else, while, for)
    - Expressions with operator precedence
    - String/number/boolean literals
    - List/dict literals
    - Return statements
    - Print builtin
    - Class definitions (basic)
    - Lambda expressions
    - Import statements
    - Custom keyword→Python keyword mapping via LanguageConfig
"""  # pylint: disable=too-many-lines

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from parsercraft.parser.grammar import SourceAST


@dataclass
class TranspileOptions:
    """Configuration for the transpiler."""
    indent_str: str = "    "                    # Indentation string
    keyword_map: Dict[str, str] = field(default_factory=dict)  # custom→Python
    function_map: Dict[str, str] = field(
        default_factory=dict)  # custom→Python builtins
    operator_map: Dict[str, str] = field(
        default_factory=dict)  # custom→Python ops
    inject_runtime: bool = False                # Inject runtime helpers
    source_maps: bool = False  # Generate source mapping comments
    wrap_in_main: bool = False  # Wrap in if __name__ == "__main__"


class PythonTranspiler:
    """Transpiles a SourceAST tree into Python source code.

    Handles both SourceAST nodes (from the PEG grammar engine) and
    generic dict-based AST representations.
    """

    def __init__(self, options: Optional[TranspileOptions] = None):
        self.options = options or TranspileOptions()
        self.indent_level = 0
        self.output_lines: List[str] = []
        self._runtime_needed: Set[str] = set()
        self._imports_needed: Set[str] = set()

        # Node-type → handler method mapping
        self._handlers: Dict[str, Callable] = {
            # Program structure
            "Program": self._emit_program,
            "program": self._emit_program,
            "Module": self._emit_program,

            # Statements
            "assignment": self._emit_assignment,
            "Assignment": self._emit_assignment,
            "function_def": self._emit_function_def,
            "FunctionDef": self._emit_function_def,
            "class_def": self._emit_class_def,
            "ClassDef": self._emit_class_def,
            "if_stmt": self._emit_if,
            "IfStmt": self._emit_if,
            "while_stmt": self._emit_while,
            "WhileStmt": self._emit_while,
            "for_stmt": self._emit_for,
            "ForStmt": self._emit_for,
            "return_stmt": self._emit_return,
            "ReturnStmt": self._emit_return,
            "import_stmt": self._emit_import,
            "ImportStmt": self._emit_import,
            "expr_stmt": self._emit_expr_stmt,
            "ExprStmt": self._emit_expr_stmt,
            "print_stmt": self._emit_print,
            "PrintStmt": self._emit_print,
            "break_stmt": self._emit_break,
            "continue_stmt": self._emit_continue,
            "pass_stmt": self._emit_pass,

            # TempleCode / BASIC / Logo / PILOT statements
            "say_stmt": self._emit_say,
            "ask_stmt": self._emit_ask,
            "let_stmt": self._emit_let,
            "repeat_stmt": self._emit_repeat,
            "gosub_stmt": self._emit_gosub,
            "goto_stmt": self._emit_goto,
            "label_def": self._emit_label,
            "turtle_stmt": self._emit_transparent,
            "turtle_move": self._emit_turtle_move,
            "turtle_turn": self._emit_turtle_turn,
            "turtle_pen": self._emit_turtle_pen,
            "turtle_pos": self._emit_turtle_pos,
            "cls_stmt": self._emit_cls,
            "color_stmt": self._emit_color,
            "wait_stmt": self._emit_wait,
            "grade_stmt": self._emit_grade,
            "program_stmt": self._emit_program_stmt,

            # Expressions
            "expr": self._emit_transparent,
            "Expr": self._emit_transparent,
            "comparison": self._emit_transparent,
            "addition": self._emit_transparent,
            "multiplication": self._emit_transparent,
            "BinaryOp": self._emit_binary_op,
            "binary_op": self._emit_binary_op,
            "unary": self._emit_unary,
            "UnaryOp": self._emit_unary,
            "call": self._emit_call,
            "Call": self._emit_call,
            "FunctionCall": self._emit_call,

            # Atoms — only meaningful in expression context, emit as expr_stmt
            "Number": self._emit_expr_stmt,
            "String": self._emit_expr_stmt,
            "Boolean": self._emit_expr_stmt,
            "Identifier": self._emit_expr_stmt,
            "IDENT": self._emit_expr_stmt,

            # Containers
            "list_literal": self._emit_expr_stmt,
            "ListLiteral": self._emit_expr_stmt,
            "dict_literal": self._emit_expr_stmt,
            "DictLiteral": self._emit_expr_stmt,

            # Blocks
            "block": self._emit_block,
            "Block": self._emit_block,
            "statement": self._emit_transparent,
            "Statement": self._emit_transparent,
            "factor": self._emit_transparent,
            "primary": self._emit_transparent,
            "term": self._emit_transparent_binary,
            "param_list": self._emit_param_list,
            "arg_list": self._emit_arg_list,
        }

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def transpile(self, ast: SourceAST) -> str:
        """Transpile a SourceAST tree to Python source code."""
        self.output_lines = []
        self.indent_level = 0
        self._runtime_needed = set()
        self._imports_needed = set()

        self._emit_node(ast)

        result = "\n".join(self.output_lines)

        if self.options.inject_runtime and self._runtime_needed:
            runtime = self._generate_runtime()
            result = runtime + "\n\n" + result

        # Auto-prepend imports for modules referenced by generated code
        if self._imports_needed:
            imports = "\n".join(
                f"import {m}" for m in sorted(self._imports_needed))
            result = imports + "\n\n" + result

        # Inject CGA color helper when turtle is used
        if "turtle" in self._imports_needed:
            cga_helper = (
                "_CGA_PALETTE = {\n"
                "    0: '#000000', 1: '#0000AA',"
                " 2: '#00AA00', 3: '#00AAAA',\n"
                "    4: '#AA0000', 5: '#AA00AA',"
                " 6: '#AA5500', 7: '#AAAAAA',\n"
                "    8: '#555555', 9: '#5555FF',"
                " 10: '#55FF55', 11: '#55FFFF',\n"
                "    12: '#FF5555', 13: '#FF55FF',"
                " 14: '#FFFF55', 15: '#FFFFFF',\n"
                "}\n"
                "def _cga(c):\n"
                "    if isinstance(c, int):"
                " return _CGA_PALETTE.get(c, '#AAAAAA')\n"
                "    return c\n"
            )
            result_parts = result.split("\n", 1)
            result = result_parts[0] + "\n" + cga_helper + result_parts[1]

        if self.options.wrap_in_main:
            # Re-indent everything under if __name__
            indented = "\n".join(f"    {line}" if line.strip(
            ) else "" for line in result.split("\n"))
            result = f'if __name__ == "__main__":\n{indented}\n'

        return result

    def translate_source_ast(self, ast: SourceAST) -> str:
        """Alias for :meth:`transpile` to match the common backend interface."""
        return self.transpile(ast)

    def transpile_expression(self, ast: SourceAST) -> str:
        """Transpile a single expression AST node to a Python
        expression string."""
        return self._expr_to_str(ast)

    # -----------------------------------------------------------------------
    # Core dispatch
    # -----------------------------------------------------------------------

    def _emit_node(self, node: SourceAST) -> None:
        """Dispatch to the appropriate handler for a node."""
        handler = self._handlers.get(node.node_type)
        if handler:
            handler(node)
        else:
            # Fallback: emit children transparently
            for child in node.children:
                self._emit_node(child)

    def _expr_to_str(self, node: SourceAST) -> str:
        """Convert an expression AST node to a Python expression string."""
        handler_name = f"_expr_{node.node_type}"
        if hasattr(self, handler_name):
            return getattr(self, handler_name)(node)

        # Dispatch table for expressions
        nt = node.node_type
        nt_lower = nt.lower()

        if nt_lower in ("number", "string", "boolean", "bool"):
            return self._expr_literal(node)
        if nt_lower in ("identifier", "ident"):
            return self._expr_identifier(node)
        if nt in (
                "expr", "Expr", "comparison",
                "addition", "multiplication"):
            return self._expr_binary_chain(node)
        if nt in ("BinaryOp", "binary_op"):
            return self._expr_binary(node)
        if nt in ("UnaryOp", "unary"):
            return self._expr_unary(node)
        if nt in ("call", "Call", "FunctionCall"):
            return self._expr_call(node)
        if nt in ("list_literal", "ListLiteral"):
            return self._expr_list(node)
        if nt in ("dict_literal", "DictLiteral"):
            return self._expr_dict(node)
        if nt in ("factor", "primary", "statement", "Statement"):
            # Transparent wrapper — pass through to meaningful child
            # BUT detect parenthesized expressions: factor → "(" expr ")"
            has_open = any(c.node_type == "Operator" and c.value ==
                           "(" for c in node.children)
            has_close = any(c.node_type == "Operator" and c.value ==
                            ")" for c in node.children)
            meaningful = [
                c for c in node.children if c.node_type != "Operator"]
            if has_open and has_close and meaningful:
                inner = self._expr_to_str(meaningful[0])
                return f"({inner})"
            if meaningful:
                return self._expr_to_str(meaningful[0])
            return self._expr_passthrough(node)
        if nt == "term":
            return self._expr_binary_chain(node)
        if nt in ("assignment", "Assignment"):
            return self._expr_assignment(node)
        if nt in ("param_list",):
            return self._expr_param_list(node)
        if nt in ("arg_list",):
            return self._expr_arg_list(node)
        if nt == "Operator":
            return str(node.value) if node.value else ""

        # Last resort: if it has a value, use it; if it has children, join them
        if node.value is not None:
            return str(node.value)
        if node.children:
            parts = [self._expr_to_str(c) for c in node.children]
            return " ".join(p for p in parts if p)
        return ""

    # -----------------------------------------------------------------------
    # Statement emitters (produce lines of output)
    # -----------------------------------------------------------------------

    def _emit_program(self, node: SourceAST) -> None:
        for child in node.children:
            self._emit_node(child)

    def _emit_assignment(self, node: SourceAST) -> None:
        """Emit: target = value

        Handles AST shapes:
        - [Identifier, expr]                        (no operator nodes)
        - [Identifier, Operator('='), expr, ...]    (operator nodes from PEG)
        """
        # Filter out structural punctuation operators
        meaningful = [
            c for c in node.children
            if not (c.node_type == "Operator"
                    and c.value in ("=", ":=", ";", ":", ","))]

        if len(meaningful) >= 2:
            target = self._expr_to_str(meaningful[0])
            value = self._expr_to_str(meaningful[1])
        elif (node.value
              and isinstance(node.value, (list, tuple))
              and len(node.value) >= 2):
            target = str(node.value[0])
            value = str(node.value[1])
        else:
            self._line(node.source_text.strip()
                       if node.source_text else "# assignment")
            return

        target = self._map_identifier(target)
        self._line(f"{target} = {value}")

    def _emit_function_def(self, node: SourceAST) -> None:
        """Emit: def name(params): body"""
        children = node.children
        name = ""
        params = ""
        body_children = []

        for child in children:
            if child.node_type in ("Identifier", "IDENT") and not name:
                name = self._expr_to_str(child)
            elif child.node_type == "param_list":
                params = self._expr_to_str(child)
            elif child.node_type in ("block", "Block"):
                body_children = child.children
            else:
                body_children.append(child)

        if not name and node.value:
            name = str(node.value)

        name = self._map_keyword(name)
        self._line(f"def {name}({params}):")
        self.indent_level += 1
        if body_children:
            for child in body_children:
                self._emit_node(child)
        else:
            self._line("pass")
        self.indent_level -= 1

    def _emit_class_def(self, node: SourceAST) -> None:
        """Emit: class Name(bases): body"""
        children = node.children
        name = ""
        base_parts: list[str] = []
        body_children = []

        for child in children:
            if child.node_type in ("Identifier", "IDENT") and not name:
                name = self._expr_to_str(child)
            elif child.node_type in ("param_list", "arg_list"):
                base_parts.append(self._expr_to_str(child))
            elif child.node_type in ("Identifier", "IDENT"):
                base_parts.append(self._expr_to_str(child))
            elif child.node_type in ("block", "Block"):
                body_children = child.children
            else:
                body_children.append(child)

        bases = ", ".join(part for part in base_parts if part)
        base_str = f"({bases})" if bases else ""
        self._line(f"class {name}{base_str}:")
        self.indent_level += 1
        if body_children:
            for child in body_children:
                self._emit_node(child)
        else:
            self._line("pass")
        self.indent_level -= 1

    def _emit_if(self, node: SourceAST) -> None:
        """Emit: if condition: body [elif ...] [else: body]

        Handles both Python-style ASTs (block children) and BASIC-style
        ASTs produced by PEG rules like:
            'IF' expr 'THEN' statement+ ('ELSEIF' expr 'THEN' statement+)*
            ('ELSE' statement+)? 'ENDIF'
        """
        children = node.children
        if not children:
            return

        # Detect BASIC/TempleCode style: first child is Operator('IF')
        if children[0].node_type == "Operator" and children[0].value == "IF":
            self._emit_basic_if(children)
            return

        # Python-style: condition, block,
        # [elif_condition, block]*, [else_block]?
        # Structural keyword operators ('if', 'elif', 'else', ':') produced by
        # PEG literal matches are handled explicitly; they are NOT conditions.
        idx = 0
        keyword = "if"
        while idx < len(children):
            child = children[idx]
            if child.node_type in ("block", "Block"):
                self.indent_level += 1
                for stmt in child.children:
                    self._emit_node(stmt)
                self.indent_level -= 1
                idx += 1
            elif child.node_type == "else_block":
                self._line("else:")
                self.indent_level += 1
                for stmt in child.children:
                    self._emit_node(stmt)
                self.indent_level -= 1
                idx += 1
            elif child.node_type == "Operator" and child.value == "else":
                # Python-style 'else' keyword from PEG literal match
                self._line("else:")
                idx += 1
                # Skip optional ':' operator
                if (idx < len(children)
                        and children[idx].node_type == "Operator"
                        and children[idx].value == ":"):
                    idx += 1
                # Emit attached block
                if idx < len(children) and children[idx].node_type in (
                        "block", "Block"):
                    self.indent_level += 1
                    for stmt in children[idx].children:
                        self._emit_node(stmt)
                    self.indent_level -= 1
                    idx += 1
            elif (child.node_type == "Operator"
                  and child.value in ("if", "elif", ":")):
                # Skip structural keyword/punctuation operators.
                # 'elif' signals the next condition uses 'elif' keyword.
                if child.value == "elif":
                    keyword = "elif"
                idx += 1
            else:
                cond = self._expr_to_str(child)
                self._line(f"{keyword} {cond}:")
                keyword = "elif"
                idx += 1

    def _emit_basic_if(self, children: list) -> None:
        """Emit a BASIC-style IF/ELSEIF/ELSE/ENDIF block."""
        # Parse the children sequence into clauses
        i = 0
        keyword = "if"
        while i < len(children):
            c = children[i]
            if c.node_type == "Operator" and c.value in ("IF", "ELSEIF"):
                # Next: expr, THEN, statement(s)...
                i += 1
                if i >= len(children):
                    break
                cond = self._expr_to_str(children[i])
                # Map '=' comparisons to '==' (TempleCode uses = for both)
                cond = self._fix_basic_comparison(cond)
                self._line(f"{keyword} {cond}:")
                keyword = "elif"
                i += 1
                # Skip past 'THEN' operator
                if (i < len(children)
                        and children[i].node_type == "Operator"
                        and children[i].value == "THEN"):
                    i += 1
                # Collect body statements
                self.indent_level += 1
                while i < len(children) and children[i].node_type not in (
                        "Operator",):
                    self._emit_node(children[i])
                    i += 1
                self.indent_level -= 1
            elif c.node_type == "Operator" and c.value == "ELSE":
                self._line("else:")
                i += 1
                self.indent_level += 1
                while i < len(children) and children[i].node_type not in (
                        "Operator",):
                    self._emit_node(children[i])
                    i += 1
                self.indent_level -= 1
            elif c.node_type == "Operator" and c.value == "ENDIF":
                i += 1  # Done
            else:
                i += 1

    @staticmethod
    def _fix_basic_comparison(expr: str) -> str:
        """In BASIC-style languages, = is both assignment and comparison.
        When used in an IF condition, single = should become ==.
        Also map <> to !=."""
        expr = expr.replace(" <> ", " != ")
        # Replace standalone '=' with '==' (leave ==, !=, <=, >=, := alone)
        expr = re.sub(r'(?<![<>=!:])\s*=\s*(?![=])', ' == ', expr)
        return expr

    def _emit_while(self, node: SourceAST) -> None:
        """Emit: while condition: body

        Handles both Python-style and BASIC-style (WHILE expr statements WEND).
        """
        children = node.children
        if not children:
            return

        # Detect BASIC-style: first child is Operator('WHILE')
        if (children[0].node_type == "Operator"
                and children[0].value == "WHILE"):
            cond = self._expr_to_str(children[1]) if len(
                children) > 1 else "True"
            self._line(f"while {cond}:")
            self.indent_level += 1
            body = [c for c in children[2:]
                    if not (c.node_type == "Operator" and c.value == "WEND")]
            if body:
                for child in body:
                    self._emit_node(child)
            else:
                self._line("pass")
            self.indent_level -= 1
            return

        # Python-style: filter structural keyword operators ('while', ':')
        # produced by PEG literal matches so they are not used as the
        # condition.
        filtered_while = [
            c for c in children
            if not (c.node_type == "Operator"
                    and c.value in ("while", ":"))]
        if not filtered_while:
            return
        cond = self._expr_to_str(filtered_while[0])
        self._line(f"while {cond}:")
        self.indent_level += 1
        if len(filtered_while) > 1:
            for child in filtered_while[1:]:
                if child.node_type in ("block", "Block"):
                    for stmt in child.children:
                        self._emit_node(stmt)
                else:
                    self._emit_node(child)
        else:
            self._line("pass")
        self.indent_level -= 1

    def _emit_for(self, node: SourceAST) -> None:
        """Emit: for var in range(...): body

        Handles both Python-style and BASIC-style:
            FOR var = start TO end (STEP step)? statements NEXT var?
        """
        children = node.children
        if len(children) < 2:
            return

        # Detect BASIC-style: first child is Operator('FOR')
        if children[0].node_type == "Operator" and children[0].value == "FOR":
            self._emit_basic_for(children)
            return

        # Python-style: filter structural keyword operators ('for', 'in', ':')
        # produced by PEG literal matches so they don't corrupt var/iterable.
        filtered_for = [
            c for c in children
            if not (c.node_type == "Operator"
                    and c.value in ("for", "in", ":"))]
        if len(filtered_for) < 2:
            return
        var = self._expr_to_str(filtered_for[0])
        iterable = self._expr_to_str(filtered_for[1])
        self._line(f"for {var} in {iterable}:")
        self.indent_level += 1
        if len(filtered_for) > 2:
            for child in filtered_for[2:]:
                if child.node_type in ("block", "Block"):
                    for stmt in child.children:
                        self._emit_node(stmt)
                else:
                    self._emit_node(child)
        else:
            self._line("pass")
        self.indent_level -= 1

    def _emit_basic_for(self, children: list) -> None:
        """Emit a BASIC-style FOR/TO/STEP/NEXT loop as Python range()."""
        i = 1  # skip FOR
        var = self._expr_to_str(children[i])
        i += 1
        if (i < len(children)
                and children[i].node_type == "Operator"
                and children[i].value == "="):
            i += 1
        start = self._expr_to_str(children[i])
        i += 1
        if (i < len(children)
                and children[i].node_type == "Operator"
                and children[i].value == "TO"):
            i += 1
        end = self._expr_to_str(children[i])
        i += 1
        step = None
        if (i < len(children)
                and children[i].node_type == "Operator"
                and children[i].value == "STEP"):
            i += 1
            step = self._expr_to_str(children[i])
            i += 1
        if step:
            self._line(f"for {var} in range({start}, {end} + 1, {step}):")
        else:
            self._line(f"for {var} in range({start}, {end} + 1):")
        self.indent_level += 1
        body = []
        while i < len(children):
            if (children[i].node_type == "Operator"
                    and children[i].value == "NEXT"):
                break
            body.append(children[i])
            i += 1
        if body:
            for child in body:
                self._emit_node(child)
        else:
            self._line("pass")
        self.indent_level -= 1

    def _emit_return(self, node: SourceAST) -> None:
        # Filter structural operator nodes ('return', ';') produced by PEG
        # literal matches so they are not emitted as the returned expression.
        meaningful = [
            c for c in node.children
            if not (c.node_type == "Operator"
                    and c.value in ("return", "RETURN", ";"))]
        if meaningful:
            val = self._expr_to_str(meaningful[0])
            self._line(f"return {val}")
        else:
            self._line("return")

    def _emit_import(self, node: SourceAST) -> None:
        parts = [
            c for c in node.children
            if not (c.node_type == "Operator"
                    and c.value in ("import", "from", ";", ","))
        ]
        if parts:
            module = self._expr_to_str(parts[0])
            self._line(f"import {module}")
        elif node.value:
            self._line(f"import {node.value}")
        else:
            self._line("# import (unresolved)")

    def _emit_expr_stmt(self, node: SourceAST) -> None:
        """Emit an expression as a statement."""
        expr = self._expr_to_str(node)
        if expr:
            self._line(expr)

    def _emit_print(self, node: SourceAST) -> None:
        args = [
            self._expr_to_str(c) for c in node.children
            if not (c.node_type == "Operator"
                    and c.value in ("print", "PRINT", ";", ",", "(", ")"))
        ]
        if args:
            self._line(f"print({', '.join(args)})")
        else:
            self._line("print()")

    def _emit_break(self, _node: SourceAST) -> None:
        self._line("break")

    def _emit_continue(self, _node: SourceAST) -> None:
        self._line("continue")

    def _emit_pass(self, _node: SourceAST) -> None:
        self._line("pass")

    # -------------------------------------------------------------------
    # TempleCode / BASIC / Logo / PILOT statement handlers
    # -------------------------------------------------------------------

    def _emit_say(self, node: SourceAST) -> None:
        """SAY expr[, expr]* → print(expr...)"""
        args = [
            self._expr_to_str(c) for c in node.children
            if not (c.node_type == "Operator"
                    and c.value in ("SAY", ",", ";", "(", ")"))
        ]
        if args:
            self._line(f"print({', '.join(args)})")
        else:
            self._line("print()")

    def _emit_ask(self, node: SourceAST) -> None:
        """ASK STRING , IDENT → var = input(prompt)"""
        # Children: [Operator('ASK'), String, Operator(','), Identifier]
        parts = [c for c in node.children if c.node_type != "Operator"]
        if len(parts) >= 2:
            prompt = self._expr_to_str(parts[0])
            var = self._expr_to_str(parts[1])
            self._line(f"{var} = input({prompt})")
        elif len(parts) == 1:
            self._line(f"_ = input({self._expr_to_str(parts[0])})")
        else:
            self._line("_ = input()")

    def _emit_let(self, node: SourceAST) -> None:
        """LET IDENT = expr → var = expr"""
        # Children: [Operator('LET'), Identifier, Operator('='), expr]
        parts = [
            c for c in node.children
            if not (c.node_type == "Operator"
                    and c.value in ("LET", "="))]
        if len(parts) >= 2:
            var = self._expr_to_str(parts[0])
            val = self._expr_to_str(parts[1])
            self._line(f"{var} = {val}")
        else:
            self._emit_assignment(node)

    def _emit_repeat(self, node: SourceAST) -> None:
        """REPEAT count statement+ END → for _ in range(count): body"""
        children = node.children
        # Children: [Operator('REPEAT'), expr, statement+, Operator('END')]
        parts = [
            c for c in children
            if not (c.node_type == "Operator"
                    and c.value in ("REPEAT", "END"))]
        if not parts:
            return
        count = self._expr_to_str(parts[0])
        self._line(f"for _ in range({count}):")
        self.indent_level += 1
        body = parts[1:]
        if body:
            for child in body:
                self._emit_node(child)
        else:
            self._line("pass")
        self.indent_level -= 1

    def _emit_gosub(self, node: SourceAST) -> None:
        """GOSUB label → label()"""
        parts = [c for c in node.children if c.node_type != "Operator"]
        if parts:
            label = self._expr_to_str(parts[0])
            self._line(f"{label}()")

    def _emit_goto(self, node: SourceAST) -> None:
        """GOTO label → (comment, not directly translatable)"""
        parts = [c for c in node.children if c.node_type != "Operator"]
        if parts:
            label = self._expr_to_str(parts[0])
            self._line(f"# GOTO {label}")

    def _emit_label(self, node: SourceAST) -> None:
        """label: → def label(): (placeholder)"""
        parts = [c for c in node.children if c.node_type != "Operator"]
        if parts:
            label = self._expr_to_str(parts[0])
            self._line(f"# LABEL {label}")

    def _emit_turtle_move(self, node: SourceAST) -> None:
        """FORWARD/FD/BACK/BK expr
        → turtle.forward(expr) / turtle.backward(expr)"""
        self._imports_needed.add("turtle")
        cmd = ""
        expr_nodes = []
        for c in node.children:
            if (c.node_type == "Operator"
                    and c.value in ("FORWARD", "FD", "BACK", "BK")):
                cmd = c.value
            else:
                expr_nodes.append(c)
        func = "forward" if cmd in ("FORWARD", "FD") else "backward"
        arg = self._expr_to_str(expr_nodes[0]) if expr_nodes else "0"
        self._line(f"turtle.{func}({arg})")

    def _emit_turtle_turn(self, node: SourceAST) -> None:
        """LEFT/LT/RIGHT/RT expr → turtle.left(expr) / turtle.right(expr)"""
        self._imports_needed.add("turtle")
        cmd = ""
        expr_nodes = []
        for c in node.children:
            if (c.node_type == "Operator"
                    and c.value in ("LEFT", "LT", "RIGHT", "RT")):
                cmd = c.value
            else:
                expr_nodes.append(c)
        func = "left" if cmd in ("LEFT", "LT") else "right"
        arg = self._expr_to_str(expr_nodes[0]) if expr_nodes else "0"
        self._line(f"turtle.{func}({arg})")

    def _emit_turtle_pen(self, node: SourceAST) -> None:
        """PENUP/PU/PENDOWN/PD/HOME → turtle.penup() etc."""
        self._imports_needed.add("turtle")
        for c in node.children:
            if c.node_type == "Operator":
                cmd_map = {
                    "PENUP": "penup", "PU": "penup",
                    "PENDOWN": "pendown", "PD": "pendown",
                    "HOME": "home",
                }
                func = cmd_map.get(c.value, c.value.lower())
                self._line(f"turtle.{func}()")
                return
        # Single value node
        if node.value:
            self._line(f"turtle.{node.value.lower()}()")

    def _emit_turtle_pos(self, node: SourceAST) -> None:
        """SETXY/SETCOLOR/CIRCLE/ARC expr* → turtle calls"""
        self._imports_needed.add("turtle")
        cmd = ""
        expr_nodes = []
        for c in node.children:
            if (c.node_type == "Operator"
                    and c.value in ("SETXY", "SETCOLOR", "CIRCLE", "ARC")):
                cmd = c.value
            elif c.node_type != "Operator":
                expr_nodes.append(c)
        args_list = [self._expr_to_str(e) for e in expr_nodes]
        cmd_map = {
            "SETXY": "goto", "SETCOLOR": "color",
            "CIRCLE": "circle", "ARC": "circle",
        }
        func = cmd_map.get(cmd, cmd.lower())
        if cmd == "SETCOLOR" and args_list:
            # Wrap CGA integer color through helper
            self._line(f"turtle.{func}(_cga({args_list[0]}))")
        else:
            args = ", ".join(args_list)
            self._line(f"turtle.{func}({args})")

    def _emit_cls(self, _node: SourceAST) -> None:
        """CLS → clear screen"""
        self._line("# CLS (clear screen)")

    def _emit_color(self, node: SourceAST) -> None:
        """COLOR expr → set turtle pen color via CGA palette."""
        self._imports_needed.add("turtle")
        parts = [c for c in node.children if c.node_type != "Operator"]
        if parts:
            arg = self._expr_to_str(parts[0])
            self._line(f"turtle.color(_cga({arg}))")
        else:
            self._line("# COLOR (no argument)")

    def _emit_wait(self, node: SourceAST) -> None:
        """WAIT expr → time.sleep(expr)"""
        parts = [c for c in node.children if c.node_type != "Operator"]
        if parts:
            arg = self._expr_to_str(parts[0])
            self._line(f"import time; time.sleep({arg})")
        else:
            self._line("import time; time.sleep(1)")

    def _emit_grade(self, node: SourceAST) -> None:
        """GRADE expr → grading feedback (comment)"""
        parts = [c for c in node.children if c.node_type != "Operator"]
        if parts:
            arg = self._expr_to_str(parts[0])
            self._line(f"# GRADE {arg}")
        else:
            self._line("# GRADE")

    def _emit_program_stmt(self, node: SourceAST) -> None:
        """PROGRAM name → comment"""
        parts = [c for c in node.children if c.node_type != "Operator"]
        if parts:
            name = self._expr_to_str(parts[0])
            self._line(f"# PROGRAM {name}")
        else:
            self._line("# PROGRAM")

    def _emit_block(self, node: SourceAST) -> None:
        for child in node.children:
            self._emit_node(child)

    def _emit_transparent(self, node: SourceAST) -> None:
        """For wrapper nodes that don't represent structure
        (e.g., 'statement').

        Also detects inline assignment patterns (IDENT '=' expr ';').
        """
        if node.children:
            # Detect assignment pattern: IDENT = expr ;  (or := for Pascal)
            has_eq = any(
                c.node_type == "Operator" and c.value in ("=", ":=")
                for c in node.children
            )
            if has_eq:
                self._emit_assignment(node)
                return

            for child in node.children:
                self._emit_node(child)
        elif node.value is not None:
            self._line(str(node.value))

    def _emit_binary_chain(self, node: SourceAST) -> None:
        """Emit a binary chain as a statement (rare — usually in expr_stmt)."""
        expr = self._expr_binary_chain(node)
        self._line(expr)

    def _emit_binary_op(self, node: SourceAST) -> None:
        expr = self._expr_binary(node)
        self._line(expr)

    def _emit_unary(self, node: SourceAST) -> None:
        expr = self._expr_unary(node)
        self._line(expr)

    def _emit_call(self, node: SourceAST) -> None:
        expr = self._expr_call(node)
        self._line(expr)

    def _emit_list(self, node: SourceAST) -> None:
        expr = self._expr_list(node)
        self._line(expr)

    def _emit_dict(self, node: SourceAST) -> None:
        expr = self._expr_dict(node)
        self._line(expr)

    def _emit_param_list(self, node: SourceAST) -> None:
        return  # Handled inline by function_def

    def _emit_arg_list(self, node: SourceAST) -> None:
        return  # Handled inline by call

    # -----------------------------------------------------------------------
    # Expression stringifiers (produce expression strings)
    # -----------------------------------------------------------------------

    def _expr_literal(self, node: SourceAST) -> str:
        val = node.value
        node_type = node.node_type.lower()
        if node_type == "string":
            return repr(str(val))
        if node_type in ("boolean", "bool"):
            if isinstance(val, bool):
                return "True" if val else "False"
            return "True" if str(val).strip().lower() == "true" else "False"
        return str(val)

    def _expr_identifier(self, node: SourceAST) -> str:
        name = str(node.value) if node.value else ""
        return self._map_identifier(name)

    def _expr_passthrough(self, node: SourceAST) -> str:
        """For transparent wrapper nodes — return child expression."""
        if node.children:
            return self._expr_to_str(node.children[0])
        if node.value is not None:
            return str(node.value)
        return ""

    def _expr_binary_chain(self, node: SourceAST) -> str:
        """Handle grammar patterns like: term (('+' / '-') term)*

        AST shape from PEG:
        [term, Operator('+'), term, Operator('-'), term, ...]
        Operators are SourceAST nodes with node_type="Operator".
        """
        if not node.children:
            if node.value is not None:
                return str(node.value)
            return ""

        # In comparison nodes, '=' is a comparison operator, not structural
        structural = {";", ":", ",", "(", ")", "{", "}", "[", "]"}
        # Keep '=' as comparison in comparison/condition contexts
        if node.node_type not in ("comparison",):
            structural.add("=")

        children = [c for c in node.children if not (
            c.node_type == "Operator" and c.value in structural)]

        if not children:
            if node.value is not None:
                return str(node.value)
            return ""

        parts = []
        for child in children:
            if child.node_type == "Operator":
                op = str(child.value)
                # Map BASIC-style operators to Python
                if op == "=" and node.node_type == "comparison":
                    parts.append("==")
                elif op == "<>":
                    parts.append("!=")
                else:
                    parts.append(self._map_operator(op))
            else:
                parts.append(self._expr_to_str(child))

        return " ".join(p for p in parts if p)

    def _expr_binary(self, node: SourceAST) -> str:
        if len(node.children) >= 2:
            left = self._expr_to_str(node.children[0])
            right = self._expr_to_str(node.children[1])
            op = self._map_operator(str(node.value)) if node.value else "+"
            return f"({left} {op} {right})"
        return ""

    def _expr_unary(self, node: SourceAST) -> str:
        if not node.children:
            return ""

        # PEG-style: children may include Operator node followed by operand
        if (node.children[0].node_type == "Operator"
                and len(node.children) >= 2):
            op = node.children[0].value or "-"
            operand = self._expr_to_str(node.children[1])
        elif len(node.children) == 1:
            # Transparent pass-through (e.g., unary → call)
            return self._expr_to_str(node.children[0])
        else:
            operand = self._expr_to_str(node.children[0])
            op = str(node.value) if node.value else "-"

        op = self._map_operator(op)
        if op.lower() in ("not", "NOT"):
            return f"not {operand}"
        return f"({op}{operand})"

    def _expr_call(self, node: SourceAST) -> str:
        children = node.children
        if not children:
            return ""

        # Filter out parenthesis operators from PEG-style AST
        func = self._expr_to_str(children[0])
        func = self._map_function(func)

        # Track module imports for qualified names like math.sqrt,
        # random.random
        if "." in func and not func.startswith("lambda"):
            module_part = func.split(".")[0]
            if module_part.isidentifier():
                self._imports_needed.add(module_part)

        # Check if this is actually a call (has opening paren)
        has_paren = any(c.node_type == "Operator" and c.value == "("
                        for c in children)
        if not has_paren:
            # Not a call — just a primary expression wrapped in 'call'
            if len(children) == 1:
                return func
            return func

        args = []
        for child in children[1:]:
            if child.node_type == "arg_list":
                # Filter Operator(',') from arg_list children
                args = [self._expr_to_str(a) for a in child.children
                        if not (a.node_type == "Operator" and a.value == ",")]
            elif (child.node_type == "Operator"
                  and child.value in ("(", ")", ",")):
                continue  # Skip punctuation
            else:
                args.append(self._expr_to_str(child))

        arg_text = ", ".join(args)
        if func.startswith("lambda"):
            return f"({func})({arg_text})"
        return f"{func}({arg_text})"

    def _expr_list(self, node: SourceAST) -> str:
        items = [
            c for c in node.children
            if not (c.node_type == "Operator" and c.value in ("[", "]", ","))
        ]
        return f"[{', '.join(self._expr_to_str(c) for c in items)}]"

    def _expr_dict(self, node: SourceAST) -> str:
        items = [
            c for c in node.children
            if not (c.node_type == "Operator"
                    and c.value in ("{", "}", ",", ":"))
        ]
        pairs = []
        for i in range(0, len(items) - 1, 2):
            key = self._expr_to_str(items[i])
            val = self._expr_to_str(items[i + 1])
            pairs.append(f"{key}: {val}")
        return "{" + ", ".join(pairs) + "}"

    def _expr_assignment(self, node: SourceAST) -> str:
        children = node.children
        if len(children) >= 2:
            target = self._expr_to_str(children[0])
            value = self._expr_to_str(children[1])
            return f"{target} = {value}"
        return ""

    def _expr_param_list(self, node: SourceAST) -> str:
        items = [
            c for c in node.children
            if not (c.node_type == "Operator" and c.value in ("(", ")", ","))
        ]
        return ", ".join(self._expr_to_str(c) for c in items)

    def _expr_arg_list(self, node: SourceAST) -> str:
        items = [
            c for c in node.children
            if not (c.node_type == "Operator" and c.value in ("(", ")", ","))
        ]
        return ", ".join(self._expr_to_str(c) for c in items)

    def _emit_transparent_binary(self, node: SourceAST) -> None:
        """For term-like nodes that may chain operators."""
        expr = self._expr_binary_chain(node)
        self._line(expr)

    # -----------------------------------------------------------------------
    # Mapping helpers
    # -----------------------------------------------------------------------

    def _map_keyword(self, word: str) -> str:
        return self.options.keyword_map.get(word, word)

    def _map_identifier(self, name: str) -> str:
        return self.options.keyword_map.get(name, name)

    def _map_function(self, name: str) -> str:
        # Check explicit map first
        mapped = self.options.function_map.get(name)
        if mapped:
            return mapped
        # Built-in BASIC→Python function mappings
        _basic_funcs = {
            "STR": "str", "VAL": "int", "INT": "int",
            "ABS": "abs", "LEN": "len", "CHRS": "chr",
            "ASC": "ord", "UCASE": "str.upper",
            "LCASE": "str.lower",
            "MID": "lambda s,i,n: s[i:i+n]",
            "LEFTS": "lambda s,n: s[:n]",
            "RIGHTS": "lambda s,n: s[-n:]",
            "SQR": "math.sqrt", "RND": "random.random",
            "SGN": "lambda x: (x>0)-(x<0)",
            "TIMER": "time.time", "INSTR": "str.find",
            "TAB": "lambda n: ' '*n",
            "SPC": "lambda n: ' '*n",
        }
        return _basic_funcs.get(name, name)

    def _map_operator(self, op: str) -> str:
        return self.options.operator_map.get(op, op)

    # -----------------------------------------------------------------------
    # Output helpers
    # -----------------------------------------------------------------------

    def _line(self, text: str) -> None:
        """Add an indented line to output."""
        indent = self.options.indent_str * self.indent_level
        self.output_lines.append(f"{indent}{text}")

    def _generate_runtime(self) -> str:
        """Generate runtime helper functions."""
        parts = ["# ParserCraft Runtime Helpers"]
        if "range" in self._runtime_needed:
            parts.append("# range() is a Python builtin — no helper needed")
        if "print" in self._runtime_needed:
            parts.append("# print() is a Python builtin — no helper needed")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def transpile_to_python(ast: SourceAST,
                        keyword_map: Optional[Dict[str, str]] = None,
                        function_map: Optional[Dict[str, str]] = None,
                        wrap_main: bool = False) -> str:
    """One-liner to transpile a SourceAST to Python source."""
    opts = TranspileOptions(
        keyword_map=keyword_map or {},
        function_map=function_map or {},
        wrap_in_main=wrap_main,
    )
    return PythonTranspiler(opts).transpile(ast)


def transpile_and_exec(ast: SourceAST,
                       keyword_map: Optional[Dict[str, str]] = None,
                       function_map: Optional[Dict[str, str]] = None,
                       globals_dict: Optional[Dict[str, Any]] = None
                       ) -> Dict[str, Any]:
    """Transpile and execute, returning the user-visible namespace.

    Dunder entries injected by ``exec`` (notably ``__builtins__``) are
    filtered out so the result only contains program-defined names plus
    anything supplied via ``globals_dict``.
    """
    code = transpile_to_python(ast, keyword_map, function_map)
    ns = globals_dict if globals_dict is not None else {}
    exec(code, ns)  # noqa: S102  # pylint: disable=exec-used
    return {key: value for key, value in ns.items() if not key.startswith("__")}
