"""Tests for code generators (C, WASM, LLVM IR)."""

from pathlib import Path

import pytest

from lashon.codegen.codegen_c import CCodeGenerator
from lashon.codegen.codegen_wasm import WasmGenerator
from lashon.codegen.llvm_ir import LLVMIRGenerator
from lashon.parser.grammar import GrammarParser, PEGInterpreter


@pytest.fixture
def interpreter():
    parser = GrammarParser()
    grammar = parser.parse(
        'program <- statement+\n'
        'statement <- assignment\n'
        'assignment <- IDENT "=" expr ";"\n'
        'expr <- term (("+" / "-") term)*\n'
        'term <- factor (("*" / "/") factor)*\n'
        'factor <- NUMBER / IDENT / "(" expr ")"'
    )
    return PEGInterpreter(grammar)


class TestCCodeGenerator:
    """Test AST to C code generation."""

    def test_simple_assignment(self, interpreter):
        ast = interpreter.parse("x = 10 ;")
        gen = CCodeGenerator()
        c_code = gen.translate_source_ast(ast)
        assert "int x = 10" in c_code
        assert "int main(" in c_code

    def test_arithmetic(self, interpreter):
        ast = interpreter.parse("y = 3 + 4 ;")
        gen = CCodeGenerator()
        c_code = gen.translate_source_ast(ast)
        assert "y" in c_code
        assert "3" in c_code

    def test_multiple_variables(self, interpreter):
        ast = interpreter.parse("a = 1 ; b = 2 ; c = a + b ;")
        gen = CCodeGenerator()
        c_code = gen.translate_source_ast(ast)
        assert "int a" in c_code
        assert "int b" in c_code
        assert "int c" in c_code

    def test_produces_valid_c_structure(self, interpreter):
        ast = interpreter.parse("x = 42 ;")
        gen = CCodeGenerator()
        c_code = gen.translate_source_ast(ast)
        assert "#include" in c_code or "int main" in c_code
        assert "return 0;" in c_code


class TestWasmGenerator:
    """Test AST to WebAssembly (WAT) code generation."""

    def test_simple_assignment(self, interpreter):
        ast = interpreter.parse("x = 10 ;")
        gen = WasmGenerator()
        result = gen.translate_source_ast(ast)
        wat = result.to_wat()
        assert "(module" in wat
        assert "(func" in wat

    def test_arithmetic(self, interpreter):
        ast = interpreter.parse("y = 3 + 4 ;")
        gen = WasmGenerator()
        result = gen.translate_source_ast(ast)
        wat = result.to_wat()
        assert "i32.add" in wat or "i32.const" in wat

    def test_multiple_statements(self, interpreter):
        ast = interpreter.parse("a = 5 ; b = a ;")
        gen = WasmGenerator()
        result = gen.translate_source_ast(ast)
        wat = result.to_wat()
        assert "(local" in wat


class TestLLVMIRGenerator:
    """Test AST to LLVM IR code generation."""

    def test_simple_assignment(self, interpreter):
        ast = interpreter.parse("x = 10 ;")
        gen = LLVMIRGenerator()
        ir = gen.translate_source_ast(ast)
        assert "define" in ir
        assert "alloca" in ir
        assert "store" in ir

    def test_arithmetic(self, interpreter):
        ast = interpreter.parse("y = 3 + 4 ;")
        gen = LLVMIRGenerator()
        ir = gen.translate_source_ast(ast)
        assert "add" in ir

    def test_multiplication(self, interpreter):
        ast = interpreter.parse("z = 5 * 6 ;")
        gen = LLVMIRGenerator()
        ir = gen.translate_source_ast(ast)
        assert "mul" in ir

    def test_complex_expression(self, interpreter):
        ast = interpreter.parse("r = 2 + 3 * 4 ;")
        gen = LLVMIRGenerator()
        ir = gen.translate_source_ast(ast)
        # Should have both mul and add
        assert "mul" in ir
        assert "add" in ir

    def test_variable_reference(self, interpreter):
        ast = interpreter.parse("a = 10 ; b = a ;")
        gen = LLVMIRGenerator()
        ir = gen.translate_source_ast(ast)
        assert "load" in ir

    def test_produces_ssa_form(self, interpreter):
        ast = interpreter.parse("x = 1 ; y = 2 ;")
        gen = LLVMIRGenerator()
        ir = gen.translate_source_ast(ast)
        # SSA form uses numbered registers
        assert "%1" in ir or "%0" in ir or "%" in ir


