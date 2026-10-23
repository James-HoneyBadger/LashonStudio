"""Tests for loading the bundled language configurations."""

from pathlib import Path

import pytest

from parsercraft.config import LanguageConfig, list_presets

EXAMPLE_DIR = Path(__file__).resolve().parent.parent / "configs" / "examples"
EXAMPLE_CONFIGS = (
    sorted(EXAMPLE_DIR.glob("*.yaml")) + sorted(EXAMPLE_DIR.glob("*.json"))
)


@pytest.mark.parametrize("path", EXAMPLE_CONFIGS, ids=lambda p: p.name)
def test_every_example_config_loads(path):
    """All shipped configs must load through the public API."""
    config = LanguageConfig.load(path)
    assert config.name
    assert config.keyword_mappings


def test_shorthand_keyword_values_are_normalized():
    config = LanguageConfig.from_dict({"name": "X", "keywords": {"if": "when"}})
    assert config.name == "X"
    assert config.keyword_mappings["if"].custom == "when"


def test_builtin_functions_alias_is_supported():
    config = LanguageConfig.from_dict({
        "builtin_functions": {"print": {"name": "print", "arity": -1}},
    })
    assert "print" in config.builtin_functions


def test_function_entry_without_arity_is_accepted():
    config = LanguageConfig.from_dict({
        "functions": {
            "print": {"name": "WriteLn", "min_args": 0, "max_args": -1},
        },
    })
    assert config.builtin_functions["print"].arity == -1


def test_operator_list_is_supported():
    config = LanguageConfig.from_dict({
        "operators": [{
            "symbol": "+",
            "precedence": 4,
            "associativity": "left",
            "description": "add",
        }],
    })
    assert config.operators["+"].precedence == 4
    assert config.operators["+"].associativity == "left"


def test_top_level_runtime_flags_are_supported():
    config = LanguageConfig.from_dict({"debug_mode": True, "strict_mode": True})
    assert config.debug_mode is True
    assert config.strict_mode is True


def test_unknown_syntax_options_are_ignored():
    config = LanguageConfig.from_dict({
        "syntax_options": {
            "single_line_comment": "#",
            "unknown_option": True,
        },
    })
    assert config.syntax_options.single_line_comment == "#"


def test_every_listed_preset_loads():
    for preset in list_presets():
        assert LanguageConfig.from_preset(preset).name


@pytest.mark.parametrize("path", EXAMPLE_CONFIGS, ids=lambda p: p.name)
def test_every_example_config_validates(path):
    """Shipped configs must not contain hard validation errors."""
    assert LanguageConfig.load(path).validate() == []


def test_duplicate_keyword_aliases_are_warnings():
    config = LanguageConfig.from_dict({
        "keywords": {"function": "fun", "lambda": "fun", "if": "if"},
    })
    assert config.validate() == []
    warnings = config.validation_warnings()
    assert any("fun" in warning for warning in warnings)


def test_unique_keywords_have_no_warnings():
    config = LanguageConfig.from_dict({
        "keywords": {"function": "fun", "lambda": "fn"},
    })
    assert config.validation_warnings() == []


def test_boolean_yaml_keys_are_normalized_to_strings():
    """PyYAML parses bare ``true``/``false`` keys as booleans."""
    config = LanguageConfig.from_dict({
        "keywords": {True: "TRUE", False: "FALSE"},
    })
    assert config.keyword_mappings["true"].original == "true"
    assert config.keyword_mappings["false"].original == "false"


def test_pascal_config_boolean_keywords_translate_to_strings():
    config = LanguageConfig.load(EXAMPLE_DIR / "pascal_like.yaml")
    assert config.keyword_mappings["true"].original == "true"
    assert config.keyword_mappings["false"].original == "false"
