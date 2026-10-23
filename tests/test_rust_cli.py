"""End-to-end checks for the `parsercraft-rs` binary.

Skipped when the Rust workspace has not been built
(``cargo build --workspace --release``).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "target" / "release" / "parsercraft-rs"
GRAMMAR = ROOT / "projects" / "aurora" / "grammar.peg"
CONFIG = ROOT / "projects" / "aurora" / "language.yaml"
SAMPLES = ROOT / "projects" / "aurora" / "samples"

pytestmark = pytest.mark.skipif(
    not BINARY.is_file(), reason="cargo build --workspace --release not run"
)


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(BINARY), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


def test_version():
    completed = run("version")
    assert completed.returncode == 0
    assert completed.stdout.startswith("parsercraft-rs ")


def test_rules_and_validate():
    rules = run("rules", str(GRAMMAR))
    assert rules.returncode == 0
    names = rules.stdout.split()
    assert names[0] == "program"
    assert "while_stmt" in names

    validated = run("validate", str(GRAMMAR))
    assert validated.returncode == 0
    assert "start rule 'program'" in validated.stdout


def test_validate_reports_undefined_rules(tmp_path):
    grammar = tmp_path / "broken.peg"
    grammar.write_text("program <- missing\n", encoding="utf-8")
    completed = run("validate", str(grammar))
    assert "undefined rule 'missing'" in completed.stdout


def test_parse_reports_errors_with_position(tmp_path):
    program = tmp_path / "bad.aur"
    program.write_text("x = ;\n", encoding="utf-8")
    completed = run("parse", str(GRAMMAR), str(program))
    assert completed.returncode == 1
    assert "line 1, column 5" in completed.stderr


@pytest.mark.parametrize("sample", ["hello.aur", "fibonacci.aur", "fizzbuzz.aur"])
def test_c_backend_matches_python_output(sample, tmp_path):
    compiler = shutil.which("cc") or shutil.which("gcc")
    if compiler is None:
        pytest.skip("no C compiler available")

    source = SAMPLES / sample
    output = tmp_path / source.with_suffix(".c").name
    completed = run(
        "codegen-c", str(GRAMMAR), str(source), "-o", str(output), "--compile",
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr
    binary = output.with_suffix(".out")
    assert binary.is_file()

    native = subprocess.run(
        [str(binary)], capture_output=True, text=True, check=True
    ).stdout

    import io
    from contextlib import redirect_stdout

    from parsercraft.codegen.python_transpiler import PythonTranspiler
    from parsercraft.parser import GrammarParser, PEGInterpreter

    grammar = GrammarParser().parse(GRAMMAR.read_text(encoding="utf-8"))
    ast = PEGInterpreter(grammar).parse(source.read_text(encoding="utf-8"))
    code = PythonTranspiler().transpile(ast)
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exec(compile(code, str(source), "exec"), {"__name__": "__main__"})  # noqa: S102

    assert native == buffer.getvalue()


@pytest.mark.parametrize("sample", ["hello.aur", "fibonacci.aur", "fizzbuzz.aur"])
def test_python_backend_matches_python_pipeline(sample, tmp_path):
    source = SAMPLES / sample
    output = tmp_path / source.with_suffix(".py").name
    completed = run(
        "codegen-py", str(GRAMMAR), str(source), "-o", str(output)
    )
    assert completed.returncode == 0, completed.stderr
    generated = output.read_text(encoding="utf-8")
    assert generated.strip(), "generated Python should not be empty"

    import io
    import sys
    from contextlib import redirect_stdout

    def execute(code: str) -> str:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exec(compile(code, "generated", "exec"), {"__name__": "__main__"})  # noqa: S102
        return buffer.getvalue()

    produced = subprocess.run(
        [sys.executable, str(output)], capture_output=True, text=True, check=True
    ).stdout

    from parsercraft.codegen.python_transpiler import PythonTranspiler
    from parsercraft.parser import GrammarParser, PEGInterpreter

    grammar = GrammarParser().parse(GRAMMAR.read_text(encoding="utf-8"))
    ast = PEGInterpreter(grammar).parse(source.read_text(encoding="utf-8"))
    reference = execute(PythonTranspiler().transpile(ast))

    assert produced == reference


@pytest.mark.parametrize("sample", ["hello.aur", "fibonacci.aur", "fizzbuzz.aur"])
def test_wasm_backend_runs_like_the_python_backend(sample, tmp_path):
    wasmtime = pytest.importorskip("wasmtime")

    source = SAMPLES / sample
    output = tmp_path / source.with_suffix(".wat").name
    completed = run("codegen-wasm", str(GRAMMAR), str(source), "-o", str(output))
    assert completed.returncode == 0, completed.stderr

    def execute(wat: str) -> list[str]:
        engine = wasmtime.Engine()
        store = wasmtime.Store(engine)
        module = wasmtime.Module(engine, wasmtime.wat2wasm(wat))
        printed: list[str] = []

        def log_i32(value):
            printed.append(str(value))

        def log_str(caller, ptr, length):
            memory = caller.get("memory")
            printed.append(
                bytes(memory.read(caller, ptr, ptr + length)).decode("utf-8")
            )

        i32 = wasmtime.ValType.i32()
        f64 = wasmtime.ValType.f64()
        instance = wasmtime.Instance(
            store,
            module,
            [
                wasmtime.Func(store, wasmtime.FuncType([i32], []), log_i32),
                wasmtime.Func(
                    store, wasmtime.FuncType([i32, i32], []), log_str,
                    access_caller=True,
                ),
                wasmtime.Func(
                    store, wasmtime.FuncType([f64], [f64]), lambda v: v ** 0.5
                ),
            ],
        )
        instance.exports(store)["main"](store)
        return printed

    from parsercraft.codegen.codegen_wasm import WasmGenerator
    from parsercraft.parser import GrammarParser, PEGInterpreter

    grammar = GrammarParser().parse(GRAMMAR.read_text(encoding="utf-8"))
    ast = PEGInterpreter(grammar).parse(source.read_text(encoding="utf-8"))
    reference = execute(WasmGenerator().translate_source_ast(ast).to_wat())

    assert execute(output.read_text(encoding="utf-8")) == reference
