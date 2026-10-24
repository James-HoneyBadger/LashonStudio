"""Tests for the PEG grammar engine."""

import pytest

from lashon.parser.grammar import (
    Grammar,
    GrammarBuilder,
    GrammarParser,
    PEGInterpreter,
    PEGNode,
    PEGNodeType,
    SourceAST,
    grammar_from_config,
)


class TestGrammarParser:
    """Test parsing PEG grammar notation into Grammar objects."""

    def test_parse_simple_rule(self):
        parser = GrammarParser()
        grammar = parser.parse('program <- statement*')
        assert "program" in grammar.rules
        assert grammar.start_rule == "program"

    def test_parse_multiple_rules(self):
        parser = GrammarParser()
        grammar = parser.parse(
            'program <- statement*\n'
            'statement <- assignment\n'
            'assignment <- IDENT "=" expr ";"'
        )
        assert len(grammar.rules) == 3
        assert "program" in grammar.rules
        assert "statement" in grammar.rules
        assert "assignment" in grammar.rules

    def test_parse_choice(self):
        parser = GrammarParser()
        grammar = parser.parse('factor <- NUMBER / IDENT / "(" expr ")"')
        assert "factor" in grammar.rules
        rule = grammar.rules["factor"]
        assert rule.pattern.node_type == PEGNodeType.ORDERED_CHOICE

    def test_parse_quantifiers(self):
        parser = GrammarParser()
        grammar = parser.parse(
            'program <- statement+\n'
            'optional <- item?\n'
            'many <- item*'
        )
        prog_pat = grammar.rules["program"].pattern
        assert prog_pat.node_type == PEGNodeType.ONE_OR_MORE

    def test_parse_literal(self):
        parser = GrammarParser()
        grammar = parser.parse('op <- "+"')
        rule = grammar.rules["op"]
        assert rule.pattern.node_type == PEGNodeType.LITERAL
        assert rule.pattern.value == "+"

    def test_validate_valid_grammar(self):
        parser = GrammarParser()
        grammar = parser.parse(
            'program <- statement+\n'
            'statement <- IDENT "=" NUMBER ";"'
        )
        errors = grammar.validate()
        assert errors == []

    def test_trailing_text_is_rejected(self):
        with pytest.raises(ValueError, match="unexpected"):
            GrammarParser().parse('program <- NUMBER )')

    def test_unterminated_literal_is_rejected(self):
        with pytest.raises(ValueError, match="Unterminated string literal"):
            GrammarParser().parse('program <- "abc')

    def test_unclosed_group_is_rejected(self):
        with pytest.raises(ValueError, match="Unclosed group"):
            GrammarParser().parse('program <- (NUMBER')

    def test_pipe_is_accepted_as_choice(self):
        grammar = GrammarParser().parse('program <- NUMBER | IDENT')
        pattern = grammar.rules["program"].pattern
        assert pattern.node_type == PEGNodeType.ORDERED_CHOICE


class TestPEGInterpreter:
    """Test parsing source code using a Grammar."""

    @pytest.fixture
    def arith_grammar(self):
        parser = GrammarParser()
        return parser.parse(
            'program <- statement+\n'
            'statement <- assignment\n'
            'assignment <- IDENT "=" expr ";"\n'
            'expr <- term (("+" / "-") term)*\n'
            'term <- factor (("*" / "/") factor)*\n'
            'factor <- NUMBER / IDENT / "(" expr ")"'
        )

    def test_parse_assignment(self, arith_grammar):
        interp = PEGInterpreter(arith_grammar)
        ast = interp.parse("x = 10 ;")
        assert ast is not None
        assert ast.node_type == "program"

    def test_parse_expression(self, arith_grammar):
        interp = PEGInterpreter(arith_grammar)
        ast = interp.parse("y = 3 + 4 ;")
        assert ast is not None
        assert len(ast.children) >= 1

    def test_parse_complex_expression(self, arith_grammar):
        interp = PEGInterpreter(arith_grammar)
        ast = interp.parse("z = 2 + 3 * 4 ;")
        assert ast is not None

    def test_parse_multiple_statements(self, arith_grammar):
        interp = PEGInterpreter(arith_grammar)
        ast = interp.parse("x = 1 ; y = 2 ; z = x + y ;")
        assert ast is not None
        assert len(ast.children) == 3

    def test_parse_parenthesized(self, arith_grammar):
        interp = PEGInterpreter(arith_grammar)
        ast = interp.parse("w = ( 2 + 3 ) * 4 ;")
        assert ast is not None

    def test_parse_variable_reference(self, arith_grammar):
        interp = PEGInterpreter(arith_grammar)
        ast = interp.parse("a = 5 ; b = a ;")
        assert ast is not None
        assert len(ast.children) == 2

    def test_invalid_syntax_raises(self, arith_grammar):
        interp = PEGInterpreter(arith_grammar)
        with pytest.raises(SyntaxError):
            interp.parse("= = = ;")

    def test_pretty_print(self, arith_grammar):
        interp = PEGInterpreter(arith_grammar)
        ast = interp.parse("x = 10 ;")
        pretty = ast.pretty()
        assert "program" in pretty
        assert "10" in pretty

    def test_error_message_names_the_rule(self, arith_grammar):
        interp = PEGInterpreter(arith_grammar)
        with pytest.raises(SyntaxError, match="in rule 'program'"):
            interp.parse("= = ;")

    def test_zero_width_comment_pattern_terminates(self):
        grammar = Grammar()
        grammar.add_rule(
            "program",
            PEGNode(
                PEGNodeType.ONE_OR_MORE,
                children=[PEGNode(PEGNodeType.TOKEN_REF, "NUMBER")],
            ),
        )
        grammar.comment_patterns = ["x*"]
        ast = PEGInterpreter(grammar).parse("1 2")
        assert ast.node_type == "program"

    def test_unsupported_token_is_reported(self):
        grammar = GrammarParser().parse("program <- INDENT")
        errors = grammar.validate()
        assert any("unsupported token 'INDENT'" in error for error in errors)


