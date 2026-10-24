#!/usr/bin/env python3
"""
Identifier Validator for Language Configuration

Provides validation for identifier names, keywords, and function names.
Ensures compatibility with Python and other common languages.
"""

import re
from typing import Any, Dict, List, Optional, Tuple


class IdentifierValidator:
    """Validates identifiers for use as keywords, function names, etc."""

    # Python reserved words that should be avoided
    PYTHON_RESERVED = {
        "and",
        "as",
        "assert",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
        "True",
        "False",
        "None",
        "__name__",
        "__file__",
        "__doc__",
        "__dict__",
        "__class__",
    }

    # Common naming patterns
    SNAKE_CASE_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")
    CAMEL_CASE_PATTERN = re.compile(r"^[a-z][a-zA-Z0-9]*$")
    PASCAL_CASE_PATTERN = re.compile(r"^[A-Z][a-zA-Z0-9]*$")
    SCREAMING_SNAKE_CASE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

    @staticmethod
    def is_valid_identifier(name: str) -> bool:
        """Check if name is a valid Python identifier."""
        if not name:
            return False
        return name.isidentifier()

    @staticmethod
    def is_valid_length(name: str, min_len: int = 1, max_len: int = 255) -> bool:
        """Check if identifier length is within acceptable bounds."""
        return min_len <= len(name) <= max_len

    @staticmethod
    def is_python_reserved(name: str) -> bool:
        """Check if identifier conflicts with Python reserved words."""
        return name in IdentifierValidator.PYTHON_RESERVED

    @staticmethod
    def detect_naming_style(name: str) -> Optional[str]:
        """Detect the naming style used in an identifier."""
        if IdentifierValidator.SNAKE_CASE_PATTERN.match(name):
            return "snake_case"
        elif IdentifierValidator.CAMEL_CASE_PATTERN.match(name):
            return "camelCase"
        elif IdentifierValidator.PASCAL_CASE_PATTERN.match(name):
            return "PascalCase"
        elif IdentifierValidator.SCREAMING_SNAKE_CASE_PATTERN.match(name):
            return "SCREAMING_SNAKE_CASE"
        return None

    @staticmethod
    def validate_identifier(
        name: str,
        reserved_set: Optional[set[str]] = None,
        allow_reserved: bool = False,
        min_length: int = 1,
        max_length: int = 255,
        allow_symbols: bool = False,
    ) -> Tuple[bool, List[str]]:
        """
        Comprehensive validation of an identifier.

        Returns:
            Tuple of (is_valid, list_of_warnings)
        """
        warnings = []

        # Check basic identifier validity
        is_identifier = IdentifierValidator.is_valid_identifier(name)
        if not is_identifier:
            if allow_symbols:
                # If symbols allowed, ensure no whitespace and length check
                if not name or any(c.isspace() for c in name):
                    return False, [f"'{name}' contains whitespace or is empty"]
            else:
                return False, [f"'{name}' is not a valid identifier"]

        # Check length
        if not IdentifierValidator.is_valid_length(name, min_length, max_length):
            return False, [
                f"Identifier length {len(name)} out of range "
                f"[{min_length}, {max_length}]"
            ]

        # Check Python reserved words (only if it looks like an identifier)
        if is_identifier and IdentifierValidator.is_python_reserved(name):
            if not allow_reserved:
                return False, [f"'{name}' is a Python reserved word"]
            else:
                warnings.append(
                    f"'{name}' is a Python reserved word (may cause issues)"
                )

        # Check custom reserved set
        if reserved_set and name in reserved_set:
            return False, [f"'{name}' conflicts with existing identifier"]

        # Style consistency warnings
        style = IdentifierValidator.detect_naming_style(name)
        if style is None:
            warnings.append(
                f"'{name}' uses non-standard naming convention "
                "(recommend snake_case, camelCase, or PascalCase)"
            )

        # Check for ambiguous names
        if len(name) <= 2 and name.isalpha():
            warnings.append(
                f"'{name}' is very short (1-2 chars); may reduce readability"
            )

        return True, warnings

    @staticmethod
    def suggest_name(invalid_name: str, style: str = "snake_case") -> str:
        """Suggest a valid alternative name based on the invalid one."""
        # Remove invalid characters
        cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", invalid_name)

        # Ensure starts with letter or underscore
        if cleaned and cleaned[0].isdigit():
            cleaned = f"_{cleaned}"

        # Apply naming style
        if style == "snake_case":
            # Convert camelCase to snake_case
            cleaned = re.sub(r"(?<!^)(?=[A-Z])", "_", cleaned).lower()
        elif style == "camelCase":
            # Convert snake_case to camelCase
            parts = cleaned.split("_")
            cleaned = parts[0] + "".join(word.capitalize() for word in parts[1:])
        elif style == "PascalCase":
            # Convert to PascalCase
            parts = cleaned.split("_")
            cleaned = "".join(word.capitalize() for word in parts)
        elif style == "SCREAMING_SNAKE_CASE":
            # Convert to SCREAMING_SNAKE_CASE
            cleaned = re.sub(r"(?<!^)(?=[A-Z])", "_", cleaned).upper()

        return cleaned or "identifier"


class ConflictDetector:
    """Detects conflicts and ambiguities in language configurations."""

    @staticmethod
    def find_duplicate_names(
        items: dict[str, Any],
        get_custom_name: Any,
    ) -> List[Tuple[str, str, str]]:
        """Find duplicates where multiple originals map to same custom name."""
        custom_to_originals: Dict[str, List[str]] = {}

        for original, item in items.items():
            custom = get_custom_name(item)
            if custom not in custom_to_originals:
                custom_to_originals[custom] = []
            custom_to_originals[custom].append(original)

        duplicates = []
        for custom, originals in custom_to_originals.items():
            if len(originals) > 1:
                for orig in originals:
                    duplicates.append((orig, custom, "duplicate_mapping"))

        return duplicates

    @staticmethod
    def find_namespace_collisions(
        keywords: dict[str, Any],
        functions: dict[str, Any],
        operators: dict[str, Any],
    ) -> List[Tuple[str, str, str]]:
        """Find collisions between different identifier types."""
        kw_set = set(k.custom for k in keywords.values())
        func_set = set(f.name for f in functions.values())
        op_set = set(o.symbol for o in operators.values())

        collisions = []

        # Keywords vs functions
        kw_func = kw_set & func_set
        for name in kw_func:
            collisions.append((name, "keyword_function", "namespace_collision"))

        # Keywords vs operators
        kw_op = kw_set & op_set
        for name in kw_op:
            collisions.append((name, "keyword_operator", "namespace_collision"))

        # Functions vs operators
        func_op = func_set & op_set
        for name in func_op:
            collisions.append((name, "function_operator", "namespace_collision"))

        return collisions

    @staticmethod
    def check_operator_precedence_consistency(
        operators: dict[str, Any],
    ) -> List[str]:
        """Check for operator precedence issues."""
        issues = []

        precedences: dict[int, list[str]] = {}
        for symbol, op in operators.items():
            prec = op.precedence
            if prec < 0:
                issues.append(f"Operator '{symbol}' has negative precedence: {prec}")

            if op.associativity not in ["left", "right", "none"]:
                issues.append(
                    f"Operator '{symbol}' has invalid associativity: "
                    f"{op.associativity}"
                )

            if prec not in precedences:
                precedences[prec] = []
            precedences[prec].append(symbol)

        return issues
