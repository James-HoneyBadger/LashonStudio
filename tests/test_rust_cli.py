"""End-to-end checks for the `parsercraft-rs` binary.

Skipped when the Rust workspace has not been built
(``cargo build --workspace --release``).
"""

from __future__ import annotations

import json
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


@pytest.mark.parametrize("sample", ["hello.aur", "fibonacci.aur", "fizzbuzz.aur"])
def test_llvm_backend_matches_python_backend(sample, tmp_path):
    compiler = shutil.which("clang")
    if compiler is None:
        pytest.skip("no clang available")

    source = SAMPLES / sample
    rust_ir = tmp_path / "rust.ll"
    completed = run("codegen-llvm", str(GRAMMAR), str(source), "-o", str(rust_ir))
    assert completed.returncode == 0, completed.stderr

    from parsercraft.codegen.llvm_ir import LLVMIRGenerator
    from parsercraft.parser import GrammarParser, PEGInterpreter

    grammar = GrammarParser().parse(GRAMMAR.read_text(encoding="utf-8"))
    ast = PEGInterpreter(grammar).parse(source.read_text(encoding="utf-8"))
    python_ir = tmp_path / "python.ll"
    python_ir.write_text(
        LLVMIRGenerator().translate_source_ast(ast), encoding="utf-8"
    )

    def compile_and_run(path: Path) -> str:
        binary = path.with_suffix(".out")
        subprocess.run(
            [compiler, "-O1", "-o", str(binary), str(path)],
            check=True, capture_output=True,
        )
        return subprocess.run(
            [str(binary)], check=True, capture_output=True, text=True
        ).stdout

    assert compile_and_run(rust_ir) == compile_and_run(python_ir)