class TestBackendControlFlow:
    """Regression tests for functions, branches, loops, and calls."""

    GRAMMAR = (
        'program <- statement+\n'
        'statement <- function_def / if_stmt / while_stmt / return_stmt / '
        'print_stmt / assignment / expr_stmt\n'
        'function_def <- "fn" IDENT "(" param_list? ")" block\n'
        'block <- "{" statement* "}"\n'
        'param_list <- IDENT ("," IDENT)*\n'
        'if_stmt <- "if" comparison block ("else" block)?\n'
        'while_stmt <- "while" comparison block\n'
        'return_stmt <- "return" expr ";"\n'
        'print_stmt <- "print" expr ";"\n'
        'assignment <- IDENT "=" expr ";"\n'
        'expr_stmt <- call ";"\n'
        'comparison <- expr (("==" / "!=" / "<=" / ">=" / "<" / ">") expr)\n'
        'expr <- term (("+" / "-") term)*\n'
        'term <- factor (("*" / "/") factor)*\n'
        'factor <- call / NUMBER / STRING / IDENT / "(" expr ")"\n'
        'call <- IDENT "(" arg_list? ")"\n'
        'arg_list <- expr ("," expr)*'
    )

    PROGRAM = (
        'fn fib(n) {\n'
        '  if n <= 1 { return n ; } else { return fib(n - 1) + fib(n - 2) ; }\n'
        '}\n'
        'print "fib" ;\n'
        'print fib(6) ;\n'
        'fn count(limit) {\n'
        '  i = 1 ;\n'
        '  while i <= limit { print i ; i = i + 1 ; }\n'
        '}\n'
        'count(3) ;\n'
    )

    @pytest.fixture
    def ast(self):
        grammar = GrammarParser().parse(self.GRAMMAR)
        return PEGInterpreter(grammar).parse(self.PROGRAM)

    def test_c_emits_string_literals_with_string_format(self, ast):
        c_code = CCodeGenerator().translate_source_ast(ast)
        assert 'printf("%s\\n", "fib");' in c_code
        assert 'printf("%d\\n", fib(6));' in c_code

    def test_c_emits_loop_bodies_and_no_redeclaration(self, ast):
        c_code = CCodeGenerator().translate_source_ast(ast)
        assert "while (i <= limit)" in c_code
        assert "int i = 1;" in c_code
        assert "i = i + 1;" in c_code
        assert "int i = i + 1;" not in c_code

    def test_c_emits_else_branch(self, ast):
        c_code = CCodeGenerator().translate_source_ast(ast)
        assert "} else {" in c_code

    def test_llvm_emits_calls_and_no_undefined_warnings(self, ast):
        ir = LLVMIRGenerator().translate_source_ast(ast)
        assert "call i32 @fib(" in ir
        assert "undefined variable" not in ir

    def test_llvm_emits_printf_calls(self, ast):
        ir = LLVMIRGenerator().translate_source_ast(ast)
        assert "call i32 (ptr, ...) @printf" in ir
        assert '@.fmt.0 = private unnamed_addr constant' in ir

    def test_llvm_uses_i1_for_comparisons(self, ast):
        ir = LLVMIRGenerator().translate_source_ast(ast)
        assert "icmp sle i32" in ir
        assert "icmp ne i32 %" not in ir


