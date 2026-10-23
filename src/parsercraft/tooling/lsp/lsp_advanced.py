#!/usr/bin/env python3
"""
LSP Advanced Features: Refactoring, Formatting, and Semantic Highlighting

Extends LSP server with professional IDE features.

Features:
    - Rename refactoring
    - Extract function/variable
    - Code formatting (configurable)
    - Semantic highlighting tokens
    - Inlay hints
    - Code actions (quick fixes)

Usage:
    from parsercraft.lsp_advanced import RefactoringEngine, CodeFormatter
    
    refactor = RefactoringEngine(config)
    edits = refactor.rename("oldName", "newName", file_path)
    
    formatter = CodeFormatter(config)
    formatted = formatter.format(source_code)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class TokenType(Enum):
    """Semantic token types for highlighting."""

    KEYWORD = "keyword"
    VARIABLE = "variable"
    FUNCTION = "function"
    CLASS = "class"
    INTERFACE = "interface"
    STRUCT = "struct"
    ENUM = "enum"
    TYPE = "type"
    PARAMETER = "parameter"
    PROPERTY = "property"
    FIELD = "field"
    CONSTANT = "constant"
    COMMENT = "comment"
    STRING = "string"
    NUMBER = "number"
    OPERATOR = "operator"
    NAMESPACE = "namespace"


class TokenModifier(Enum):
    """Semantic token modifiers."""

    DECLARATION = "declaration"
    DEFINITION = "definition"
    READONLY = "readonly"
    STATIC = "static"
    ABSTRACT = "abstract"
    DEPRECATED = "deprecated"
    ASYNC = "async"


@dataclass
class TextEdit:
    """Represents a text edit for refactoring."""

    line: int
    start_col: int
    end_col: int
    new_text: str

    def __repr__(self) -> str:
        return f"Edit({self.line}:{self.start_col}-{self.end_col} -> '{self.new_text}')"


@dataclass
class SemanticToken:
    """Represents a semantic token for highlighting."""

    line: int
    start_col: int
    length: int
    token_type: TokenType
    modifiers: List[TokenModifier] = field(default_factory=list)

    def to_lsp_format(self) -> Tuple[int, int, int, int, int]:
        """Convert to LSP semantic tokens format."""
        # (line, start_char, length, tokenType, tokenModifiers)
        token_type_idx = list(TokenType).index(self.token_type)
        modifier_mask = 0
        for modifier in self.modifiers:
            modifier_idx = list(TokenModifier).index(modifier)
            modifier_mask |= 1 << modifier_idx

        return (self.line, self.start_col, self.length, token_type_idx, modifier_mask)


@dataclass
class CodeAction:
    """Represents a code action (quick fix)."""

    title: str
    kind: str  # e.g., "quickfix", "refactor"
    edits: List[TextEdit]
    command: Optional[str] = None
    is_preferred: bool = False

    def __repr__(self) -> str:
        return f"CodeAction('{self.title}', {len(self.edits)} edits)"


class RefactoringEngine:
    """Performs code refactoring operations."""

    def __init__(self, config: Any = None):
        self.config = config
        self.symbol_table: Dict[str, List[Tuple[int, int]]] = {}  # name -> positions

    def build_symbol_table(self, source: str) -> None:
        """Build symbol table from source code."""
        lines = source.split("\n")
        self.symbol_table.clear()

        for line_num, line in enumerate(lines):
            # Simple identifier matching
            import re

            for match in re.finditer(r"\b([a-zA-Z_]\w*)\b", line):
                name = match.group(1)
                if name not in self.symbol_table:
                    self.symbol_table[name] = []
                self.symbol_table[name].append((line_num, match.start()))

    def rename(
        self, old_name: str, new_name: str, source: str
    ) -> List[TextEdit]:
        """Generate text edits for renaming a symbol."""
        edits = []

        if old_name not in self.symbol_table:
            return edits

        for line_num, col in self.symbol_table[old_name]:
            edits.append(
                TextEdit(
                    line=line_num,
                    start_col=col,
                    end_col=col + len(old_name),
                    new_text=new_name,
                )
            )

        return edits

    def extract_variable(
        self,
        source: str,
        start_line: int,
        start_col: int,
        end_line: int,
        end_col: int,
        var_name: str,
    ) -> List[TextEdit]:
        """Extract selected code into a variable."""
        edits = []

        # Insert variable declaration before selection
        edits.append(
            TextEdit(
                line=start_line,
                start_col=0,
                end_col=0,
                new_text=f"{var_name} = ",
            )
        )

        # Add newline and assignment
        edits.append(
            TextEdit(
                line=end_line,
                start_col=end_col,
                end_col=end_col,
                new_text="\n",
            )
        )

        return edits

    def extract_function(
        self,
        source: str,
        name: str,
        parameters: List[str],
        start_line: int,
        end_line: int,
    ) -> List[TextEdit]:
        """Extract lines into a separate function."""
        lines = source.split("\n")
        body = "\n".join(lines[start_line:end_line + 1])

        func_def = f"function {name}({', '.join(parameters)})\n{body}\nend\n"

        edits = []

        # Add function definition at top
        edits.append(
            TextEdit(
                line=0,
                start_col=0,
                end_col=0,
                new_text=func_def + "\n",
            )
        )

        # Replace extracted code with function call
        args = ", ".join(parameters)
        call = f"{name}({args})"
        edits.append(
            TextEdit(
                line=start_line,
                start_col=0,
                end_col=len("\n".join(lines[start_line:end_line + 1])),
                new_text=call,
            )
        )

        return edits

    def inline_variable(
        self, source: str, var_name: str, line_num: int
    ) -> List[TextEdit]:
        """Inline a variable at its usage point."""
        # This is a simplified version
        lines = source.split("\n")
        edits = []

        # Find variable declaration and its value
        for i, line in enumerate(lines):
            if f"{var_name} =" in line:
                # Extract the value
                value = line.split("=", 1)[1].strip()
                # Replace all usages with the value
                for j, usage_line in enumerate(lines):
                    if var_name in usage_line and i != j:
                        new_line = usage_line.replace(var_name, f"({value})")
                        edits.append(
                            TextEdit(
                                line=j,
                                start_col=0,
                                end_col=len(usage_line),
                                new_text=new_line,
                            )
                        )

        return edits

    def generate_code_actions(self, diagnostics: List[Dict[str, Any]]) -> List[CodeAction]:
        """Generate code actions for fixing errors."""
        actions = []

        for diagnostic in diagnostics:
            message = diagnostic.get("message", "")

            # Type mismatch - suggest cast
            if "type mismatch" in message.lower():
                actions.append(
                    CodeAction(
                        title="Cast to expected type",
                        kind="quickfix",
                        edits=[],
                        is_preferred=True,
                    )
                )

            # Undefined variable - suggest declaration
            if "undefined" in message.lower():
                actions.append(
                    CodeAction(
                        title="Declare variable",
                        kind="quickfix",
                        edits=[],
                    )
                )

            # Unused import - suggest removal
            if "unused import" in message.lower():
                actions.append(
                    CodeAction(
                        title="Remove unused import",
                        kind="quickfix",
                        edits=[],
                        is_preferred=True,
                    )
                )

        return actions


class CodeFormatter:
    """Formats code according to style rules."""

    def __init__(self, config: Any = None, tab_size: int = 4):
        self.config = config
        self.tab_size = tab_size
        self.indent_level = 0

    def format(self, source: str) -> str:
        """Format source code."""
        self.indent_level = 0  # Reset state for each format call
        lines = source.split("\n")
        formatted_lines = []

        for line in lines:
            formatted = self._format_line(line)
            formatted_lines.append(formatted)

        return "\n".join(formatted_lines)

    def _format_line(self, line: str) -> str:
        """Format a single line."""
        stripped = line.strip()

        if not stripped:
            return ""

        # Track indentation
        if any(stripped.startswith(kw) for kw in ["end", "}", ")"]):
            self.indent_level = max(0, self.indent_level - 1)

        indent = " " * (self.indent_level * self.tab_size)

        # Increase indentation for next lines
        if any(
            stripped.startswith(kw)
            for kw in ["function", "class", "if", "for", "while", "{", "["]
        ):
            self.indent_level += 1

        # Add spacing around operators
        formatted = self._add_operator_spacing(stripped)

        return indent + formatted

    def _add_operator_spacing(self, line: str) -> str:
        """Add spacing around operators."""
        # Process multi-character operators first, then single-char ones.
        # Use a single regex to avoid re-matching parts of already-spaced operators.
        multi_char_ops = ["==", "!=", "<=", ">="]
        single_char_ops = ["=", "<", ">", "+", "-", "*", "/"]

        # First pass: multi-char operators
        for op in multi_char_ops:
            line = re.sub(
                rf"(?<![\s{re.escape(op[0])}]){re.escape(op)}(?!\s)",
                f" {op} ",
                line,
            )

        # Second pass: single-char operators (avoid already-spaced multi-char ones)
        for op in single_char_ops:
            # Negative lookbehind/lookahead to skip already-handled multi-char ops
            if op == "=":
                line = re.sub(r'(?<![=!<>])=(?!=)', ' = ', line)
            elif op in ("<", ">"):
                line = re.sub(
                    rf'(?<!\s){re.escape(op)}(?![=\s])',
                    f' {op} ',
                    line,
                )
            else:
                line = re.sub(
                    rf'(?<!\s){re.escape(op)}(?!\s)',
                    f' {op} ',
                    line,
                )

        # Clean up any double spaces
        line = re.sub(r'  +', ' ', line)

        return line


class SemanticHighlighter:
    """Provides semantic tokens for syntax highlighting."""

    def __init__(self, config: Any = None):
        self.config = config
        self.keywords = {
            "function",
            "class",
            "interface",
            "if",
            "else",
            "for",
            "while",
            "return",
            "import",
            "export",
        }

    def extract_tokens(self, source: str) -> List[SemanticToken]:
        """Extract semantic tokens from source."""
        tokens = []
        lines = source.split("\n")

        import re

        for line_num, line in enumerate(lines):
            # Match identifiers
            for match in re.finditer(r"\b([a-zA-Z_]\w*)\b", line):
                text = match.group(1)
                col = match.start()

                if text in self.keywords:
                    token_type = TokenType.KEYWORD
                elif text[0].isupper():
                    token_type = TokenType.CLASS
                else:
                    token_type = TokenType.VARIABLE

                tokens.append(
                    SemanticToken(
                        line=line_num,
                        start_col=col,
                        length=len(text),
                        token_type=token_type,
                    )
                )

            # Match numbers
            for match in re.finditer(r"\b\d+\.?\d*\b", line):
                tokens.append(
                    SemanticToken(
                        line=line_num,
                        start_col=match.start(),
                        length=len(match.group()),
                        token_type=TokenType.NUMBER,
                    )
                )

            # Match strings
            for match in re.finditer(r'["\'].*?["\']', line):
                tokens.append(
                    SemanticToken(
                        line=line_num,
                        start_col=match.start(),
                        length=len(match.group()),
                        token_type=TokenType.STRING,
                    )
                )

        return tokens
