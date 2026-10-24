#!/usr/bin/env python3
"""
Language validator for Lashon Studio

Provides comprehensive validation for language configurations:
- Detects ambiguous grammars
- Checks for keyword conflicts
- Validates operator precedence
- Identifies potential issues
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .language_config import LanguageConfig


@dataclass
class ValidationIssue:
    """Represents a validation issue found in the configuration."""

    severity: str  # "error", "warning", "info"
    category: str
    message: str
    details: Optional[str] = None
    suggestion: Optional[str] = None

    def __str__(self) -> str:
        prefix = {
            "error": "❌ ERROR",
            "warning": "⚠️  WARNING",
            "info": "ℹ️  INFO",
        }
        result = (  # noqa: E501
            f"{prefix.get(self.severity, 'ISSUE')} "
            f"[{self.category}]: {self.message}"
        )
        if self.details:
            result += f"\n    Details: {self.details}"
        if self.suggestion:
            result += f"\n    Suggestion: {self.suggestion}"
        return result


class LanguageValidator:
    """Comprehensive validator for language configurations."""

    def __init__(self, config: LanguageConfig):
        self.config = config
        self.issues: List[ValidationIssue] = []

    def validate_all(self) -> List[ValidationIssue]:
        """Run all validation checks."""
        self.issues = []

        self.check_keyword_conflicts()
        self.check_function_conflicts()
        self.check_operator_precedence()
        self.check_syntax_ambiguities()
        self.check_reserved_words()
        self.check_naming_conventions()
        self.check_completeness()

        return self.issues

    def check_keyword_conflicts(self) -> None:
        """Check for keyword conflicts and ambiguities."""
        custom_keywords = [
            kw.custom for kw in self.config.keyword_mappings.values()
        ]  # noqa: E501 pylint: disable=line-too-long

        # Check for duplicate custom keywords
        seen = set()
        duplicates = set()
        for keyword in custom_keywords:
            if keyword in seen:
                duplicates.add(keyword)
            seen.add(keyword)

        for dup in duplicates:
            self.issues.append(
                ValidationIssue(
                    severity="warning",
                    category="keyword_conflict",
                    message=f"Duplicate keyword alias: '{dup}'",
                    details="Multiple original keywords map to the same custom keyword",  # noqa: E501 pylint: disable=line-too-long
                    suggestion="Use unique custom keywords if reverse translation must be unambiguous",  # noqa: E501 pylint: disable=line-too-long
                )
            )

        # Check for keywords that conflict with Python reserved words
        python_reserved = {
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
        }

        for keyword in custom_keywords:
            if keyword in python_reserved:
                self.issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="python_reserved",
                        message=f"Keyword '{keyword}' conflicts with Python reserved word",  # noqa: E501 pylint: disable=line-too-long
                        details="This may cause issues when transpiling to Python",  # noqa: E501 pylint: disable=line-too-long
                        suggestion=f"Consider using a different name like '{keyword}_'",  # noqa: E501
                    )
                )

        # Check for very short keywords (1-2 chars) that might cause ambiguity
        for kw_mapping in self.config.keyword_mappings.values():
            if len(kw_mapping.custom) <= 2 and kw_mapping.custom.isalpha():
                self.issues.append(
                    ValidationIssue(
                        severity="info",
                        category="short_keyword",
                        message=f"Very short keyword: '{kw_mapping.custom}'",
                        details="Short keywords may reduce code readability",
                        suggestion="Consider using more descriptive keywords",
                    )
                )

    def check_function_conflicts(self) -> None:
        """Check for function naming conflicts."""
        function_names = [
            f.name for f in self.config.builtin_functions.values()
        ]  # noqa: E501

        # Check for duplicate function names
        seen = set()
        for name in function_names:
            if name in seen:
                self.issues.append(
                    ValidationIssue(
                        severity="error",
                        category="function_conflict",
                        message=f"Duplicate function name: '{name}'",
                        details="Multiple functions have the same name",
                        suggestion="Rename one of the functions",
                    )
                )
            seen.add(name)

        # Check if function names conflict with keywords
        custom_keywords = set(
            kw.custom for kw in self.config.keyword_mappings.values()
        )  # noqa: E501
        for name in function_names:
            if name in custom_keywords:
                self.issues.append(
                    ValidationIssue(
                        severity="error",
                        category="function_keyword_conflict",
                        message=f"Function '{name}' conflicts with keyword",
                        details="Function name is also used as a keyword",
                        suggestion="Rename the function or keyword",
                    )
                )

        # Check function arity validity
        for func in self.config.builtin_functions.values():
            if func.arity < -1:
                self.issues.append(
                    ValidationIssue(
                        severity="error",
                        category="invalid_arity",
                        message=f"Invalid arity for function '{func.name}': {func.arity}",  # noqa: E501
                        details="Arity must be -1 (variadic) or >= 0",
                        suggestion="Set arity to -1 for variable arguments or a positive number",  # noqa: E501
                    )
                )

    def check_operator_precedence(self) -> None:
        """Validate operator precedence and associativity."""
        if not self.config.operators:
            return

        operators = self.config.operators.values()
        precedence_groups: Dict[int, List] = defaultdict(list)

        for op in operators:
            precedence_groups[op.precedence].append(op)

        # Check for operators with same precedence but different associativity
        for prec, ops in precedence_groups.items():
            assocs = set(op.associativity for op in ops)
            if len(assocs) > 1:
                op_symbols = ", ".join(op.symbol for op in ops)
                self.issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="precedence_ambiguity",
                        message=f"Operators at precedence {prec} have mixed associativity",  # noqa: E501 pylint: disable=line-too-long
                        details=f"Operators: {op_symbols}",
                        suggestion="Use consistent associativity for operators at same precedence",  # noqa: E501 pylint: disable=line-too-long
                    )
                )

        # Check for very high precedence values
        for op in operators:
            if op.precedence > 20:
                self.issues.append(
                    ValidationIssue(
                        severity="info",
                        category="high_precedence",
                        message=f"Operator '{op.symbol}' has very high precedence: {op.precedence}",  # noqa: E501 pylint: disable=line-too-long
                        details="Typical precedence ranges from 1-15",
                        suggestion="Consider using standard precedence values",
                    )
                )

    def check_syntax_ambiguities(self) -> None:
        """Check for potential syntax ambiguities."""
        syntax_opts = self.config.syntax_options

        # Check for conflicting delimiters
        delimiters = [
            syntax_opts.single_line_comment,
            syntax_opts.multi_line_comment_start,
            syntax_opts.multi_line_comment_end,
            syntax_opts.statement_terminator,
        ]

        # Remove None values
        delimiters = [d for d in delimiters if d]

        # Check if any delimiter is prefix of another
        for i, d1 in enumerate(delimiters):
            for d2 in delimiters[i + 1 :]:  # noqa: E203
                if d1 and d2 and (d1.startswith(d2) or d2.startswith(d1)):
                    self.issues.append(
                        ValidationIssue(
                            severity="warning",
                            category="delimiter_ambiguity",
                            message=f"Delimiter conflict: '{d1}' and '{d2}'",
                            details="One delimiter is a prefix of another",
                            suggestion="Use distinct delimiters",
                        )
                    )

        # Check fractional indexing with non-zero start
        if (
            syntax_opts.allow_fractional_indexing and syntax_opts.array_start_index != 0
        ):  # noqa: E501
            self.issues.append(
                ValidationIssue(
                    severity="warning",
                    category="indexing_confusion",
                    message="Fractional indexing with non-zero array start",
                    details=f"Array start index is {syntax_opts.array_start_index}",  # noqa: E501
                    suggestion="Fractional indexing works best with 0-based indexing",  # noqa: E501
                )
            )

    def check_reserved_words(self) -> None:
        """Check for potential conflicts with common reserved words."""
        common_reserved = {
            "class",
            "struct",
            "enum",
            "interface",
            "public",
            "private",
            "protected",
            "static",
            "const",
            "var",
            "let",
            "function",
            "return",
            "if",
            "else",
            "while",
            "for",
            "switch",
            "case",
            "break",
            "continue",
            "new",
            "delete",
            "this",
            "super",
        }

        custom_keywords = set(
            kw.custom for kw in self.config.keyword_mappings.values()
        )  # noqa: E501
        conflicts = custom_keywords & common_reserved

        if conflicts:
            self.issues.append(
                ValidationIssue(
                    severity="info",
                    category="common_reserved",
                    message=f"Keywords match common reserved words: {', '.join(conflicts)}",  # noqa: E501 pylint: disable=line-too-long
                    details="These words are reserved in many programming languages",  # noqa: E501
                    suggestion="This is usually fine but be aware of potential confusion",  # noqa: E501 pylint: disable=line-too-long
                )
            )

    def check_naming_conventions(self) -> None:
        """Check naming conventions for keywords and functions."""
        # Check for mixed case conventions
        keyword_cases: dict[str, int] = defaultdict(int)
        for kw in self.config.keyword_mappings.values():
            if kw.custom.isupper():
                keyword_cases["upper"] += 1
            elif kw.custom.islower():
                keyword_cases["lower"] += 1
            elif kw.custom[0].isupper():
                keyword_cases["title"] += 1
            else:
                keyword_cases["mixed"] += 1

        if len(keyword_cases) > 2:
            self.issues.append(
                ValidationIssue(
                    severity="info",
                    category="naming_convention",
                    message="Inconsistent keyword casing",
                    details=f"Found {len(keyword_cases)} different casing styles",  # noqa: E501
                    suggestion="Use consistent casing for all keywords",
                )
            )

        # Check for keywords with numbers
        for kw in self.config.keyword_mappings.values():
            if any(c.isdigit() for c in kw.custom):
                self.issues.append(
                    ValidationIssue(
                        severity="info",
                        category="keyword_with_digits",
                        message=f"Keyword contains digits: '{kw.custom}'",
                        details="Keywords with digits may reduce readability",
                        suggestion="Consider using words only",
                    )
                )

    def check_completeness(self) -> None:
        """Check if the language configuration is complete."""
        # Check for essential keywords
        essential_originals = {"if", "while", "for", "function", "return"}
        defined_originals = set(
            kw.original for kw in self.config.keyword_mappings.values()
        )

        missing = essential_originals - defined_originals
        if missing:
            self.issues.append(
                ValidationIssue(
                    severity="info",
                    category="incomplete",
                    message=f"Missing common keywords: {', '.join(missing)}",
                    details="These keywords are common in most languages",
                    suggestion="Consider adding mappings for these keywords",
                )
            )

        # Check for essential functions
        essential_functions = {"print", "input", "len"}
        defined_functions = set(
            f.name for f in self.config.builtin_functions.values()
        )  # noqa: E501

        missing_funcs = essential_functions - defined_functions
        if missing_funcs:
            self.issues.append(
                ValidationIssue(
                    severity="info",
                    category="incomplete",
                    message=f"Missing common functions: {', '.join(missing_funcs)}",  # noqa: E501
                    details="These are basic I/O and utility functions",
                    suggestion="Consider adding these functions",
                )
            )

    def get_issues_by_severity(self, severity: str) -> List[ValidationIssue]:
        """Get all issues of a specific severity."""
        return [issue for issue in self.issues if issue.severity == severity]

    def get_issues_by_category(self, category: str) -> List[ValidationIssue]:
        """Get all issues of a specific category."""
        return [issue for issue in self.issues if issue.category == category]

    def has_errors(self) -> bool:
        """Check if there are any error-level issues."""
        return any(issue.severity == "error" for issue in self.issues)

    def has_warnings(self) -> bool:
        """Check if there are any warning-level issues."""
        return any(issue.severity == "warning" for issue in self.issues)

    def generate_report(self) -> str:
        """Generate a formatted validation report."""
        lines = []
        lines.append("=" * 70)
        lines.append("LANGUAGE CONFIGURATION VALIDATION REPORT")
        lines.append("=" * 70)
        lines.append(f"\nLanguage: {self.config.name}")
        lines.append(f"Version: {self.config.version}\n")

        errors = self.get_issues_by_severity("error")
        warnings = self.get_issues_by_severity("warning")
        infos = self.get_issues_by_severity("info")

        lines.append(f"Total Issues: {len(self.issues)}")
        lines.append(f"  Errors:   {len(errors)}")
        lines.append(f"  Warnings: {len(warnings)}")
        lines.append(f"  Info:     {len(infos)}\n")

        if not self.issues:
            lines.append("✅ No issues found! Configuration is valid.\n")
        else:
            if errors:
                lines.append("-" * 70)
                lines.append("ERRORS (Must be fixed)")
                lines.append("-" * 70)
                for issue in errors:
                    lines.append(str(issue))
                    lines.append("")

            if warnings:
                lines.append("-" * 70)
                lines.append("WARNINGS (Should be reviewed)")
                lines.append("-" * 70)
                for issue in warnings:
                    lines.append(str(issue))
                    lines.append("")

            if infos:
                lines.append("-" * 70)
                lines.append("INFORMATION (Suggestions)")
                lines.append("-" * 70)
                for issue in infos:
                    lines.append(str(issue))
                    lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)


def validate_config(
    config: LanguageConfig,
) -> Tuple[bool, List[ValidationIssue]]:
    """Validate a language configuration and return status and issues."""
    validator = LanguageValidator(config)
    issues = validator.validate_all()
    is_valid = not validator.has_errors()

    return is_valid, issues
