"""Statement emission for the Python transpiler."""

from __future__ import annotations

from typing import Optional

from lashon.ast import SourceAST


class StatementEmitter:
    """Turns statement AST nodes into Python source text."""

    def _emit_program(self, node: SourceAST) -> None:
        lines = [c for c in node.children if c.node_type == "line"]
        others = [
            c for c in node.children
            if c.node_type not in ("line", "Operator")
        ]
        if lines and not others:
            self._emit_numbered_program(lines)
            return
        for child in node.children:
            self._emit_node(child)

    # -- line-numbered programs -----------------------------------------

    @staticmethod
    def _line_number(node: SourceAST) -> Optional[int]:
        """The number a ``line`` node starts with, if any."""
        for child in node.children:
            if child.node_type in ("Number", "NUMBER"):
                try:
                    return int(float(child.value))
                except (TypeError, ValueError):
                    return None
        return None

    @staticmethod
    def _line_statement(node: SourceAST) -> Optional[SourceAST]:
        """The statement a ``line`` node carries, if any."""
        for child in node.children:
            if child.node_type not in ("Number", "NUMBER", "Operator"):
                return child
        return None

    def _emit_rem(self, node: SourceAST) -> None:
        """REM comment → a Python comment."""
        text = node.value if isinstance(node.value, str) else ""
        self._line(f"# {text}".rstrip())

    def _emit_line(self, node: SourceAST) -> None:
        """A ``line`` outside a numbered program: emit just its statement."""
        statement = self._line_statement(node)
        if statement is not None:
            self._emit_node(statement)

    def _emit_numbered_program(self, lines: list[SourceAST]) -> None:
        """Emit a BASIC-style program as a program-counter loop.

        Python has no ``goto``, so every line becomes one branch of a
        ``while`` over a synthetic program counter. Variables stay local to the
        generated function, which is then merged back into the namespace the
        callers report.
        """
        entries: list[tuple[int, Optional[SourceAST], Optional[int]]] = []
        for line in lines:
            number = self._line_number(line)
            if number is not None:
                entries.append((number, self._line_statement(line), None))
        if not entries:
            return

        numbered = [
            (number, statement,
             entries[index + 1][0] if index + 1 < len(entries) else None)
            for index, (number, statement, _) in enumerate(entries)
        ]

        assigned = sorted(self._assigned_names(lines))
        self._line("def _lashon_numbered_program():")
        self.indent_level += 1
        if assigned:
            self._line(f"global {', '.join(assigned)}")
        self._line(f"_pc = {numbered[0][0]}")
        self._line("while _pc is not None:")
        self.indent_level += 1
        for index, (number, statement, next_number) in enumerate(numbered):
            keyword = "if" if index == 0 else "elif"
            self._line(f"{keyword} _pc == {number}:")
            self.indent_level += 1
            self._emit_numbered_statement(statement, next_number)
            self.indent_level -= 1
        self._line("else:")
        self.indent_level += 1
        self._line("_pc = None")
        self.indent_level -= 1
        self.indent_level -= 1
        self.indent_level -= 1
        self._line("_lashon_numbered_program()")

    def _emit_numbered_statement(self, statement: Optional[SourceAST],
                                 next_number: Optional[int]) -> None:
        """Emit one BASIC statement, then fall through or jump."""
        if statement is None:
            self._line(self._advance(next_number))
            return

        while statement.node_type in ("statement", "Statement"):
            inner = [
                child for child in statement.children
                if child.node_type != "Operator"
            ]
            if len(inner) != 1:
                break
            statement = inner[0]

        kind = statement.node_type
        if kind in ("goto_stmt", "GotoStmt"):
            target = self._line_number(statement)
            self._line(
                f"_pc = {target}" if target is not None else "_pc = None"
            )
            return
        if kind in ("end_stmt", "EndStmt"):
            self._line("_pc = None")
            return
        if kind in ("rem_stmt", "RemStmt"):
            self._line(self._advance(next_number))
            return
        if kind in ("if_stmt", "IfStmt"):
            self._emit_numbered_if(statement, next_number)
            return

        self._emit_node(statement)
        self._line(self._advance(next_number))

    def _emit_numbered_if(self, statement: SourceAST,
                          next_number: Optional[int]) -> None:
        """IF condition THEN statement [ELSE statement]."""
        parts = [
            child for child in statement.children
            if child.node_type != "Operator"
        ]
        if not parts:
            self._line(self._advance(next_number))
            return
        condition = self._expr_to_str(parts[0])
        self._line(f"if {condition}:")
        self.indent_level += 1
        self._emit_numbered_statement(
            parts[1] if len(parts) > 1 else None, next_number
        )
        self.indent_level -= 1
        self._line("else:")
        self.indent_level += 1
        if len(parts) > 2:
            self._emit_numbered_statement(parts[2], next_number)
        else:
            self._line(self._advance(next_number))
        self.indent_level -= 1


    @classmethod
    def _assigned_names(cls, nodes) -> set[str]:
        """Identifiers the program assigns, for the generated ``global`` line."""
        names: set[str] = set()
        for node in nodes:
            names |= cls._assigned_names_in(node)
        return names

    @classmethod
    def _assigned_names_in(cls, node: SourceAST) -> set[str]:
        names: set[str] = set()
        if node.node_type in ("let_stmt", "LetStmt", "assign_stmt",
                              "AssignStmt"):
            for child in node.children:
                if child.node_type in ("Identifier", "IDENT"):
                    names.add(str(child.value))
                    break
        elif node.node_type in ("statement", "Statement"):
            parts = [
                child for child in node.children
                if child.node_type != "Operator"
            ]
            operators = [
                child.value for child in node.children
                if child.node_type == "Operator"
            ]
            if (
                len(parts) == 2
                and parts[0].node_type in ("Identifier", "IDENT")
                and any(op in ("=", ":=") for op in operators)
            ):
                names.add(str(parts[0].value))
        for child in node.children:
            names |= cls._assigned_names_in(child)
        return names

    @staticmethod
    def _advance(next_number: Optional[int]) -> str:
        return "_pc = None" if next_number is None else f"_pc = {next_number}"

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
        """CLS → clear the canvas"""
        self._imports_needed.add("turtle")
        self._line("turtle.clear()")

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
