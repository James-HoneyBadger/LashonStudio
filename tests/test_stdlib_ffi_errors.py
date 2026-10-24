"""Tests for stdlib, FFI, and error localization."""

import math

import pytest

from lashon.runtime.ffi import FFIBinding, FFIBridge
from lashon.runtime.stdlib import StdFunction, StdLib, StdModule
from lashon.tooling.error_localization import ErrorLocalizer


class TestStdLib:
    """Test standard library framework."""

    def test_register_builtins(self):
        stdlib = StdLib()
        stdlib.register_builtins()
        modules = stdlib.list_modules()
        assert "math" in modules
        assert "io" in modules
        assert "string" in modules
        assert "collections" in modules
        assert "system" in modules
        assert "random" in modules

    def test_inject_builtins(self):
        stdlib = StdLib()
        stdlib.register_builtins()
        ns = stdlib.inject({})
        assert "print" in ns
        assert "len" in ns
        assert "int" in ns

    def test_inject_module(self):
        stdlib = StdLib()
        stdlib.register_builtins()
        ns = {}
        stdlib.inject_module("math", ns, ["sqrt", "PI"])
        assert ns["sqrt"](144) == 12.0
        assert abs(ns["PI"] - math.pi) < 1e-10

    def test_inject_module_as_namespace(self):
        stdlib = StdLib()
        stdlib.register_builtins()
        ns = {}
        stdlib.inject_module("math", ns)
        assert hasattr(ns["math"], "sqrt")
        assert ns["math"].sqrt(25) == 5.0

    def test_custom_module(self):
        stdlib = StdLib()
        mod = StdModule("mylib")
        mod.add_function("double", lambda x: x * 2,
                         params=[("x", "int")], returns="int")
        mod.add_constant("VERSION", "1.0")
        stdlib.add_module(mod)

        ns = {}
        stdlib.inject_module("mylib", ns, ["double", "VERSION"])
        assert ns["double"](21) == 42
        assert ns["VERSION"] == "1.0"

    def test_module_not_found(self):
        stdlib = StdLib()
        with pytest.raises(ImportError, match="No standard library module"):
            stdlib.inject_module("nonexistent", {})

    def test_symbol_not_found_in_module(self):
        stdlib = StdLib()
        stdlib.register_builtins()
        with pytest.raises(ImportError, match="Cannot import"):
            stdlib.inject_module("math", {}, ["nonexistent_fn"])

    def test_std_function_callable(self):
        func = StdFunction(name="square", callable=lambda x: x ** 2,
                           params=[("x", "int")], returns="int")
        assert func(5) == 25

    def test_module_list_symbols(self):
        mod = StdModule("test")
        mod.add_function("foo", lambda: None)
        mod.add_constant("BAR", 42)
        symbols = mod.list_symbols()
        assert "foo" in symbols
        assert "BAR" in symbols


