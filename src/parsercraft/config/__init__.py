"""
parsercraft.config — Language definition and configuration management.

This subpackage provides the LanguageConfig class and related validators
for defining, loading, saving, and manipulating custom language configs.

LanguageConfig
    Central class for all language definition work::

        # From a built-in preset
        config = LanguageConfig.from_preset("pascal_like")

        # From a file
        config = LanguageConfig.load("my_lang.yaml")

        # Customise
        config.rename_keyword("if", "si")
        config.add_function("imprimir", "print")
        config.save("espanol.yaml")

    Supported preset names:  python_like · js_like · ruby_like ·
    golang_like · rust_like · clike · functional · lisp_like ·
    basic_like · minimal

LanguageValidator
    Validate a LanguageConfig against the schema.  Returns a list of
    human-readable error strings (empty list ⇒ valid).

IdentifierValidator
    Check that identifier names satisfy the language’s configured
    naming rules (case sensitivity, reserved words, etc.).

See docs/USER_GUIDE.md for comprehensive usage examples.
"""

from .identifier_validator import IdentifierValidator
from .language_config import (
    FunctionConfig,
    KeywordMapping,
    LanguageConfig,
    OperatorConfig,
    ParsingConfig,
    SyntaxOptions,
    list_presets,
)
from .language_validator import LanguageValidator

__all__ = [
    "LanguageConfig",
    "KeywordMapping",
    "FunctionConfig",
    "OperatorConfig",
    "ParsingConfig",
    "SyntaxOptions",
    "LanguageValidator",
    "IdentifierValidator",
    "list_presets",
]
