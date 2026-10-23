"""Tests for the type-system layers."""

from parsercraft.types import (
    GenericsTypeChecker,
    ProtocolTypeChecker,
    Type,
    TypeChecker,
    TypeEnvironment,
    TypeKind,
    TypeNarrowingPass,
)


class TestTypeCompatibility:
    """Test core Type compatibility rules."""

    def test_same_kind_is_compatible(self):
        assert Type.int().is_compatible_with(Type.int())

    def test_int_is_compatible_with_float(self):
        assert Type.int().is_compatible_with(Type.float())

    def test_string_is_not_compatible_with_int(self):
        assert not Type.str().is_compatible_with(Type.int())

    def test_optional_without_type_args_does_not_crash(self):
        optional = Type(kind=TypeKind.OPTIONAL)
        assert optional.is_compatible_with(Type.int())
        assert Type.int().is_compatible_with(optional)

    def test_any_is_compatible_with_everything(self):
        assert Type(kind=TypeKind.ANY).is_compatible_with(Type.int())


class TestTypeEnvironment:
    """Test scoped type bindings."""

    def test_child_scope_sees_parent_variables(self):
        parent = TypeEnvironment()
        parent.define_variable("x", Type.int())
        child = parent.create_child_scope()
        assert child.get_variable_type("x") == Type.int()

    def test_child_scope_shadows_parent(self):
        parent = TypeEnvironment()
        parent.define_variable("x", Type.int())
        child = parent.create_child_scope()
        child.define_variable("x", Type.str())
        assert child.get_variable_type("x") == Type.str()
        assert parent.get_variable_type("x") == Type.int()

    def test_unknown_variable_returns_none(self):
        assert TypeEnvironment().get_variable_type("missing") is None


class TestTypeNarrowing:
    """Test the narrowing pass for comparisons."""

    def _optional_int(self):
        return Type(kind=TypeKind.OPTIONAL, name="int", type_args=[Type.int()])

    def test_not_equal_none_removes_nullable(self):
        narrowing = TypeNarrowingPass()
        narrowing.narrowed_types["x"] = self._optional_int()
        narrowing.narrow_by_comparison("x", "!=", None)
        assert narrowing.get_narrowed_type("x").nullable is False

    def test_equal_none_adds_nullable(self):
        narrowing = TypeNarrowingPass()
        narrowing.narrowed_types["x"] = Type.int()
        narrowing.narrow_by_comparison("x", "==", None)
        assert narrowing.get_narrowed_type("x").nullable is True

    def test_unknown_variable_is_ignored(self):
        narrowing = TypeNarrowingPass()
        narrowing.narrow_by_comparison("missing", "!=", None)
        assert narrowing.get_narrowed_type("missing") is None

    def test_comparison_against_value_removes_nullable(self):
        narrowing = TypeNarrowingPass()
        narrowing.narrowed_types["x"] = self._optional_int()
        narrowing.narrow_by_comparison("x", ">", 0)
        assert narrowing.get_narrowed_type("x").nullable is False


class TestIntegrationLayers:
    """Test the generics/protocol integration layers."""

    def test_generic_function_is_registered(self):
        checker = GenericsTypeChecker()
        assert checker.check_generic_function("identity", ["T"], None) == []
        assert "identity" in checker.generic_functions

    def test_unknown_protocol_is_reported(self):
        checker = ProtocolTypeChecker()
        conforms, errors = checker.check_protocol_conformance("Thing", "Missing")
        assert conforms is False
        assert errors == ["Unknown protocol: Missing"]


class TestTypeCheckerRegression:
    """Regression tests for literal inference and diagnostic locations."""

    def test_numeric_literal_is_not_treated_as_variable(self):
        from parsercraft.config import LanguageConfig

        checker = TypeChecker(LanguageConfig())
        env = TypeEnvironment()
        assert checker.check_expression("42", env) == Type.int()
        assert checker.check_expression("3.5", env) == Type.float()

    def test_type_mismatch_reports_real_line_and_file(self, tmp_path):
        from parsercraft.config import LanguageConfig

        source = tmp_path / "program.src"
        source.write_text("x: int = 1\ny: str = 2\n", encoding="utf-8")

        checker = TypeChecker(LanguageConfig())
        errors = checker.check_file(str(source))

        assert len(errors) == 1
        assert errors[0].line == 2
        assert errors[0].location == str(source)
        assert "int to str" in errors[0].message

    def test_boolean_literals_infer_bool(self):
        from parsercraft.config import LanguageConfig

        checker = TypeChecker(LanguageConfig())
        env = TypeEnvironment()
        assert checker.check_expression("True", env) == Type.bool()
        assert checker.check_expression("false", env) == Type.bool()