class LspClient:
    """Minimal LSP client speaking JSON-RPC to the Rust server over stdio."""

    def __init__(self, grammar: Path):
        self.process = subprocess.Popen(
            [str(BINARY), "lsp", "--grammar", str(grammar)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.sequence = 0

    def send(self, method: str, params=None, request_id=None):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if request_id is not None:
            message["id"] = request_id
        body = json.dumps(message).encode()
        self.process.stdin.write(
            f"Content-Length: {len(body)}\r\n\r\n".encode() + body
        )
        self.process.stdin.flush()

    def read(self):
        headers = {}
        while True:
            line = self.process.stdout.readline()
            assert line, "server closed the connection"
            if line in (b"\r\n", b"\n"):
                break
            key, _, value = line.decode().partition(":")
            headers[key.lower()] = value.strip()
        return json.loads(self.process.stdout.read(int(headers["content-length"])))

    def request(self, method: str, params=None):
        self.sequence += 1
        self.send(method, params, self.sequence)
        while True:
            message = self.read()
            if message.get("id") == self.sequence:
                return message

    def close(self):
        self.send("shutdown", request_id=999)
        self.send("exit")
        self.process.wait(timeout=5)


@pytest.fixture
def lsp():
    client = LspClient(GRAMMAR)
    try:
        yield client
    finally:
        client.close()


def test_lsp_initializes_with_editing_capabilities(lsp):
    result = lsp.request("initialize", {"processId": None, "rootUri": None})
    capabilities = result["result"]["capabilities"]
    assert capabilities["textDocumentSync"] == 1
    assert capabilities["hoverProvider"] is True
    assert capabilities["renameProvider"] is True
    assert capabilities["documentSymbolProvider"] is True


def test_lsp_publishes_parse_diagnostics(lsp):
    lsp.request("initialize", {"processId": None, "rootUri": None})
    lsp.send(
        "textDocument/didOpen",
        {
            "textDocument": {
                "uri": "file:///tmp/bad.aur",
                "languageId": "aurora",
                "version": 1,
                "text": "x = ;\n",
            }
        },
    )
    notification = lsp.read()
    assert notification["method"] == "textDocument/publishDiagnostics"
    diagnostics = notification["params"]["diagnostics"]
    assert diagnostics

    from parsercraft.parser import GrammarParser, PEGInterpreter

    grammar = GrammarParser().parse(GRAMMAR.read_text(encoding="utf-8"))
    try:
        PEGInterpreter(grammar).parse("x = ;\n")
        raise AssertionError("expected a parse error")
    except SyntaxError as error:
        message = str(error).splitlines()[0]
    expected_line = int(message.split("line ")[1].split(",")[0])
    expected_column = int(message.split("column ")[1].split(" ")[0])

    first = diagnostics[0]
    assert first["code"] == "parse-error"
    assert first["range"]["start"] == {
        "line": expected_line - 1,
        "character": expected_column - 1,
    }


def test_lsp_grammar_intelligence(lsp):
    lsp.request("initialize", {"processId": None, "rootUri": None})
    grammar_uri = "file:///tmp/grammar.peg"
    lsp.send(
        "textDocument/didOpen",
        {
            "textDocument": {
                "uri": grammar_uri,
                "languageId": "peg",
                "version": 1,
                "text": GRAMMAR.read_text(encoding="utf-8"),
            }
        },
    )
    lsp.read()  # publishDiagnostics

    symbols = lsp.request(
        "textDocument/documentSymbol", {"textDocument": {"uri": grammar_uri}}
    )["result"]
    names = [symbol["name"] for symbol in symbols]
    assert names[0] == "program"
    assert "while_stmt" in names

    hover = lsp.request(
        "textDocument/hover",
        {
            "textDocument": {"uri": grammar_uri},
            "position": {"line": 3, "character": 0},
        },
    )["result"]
    assert "program <- statement+" in hover["contents"]["value"]

    completion = lsp.request(
        "textDocument/completion",
        {
            "textDocument": {"uri": grammar_uri},
            "position": {"line": 3, "character": 0},
        },
    )["result"]
    labels = [item["label"] for item in completion["items"]]
    assert "program" in labels
    assert "IDENT" in labels


@pytest.mark.parametrize("sample", ["hello.aur", "fibonacci.aur", "fizzbuzz.aur"])
def test_rust_runner_matches_python_pipeline(sample):
    """The Rust evaluator executes programs with no Python involved."""
    source = SAMPLES / sample
    completed = run("run", str(GRAMMAR), str(source))
    assert completed.returncode == 0, completed.stderr

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

    assert completed.stdout == buffer.getvalue()


def test_dap_breakpoint_variables_and_continue(tmp_path):
    program = tmp_path / "loop.aur"
    program.write_text(
        "i = 0 ;\nx = 2 ;\nwhile i < 2 {\n  i = i + 1 ;\n  print i ;\n}\n",
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [str(BINARY), "dap", "--grammar", str(GRAMMAR), "--program", str(program)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    sequence = 0

    def send(command, arguments=None):
        nonlocal sequence
        sequence += 1
        message = {"seq": sequence, "type": "request", "command": command}
        if arguments is not None:
            message["arguments"] = arguments
        body = json.dumps(message).encode()
        process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
        process.stdin.flush()
        return sequence

    def read():
        headers = {}
        while True:
            line = process.stdout.readline()
            assert line, "adapter closed the connection"
            if line in (b"\r\n", b"\n"):
                break
            key, _, value = line.decode().partition(":")
            headers[key.lower()] = value.strip()
        return json.loads(process.stdout.read(int(headers["content-length"])))

    def request(command, arguments=None):
        seq = send(command, arguments)
        while True:
            message = read()
            if message.get("type") == "response" and message.get("request_seq") == seq:
                return message

    try:
        capabilities = request("initialize", {"adapterID": "parsercraft"})
        assert capabilities["success"] is True
        assert capabilities["body"]["supportsConfigurationDoneRequest"] is True

        verified = request(
            "setBreakpoints",
            {
                "source": {"path": str(program)},
                "breakpoints": [{"line": 4}],
            },
        )
        assert verified["body"]["breakpoints"][0]["verified"] is True

        request("configurationDone", {})
        stopped = read()
        assert stopped["event"] == "stopped"

        stack = request("stackTrace", {"threadId": 1})
        assert stack["body"]["stackFrames"][0]["line"] == 4

        request("scopes", {"frameId": 0})
        variables = request("variables", {"variablesReference": 1})
        values = {v["name"]: v["value"] for v in variables["body"]["variables"]}
        assert values["i"] == "0"

        request("continue", {"threadId": 1})
        stopped_again = read()
        assert stopped_again["event"] == "stopped"

        request("disconnect", {})
    finally:
        process.wait(timeout=5)


def test_demo_walks_the_pipeline():
    completed = run("demo")
    assert completed.returncode == 0, completed.stderr
    for stage in ("grammar", "ast", "python", "c", "wasm", "llvm", "run"):
        assert stage in completed.stdout


def test_init_scaffolds_a_runnable_project(tmp_path):
    completed = run("init", "Pocket Calc", "-t", "calculator", "-d", str(tmp_path))
    assert completed.returncode == 0, completed.stderr

    root = tmp_path / "pocket-calc"
    assert (root / "grammar.peg").is_file()
    assert (root / "samples" / "hello.aur").is_file()
    assert (root / "README.md").is_file()

    executed = run(
        "run", str(root / "grammar.peg"), str(root / "samples" / "hello.aur")
    )
    assert executed.returncode == 0, executed.stderr
    assert executed.stdout.split() == ["84", "38"]


def test_init_refuses_to_overwrite_without_force(tmp_path):
    assert run("init", "Tiny", "-d", str(tmp_path)).returncode == 0
    second = run("init", "Tiny", "-d", str(tmp_path))
    assert second.returncode == 1
    assert "already exists" in second.stderr

    forced = run("init", "Tiny", "-d", str(tmp_path), "--force")
    assert forced.returncode == 0


def test_lint_reports_problems_and_exit_codes(tmp_path):
    healthy = run("lint", str(GRAMMAR))
    assert healthy.returncode == 0
    assert "no problems" in healthy.stdout

    broken = tmp_path / "broken.peg"
    broken.write_text("program <- missing\n", encoding="utf-8")
    failed = run("lint", str(broken))
    assert failed.returncode == 1
    assert "undefined rule 'missing'" in failed.stdout

    as_json = run("lint", str(broken), "--json")
    assert as_json.returncode == 1
    payload = json.loads(as_json.stdout)
    assert payload["ok"] is False
    assert payload["problems"]


def test_lint_checks_a_source_file(tmp_path):
    program = tmp_path / "bad.aur"
    program.write_text("x = ;\n", encoding="utf-8")
    completed = run("lint", str(GRAMMAR), "--source", str(program))
    assert completed.returncode == 1
    assert "line 1" in completed.stdout


BASIC = ROOT / "projects" / "basic"


@pytest.mark.parametrize(
    ("sample", "expected"),
    [
        ("hello.bas", "HELLO, BASIC!\nTHE ANSWER IS 42\n"),
        ("countdown.bas", "3\n2\n1\nLIFTOFF!\n"),
        (
            "fizzbuzz.bas",
            "1\n2\nFIZZ\n4\nBUZZ\nFIZZ\n7\n8\nFIZZ\nBUZZ\n11\nFIZZ\n13\n14\nFIZZBUZZ\n",
        ),
    ],
)
def test_basic_interpreter_runs_its_own_language(sample, expected):
    """A language defined only by a grammar is parsed and executed."""
    completed = run(
        "run", str(BASIC / "grammar.peg"), str(BASIC / "samples" / sample)
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == expected


def test_basic_project_lints_clean():
    completed = run("lint", str(BASIC / "grammar.peg"))
    assert completed.returncode == 0, completed.stderr
    assert "no problems" in completed.stdout


def test_basic_reports_undefined_goto_targets(tmp_path):
    program = tmp_path / "broken.bas"
    program.write_text("10 GOTO 999\n", encoding="utf-8")
    completed = run("run", str(BASIC / "grammar.peg"), str(program))
    assert completed.returncode == 1
    assert "undefined line 999" in completed.stderr


@pytest.mark.parametrize("sample", ["hello.bas", "countdown.bas", "fizzbuzz.bas"])
def test_basic_compiles_to_c_with_matching_output(sample, tmp_path):
    """A GOTO-based dialect compiles to C and behaves like the interpreter."""
    compiler = shutil.which("cc") or shutil.which("gcc")
    if compiler is None:
        pytest.skip("no C compiler available")

    source = BASIC / "samples" / sample
    output = tmp_path / source.with_suffix(".c").name
    compiled = run(
        "codegen-c", str(BASIC / "grammar.peg"), str(source),
        "-o", str(output), "--compile",
    )
    assert compiled.returncode == 0, compiled.stderr

    produced = subprocess.run(
        [str(output.with_suffix(".out"))], capture_output=True, text=True, check=True
    ).stdout
    interpreted = run("run", str(BASIC / "grammar.peg"), str(source))
    assert produced == interpreted.stdout
