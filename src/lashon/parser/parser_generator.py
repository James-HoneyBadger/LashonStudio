#!/usr/bin/env python3
"""
Parser generator for Lashon Studio

Generates parsers from language configurations with support for:
- Custom grammars
- AST generation and visualization
- Syntax validation
- Token analysis
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from lashon.config.language_config import LanguageConfig


class TokenType(Enum):
    """Token types for lexical analysis."""

    KEYWORD = "KEYWORD"
    IDENTIFIER = "IDENTIFIER"
    NUMBER = "NUMBER"
    STRING = "STRING"
    OPERATOR = "OPERATOR"
    PUNCTUATION = "PUNCTUATION"
    COMMENT = "COMMENT"
    WHITESPACE = "WHITESPACE"
    EOF = "EOF"
    UNKNOWN = "UNKNOWN"


@dataclass
class Token:
    """Represents a single token in the source code."""

    type: TokenType
    value: str
    line: int
    column: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"Token({self.type.value}, '{self.value}', {self.line}:{self.column})"  # noqa: E501


@dataclass
class ASTNode:
    """Represents a node in the Abstract Syntax Tree."""

    node_type: str
    value: Optional[Any] = None
    children: List["ASTNode"] = field(default_factory=list)
    token: Optional[Token] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert AST node to dictionary for visualization."""
        return {
            "type": self.node_type,
            "value": self.value,
            "children": [child.to_dict() for child in self.children],
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        if self.value:
            return f"{self.node_type}({self.value})"
        return self.node_type


class Lexer:
    """Tokenizes source code based on language configuration."""

    def __init__(self, config: LanguageConfig):
        self.config = config
        self.keywords = set(kw.custom for kw in config.keyword_mappings.values())
        self.operators = set()
        if config.operators:
            self.operators = set(op.symbol for op in config.operators.values())

    def tokenize(self, source: str) -> List[Token]:
        """Tokenize source code into a list of tokens."""
        tokens = []
        lines = source.split("\n")

        for line_num, line in enumerate(lines, 1):
            column = 1
            i = 0

            while i < len(line):
                # Skip whitespace
                if line[i].isspace():
                    i += 1
                    column += 1
                    continue

                # Check for comments
                comment_style = self.config.syntax_options.single_line_comment
                if comment_style and line[i:].startswith(comment_style):
                    tokens.append(Token(TokenType.COMMENT, line[i:], line_num, column))
                    break

                # Check for strings
                if line[i] in ['"', "'"]:
                    quote = line[i]
                    j = i + 1
                    while j < len(line) and line[j] != quote:
                        if line[j] == "\\" and j + 1 < len(line):
                            j += 2
                        else:
                            j += 1

                    if j < len(line):
                        j += 1  # Include closing quote
                        tokens.append(
                            Token(TokenType.STRING, line[i:j], line_num, column)
                        )
                        column += j - i
                        i = j
                        continue

                # Check for numbers
                if line[i].isdigit():
                    j = i
                    has_dot = False
                    while j < len(line) and (line[j].isdigit() or line[j] == "."):
                        if line[j] == ".":
                            if has_dot:
                                break
                            has_dot = True
                        j += 1

                    tokens.append(Token(TokenType.NUMBER, line[i:j], line_num, column))
                    column += j - i
                    i = j
                    continue

                # Check for operators
                matched_op = False
                for op in sorted(self.operators, key=len, reverse=True):
                    if line[i:].startswith(op):
                        tokens.append(Token(TokenType.OPERATOR, op, line_num, column))
                        column += len(op)
                        i += len(op)
                        matched_op = True
                        break

                if matched_op:
                    continue

                # Check for identifiers and keywords
                if line[i].isalpha() or line[i] == "_":
                    j = i
                    while j < len(line) and (line[j].isalnum() or line[j] == "_"):
                        j += 1

                    word = line[i:j]
                    token_type = (
                        TokenType.KEYWORD
                        if word in self.keywords
                        else TokenType.IDENTIFIER
                    )

                    tokens.append(Token(token_type, word, line_num, column))
                    column += j - i
                    i = j
                    continue

                # Punctuation
                if line[i] in "()[]{},.;:":
                    tokens.append(
                        Token(TokenType.PUNCTUATION, line[i], line_num, column)
                    )
                    column += 1
                    i += 1
                    continue

                # Unknown character
                tokens.append(Token(TokenType.UNKNOWN, line[i], line_num, column))
                column += 1
                i += 1

        tokens.append(Token(TokenType.EOF, "", len(lines) + 1, 1))
        return tokens


class Parser:
    """Parses tokens into an Abstract Syntax Tree."""

    def __init__(self, config: LanguageConfig, tokens: List[Token]):
        self.config = config
        self.tokens = tokens
        self.current = 0

    def parse(self) -> ASTNode:
        """Parse tokens into an AST."""
        root = ASTNode("Program")

        while not self.is_at_end():
            if self.peek().type == TokenType.EOF:
                break

            pos_before = self.current
            stmt = self.parse_statement()
            if stmt:
                root.children.append(stmt)
            # Prevent infinite loop: if no progress was made, advance past the token
            if self.current == pos_before:
                self.advance()

        return root

    def parse_statement(self) -> Optional[ASTNode]:
        """Parse a single statement."""
        token = self.peek()

        if token.type == TokenType.COMMENT:
            self.advance()
            return ASTNode("Comment", token.value, token=token)

        if token.type == TokenType.KEYWORD:
            return self.parse_keyword_statement()

        # Expression statement
        expr = self.parse_expression()
        return ASTNode("ExpressionStatement", children=[expr]) if expr else None

    def parse_keyword_statement(self) -> Optional[ASTNode]:
        """Parse keyword-based statements."""
        keyword_token = self.advance()
        keyword = keyword_token.value

        # Find original keyword for semantic understanding
        original = None
        for mapping in self.config.keyword_mappings.values():
            if mapping.custom == keyword:
                original = mapping.original
                break

        if original in ["if", "when"]:
            return self.parse_if_statement(keyword_token)
        elif original in ["while", "for"]:
            return self.parse_loop_statement(keyword_token, original)
        elif original in ["function", "def"]:
            return self.parse_function_def(keyword_token)
        elif original == "return":
            return self.parse_return_statement(keyword_token)
        else:
            # Generic keyword statement
            node = ASTNode("KeywordStatement", keyword, token=keyword_token)
            node.metadata["original_keyword"] = original
            return node

    def _get_block_terminators(self, *default_keywords: str) -> list:
        """Get block terminator keywords respecting custom mappings."""
        terminators = []
        for kw in default_keywords:
            terminators.append(kw)
            # Also add the custom-mapped version
            for mapping in self.config.keyword_mappings.values():
                if mapping.original == kw and mapping.custom != kw:
                    terminators.append(mapping.custom)
        return terminators

    def parse_if_statement(self, keyword_token: Token) -> ASTNode:
        """Parse if/conditional statement."""
        node = ASTNode("IfStatement", token=keyword_token)

        # Parse condition
        condition = self.parse_expression()
        if condition:
            node.children.append(condition)

        # Parse body (simplified - just collect tokens until we hit else/end)
        block_terminators = self._get_block_terminators("else", "end", "endif")
        body = ASTNode("Block")
        while not self.is_at_end() and self.peek().value not in block_terminators:
            stmt = self.parse_statement()
            if stmt:
                body.children.append(stmt)
            else:
                self.advance()  # Prevent infinite loop on unparseable tokens

        node.children.append(body)
        return node

    def parse_loop_statement(self, keyword_token: Token, loop_type: str) -> ASTNode:
        """Parse loop statement."""
        node = ASTNode(f"{loop_type.capitalize()}Loop", token=keyword_token)

        # Parse loop header
        header = self.parse_expression()
        if header:
            node.children.append(header)

        # Parse body
        block_terminators = self._get_block_terminators("end", "endwhile", "next")
        body = ASTNode("Block")
        while not self.is_at_end() and self.peek().value not in block_terminators:
            stmt = self.parse_statement()
            if stmt:
                body.children.append(stmt)
            else:
                self.advance()  # Prevent infinite loop on unparseable tokens

        node.children.append(body)
        return node

    def parse_function_def(self, keyword_token: Token) -> ASTNode:
        """Parse function definition."""
        node = ASTNode("FunctionDef", token=keyword_token)

        # Get function name
        if self.peek().type == TokenType.IDENTIFIER:
            name_token = self.advance()
            node.value = name_token.value
            node.metadata["name"] = name_token.value

        # Parse parameters (simplified)
        if self.peek().value == "(":
            self.advance()
            params = ASTNode("Parameters")
            while self.peek().value != ")" and not self.is_at_end():
                if self.peek().type == TokenType.IDENTIFIER:
                    param = self.advance()
                    params.children.append(ASTNode("Parameter", param.value))
                else:
                    self.advance()
            if self.peek().value == ")":
                self.advance()
            node.children.append(params)

        return node

    def parse_return_statement(self, keyword_token: Token) -> ASTNode:
        """Parse return statement."""
        node = ASTNode("ReturnStatement", token=keyword_token)

        # Parse return value
        expr = self.parse_expression()
        if expr:
            node.children.append(expr)

        return node

    def parse_expression(self) -> Optional[ASTNode]:
        """Parse expression (simplified)."""
        token = self.peek()

        if token.type == TokenType.NUMBER:
            self.advance()
            return ASTNode("Number", token.value, token=token)
        elif token.type == TokenType.STRING:
            self.advance()
            return ASTNode("String", token.value, token=token)
        elif token.type == TokenType.IDENTIFIER:
            self.advance()
            node = ASTNode("Identifier", token.value, token=token)

            # Check for function call
            if self.peek().value == "(":
                return self.parse_function_call(node)

            return node
        elif token.value == "(":
            self.advance()
            expr = self.parse_expression()
            if self.peek().value == ")":
                self.advance()
            return expr

        return None

    def parse_function_call(self, func_node: ASTNode) -> ASTNode:
        """Parse function call."""
        call_node = ASTNode("FunctionCall", func_node.value)
        self.advance()  # consume '('

        # Parse arguments
        args = ASTNode("Arguments")
        while self.peek().value != ")" and not self.is_at_end():
            arg = self.parse_expression()
            if arg:
                args.children.append(arg)
            if self.peek().value == ",":
                self.advance()

        if self.peek().value == ")":
            self.advance()

        call_node.children.append(args)
        return call_node

    def peek(self) -> Token:
        """Look at current token without consuming it."""
        if self.current < len(self.tokens):
            return self.tokens[self.current]
        return self.tokens[-1]  # EOF

    def advance(self) -> Token:
        """Consume and return current token."""
        token = self.peek()
        if not self.is_at_end():
            self.current += 1
        return token

    def is_at_end(self) -> bool:
        """Check if we've reached the end of tokens."""
        return self.current >= len(self.tokens) or self.peek().type == TokenType.EOF


class ParserGenerator:
    """Main parser generator that coordinates lexing and parsing."""

    def __init__(self, config: LanguageConfig):
        self.config = config

    def parse(self, source: str) -> Tuple[List[Token], ASTNode]:
        """Parse source code and return tokens and AST."""
        lexer = Lexer(self.config)
        tokens = lexer.tokenize(source)

        parser = Parser(self.config, tokens)
        ast = parser.parse()

        return tokens, ast

    def visualize_tokens(self, tokens: List[Token]) -> str:
        """Create a visual representation of tokens."""
        output = []
        output.append("=" * 60)
        output.append("TOKEN ANALYSIS")
        output.append("=" * 60)

        # Group tokens by type
        by_type: Dict[TokenType, List[Token]] = {}
        for token in tokens:
            if token.type != TokenType.EOF:
                if token.type not in by_type:
                    by_type[token.type] = []
                by_type[token.type].append(token)

        output.append(f"\nTotal tokens: {len(tokens) - 1}")  # -1 for EOF
        output.append("\nToken types found:")
        for token_type, token_list in sorted(by_type.items(), key=lambda x: x[0].value):
            output.append(f"  {token_type.value}: {len(token_list)}")

        output.append("\nDetailed token list:")
        for i, token in enumerate(tokens):
            if token.type != TokenType.EOF:
                output.append(f"  {i+1}. {token}")

        output.append("\n" + "=" * 60)
        return "\n".join(output)

    def visualize_ast(self, ast: ASTNode, indent: int = 0) -> str:
        """Create a visual tree representation of the AST."""
        output = []
        prefix = "  " * indent

        if ast.value:
            output.append(f"{prefix}{ast.node_type}: {ast.value}")
        else:
            output.append(f"{prefix}{ast.node_type}")

        for child in ast.children:
            output.append(self.visualize_ast(child, indent + 1))

        return "\n".join(output)

    def ast_to_json(self, ast: ASTNode) -> str:
        """Convert AST to JSON format."""
        return json.dumps(ast.to_dict(), indent=2)

    def generate_parser_code(self) -> str:
        """Generate Python parser code for the language."""
        code = []
        code.append("# Auto-generated parser for " + self.config.name)
        code.append("# Generated by Lashon Studio\n")
        code.append("from typing import List, Dict, Any")
        code.append("import re\n")

        code.append("class Token:")
        code.append("    def __init__(self, type, value, line, column):")
        code.append("        self.type = type")
        code.append("        self.value = value")
        code.append("        self.line = line")
        code.append("        self.column = column\n")

        code.append("class Lexer:")
        code.append("    KEYWORDS = " + str(list(self.keywords)))
        code.append("    \n    def tokenize(self, source):")
        code.append("        # Tokenization logic here")
        code.append("        pass\n")

        code.append("class Parser:")
        code.append("    def __init__(self, tokens):")
        code.append("        self.tokens = tokens")
        code.append("        self.current = 0")
        code.append("    \n    def parse(self):")
        code.append("        # Parsing logic here")
        code.append("        pass\n")

        return "\n".join(code)

    @property
    def keywords(self) -> List[str]:
        """Get list of custom keywords."""
        return [kw.custom for kw in self.config.keyword_mappings.values()]

    @property
    def operators(self) -> List[str]:
        """Get list of operators."""
        if self.config.operators:
            return [op.symbol for op in self.config.operators.values()]
        return []


def generate_parser(config: LanguageConfig) -> ParserGenerator:
    """Factory function to create a parser generator."""
    return ParserGenerator(config)
