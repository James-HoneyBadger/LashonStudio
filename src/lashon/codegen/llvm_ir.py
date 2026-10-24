"""
LLVM IR Code Generator for Lashon

Generates LLVM Intermediate Representation from SourceAST trees produced
by the PEG grammar engine. The output can be compiled with clang/llc to
produce native executables for any LLVM-supported target.

Usage:
    from lashon.codegen.llvm_ir import LLVMIRGenerator

    gen = LLVMIRGenerator()
    ir = gen.translate_source_ast(ast)  # SourceAST from grammar engine
    gen.save("output.ll")

    # Compile with:
    #   clang output.ll -o program
    #   OR:
    #   llc output.ll -o output.s && gcc output.s -o program

LLVM IR overview:
    - SSA form (Static Single Assignment)
    - Typed instructions (i32, i64, double, ptr)
    - Basic blocks with explicit terminators (br, ret)
    - Global strings via @.str constants
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from lashon.codegen.common import (
    COMPARISON_OPERATORS,
    inline_assignment,
    meaningful_children,
    split_chain,
)

_COMPARISON_OPS = frozenset({"==", "!=", "<", ">", "<=", ">="})


@dataclass
class IRValue:
    """A value in LLVM IR (register, constant, or global)."""
    name: str          # e.g., "%1", "%x", "@.str.0"
    ir_type: str       # e.g., "i32", "double", "ptr"
    is_const: bool = False

    def typed(self) -> str:
        """Return 'type name' for use in instructions."""
        return f"{self.ir_type} {self.name}"

    def __repr__(self) -> str:
        return self.name


@dataclass
class BasicBlock:
    """A basic block in LLVM IR."""
    label: str
    instructions: List[str] = field(default_factory=list)
    terminated: bool = False

    def emit(self, inst: str) -> None:
        if not self.terminated:
            self.instructions.append(f"  {inst}")

    def terminate(self, inst: str) -> None:
        if not self.terminated:
            self.instructions.append(f"  {inst}")
            self.terminated = True

    def to_ir(self) -> str:
        lines = [f"{self.label}:"]
        lines.extend(self.instructions)
        return "\n".join(lines)


@dataclass
class IRFunction:
    """An LLVM IR function."""
    name: str
    return_type: str = "i32"
    params: List[Tuple[str, str]] = field(default_factory=list)  # (type, name)
    blocks: List[BasicBlock] = field(default_factory=list)
    local_allocs: List[str] = field(default_factory=list)

    def to_ir(self) -> str:
        params_str = ", ".join(f"{t} {n}" for t, n in self.params)
        lines = [f"define {self.return_type} @{self.name}({params_str}) {{"]
        for block in self.blocks:
            lines.append(block.to_ir())
        lines.append("}")
        return "\n".join(lines)


class LLVMIRGenerator:
    """Generates LLVM IR from SourceAST trees.

    Produces textual LLVM IR (.ll files) that can be compiled to
    native code via clang or llc.
    """

    def __init__(self):
        self.globals: List[str] = []
        self.functions: List[IRFunction] = []
        self.string_constants: Dict[str, str] = {}  # value -> @name
        self._reg_counter = 0
        self._str_counter = 0
        self._fmt_counter = 0
        self._label_counter = 0
        self._current_func: Optional[IRFunction] = None
        self._current_block: Optional[BasicBlock] = None
        self._variables: Dict[str, IRValue] = {}   # name -> alloca'd pointer
        self._output: str = ""

    def translate_source_ast(self, ast: Any) -> str:
        """Translate a SourceAST tree into LLVM IR text."""
        self.globals = []
        self.functions = []
        self.string_constants = {}
        self._reg_counter = 0
        self._str_counter = 0
        self._fmt_counter = 0
        self._label_counter = 0
        self._variables = {}

        # Declare printf for output support
        self.globals.append('declare i32 @printf(ptr, ...)')
        self.globals.append('')

        # Create main function
        main = IRFunction(name="main", return_type="i32")
        entry = BasicBlock(label="entry")
        main.blocks.append(entry)
        self._current_func = main
        self._current_block = entry

        # Translate AST
        self._visit(ast)

        # Ensure terminator
        if not self._current_block.terminated:
            self._current_block.terminate("ret i32 0")

        self.functions.append(main)

        return self._build_output()

    def save(self, filename: str) -> None:
        """Save the LLVM IR to a file."""
        with open(filename, "w") as f:
            f.write(self._output)

    # -------------------------------------------------------------------
    # AST visitor
    # -------------------------------------------------------------------

    def _visit(self, node: Any) -> Optional[IRValue]:
        """Visit a SourceAST node, returning an IRValue for expression nodes."""
        nt = node.node_type
        method = f"_visit_{nt}"
        if hasattr(self, method):
            return getattr(self, method)(node)

        # Generic dispatch
        if nt in ("program", "Program", "Module"):
            return self._visit_program(node)
        if nt in ("statement", "Statement"):
            return self._visit_transparent(node)
        if nt in ("assignment", "Assignment"):
            return self._visit_assignment(node)
        if nt in ("expr_stmt", "ExprStmt"):
            return self._visit_expr_stmt(node)
        if nt in ("expr", "Expr", "comparison", "addition", "multiplication", "term"):
            return self._visit_binary_chain(node)
        if nt in ("factor", "primary"):
            return self._visit_transparent(node)
        if nt in ("Number",):
            return self._visit_number(node)
        if nt in ("String",):
            return self._visit_string(node)
        if nt in ("Identifier", "IDENT"):
            return self._visit_identifier(node)
        if nt == "Operator":
            return None
        if nt in ("function_def", "FunctionDef"):
            return self._visit_function_def(node)
        if nt in ("return_stmt", "ReturnStmt"):
            return self._visit_return(node)
        if nt in ("if_stmt", "IfStmt"):
            return self._visit_if(node)
        if nt in ("while_stmt", "WhileStmt"):
            return self._visit_while(node)
        if nt in ("block", "Block"):
            for child in node.children:
                self._visit(child)
            return None
        if nt in ("call", "Call", "FunctionCall"):
            return self._visit_call(node)
        if nt in ("print_stmt", "PrintStmt"):
            return self._visit_print_stmt(node)

        # Fallback: visit children
        return self._visit_transparent(node)

    def _visit_program(self, node: Any) -> None:
        for child in node.children:
            self._visit(child)

    def _visit_transparent(self, node: Any) -> Optional[IRValue]:
        """Pass-through wrapper nodes, returning the value of the first meaningful child.

        For statement nodes, detect inline assignment patterns.
        """
        pair = inline_assignment(node)
        if pair is not None:
            target, value_node = pair
            name = self._node_name(target)
            val = self._visit(value_node)
            if val is not None:
                if name not in self._variables:
                    ptr = self._next_reg()
                    self._emit(f"{ptr} = alloca {val.ir_type}")
                    self._variables[name] = IRValue(ptr, "ptr")
                self._emit(f"store {val.typed()}, ptr {self._variables[name].name}")
            return None

        meaningful = [c for c in node.children if c.node_type != "Operator"]
        if meaningful:
            return self._visit(meaningful[0])
        return None

    def _visit_assignment(self, node: Any) -> None:
        meaningful = meaningful_children(node)
        if len(meaningful) < 2:
            return

        name = self._node_name(meaningful[0])
        val = self._visit(meaningful[1])
        if val is None:
            return

        # Allocate local if needed
        if name not in self._variables:
            ptr = self._next_reg()
            self._emit(f"{ptr} = alloca {val.ir_type}")
            self._variables[name] = IRValue(ptr, "ptr")

        # Store
        self._emit(f"store {val.typed()}, ptr {self._variables[name].name}")

    def _visit_number(self, node: Any) -> IRValue:
        val = node.value
        if isinstance(val, float):
            return IRValue(str(val), "double", is_const=True)
        return IRValue(str(int(val)), "i32", is_const=True)

    def _visit_string(self, node: Any) -> IRValue:
        text = str(node.value)
        if text not in self.string_constants:
            name = f"@.str.{self._str_counter}"
            self._str_counter += 1
            # +1 for null terminator
            length = len(text) + 1
            escaped = text.replace("\\", "\\5C").replace('"', '\\22').replace("\n", "\\0A")
            self.globals.append(
                f'{name} = private unnamed_addr constant [{length} x i8] c"{escaped}\\00"'
            )
            self.string_constants[text] = name
        return IRValue(self.string_constants[text], "ptr", is_const=True)

    def _visit_identifier(self, node: Any) -> Optional[IRValue]:
        name = str(node.value)
        if name in self._variables:
            ptr = self._variables[name]
            reg = self._next_reg()
            self._emit(f"{reg} = load i32, ptr {ptr.name}")
            return IRValue(reg, "i32")
        # Unknown identifier — return as i32 0 with a comment
        self._emit(f"; WARNING: undefined variable '{name}'")
        return IRValue("0", "i32", is_const=True)

    def _visit_binary_chain(self, node: Any) -> Optional[IRValue]:
        """Handle binary operator chains: operand (op operand)*"""
        operands, operators = split_chain(node)
        if not operands:
            return None

        result = self._visit(operands[0])
        if result is None:
            return None

        for i, op_node in enumerate(operators):
            if i + 1 >= len(operands):
                break
            rhs = self._visit(operands[i + 1])
            if rhs is None:
                continue

            op = str(op_node.value)
            reg = self._next_reg()
            ir_type = result.ir_type

            if ir_type == "double":
                inst = self._float_op(op, result, rhs, reg)
            else:
                inst = self._int_op(op, result, rhs, reg)

            if inst:
                self._emit(inst)
                result = IRValue(reg, "i1" if op in COMPARISON_OPERATORS else ir_type)

        return result

    def _visit_expr_stmt(self, node: Any) -> None:
        meaningful = [c for c in node.children if c.node_type != "Operator"]
        if meaningful:
            self._visit(meaningful[0])
            # Result is discarded

    def _visit_function_def(self, node: Any) -> None:
        """Translate function definition."""
        meaningful = [c for c in node.children if c.node_type != "Operator"]
        name = ""
        params = []
        body_children = []

        for child in meaningful:
            if child.node_type in ("Identifier", "IDENT") and not name:
                name = str(child.value)
            elif child.node_type == "param_list":
                params = [(str(p.value), "i32") for p in child.children
                          if p.node_type in ("Identifier", "IDENT")]
            elif child.node_type in ("block", "Block"):
                body_children = child.children
            else:
                body_children.append(child)

        if not name:
            return

        # Save current state
        saved_func = self._current_func
        saved_block = self._current_block
        saved_vars = self._variables.copy()

        # Create new function
        func = IRFunction(
            name=name,
            return_type="i32",
            params=[("i32", f"%{pn}") for pn, _ in params],
        )
        entry = BasicBlock(label="entry")
        func.blocks.append(entry)
        self._current_func = func
        self._current_block = entry
        self._variables = {}

        # Add params to scope
        for pname, _ in params:
            ptr = self._next_reg()
            self._emit(f"{ptr} = alloca i32")
            self._emit(f"store i32 %{pname}, ptr {ptr}")
            self._variables[pname] = IRValue(ptr, "ptr")

        # Translate body
        for child in body_children:
            self._visit(child)

        if not self._current_block.terminated:
            self._current_block.terminate("ret i32 0")

        self.functions.append(func)

        # Restore state
        self._current_func = saved_func
        self._current_block = saved_block
        self._variables = saved_vars

    def _visit_return(self, node: Any) -> None:
        meaningful = [c for c in node.children if c.node_type != "Operator"]
        if meaningful:
            val = self._visit(meaningful[0])
            if val:
                if val.ir_type == "i1":
                    widened = self._next_reg()
                    self._emit(f"{widened} = zext i1 {val.name} to i32")
                    val = IRValue(widened, "i32")
                self._current_block.terminate(f"ret {val.typed()}")
            else:
                self._current_block.terminate("ret i32 0")
        else:
            self._current_block.terminate("ret i32 0")

    def _visit_if(self, node: Any) -> None:
        children = [c for c in node.children if c.node_type != "Operator"]
        if not children:
            return

        cond = self._visit(children[0])
        if cond is None:
            return

        cond_bool = self._as_condition(cond)

        then_label = self._next_label("then")
        else_label = self._next_label("else")
        end_label = self._next_label("endif")

        self._current_block.terminate(f"br i1 {cond_bool}, label %{then_label}, label %{else_label}")

        # Then block
        then_block = BasicBlock(label=then_label)
        self._current_func.blocks.append(then_block)
        self._current_block = then_block

        blocks = [
            c for c in children[1:]
            if c.node_type in ("block", "Block")
        ]
        then_nodes = blocks[0].children if blocks else children[1:]
        else_nodes = blocks[1].children if len(blocks) > 1 else []

        for stmt in then_nodes:
            self._visit(stmt)

        if not self._current_block.terminated:
            self._current_block.terminate(f"br label %{end_label}")

        # Else block
        else_block = BasicBlock(label=else_label)
        self._current_func.blocks.append(else_block)
        self._current_block = else_block
        for stmt in else_nodes:
            self._visit(stmt)
        self._current_block.terminate(f"br label %{end_label}")

        # End block
        end_block = BasicBlock(label=end_label)
        self._current_func.blocks.append(end_block)
        self._current_block = end_block

    def _visit_while(self, node: Any) -> None:
        children = [c for c in node.children if c.node_type != "Operator"]
        if not children:
            return

        cond_label = self._next_label("while.cond")
        body_label = self._next_label("while.body")
        end_label = self._next_label("while.end")

        self._current_block.terminate(f"br label %{cond_label}")

        # Condition block
        cond_block = BasicBlock(label=cond_label)
        self._current_func.blocks.append(cond_block)
        self._current_block = cond_block

        cond = self._visit(children[0])
        if cond:
            cond_bool = self._as_condition(cond)
            self._current_block.terminate(f"br i1 {cond_bool}, label %{body_label}, label %{end_label}")
        else:
            self._current_block.terminate(f"br label %{end_label}")

        # Body block
        body_block = BasicBlock(label=body_label)
        self._current_func.blocks.append(body_block)
        self._current_block = body_block

        if len(children) > 1:
            for child in children[1:]:
                self._visit(child)

        if not self._current_block.terminated:
            self._current_block.terminate(f"br label %{cond_label}")

        # End block
        end_block = BasicBlock(label=end_label)
        self._current_func.blocks.append(end_block)
        self._current_block = end_block

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    def _as_condition(self, value: IRValue) -> str:
        """Return an i1 register usable in a conditional branch."""
        if value.ir_type == "i1":
            return value.name
        reg = self._next_reg()
        self._emit(f"{reg} = icmp ne {value.typed()}, 0")
        return reg

    def _visit_call(self, node: Any) -> Optional[IRValue]:
        """Translate a function call, emitting a ``call`` instruction."""
        structural = {"(", ")", ",", ";"}
        meaningful = [
            c for c in node.children
            if not (c.node_type == "Operator" and c.value in structural)
        ]
        if not meaningful:
            return None

        name = self._node_name(meaningful[0])
        args: List[IRValue] = []
        for child in meaningful[1:]:
            value = self._visit(child)
            if value is not None:
                args.append(value)

        arg_list = ", ".join(arg.typed() for arg in args)
        reg = self._next_reg()
        self._emit(f"{reg} = call i32 @{name}({arg_list})")
        return IRValue(reg, "i32")

    def _visit_print_stmt(self, node: Any) -> None:
        """Translate a print statement into a printf call per argument."""
        args = [c for c in node.children if c.node_type != "Operator"]
        for child in args:
            value = self._visit(child)
            if value is None:
                continue
            fmt = self._format_global(value.ir_type)
            reg = self._next_reg()
            self._emit(
                f"{reg} = call i32 (ptr, ...) @printf(ptr {fmt}, {value.typed()})"
            )

    def _format_global(self, ir_type: str) -> str:
        """Return (creating on demand) a printf format string for a type."""
        specifier = {
            "double": "%f",
            "ptr": "%s",
            "i64": "%ld",
        }.get(ir_type, "%d")
        if specifier in self.string_constants:
            return self.string_constants[specifier]

        name = f"@.fmt.{self._fmt_counter}"
        self._fmt_counter += 1
        raw = specifier + "\n"
        escaped = raw.replace("\\", "\\5C").replace('"', '\\22').replace("\n", "\\0A")
        self.globals.append(
            f'{name} = private unnamed_addr constant [{len(raw) + 1} x i8] '
            f'c"{escaped}\\00"'
        )
        self.string_constants[specifier] = name
        return name

    def _int_op(self, op: str, lhs: IRValue, rhs: IRValue, reg: str) -> str:
        op_map = {
            "+": "add", "-": "sub", "*": "mul", "/": "sdiv", "%": "srem",
            "==": "icmp eq", "!=": "icmp ne",
            "<": "icmp slt", ">": "icmp sgt",
            "<=": "icmp sle", ">=": "icmp sge",
        }
        ir_op = op_map.get(op)
        if ir_op:
            return f"{reg} = {ir_op} i32 {lhs.name}, {rhs.name}"
        return ""

    def _float_op(self, op: str, lhs: IRValue, rhs: IRValue, reg: str) -> str:
        op_map = {
            "+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv",
            "==": "fcmp oeq", "!=": "fcmp one",
            "<": "fcmp olt", ">": "fcmp ogt",
            "<=": "fcmp ole", ">=": "fcmp oge",
        }
        ir_op = op_map.get(op)
        if ir_op:
            return f"{reg} = {ir_op} double {lhs.name}, {rhs.name}"
        return ""

    def _emit(self, inst: str) -> None:
        if self._current_block:
            self._current_block.emit(inst)

    def _next_reg(self) -> str:
        self._reg_counter += 1
        return f"%{self._reg_counter}"

    def _next_label(self, prefix: str = "L") -> str:
        self._label_counter += 1
        return f"{prefix}.{self._label_counter}"

    def _node_name(self, node: Any) -> str:
        if node.node_type in ("Identifier", "IDENT"):
            return str(node.value)
        return str(node.value) if node.value else "unknown"

    def _build_output(self) -> str:
        parts = [
            "; Auto-generated LLVM IR from Lashon",
            "; Compile with: clang output.ll -o program",
            "",
        ]

        # Globals
        for g in self.globals:
            parts.append(g)

        parts.append("")

        # Functions
        for func in self.functions:
            parts.append(func.to_ir())
            parts.append("")

        self._output = "\n".join(parts)
        return self._output
