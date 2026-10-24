"""Control-flow emission (if/while/for) for the Python transpiler."""

from __future__ import annotations

import re

from lashon.ast import SourceAST


class ControlFlowEmitter:
    """Turns ``if``/``while``/``for`` statements into Python blocks."""

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