class TestGrammarBuilder:
    """Test the fluent grammar builder API."""

    def test_build_simple(self):
        b = GrammarBuilder()
        b.rule("program").set_pattern(b.plus(b.ref("statement")))
        b.rule("statement").set_pattern(
            b.seq(b.ref("IDENT"), b.lit("="), b.ref("NUMBER"), b.lit(";"))
        )
        grammar = b.build()
        assert "program" in grammar.rules
        assert "statement" in grammar.rules

    def test_builder_produces_valid_grammar(self):
        b = GrammarBuilder()
        b.rule("program").set_pattern(b.plus(b.ref("statement")))
        b.rule("statement").set_pattern(
            b.seq(b.ref("IDENT"), b.lit("="), b.ref("expr"), b.lit(";"))
        )
        b.rule("expr").set_pattern(b.ref("NUMBER"))
        grammar = b.build()
        errors = grammar.validate()
        assert errors == []

    def test_builder_parse_and_execute(self):
        b = GrammarBuilder()
        b.rule("program").set_pattern(b.plus(b.ref("statement")))
        b.rule("statement").set_pattern(
            b.seq(b.ref("IDENT"), b.lit("="), b.ref("NUMBER"), b.lit(";"))
        )
        grammar = b.build()
        interp = PEGInterpreter(grammar)
        ast = interp.parse("x = 42 ;")
        assert ast is not None


class TestGrammarFromConfig:
    """Test loading grammars from config dictionaries."""

    def test_from_config_dict(self):
        config = {
            "grammar": {
                "rules": {
                    "program": "statement+",
                    "statement": "assignment",
                    "assignment": 'IDENT "=" expr ";"',
                    "expr": "NUMBER",
                }
            }
        }
        grammar = grammar_from_config(config)
        assert "program" in grammar.rules
        assert len(grammar.rules) == 4

    def test_from_config_with_start(self):
        config = {
            "grammar": {
                "start": "main",
                "rules": {
                    "main": "statement+",
                    "statement": 'IDENT "=" NUMBER ";"',
                }
            }
        }
        grammar = grammar_from_config(config)
        assert grammar.start_rule == "main"

    def test_config_round_trip(self):
        """Config → Grammar → parse source."""
        config = {
            "grammar": {
                "rules": {
                    "program": "statement+",
                    "statement": 'IDENT "=" NUMBER ";"',
                }
            }
        }
        grammar = grammar_from_config(config)
        interp = PEGInterpreter(grammar)
        ast = interp.parse("x = 42 ;")
        assert ast is not None


class TestSourceAST:
    """Test SourceAST structure and methods."""

    def test_leaf_node(self):
        node = SourceAST(node_type="NUMBER", value="42")
        assert node.value == "42"
        assert node.children == []

    def test_composite_node(self):
        child1 = SourceAST(node_type="NUMBER", value="1")
        child2 = SourceAST(node_type="NUMBER", value="2")
        parent = SourceAST(node_type="expr", children=[child1, child2])
        assert len(parent.children) == 2

    def test_pretty_output(self):
        child = SourceAST(node_type="NUMBER", value="42")
        parent = SourceAST(node_type="program", children=[child])
        output = parent.pretty()
        assert "program" in output
        assert "42" in output
