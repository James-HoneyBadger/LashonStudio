"""
Lashon REPL — Interactive Read-Eval-Print Loop

Provides an interactive shell for testing custom languages in real time.
Uses the PEG grammar engine to parse and the Python transpiler to execute.

Usage:
    python -m lashon.runtime.repl --config my_lang.yaml
    python -m lashon.runtime.repl   # starts with default grammar
"""

from __future__ import annotations

import io
import sys
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Optional

from lashon.codegen.python_transpiler import PythonTranspiler, TranspileOptions
from lashon.parser.grammar import (
    Grammar,
    GrammarBuilder,
    PEGInterpreter,
    SourceAST,
    grammar_from_config,
)
from lashon.runtime.graphics import Graphics, capture


class REPL:
    """Interactive REPL for custom languages built with Lashon.

    Features:
        - Persistent namespace across evaluations
        - Multi-line input (braces/indentation continuation)
        - Special commands (:ast, :py, :grammar, :reset, :help, :quit)
        - History tracking
        - Error display with source context
    """

    BANNER = (
        "Lashon REPL v5.0.0\n"
        "Type :help for commands, :quit to exit.\n"
    )

    COMMANDS = {
        ":help": "Show this help message",
        ":quit": "Exit the REPL",
        ":reset": "Clear namespace and history",
        ":ast": "Show AST of last expression",
        ":py": "Show Python transpilation of last expression",
        ":grammar": "Show current grammar rules",
        ":vars": "Show all defined variables",
        ":load <file>": "Load and execute a source file",
        ":save <file>": "Save the last input to a file",
        ":doc <rule>": "Show a grammar rule",
        ":backends": "Generate C, WASM, and LLVM IR for the last AST",
        ":time": "Toggle timing information",
        ":canvas": "Show the drawing; :canvas save <file.svg>, :canvas show, "
                   ":canvas ascii, :canvas clear",
    }

    def __init__(
        self,
        grammar: Optional[Grammar] = None,
        transpile_options: Optional[TranspileOptions] = None,
        prompt: str = ">>> ",
        continue_prompt: str = "... ",
    ):
        self.grammar = grammar or self._default_grammar()
        self.interpreter = PEGInterpreter(self.grammar)
        self.transpiler = PythonTranspiler(transpile_options)
        self.prompt = prompt
        self.continue_prompt = continue_prompt

        self.namespace: dict[str, Any] = {}
        self.history: list[str] = []
        self._last_source: str = ""
        self._last_ast: Optional[SourceAST] = None
        self._last_python: str = ""
        self.timing = False
        self.history_file = Path.home() / ".lashon_history"
        self.graphics = Graphics()
        #: A GUI front end may install a host to show the drawing.
        self.canvas_host: Any = None

    @staticmethod
    def _default_grammar() -> Grammar:
        """Create a minimal default grammar for arithmetic + assignment."""
        b = GrammarBuilder()
        b.rule("program").set_pattern(
            b.plus(b.ref("statement"))
        )
        b.rule("statement").set_pattern(
            b.ref("assignment")
        )
        b.rule("assignment").set_pattern(
            b.seq(b.ref("IDENT"), b.lit("="), b.ref("expr"), b.lit(";"))
        )
        b.rule("expr").set_pattern(
            b.seq(
                b.ref("term"),
                b.star(b.seq(
                    b.choice(b.lit("+"), b.lit("-")),
                    b.ref("term"),
                )),
            )
        )
        b.rule("term").set_pattern(
            b.seq(
                b.ref("factor"),
                b.star(b.seq(
                    b.choice(b.lit("*"), b.lit("/")),
                    b.ref("factor"),
                )),
            )
        )
        b.rule("factor").set_pattern(
            b.choice(
                b.ref("NUMBER"),
                b.ref("IDENT"),
                b.seq(b.lit("("), b.ref("expr"), b.lit(")")),
            )
        )
        return b.build()

    @classmethod
    def from_config_file(cls, config_path: str, **kwargs) -> "REPL":
        """Create a REPL from a YAML/JSON config file."""
        import json

        import yaml

        with open(config_path) as f:
            if config_path.endswith((".yaml", ".yml")):
                config = yaml.safe_load(f)
            else:
                config = json.load(f)

        grammar = grammar_from_config(config)

        # Build transpile options from config keyword mappings
        keyword_map = {}
        if "keywords" in config:
            kw = config["keywords"]
            if isinstance(kw, dict):
                keyword_map = {v: k for k, v in kw.items()}

        options = TranspileOptions(keyword_map=keyword_map)
        return cls(grammar=grammar, transpile_options=options, **kwargs)

    def run(self) -> None:
        """Start the interactive REPL loop."""
        print(self.BANNER)
        self._configure_readline()

        while True:
            try:
                source = self._read_input()
            except (EOFError, KeyboardInterrupt):
                print("\nBye!")
                self._save_history()
                break

            source = source.strip()
            if not source:
                continue

            # Handle special commands
            if source.startswith(":"):
                if source == ":quit":
                    self._save_history()
                    break
                self._handle_command(source)
                continue

            self.history.append(source)
            self._last_source = source
            self._eval(source)

    def eval_line(self, source: str) -> str:
        """Evaluate a single line and return output as string.

        Useful for testing or embedding the REPL programmatically.
        """
        source = source.strip()
        if not source:
            return ""

        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            if source.startswith(":"):
                self._handle_command(source)
            else:
                self._last_source = source
                self._eval(source)

        result = stdout.getvalue()
        errors = stderr.getvalue()
        return result + errors if errors else result

    def eval_lines(self, sources: list[str]) -> dict[str, Any]:
        """Evaluate multiple lines and return the namespace."""
        for src in sources:
            self.eval_line(src)
        return {k: v for k, v in self.namespace.items()
                if not k.startswith("_") and k != "__builtins__"}

    def _read_input(self) -> str:
        """Read input, supporting multi-line with continuation."""
        line = input(self.prompt)
        lines = [line]

        # Multi-line: if line ends with { or : or \, continue reading
        while line.rstrip().endswith(("\\", "{", ":")):
            try:
                line = input(self.continue_prompt)
                lines.append(line)
            except EOFError:
                break

        return "\n".join(lines)

    def _configure_readline(self) -> None:
        """Enable history and tab completion when readline is available."""
        try:
            import readline
        except ImportError:  # pragma: no cover - platform dependent
            return

        try:
            if self.history_file.exists():
                readline.read_history_file(str(self.history_file))
        except OSError:
            pass

        candidates = set(self.COMMANDS)
        candidates.update(self.grammar.rules)
        candidates.update({
            "print", "range", "len", "str", "int", "float",
        })

        def completer(text: str, state: int) -> Optional[str]:
            options = sorted(
                word for word in candidates if word.startswith(text)
            )
            return options[state] if state < len(options) else None

        readline.set_completer(completer)
        readline.set_completer_delims(" \t\n()[]{};,=+")
        readline.parse_and_bind("tab: complete")

    def _save_history(self) -> None:
        try:
            import readline
        except ImportError:  # pragma: no cover - platform dependent
            return
        try:
            readline.write_history_file(str(self.history_file))
        except OSError:
            pass

    def _parse(self, source: str) -> Optional[SourceAST]:
        """Parse one entry, adding the statement terminator only if needed.

        Block statements end with their own keyword (``END``, ``}``), so
        appending ``;`` unconditionally would turn a valid entry into an
        error. Try what the user typed first, then the terminated form.
        """
        text = source.strip()
        candidates = [text]
        if not text.endswith(";"):
            candidates.append(text + " ;")
        # Line-oriented grammars (`program <- line+`) need a number in front;
        # typing `LET X = 1` in a BASIC session should still work.
        candidates.append(f"10 {text}")
        candidates.append(f"10 {text} ;")
        error: Optional[Exception] = None
        for candidate in candidates:
            try:
                return self.interpreter.parse(candidate)
            except Exception as problem:  # pylint: disable=broad-exception-caught
                error = problem
        print(f"Parse error: {error}", file=sys.stderr)
        return None

    def _eval(self, source: str) -> None:
        """Parse, transpile, and execute source code."""
        started = time.perf_counter()
        ast = self._parse(source)
        if ast is None:
            return
        self._last_ast = ast

        try:
            python_code = self.transpiler.transpile(ast)
            self._last_python = python_code
        except Exception as e:
            print(f"Transpile error: {e}", file=sys.stderr)
            return

        try:
            with capture(self.graphics):
                exec(python_code, self.namespace)  # noqa: S102
        except Exception as e:
            print(f"Runtime error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        finally:
            if self.timing:
                elapsed = (time.perf_counter() - started) * 1000
                print(f"[time] {elapsed:.2f} ms", file=sys.stderr)
            self._refresh_canvas()

    def _refresh_canvas(self) -> None:
        """Repaint the drawing window, when a front end provides one."""
        if self.canvas_host is None:
            return
        try:
            self.canvas_host.refresh(self.graphics)
        except Exception:  # pylint: disable=broad-exception-caught
            self.canvas_host = None

    def _handle_command(self, cmd: str) -> bool:
        """Handle a REPL special command. Returns True if handled."""
        parts = cmd.split(maxsplit=1)
        command = parts[0]

        if command == ":help":
            print("REPL Commands:")
            for c, desc in self.COMMANDS.items():
                print(f"  {c:<20} {desc}")
            return True

        if command == ":quit":
            print("Bye!")
            return False  # Signal to break

        if command == ":reset":
            self.namespace.clear()
            self.history.clear()
            self._last_ast = None
            self._last_python = ""
            self._last_source = ""
            print("Namespace and history cleared.")
            return True

        if command == ":ast":
            if self._last_ast:
                print(self._last_ast.pretty())
            else:
                print("No AST available. Enter an expression first.")
            return True

        if command == ":py":
            if self._last_python:
                print(self._last_python)
            else:
                print("No Python code available. Enter an expression first.")
            return True

        if command == ":grammar":
            for name, rule in self.grammar.rules.items():
                print(f"  {name} <- {rule.pattern}")
            return True

        if command == ":vars":
            user_vars = {k: v for k, v in self.namespace.items()
                         if not k.startswith("_") and k != "__builtins__"}
            if user_vars:
                for k, v in user_vars.items():
                    print(f"  {k} = {v!r}")
            else:
                print("No variables defined.")
            return True

        if command == ":load" and len(parts) > 1:
            filepath = parts[1].strip()
            try:
                with open(filepath) as f:
                    source = f.read()
                self._eval(source)
                print(f"Loaded and executed: {filepath}")
            except FileNotFoundError:
                print(f"File not found: {filepath}")
            except Exception as e:
                print(f"Error loading {filepath}: {e}")
            return True

        if command == ":time":
            self.timing = not self.timing
            print(f"Timing {'on' if self.timing else 'off'}")
            return True

        if command == ":save" and len(parts) > 1:
            if not self._last_source:
                print("Nothing to save yet.")
                return True
            Path(parts[1].strip()).write_text(
                self._last_source + "\n", encoding="utf-8"
            )
            print(f"Saved: {parts[1].strip()}")
            return True

        if command == ":doc" and len(parts) > 1:
            name = parts[1].strip()
            rule = self.grammar.rules.get(name)
            if rule is None:
                print(f"No rule named '{name}'")
                return True
            print(f"{name} <- {rule.pattern}")
            if rule.description:
                print(f"  {rule.description}")
            return True

        if command == ":backends":
            if self._last_ast is None:
                print("No AST available. Enter an expression first.")
                return True
            from lashon.codegen import (
                CCodeGenerator,
                LLVMIRGenerator,
                WasmGenerator,
            )

            try:
                c_code = CCodeGenerator().translate_source_ast(self._last_ast)
                wat = (
                    WasmGenerator()
                    .translate_source_ast(self._last_ast)
                    .to_wat()
                )
                ir = LLVMIRGenerator().translate_source_ast(self._last_ast)
            except Exception as error:  # pylint: disable=broad-exception-caught
                print(f"Generation failed: {error}")
                return True
            print(f"C:    {len(c_code.splitlines())} lines")
            print(f"WASM: {len(wat.splitlines())} lines")
            print(f"LLVM: {len(ir.splitlines())} lines")
            return True

        if command == ":canvas":
            return self._handle_canvas(parts[1].strip() if len(parts) > 1 else "")

        print(f"Unknown command: {cmd}. Type :help for available commands.")
        return True

    def _handle_canvas(self, argument: str) -> bool:
        """Inspect, save, or display the drawing surface."""
        if argument.startswith("clear"):
            self.graphics = Graphics()
            print("Canvas cleared.")
            return True
        if argument.startswith("save"):
            parts = argument.split(maxsplit=1)
            target = Path(parts[1]) if len(parts) > 1 else Path("canvas.svg")
            try:
                target.write_text(self.graphics.to_svg(), encoding="utf-8")
            except OSError as error:
                print(f"Could not save canvas: {error}", file=sys.stderr)
            else:
                print(f"Saved {self.graphics.strokes()} strokes to {target}")
            return True
        if argument.startswith("ascii"):
            print(self.graphics.to_ascii())
            return True
        if argument.startswith("show"):
            self._show_canvas()
            return True
        print(f"{self.graphics.summary()}")
        print("  :canvas ascii | save <file.svg> | show | clear")
        return True

    def show_canvas(self) -> None:
        """Ask the front end to display the drawing."""
        if self.canvas_host is None:
            print(
                "No drawing window here — run lashon-repl (or press "
                ":canvas ascii for a preview).",
                file=sys.stderr,
            )
            print(self.graphics.to_ascii())
            return
        try:
            self.canvas_host.show(self.graphics)
        except Exception as error:  # pylint: disable=broad-exception-caught
            print(f"Could not open a canvas window: {error}", file=sys.stderr)
            print(self.graphics.to_ascii())

    def _show_canvas(self) -> bool:
        self.show_canvas()
        return True


def run_repl(argv: Optional[list[str]] = None,
             canvas_host: Any = None) -> int:
    """Parse arguments and run the read-eval-print loop."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Lashon REPL — Interactive Language Shell",
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to language config file (YAML/JSON)",
    )
    parser.add_argument(
        "--prompt", "-p",
        default=">>> ",
        help="REPL prompt string",
    )
    parser.add_argument(
        "--canvas", action="store_true",
        help="Open a drawing window beside the prompt (needs a GUI entry "
             "point and a display)",
    )

    args = parser.parse_args(argv)

    if args.config:
        repl = REPL.from_config_file(args.config, prompt=args.prompt)
    else:
        repl = REPL(prompt=args.prompt)

    if canvas_host is not None:
        repl.canvas_host = canvas_host

    if args.canvas:
        repl.show_canvas()

    repl.run()
    return 0


def main() -> None:
    """CLI entry point for the headless REPL."""
    raise SystemExit(run_repl())


if __name__ == "__main__":
    main()
