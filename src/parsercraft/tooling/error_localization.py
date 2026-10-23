"""
ParserCraft Error Localization

Provides localized error messages for custom languages.
Language designers can provide translation files so that compiler errors,
warnings, and hints appear in their users' preferred language.

Usage:
    loc = ErrorLocalizer(locale="es")
    loc.load_translations({
        "E001": "Variable '{name}' no está definida",
        "E002": "Error de sintaxis: se esperaba '{expected}', pero se encontró '{got}'",
    })
    msg = loc.format("E002", expected=")", got=";")
    # → "Error de sintaxis: se esperaba ')', pero se encontró ';'"
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ErrorMessage:
    """A structured error message with code, severity, and template."""
    code: str
    severity: str  # "error", "warning", "info", "hint"
    template: str  # Format string with {named} placeholders
    category: str = "general"

    def format(self, **kwargs: Any) -> str:
        """Format this message with the given parameters."""
        try:
            return self.template.format(**kwargs)
        except KeyError:
            return self.template


# Default English error catalog
DEFAULT_ERRORS: Dict[str, ErrorMessage] = {
    # Syntax errors
    "E001": ErrorMessage("E001", "error", "Unexpected token '{got}', expected '{expected}'", "syntax"),
    "E002": ErrorMessage("E002", "error", "Unterminated string literal", "syntax"),
    "E003": ErrorMessage("E003", "error", "Invalid number format: '{text}'", "syntax"),
    "E004": ErrorMessage("E004", "error", "Unexpected end of input", "syntax"),
    "E005": ErrorMessage("E005", "error", "Mismatched bracket: '{bracket}'", "syntax"),

    # Name/scope errors
    "E010": ErrorMessage("E010", "error", "Undefined variable: '{name}'", "name"),
    "E011": ErrorMessage("E011", "error", "Variable '{name}' already defined", "name"),
    "E012": ErrorMessage("E012", "error", "Cannot assign to '{name}'", "name"),
    "E013": ErrorMessage("E013", "error", "Undefined function: '{name}'", "name"),
    "E014": ErrorMessage("E014", "error", "Module '{name}' not found", "name"),

    # Type errors
    "E020": ErrorMessage("E020", "error", "Type mismatch: expected '{expected}', got '{got}'", "type"),
    "E021": ErrorMessage("E021", "error", "Cannot apply operator '{op}' to types '{left}' and '{right}'", "type"),
    "E022": ErrorMessage("E022", "error", "Wrong number of arguments: expected {expected}, got {got}", "type"),
    "E023": ErrorMessage("E023", "error", "Cannot convert '{from_type}' to '{to_type}'", "type"),

    # Grammar errors
    "E030": ErrorMessage("E030", "error", "Grammar rule '{rule}' is undefined", "grammar"),
    "E031": ErrorMessage("E031", "error", "Left recursion detected in rule '{rule}'", "grammar"),
    "E032": ErrorMessage("E032", "error", "Duplicate rule definition: '{rule}'", "grammar"),

    # Warnings
    "W001": ErrorMessage("W001", "warning", "Variable '{name}' defined but never used", "usage"),
    "W002": ErrorMessage("W002", "warning", "Unreachable code after return statement", "usage"),
    "W003": ErrorMessage("W003", "warning", "Shadowing variable '{name}' from outer scope", "usage"),
    "W004": ErrorMessage("W004", "warning", "Division by zero", "usage"),

    # Hints
    "H001": ErrorMessage("H001", "hint", "Did you mean '{suggestion}'?", "suggestion"),
    "H002": ErrorMessage("H002", "hint", "Consider using '{alternative}' instead", "suggestion"),
}


class ErrorLocalizer:
    """Manages localized error messages for a custom language.

    Supports:
        - Loading translations from dicts or JSON files
        - Fallback to English when translation is missing
        - Custom error codes added by language designers
        - Source context (line/col) in error formatting
    """

    def __init__(self, locale: str = "en"):
        self.locale = locale
        self._catalog: Dict[str, ErrorMessage] = dict(DEFAULT_ERRORS)
        self._translations: Dict[str, Dict[str, str]] = {}  # locale → {code → template}

    def load_translations(self, translations: Dict[str, str], locale: Optional[str] = None) -> None:
        """Load translation strings for a locale.

        Args:
            translations: Mapping of error code → localized template string
            locale: Target locale (defaults to self.locale)
        """
        loc = locale or self.locale
        if loc not in self._translations:
            self._translations[loc] = {}
        self._translations[loc].update(translations)

    def load_translations_file(self, path: str, locale: Optional[str] = None) -> None:
        """Load translations from a JSON file.

        Expected format:
            {
                "E001": "Token inesperado '{got}', se esperaba '{expected}'",
                "E010": "Variable no definida: '{name}'"
            }
        """
        with open(path) as f:
            data = json.load(f)
        self.load_translations(data, locale)

    def register_error(self, code: str, severity: str, template: str,
                       category: str = "custom") -> None:
        """Register a custom error code.

        Language designers can add their own error codes for
        language-specific errors.
        """
        self._catalog[code] = ErrorMessage(code, severity, template, category)

    def format(self, code: str, **kwargs: Any) -> str:
        """Format an error message with the given parameters.

        Falls back: locale translation → English catalog → raw code.
        """
        # Try locale translation first
        locale_trans = self._translations.get(self.locale, {})
        if code in locale_trans:
            try:
                return locale_trans[code].format(**kwargs)
            except KeyError:
                return locale_trans[code]

        # Fall back to English catalog
        if code in self._catalog:
            return self._catalog[code].format(**kwargs)

        return f"[{code}]"

    def format_with_context(
        self,
        code: str,
        source: str = "",
        line: int = 0,
        col: int = 0,
        filename: str = "<input>",
        **kwargs: Any,
    ) -> str:
        """Format an error message with source location context.

        Returns a multi-line string like:
            error[E001]: Unexpected token '}', expected ')'
             --> test.lang:5:12
              |
            5 | x = foo(a, b}
              |              ^ here
        """
        msg = self.format(code, **kwargs)
        severity = "error"
        if code in self._catalog:
            severity = self._catalog[code].severity

        lines = [f"{severity}[{code}]: {msg}"]
        lines.append(f" --> {filename}:{line}:{col}")

        if source and line > 0:
            src_lines = source.split("\n")
            if 0 < line <= len(src_lines):
                src_line = src_lines[line - 1]
                gutter = f"{line:>4} | "
                lines.append("     |")
                lines.append(f"{gutter}{src_line}")
                pointer = " " * (len(gutter) + max(0, col - 1)) + "^"
                lines.append(f"{pointer} here")

        return "\n".join(lines)

    def get_severity(self, code: str) -> str:
        """Get the severity of an error code."""
        if code in self._catalog:
            return self._catalog[code].severity
        return "error"

    def list_codes(self, category: Optional[str] = None) -> List[str]:
        """List all error codes, optionally filtered by category."""
        if category:
            return [c for c, m in self._catalog.items() if m.category == category]
        return list(self._catalog.keys())

    def set_locale(self, locale: str) -> None:
        """Change the active locale."""
        self.locale = locale

    def available_locales(self) -> List[str]:
        """List available locales."""
        locales = ["en"]
        locales.extend(self._translations.keys())
        return sorted(set(locales))
