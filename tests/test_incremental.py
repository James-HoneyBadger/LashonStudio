"""Tests for the incremental parser."""

import pytest

from lashon.codegen import transpile_and_exec
from lashon.parser.grammar import GrammarParser
from lashon.parser.incremental import IncrementalParser, SourceEdit


@pytest.fixture
def arith_grammar():
    parser = GrammarParser()
    return parser.parse(
        'program <- statement+\n'
        'statement <- assignment\n'
        'assignment <- IDENT "=" expr ";"\n'
        'expr <- term (("+" / "-") term)*\n'
        'term <- factor (("*" / "/") factor)*\n'
        'factor <- NUMBER / IDENT / "(" expr ")"'
    )


class TestIncrementalParser:
    """Test incremental parsing capabilities."""

    def test_initial_parse(self, arith_grammar):
        parser = IncrementalParser(arith_grammar)
        ast = parser.parse("x = 10 ;")
        assert ast is not None
        assert ast.node_type == "program"

    def test_source_tracking(self, arith_grammar):
        parser = IncrementalParser(arith_grammar)
        parser.parse("x = 10 ;")
        assert parser.source == "x = 10 ;"

    def test_apply_edit(self, arith_grammar):
        parser = IncrementalParser(arith_grammar)
        parser.parse("x = 10 ;")

        # Change "10" to "20"
        ast = parser.apply_edit(offset=4, old_len=2, new_text="20")
        assert ast is not None
        assert parser.source == "x = 20 ;"

    def test_apply_edit_insert(self, arith_grammar):
        parser = IncrementalParser(arith_grammar)
        parser.parse("x = 10 ; y = 20 ;")

        # Insert " z = 30 ;" at the end
        ast = parser.apply_edit(
            offset=len("x = 10 ; y = 20 ;"),
            old_len=0,
            new_text=" z = 30 ;",
        )
        assert ast is not None
        assert "z = 30" in parser.source

    def test_stats(self, arith_grammar):
        parser = IncrementalParser(arith_grammar)
        parser.parse("x = 10 ;")
        stats = parser.stats
        assert stats["total_parses"] == 1
        assert "last_parse_ms" in stats

    def test_reset(self, arith_grammar):
        parser = IncrementalParser(arith_grammar)
        parser.parse("x = 10 ;")
        parser.reset()
        assert parser.ast is None
        assert parser.source == ""
        assert parser.stats["total_parses"] == 0

    def test_invalidate(self, arith_grammar):
        parser = IncrementalParser(arith_grammar)
        parser.parse("x = 10 ;")
        parser.invalidate()
        # After invalidation, next edit should do full reparse
        ast = parser.apply_edit(offset=4, old_len=2, new_text="42")
        assert ast is not None

    def test_multiple_edits(self, arith_grammar):
        parser = IncrementalParser(arith_grammar)
        parser.parse("x = 1 ; y = 2 ;")

        # Edit x's value
        parser.apply_edit(offset=4, old_len=1, new_text="100")
        assert "100" in parser.source

        # Edit y's value (offset shifted by delta)
        parser.apply_edit(offset=14, old_len=1, new_text="200")
        assert "200" in parser.source


class TestSourceEdit:
    """Test SourceEdit dataclass."""

    def test_delta_insert(self):
        edit = SourceEdit(offset=5, old_len=0, new_text="hello")
        assert edit.delta == 5

    def test_delta_delete(self):
        edit = SourceEdit(offset=5, old_len=3, new_text="")
        assert edit.delta == -3

    def test_delta_replace(self):
        edit = SourceEdit(offset=5, old_len=2, new_text="abc")
        assert edit.delta == 1

    def test_new_len(self):
        edit = SourceEdit(offset=0, old_len=0, new_text="test")
        assert edit.new_len == 4


class TestIncrementalBehaviour:
    """Verify that edits actually use the incremental path."""

    def test_edit_reparses_only_the_affected_region(self, arith_grammar):
        parser = IncrementalParser(arith_grammar)
        parser.parse("x = 10 ; y = 20 ;")

        parser.apply_edit(offset=4, old_len=2, new_text="99")

        assert parser.stats["incremental"] == 1
        assert parser.stats["full_reparse"] == 0
        assert parser.source == "x = 99 ; y = 20 ;"

    def test_edited_region_produces_correct_ast(self, arith_grammar):
        parser = IncrementalParser(arith_grammar)
        parser.parse("x = 10 ; y = 20 ;")

        ast = parser.apply_edit(offset=4, old_len=2, new_text="99")
        namespace = transpile_and_exec(ast)

        assert namespace == {"x": 99, "y": 20}
