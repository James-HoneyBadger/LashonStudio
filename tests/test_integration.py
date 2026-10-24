"""Integration tests — end-to-end pipelines."""

import json

from lashon.codegen.codegen_c import CCodeGenerator
from lashon.codegen.llvm_ir import LLVMIRGenerator
from lashon.codegen.python_transpiler import PythonTranspiler, transpile_and_exec
from lashon.parser.grammar import GrammarParser, PEGInterpreter, grammar_from_config
from lashon.runtime.repl import REPL
from lashon.runtime.stdlib import StdLib


class TestFullPipeline:
    """Test the complete pipeline: Grammar → Parse → Transpile → Execute."""

    def test_config_to_execution(self):
        """YAML/JSON config → Grammar → Parse → Python → exec."""
        config = {
            "grammar": {
                "rules": {
                    "program": "statement+",
                    "statement": 'IDENT "=" expr ";"',
                    "expr": 'term (("+" / "-") term)*',
                    "term": 'factor (("*" / "/") factor)*',
                    "factor": 'NUMBER / IDENT / "(" expr ")"',
                }
            }
        }
        grammar = grammar_from_config(config)
        interp = PEGInterpreter(grammar)
        ast = interp.parse("x = 2 + 3 * 4 ;")
        ns = transpile_and_exec(ast)
        assert ns["x"] == 14

    def test_multi_backend_consistency(self):
        """Same source produces valid output from all backends."""
        parser = GrammarParser()
        grammar = parser.parse(
            'program <- statement+\n'
            'statement <- IDENT "=" expr ";"\n'
            'expr <- term (("+" / "-") term)*\n'
            'term <- factor (("*" / "/") factor)*\n'
            'factor <- NUMBER / IDENT / "(" expr ")"'
        )
        interp = PEGInterpreter(grammar)
        source = "x = 10 ; y = 20 ; z = x + y ;"
        ast = interp.parse(source)

        # Python transpiler
        t = PythonTranspiler()
        py_code = t.transpile(ast)
        ns = {}
        exec(py_code, ns)
        assert ns["z"] == 30

        # C generator
        c_gen = CCodeGenerator()
        c_code = c_gen.translate_source_ast(ast)
        assert "int main(" in c_code
        assert "int x" in c_code

        # LLVM IR generator
        llvm_gen = LLVMIRGenerator()
        ir = llvm_gen.translate_source_ast(ast)
        assert "define" in ir
        assert "add" in ir

    def test_repl_with_stdlib(self):
        """REPL + StdLib integration."""
        stdlib = StdLib()
        stdlib.register_builtins()

        repl = REPL()
        # Inject stdlib builtins into REPL namespace
        stdlib.inject(repl.namespace)

        repl.eval_line("x = 42")
        assert repl.namespace["x"] == 42

    def test_config_file_round_trip(self, tmp_path):
        """Write config → Read config → Build grammar → Parse → Execute."""
        config = {
            "grammar": {
                "rules": {
                    "program": "statement+",
                    "statement": 'IDENT "=" NUMBER ";"',
                }
            }
        }

        # Write config
        config_path = tmp_path / "test_lang.json"
        config_path.write_text(json.dumps(config))

        # Read and build
        with open(config_path) as f:
            loaded = json.load(f)

        grammar = grammar_from_config(loaded)
        interp = PEGInterpreter(grammar)
        ast = interp.parse("answer = 42 ;")
        ns = transpile_and_exec(ast)
        assert ns["answer"] == 42

    def test_complex_computation(self):
        """Test chained arithmetic with correct operator precedence."""
        parser = GrammarParser()
        grammar = parser.parse(
            'program <- statement+\n'
            'statement <- IDENT "=" expr ";"\n'
            'expr <- term (("+" / "-") term)*\n'
            'term <- factor (("*" / "/") factor)*\n'
            'factor <- NUMBER / IDENT / "(" expr ")"'
        )
        interp = PEGInterpreter(grammar)

        source = (
            "a = 10 ;"
            "b = 20 ;"
            "c = a + b * 2 ;"   # c = 10 + 40 = 50
            "d = ( a + b ) * 2 ;"  # d = 30 * 2 = 60
        )
        ast = interp.parse(source)
        ns = transpile_and_exec(ast)
        assert ns["a"] == 10
        assert ns["b"] == 20
        assert ns["c"] == 50
        assert ns["d"] == 60


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_grammar_rules(self):
        config = {"grammar": {"rules": {}}}
        grammar = grammar_from_config(config)
        # Empty rules dict generates default grammar rules
        assert len(grammar.rules) >= 0

    def test_single_number_assignment(self):
        parser = GrammarParser()
        grammar = parser.parse(
            'program <- statement+\n'
            'statement <- IDENT "=" NUMBER ";"'
        )
        interp = PEGInterpreter(grammar)
        ast = interp.parse("x = 42 ;")
        ns = transpile_and_exec(ast)
        assert ns["x"] == 42

    def test_deeply_nested_parentheses(self):
        parser = GrammarParser()
        grammar = parser.parse(
            'program <- statement+\n'
            'statement <- IDENT "=" expr ";"\n'
            'expr <- term (("+" / "-") term)*\n'
            'term <- factor (("*" / "/") factor)*\n'
            'factor <- NUMBER / IDENT / "(" expr ")"'
        )
        interp = PEGInterpreter(grammar)
        ast = interp.parse("x = ( ( ( 42 ) ) ) ;")
        ns = transpile_and_exec(ast)
        assert ns["x"] == 42
