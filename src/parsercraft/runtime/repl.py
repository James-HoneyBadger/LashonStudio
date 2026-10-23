"""
ParserCraft REPL — Interactive Read-Eval-Print Loop

Provides an interactive shell for testing custom languages in real time.
Uses the PEG grammar engine to parse and the Python transpiler to execute.

Usage:
    python -m parsercraft.runtime.repl --config my_lang.yaml
    python -m parsercraft.runtime.repl   # starts with default grammar
"""

from __future__ import annotations

import io
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Optional

from parsercraft.codegen.python_transpiler import PythonTranspiler, TranspileOptions
from parsercraft.parser.grammar import (
    Grammar,
    GrammarBuilder,
    PEGInterpreter,
    SourceAST,
    grammar_from_config,
)


class REPL:
    """Interactive REPL for custom languages built with ParserCraft.

    Features:
        - Persistent namespace across evaluations
        - Multi-line input (braces/indentation continuation)
        - Special commands (:ast, :py, :grammar, :reset, :help, :quit)
        - History tracking
        - Error display with source context
    """

    BANNER = (
        "ParserCraft REPL v4.0.0\n"
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

        while True:
            try:
                source = self._read_input()
            except (EOFError, KeyboardInterrupt):
                print("\nBye!")
                break

            source = source.strip()
            if not source:
                continue

            # Handle special commands
            if source.startswith(":"):
                if self._handle_command(source):
                    continue
                if source == ":quit":
                    break
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

    def _eval(self, source: str) -> None:
        """Parse, transpile, and execute source code."""
        # Auto-add semicolon if missing (convenience)
        if not source.endswith(";"):
            source = source + " ;"

        try:
            ast = self.interpreter.parse(source)
            self._last_ast = ast
        except SyntaxError as e:
            print(f"Parse error: {e}", file=sys.stderr)
            return
        except Exception as e:
            print(f"Parse error: {e}", file=sys.stderr)
            return

        try:
            python_code = self.transpiler.transpile(ast)
            self._last_python = python_code
        except Exception as e:
            print(f"Transpile error: {e}", file=sys.stderr)
            return

        try:
            exec(python_code, self.namespace)  # noqa: S102
        except Exception as e:
            print(f"Runtime error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

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

        print(f"Unknown command: {cmd}. Type :help for available commands.")
        return True


def main():
    """CLI entry point for the REPL."""
    import argparse

    parser = argparse.ArgumentParser(
        description="ParserCraft REPL — Interactive Language Shell",
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

    args = parser.parse_args()

    if args.config:
        repl = REPL.from_config_file(args.config, prompt=args.prompt)
    else:
        repl = REPL(prompt=args.prompt)

    repl.run()


if __name__ == "__main__":
    main()