class TestFFIBridge:
    """Test Foreign Function Interface."""

    def test_register_python_function(self):
        ffi = FFIBridge()
        ffi.register_python("greet", lambda name: f"Hello, {name}!")
        result = ffi.call("greet", "World")
        assert result == "Hello, World!"

    def test_import_python_module(self):
        ffi = FFIBridge()
        bindings = ffi.import_python_module("math", ["sqrt", "ceil"])
        assert len(bindings) == 2
        assert ffi.call("sqrt", 16) == 4.0
        assert ffi.call("ceil", 3.2) == 4

    def test_inject_into_namespace(self):
        ffi = FFIBridge()
        ffi.register_python("double", lambda x: x * 2)
        ns = ffi.inject({})
        assert ns["double"](5) == 10

    def test_list_bindings(self):
        ffi = FFIBridge()
        ffi.register_python("foo", lambda: None)
        ffi.register_python("bar", lambda: None)
        bindings = ffi.list_bindings()
        assert "foo" in bindings
        assert "bar" in bindings

    def test_call_unknown_binding(self):
        ffi = FFIBridge()
        with pytest.raises(NameError, match="No FFI binding"):
            ffi.call("nonexistent")

    def test_import_nonexistent_module(self):
        ffi = FFIBridge()
        with pytest.raises(ImportError):
            ffi.import_python_module("totally_fake_module_xyz")

    def test_describe(self):
        ffi = FFIBridge()
        ffi.register_python("test_fn", lambda: None, doc="Test function")
        desc = ffi.describe()
        assert "test_fn" in desc

    def test_binding_callable(self):
        binding = FFIBinding(
            name="test",
            source="python:native",
            native_name="test",
            _callable=lambda x: x + 1,
        )
        assert binding(5) == 6

    def test_unresolved_binding_raises(self):
        binding = FFIBinding(
            name="test",
            source="python:native",
            native_name="test",
        )
        with pytest.raises(RuntimeError, match="not resolved"):
            binding(5)

    def test_import_with_prefix(self):
        ffi = FFIBridge()
        ffi.import_python_module("math", ["sqrt"], prefix="m_")
        assert ffi.call("m_sqrt", 9) == 3.0


class TestErrorLocalizer:
    """Test error message localization."""

    def test_english_default(self):
        loc = ErrorLocalizer()
        msg = loc.format("E001", got="}", expected=")")
        assert "}" in msg
        assert ")" in msg
        assert "Unexpected token" in msg

    def test_spanish_translation(self):
        loc = ErrorLocalizer(locale="es")
        loc.load_translations({
            "E001": "Token inesperado '{got}', se esperaba '{expected}'",
        })
        msg = loc.format("E001", got="}", expected=")")
        assert "inesperado" in msg

    def test_fallback_to_english(self):
        loc = ErrorLocalizer(locale="fr")
        msg = loc.format("E001", got="}", expected=")")
        # No French translations loaded, falls back to English
        assert "Unexpected token" in msg

    def test_custom_error_code(self):
        loc = ErrorLocalizer()
        loc.register_error("E100", "error", "Custom error: {detail}", "custom")
        msg = loc.format("E100", detail="bad stuff")
        assert "Custom error: bad stuff" == msg

    def test_format_with_context(self):
        loc = ErrorLocalizer()
        result = loc.format_with_context(
            "E010",
            source="x = y + z",
            line=1,
            col=5,
            filename="test.lang",
            name="y",
        )
        assert "error[E010]" in result
        assert "test.lang:1:5" in result
        assert "Undefined variable" in result

    def test_get_severity(self):
        loc = ErrorLocalizer()
        assert loc.get_severity("E001") == "error"
        assert loc.get_severity("W001") == "warning"
        assert loc.get_severity("H001") == "hint"

    def test_list_codes(self):
        loc = ErrorLocalizer()
        codes = loc.list_codes()
        assert "E001" in codes
        assert "W001" in codes

    def test_list_codes_by_category(self):
        loc = ErrorLocalizer()
        syntax_codes = loc.list_codes("syntax")
        assert all(c.startswith("E00") for c in syntax_codes)

    def test_set_locale(self):
        loc = ErrorLocalizer(locale="en")
        loc.set_locale("de")
        assert loc.locale == "de"

    def test_available_locales(self):
        loc = ErrorLocalizer()
        loc.load_translations({"E001": "test"}, locale="fr")
        locales = loc.available_locales()
        assert "en" in locales
        assert "fr" in locales

    def test_unknown_code(self):
        loc = ErrorLocalizer()
        msg = loc.format("E999")
        assert "[E999]" in msg

    def test_load_translations_file(self, tmp_path):
        import json
        translations = {"E001": "Erreur: '{got}' inattendu, '{expected}' attendu"}
        path = tmp_path / "fr.json"
        path.write_text(json.dumps(translations))

        loc = ErrorLocalizer(locale="fr")
        loc.load_translations_file(str(path))
        msg = loc.format("E001", got="}", expected=")")
        assert "inattendu" in msg
