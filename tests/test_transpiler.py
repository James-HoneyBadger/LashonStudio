"""Tests for the Python transpiler."""

import pytest

from parsercraft.codegen.python_transpiler import (
    PythonTranspiler,
    TranspileOptions,
    transpile_and_exec,
    transpile_to_python,
)
from parsercraft.parser.grammar import GrammarParser, PEGInterpreter


@pytest.fixture
def grammar():
    parser = GrammarParser()
    return parser.parse(
        'program <- statement+\n'
        'statement <- assignment\n'
        'assignment <- IDENT "=" expr ";"\n'
        'expr <- term (("+" / "-") term)*\n'
        'term <- factor (("*" / "/") factor)*\n'
        'factor <- NUMBER / IDENT / "(" expr ")"'
    )


@pytest.fixture
def interpreter(grammar):
    return PEGInterpreter(grammar)


class TestPythonTranspiler:
    """Test AST to Python transpilation."""

    def test_simple_assignment(self, interpreter):
        ast = interpreter.parse("x = 10 ;")
        t = PythonTranspiler()
        code = t.transpile(ast)
        assert "x = 10" in code

    def test_arithmetic(self, interpreter):
        ast = interpreter.parse("y = 3 + 4 ;")
        t = PythonTranspiler()
        code = t.transpile(ast)
        assert "y = 3 + 4" in code or "y = (3 + 4)" in code

    def test_complex_expression(self, interpreter):
        ast = interpreter.parse("z = 2 + 3 * 4 ;")
        t = PythonTranspiler()
        code = t.transpile(ast)
        ns = {}
        exec(code, ns)
        assert ns["z"] == 14

    def test_multiple_statements(self, interpreter):
        ast = interpreter.parse("a = 10 ; b = 20 ; c = a + b ;")
        t = PythonTranspiler()
        code = t.transpile(ast)
        ns = {}
        exec(code, ns)
        assert ns["a"] == 10
        assert ns["b"] == 20
        assert ns["c"] == 30

    def test_variable_references(self, interpreter):
        ast = interpreter.parse("x = 5 ; y = x * 3 ;")
        t = PythonTranspiler()
        code = t.transpile(ast)
        ns = {}
        exec(code, ns)
        assert ns["y"] == 15

    def test_parenthesized_expression(self, interpreter):
        ast = interpreter.parse("r = ( 2 + 3 ) * 4 ;")
        t = PythonTranspiler()
        code = t.transpile(ast)
        ns = {}
        exec(code, ns)
        assert ns["r"] == 20

    def test_subtraction(self, interpreter):
        ast = interpreter.parse("d = 10 - 3 ;")
        t = PythonTranspiler()
        code = t.transpile(ast)
        ns = {}
        exec(code, ns)
        assert ns["d"] == 7

    def test_division(self, interpreter):
        ast = interpreter.parse("q = 20 / 4 ;")
        t = PythonTranspiler()
        code = t.transpile(ast)
        ns = {}
        exec(code, ns)
        assert ns["q"] == 5.0 or ns["q"] == 5


class TestTranspileHelpers:
    """Test the convenience functions."""

    def test_transpile_to_python(self, interpreter):
        ast = interpreter.parse("x = 42 ;")
        code = transpile_to_python(ast)
        assert "x = 42" in code

    def test_transpile_and_exec(self, interpreter):
        ast = interpreter.parse("a = 7 ; b = a * 6 ;")
        ns = transpile_and_exec(ast)
        assert ns["a"] == 7
        assert ns["b"] == 42

    def test_transpile_and_exec_omits_dunders(self, interpreter):
        ast = interpreter.parse("a = 1 ;")
        ns = transpile_and_exec(ast)
        assert ns == {"a": 1}

    def test_transpile_and_exec_preserves_supplied_globals(self, interpreter):
        ast = interpreter.parse("b = a + 1 ;")
        ns = transpile_and_exec(ast, globals_dict={"a": 41})
        assert ns == {"a": 41, "b": 42}


class TestTranspileOptions:
    """Test transpiler with custom options."""

    def test_default_options(self):
        opts = TranspileOptions()
        assert opts.indent_str == "    "
        assert opts.keyword_map == {}

    def test_custom_indent_str(self, interpreter):
        ast = interpreter.parse("x = 1 ;")
        opts = TranspileOptions(indent_str="\t")
        t = PythonTranspiler(opts)
        code = t.transpile(ast)
        assert "x = 1" in code


