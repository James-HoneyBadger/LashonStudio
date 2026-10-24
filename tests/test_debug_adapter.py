"""Tests for the DAP debugger's safe expression evaluation."""

import pytest

from lashon.tooling.debug.debug_adapter import Debugger, Variable

SOURCE = "program.test"


@pytest.fixture
def debugger():
    dbg = Debugger(SOURCE)
    dbg.add_variable(0, Variable(name="x", value=5, var_type="int"))
    dbg.add_variable(0, Variable(name="items", value=[1, 2, 3], var_type="list"))
    return dbg


def test_evaluate_literal(debugger):
    assert debugger.evaluate_expression("42", 0) == "42"


def test_evaluate_variables_and_arithmetic(debugger):
    assert debugger.evaluate_expression("x * 2", 0) == "10"


def test_evaluate_subscript(debugger):
    assert debugger.evaluate_expression("items[0] + x", 0) == "6"


def test_evaluate_rejects_function_calls(debugger):
    assert debugger.evaluate_expression("__import__('os')", 0) is None


def test_condition_true_stops_at_breakpoint(debugger):
    debugger.set_breakpoint(SOURCE, 10, condition="x > 3 and items[0] == 1")
    assert debugger.hit_breakpoint(SOURCE, 10) is not None


def test_condition_false_skips_breakpoint(debugger):
    debugger.set_breakpoint(SOURCE, 10, condition="x < 3")
    assert debugger.hit_breakpoint(SOURCE, 10) is None


def test_invalid_condition_is_reported(debugger):
    breakpoint = debugger.set_breakpoint(SOURCE, 10, condition="x +")
    assert debugger.hit_breakpoint(SOURCE, 10) is None
    assert breakpoint.verified is False
    assert "Invalid condition" in breakpoint.message


def test_unknown_variable_condition_is_reported(debugger):
    breakpoint = debugger.set_breakpoint(SOURCE, 10, condition="missing > 1")
    assert debugger.hit_breakpoint(SOURCE, 10) is None
    assert breakpoint.verified is False
