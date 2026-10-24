"""
AST-to-Python Transpiler for Lashon

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

from lashon.ast import SourceAST

from .control_flow import ControlFlowEmitter
from .expressions import ExpressionEmitter
from .statements import StatementEmitter


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


class PythonTranspiler(StatementEmitter, ControlFlowEmitter, ExpressionEmitter):
    """Transpiles a SourceAST tree into Python source code.

    Handles both SourceAST nodes (from the PEG grammar engine) and
    generic dict-based AST representations.
    """

    def __init__(self, options: Optional[TranspileOptions] = None):
        self.options = options or TranspileOptions()
        self.indent_level = 0
        self.output_lines: List[str] = []
        self.line_map: Dict[int, int] = {}
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
            "line": self._emit_line,
            "Line": self._emit_line,
            "rem_stmt": self._emit_rem,
            "RemStmt": self._emit_rem,
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
        self.line_map = {}
        self.indent_level = 0
        self._runtime_needed = set()
        self._imports_needed = set()

        self._emit_node(ast)

        result = "\n".join(self.output_lines)

        if self.options.inject_runtime and self._runtime_needed:
            runtime = self._generate_runtime()
            result = runtime + "\n\n" + result

        # Auto-prepend imports for modules referenced by generated code
        modules = sorted(m for m in self._imports_needed if m != "turtle")
        if modules:
            imports = "\n".join(f"import {m}" for m in modules)
            result = imports + "\n\n" + result

        # Turtle statements draw on the host's canvas when there is one, and on
        # a headless recorder otherwise, so a program never needs a screen.
        if "turtle" in self._imports_needed:
            header = (
                "from lashon.runtime.graphics import attach as _lashon_attach\n"
                "turtle = _lashon_attach()\n"
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
            result = header + "\n" + result

        if self.options.wrap_in_main:
            # Re-indent everything under if __name__
            indented = "\n".join(f"    {line}" if line.strip(
            ) else "" for line in result.split("\n"))
            result = f'if __name__ == "__main__":\n{indented}\n'

        if self.options.source_maps:
            self.line_map = self._build_line_map(result)

        return result

    @staticmethod
    def _build_line_map(source: str) -> Dict[int, int]:
        """Map generated Python line numbers to source line numbers."""
        mapping: Dict[int, int] = {}
        current: Optional[int] = None
        for number, line in enumerate(source.split("\n"), 1):
            marker = re.match(r"\s*#\s*@src\s+(\d+)\s*$", line)
            if marker:
                current = int(marker.group(1))
                continue
            if current is not None:
                mapping[number] = current
        return mapping

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

    _SOURCE_MAP_NODES = frozenset({
        "assignment", "Assignment", "function_def", "FunctionDef",
        "if_stmt", "IfStmt", "while_stmt", "WhileStmt", "for_stmt",
        "ForStmt", "return_stmt", "ReturnStmt", "expr_stmt", "ExprStmt",
        "print_stmt", "PrintStmt", "say_stmt", "ask_stmt", "let_stmt",
        "repeat_stmt",
    })

    def _emit_node(self, node: SourceAST) -> None:
        """Dispatch to the appropriate handler for a node."""
        if (
            self.options.source_maps
            and getattr(node, "line", 0)
            and node.node_type in self._SOURCE_MAP_NODES
        ):
            self._line(f"# @src {node.line}")

        handler = self._handlers.get(node.node_type)
        if handler:
            handler(node)
        else:
            # Fallback: emit children transparently
            for child in node.children:
                self._emit_node(child)
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
                       globals_dict: Optional[Dict[str, Any]] = None,
                       graphics: Any = None
                       ) -> Dict[str, Any]:
    """Transpile and execute, returning the user-visible namespace.

    Dunder entries injected by ``exec`` (notably ``__builtins__``) are
    filtered out so the result only contains program-defined names plus
    anything supplied via ``globals_dict``.

    Pass a :class:`lashon.runtime.graphics.Graphics` as ``graphics`` to
    capture whatever the program draws.
    """
    code = transpile_to_python(ast, keyword_map, function_map)
    ns = globals_dict if globals_dict is not None else {}
    if graphics is None:
        exec(code, ns)  # noqa: S102  # pylint: disable=exec-used
    else:
        with graphics.active():
            exec(code, ns)  # noqa: S102  # pylint: disable=exec-used
    return {key: value for key, value in ns.items() if not key.startswith("__")}