EXPRESSION_GRAMMAR = (
    'program <- statement+\n'
    'statement <- function_def / return_stmt / print_stmt / assignment\n'
    'function_def <- "def" IDENT "(" param_list? ")" ":" block\n'
    'param_list <- IDENT ("," IDENT)*\n'
    'block <- "{" statement* "}"\n'
    'return_stmt <- "return" expr ";"\n'
    'print_stmt <- "print" expr ";"\n'
    'assignment <- IDENT "=" expr ";"\n'
    'expr <- term (("+" / "-") term)*\n'
    'term <- factor (("*" / "/") factor)*\n'
    'factor <- list_literal / dict_literal / call / STRING / NUMBER / IDENT'
    ' / "(" expr ")"\n'
    'list_literal <- "[" (expr ("," expr)*)? "]"\n'
    'dict_literal <- "{" (STRING ":" expr ("," STRING ":" expr)*)? "}"\n'
    'call <- IDENT "(" arg_list? ")"\n'
    'arg_list <- expr ("," expr)*'
)


class TestTranspilerRegressions:
    """Regression tests for AST shapes that previously emitted invalid code."""

    @staticmethod
    def _transpile(grammar_text, source):
        return transpile_to_python(PEGInterpreter(
            GrammarParser().parse(grammar_text)
        ).parse(source))

    @staticmethod
    def _execute(grammar_text, source):
        ast = PEGInterpreter(GrammarParser().parse(grammar_text)).parse(source)
        return transpile_and_exec(ast)

    def test_function_parameter_list_has_no_duplicate_commas(self):
        code = self._transpile(
            EXPRESSION_GRAMMAR,
            'def add(a, b) : { return a + b ; }',
        )
        assert "def add(a, b):" in code

    def test_function_call_executes(self):
        ns = self._execute(
            EXPRESSION_GRAMMAR,
            'def add(a, b) : { return a + b ; } x = add(1, 2) ;',
        )
        assert ns["x"] == 3

    def test_list_literal_ignores_punctuation(self):
        ns = self._execute(EXPRESSION_GRAMMAR, 'x = [1, 2, 3] ;')
        assert ns["x"] == [1, 2, 3]

    def test_dict_literal_ignores_punctuation(self):
        ns = self._execute(EXPRESSION_GRAMMAR, 'x = {"a": 1, "b": 2} ;')
        assert ns["x"] == {"a": 1, "b": 2}

    def test_print_filters_keyword_and_punctuation(self, capsys):
        self._execute(EXPRESSION_GRAMMAR, 'print 1 + 2 ;')
        assert capsys.readouterr().out.strip() == "3"

    def test_boolean_rule_emits_python_literal(self):
        grammar = (
            'program <- statement+\n'
            'statement <- assignment\n'
            'assignment <- IDENT "=" expr ";"\n'
            'expr <- boolean / NUMBER\n'
            'boolean <- "true" / "false"'
        )
        assert self._execute(grammar, 'x = true ;')["x"] is True
        assert self._execute(grammar, 'y = false ;')["y"] is False

    def test_lambda_mapped_function_is_parenthesised(self):
        ns = self._execute(EXPRESSION_GRAMMAR, 'x = LEFTS("hello", 2) ;')
        assert ns["x"] == "he"

    def test_import_filters_keyword(self):
        grammar = (
            'program <- statement+\n'
            'statement <- import_stmt / assignment\n'
            'import_stmt <- "import" IDENT ";"\n'
            'assignment <- IDENT "=" NUMBER ";"'
        )
        code = self._transpile(grammar, 'import math ; x = 1 ;')
        assert "import math" in code
        assert "import import" not in code

    def test_say_with_multiple_arguments(self, capsys):
        grammar = (
            'program <- statement+\n'
            'statement <- say_stmt / assignment\n'
            'say_stmt <- "SAY" expr ("," expr)* ";"\n'
            'assignment <- IDENT "=" expr ";"\n'
            'expr <- NUMBER / STRING / IDENT'
        )
        self._execute(grammar, 'x = 5 ; SAY "a", 1, x ;')
        assert capsys.readouterr().out.strip() == "a 1 5"

    def test_basic_comparison_leaves_operators_intact(self):
        fix = PythonTranspiler._fix_basic_comparison
        assert fix("x <= 5") == "x <= 5"
        assert fix("x >= 5") == "x >= 5"
        assert fix("x <> 5") != "x <> 5"
        assert fix("x = 5") == "x == 5"


def test_python_transpiler_implements_backend_interface(interpreter):
    ast = interpreter.parse("x = 1 ;")
    assert PythonTranspiler().translate_source_ast(ast) == PythonTranspiler().transpile(ast)


def test_print_with_parentheses_ignores_punctuation():
    grammar = (
        'program <- statement+\n'
        'statement <- print_stmt / assignment\n'
        'print_stmt <- "print" "(" expr ")" ";"\n'
        'assignment <- IDENT "=" expr ";"\n'
        'expr <- NUMBER / IDENT'
    )
    code = transpile_to_python(
        PEGInterpreter(GrammarParser().parse(grammar)).parse('print(42) ;')
    )
    assert code.strip() == "print(42)"
