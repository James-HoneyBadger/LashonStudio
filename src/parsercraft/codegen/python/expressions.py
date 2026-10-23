"""Expression emission for :class:`~.transpiler.PythonTranspiler`."""

from __future__ import annotations

from parsercraft.ast import SourceAST


class ExpressionEmitter:
    """Turns expression AST nodes into Python source text."""

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