class TestWasmFunctionCodegen:
    """WASM function, control-flow, and string-output support."""

    PROJECT = Path(__file__).resolve().parent.parent / "projects" / "aurora"

    @staticmethod
    def _run_wat(wat: str) -> list[str]:
        wasmtime = pytest.importorskip("wasmtime")

        engine = wasmtime.Engine()
        store = wasmtime.Store(engine)
        module = wasmtime.Module(engine, wasmtime.wat2wasm(wat))
        output: list[str] = []

        def log_i32(value):
            output.append(str(value))

        def log_str(caller, ptr, length):
            memory = caller.get("memory")
            output.append(
                bytes(memory.read(caller, ptr, ptr + length)).decode("utf-8")
            )

        def sqrt(value):
            return value ** 0.5

        i32 = wasmtime.ValType.i32()
        f64 = wasmtime.ValType.f64()
        imports = [
            wasmtime.Func(store, wasmtime.FuncType([i32], []), log_i32),
            wasmtime.Func(
                store,
                wasmtime.FuncType([i32, i32], []),
                log_str,
                access_caller=True,
            ),
            wasmtime.Func(
                store, wasmtime.FuncType([f64], [f64]), sqrt
            ),
        ]
        instance = wasmtime.Instance(store, module, imports)
        instance.exports(store)["main"](store)
        return output

    def _compile(self, sample: str):
        grammar = GrammarParser().parse(
            (self.PROJECT / "grammar.peg").read_text(encoding="utf-8")
        )
        ast = PEGInterpreter(grammar).parse(
            (self.PROJECT / "samples" / sample).read_text(encoding="utf-8")
        )
        return WasmGenerator().translate_source_ast(ast).to_wat()

    def test_emits_functions_locals_and_calls(self):
        wat = self._compile("fibonacci.aur")
        assert "(func $fib (param $n i32) (result i32)" in wat
        assert "call $fib" in wat
        assert "local.get $" in wat
        assert "(data" in wat

    def test_imports_precede_memory_and_export_memory(self):
        wat = self._compile("hello.aur")
        assert wat.index("(import") < wat.index("(memory")
        assert '(export "memory" (memory 0))' in wat

    @pytest.mark.parametrize(
        ("sample", "expected"),
        [
            ("fibonacci.aur", ["fib(10) =", "55", "10! =", "3628800"]),
            ("hello.aur", ["Hello, Aurora!", "Designed in Lashon Studio."]),
        ],
    )
    def test_generated_wasm_executes(self, sample, expected):
        assert self._run_wat(self._compile(sample)) == expected

    def test_fizzbuzz_control_flow_executes(self):
        output = self._run_wat(self._compile("fizzbuzz.aur"))
        assert output[:3] == ["1", "2", "Fizz"]
        assert output[-1] == "FizzBuzz"
        assert len(output) == 15

    def test_unknown_calls_are_rejected(self):
        grammar = GrammarParser().parse(
            'program <- statement+\n'
            'statement <- IDENT "=" call ";"\n'
            'call <- IDENT "(" arg_list? ")"\n'
            'arg_list <- NUMBER ("," NUMBER)*'
        )
        ast = PEGInterpreter(grammar).parse("x = missing(1) ;")

        with pytest.raises(ValueError, match="cannot resolve function"):
            WasmGenerator().translate_source_ast(ast)


class TestCSourceMaps:
    """``CCodeGenerator(source_map=True)`` emits ``#line`` directives."""

    GRAMMAR = (
        "program <- statement+\n"
        "statement <- print_stmt / assignment\n"
        "print_stmt <- 'print' expr ';'\n"
        "assignment <- IDENT '=' expr ';'\n"
        "expr <- term (('+' / '-') term)*\n"
        "term <- NUMBER / IDENT\n"
    )

    def _code(self, source: str) -> str:
        grammar = GrammarParser().parse(self.GRAMMAR)
        ast = PEGInterpreter(grammar).parse(source)
        return CCodeGenerator(
            source_map=True, source_file="demo.aur"
        ).translate_source_ast(ast)

    def test_line_directives_track_source(self):
        code = self._code("x = 1 ;\nprint x ;\nprint x + 1 ;\n")
        assert '#line 1 "demo.aur"' in code
        assert '#line 2 "demo.aur"' in code
        assert '#line 3 "demo.aur"' in code

    def test_no_directives_by_default(self):
        grammar = GrammarParser().parse(self.GRAMMAR)
        ast = PEGInterpreter(grammar).parse("x = 1 ;\n")
        assert "#line" not in CCodeGenerator().translate_source_ast(ast)

    def test_code_still_compiles_and_runs(self, tmp_path):
        import shutil
        import subprocess
        import sys

        compiler = shutil.which("gcc") or shutil.which("clang") or shutil.which("cc")
        if compiler is None or sys.platform == "win32":
            pytest.skip("no C compiler available")

        source = tmp_path / "demo.c"
        source.write_text(
            self._code("x = 1 ;\nprint x ;\nprint x + 1 ;\n"),
            encoding="utf-8",
        )
        binary = tmp_path / "demo"
        subprocess.run(
            [compiler, "-o", str(binary), str(source)],
            check=True,
            capture_output=True,
        )
        completed = subprocess.run(
            [str(binary)], check=True, capture_output=True, text=True
        )
        assert completed.stdout.split() == ["1", "2"]
