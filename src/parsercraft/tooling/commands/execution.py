"""Execution CLI commands: run helpers, REPL, batch, tests, translate."""

from __future__ import annotations

import ast
import contextlib
import io
import json
import re
import traceback
from math import e, pi
from pathlib import Path
from typing import Any, Optional, Sequence

try:
    import readline  # noqa: F401
except ImportError:  # pragma: no cover
    readline = None  # type: ignore[assignment]

from parsercraft.config import LanguageConfig
from parsercraft.runtime import LanguageRuntime
from parsercraft.tooling.commands.common import CONFIG_LOAD_ERRORS

try:
    from yaml import safe_load
except ImportError:  # pragma: no cover
    safe_load = None  # type: ignore[assignment]

SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs, "all": all, "any": any, "bool": bool, "enumerate": enumerate,
    "filter": filter, "float": float, "int": int, "len": len, "list": list,
    "map": map, "max": max, "min": min, "print": print, "range": range,
    "round": round, "sorted": sorted, "str": str, "sum": sum, "tuple": tuple,
    "zip": zip, "pi": pi, "e": e,
}


def _load_config_from_path(
    path: Path,
    error_prefix: str,
) -> Optional[LanguageConfig]:
    """Load a configuration file, reporting user-friendly errors."""
    try:
        return LanguageConfig.load(path)
    except CONFIG_LOAD_ERRORS as error:
        print(f"{error_prefix}{error}")
        return None

def _translate_with_keywords(
    source: str,
    custom_keywords: Sequence[str],
) -> str:
    """Translate custom keywords in source code back to their originals."""
    translated = source
    for custom_kw in custom_keywords:
        original_kw = LanguageRuntime.translate_keyword(custom_kw)
        pattern = r"\b" + re.escape(custom_kw) + r"\b"
        translated = re.sub(pattern, original_kw, translated)

    # Also translate custom function names if present
    for custom_func in LanguageRuntime.get_custom_functions():
        original_func = LanguageRuntime.translate_function(custom_func)
        pattern = r"\b" + re.escape(custom_func) + r"\b"
        translated = re.sub(pattern, original_func, translated)

    return translated

def _load_test_cases(path: Path) -> Optional[list[dict[str, Any]]]:
    """Load test cases from a YAML or JSON file."""
    if not path.exists():
        print(f"Error: Test file not found: {path}")
        return None

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"Error reading test file: {error}")
        return None

    try:
        if path.suffix.lower() in {".yaml", ".yml"} and safe_load is not None:
            cases = safe_load(content)
        else:
            cases = json.loads(content)
    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"Error parsing test file: {error}")
        return None

    if not isinstance(cases, list):
        print("Error: Test file must contain a list of cases")
        return None

    return cases

def _run_test_case(
    case: dict[str, Any],
    base_dir: Path,
    custom_keywords: Sequence[str],
    show_translation: bool,
    debug: bool,
) -> tuple[bool, list[str]]:
    """Execute a single test case and return (passed, details)."""
    details: list[str] = []

    source: Optional[str] = None
    if file_path := case.get("file"):
        candidate = (base_dir / file_path).resolve()
        if not candidate.exists():
            return False, [f"File not found: {candidate}"]
        try:
            source = candidate.read_text(encoding="utf-8")
        except OSError as error:
            return False, [f"Error reading file: {error}"]
    elif inline := case.get("source"):
        source = str(inline)

    if not source:
        return False, ["Missing 'file' or 'source' in test case"]

    translated = _translate_with_keywords(source, custom_keywords)

    if show_translation:
        details.append("Translated code:\n" + translated)

    buffer = io.StringIO()
    variables: dict[str, Any] = {}
    safe_globals = {"__builtins__": SAFE_BUILTINS.copy()}

    try:
        with contextlib.redirect_stdout(buffer):
            exec(  # pylint: disable=exec-used
                translated,
                safe_globals,
                variables,
            )
    except Exception as error:  # pylint: disable=broad-exception-caught
        failure = f"Execution error: {error}"
        if debug:
            traceback.print_exc()
        return False, details + [failure]

    stdout = buffer.getvalue()
    expected_stdout = case.get("expect_stdout")
    expected_vars = case.get("expect_vars") or {}

    passed = True

    if expected_stdout is not None:
        if stdout.strip() != str(expected_stdout).strip():
            passed = False
            details.append(
                "Stdout mismatch:\n"
                f"Expected: {expected_stdout!r}\n"
                f"Actual:   {stdout!r}"
            )

    for name, expected_value in expected_vars.items():
        if name not in variables:
            passed = False
            details.append(f"Missing variable: {name}")
            continue
        if variables[name] != expected_value:
            passed = False
            details.append(
                f"Variable mismatch for '{name}': "
                f"expected {expected_value!r}, got {variables[name]!r}"
            )

    return passed, details

def _handle_repl_command(
    command: str,
    config: LanguageConfig,
    variables: dict[str, Any],
    debug: bool,
) -> tuple[bool, bool]:
    """Handle REPL meta-commands. Returns (should_continue, debug)."""
    if command in {"exit", "quit"}:
        print("Goodbye!")
        return False, debug

    if command == "help":
        print("\nCommands:")
        print("  .help       - Show this help")
        print("  .info       - Show language info")
        print("  .keywords   - List all keywords")
        print("  .functions  - List all functions")
        print("  .vars       - Show current variables")
        print("  .clear      - Clear all variables")
        print("  .debug      - Toggle debug mode")
        print("  .exit       - Exit REPL\n")
        return True, debug

    if command == "info":
        print(f"\nLanguage: {config.name}")
        print(f"Version: {config.version}")
        print(f"Keywords: {len(config.keyword_mappings)}")
        print(f"Functions: {len(config.builtin_functions)}\n")
        return True, debug

    if command == "keywords":
        print("\nKeywords:")
        for kw in sorted(
            config.keyword_mappings.values(),
            key=lambda mapping: mapping.custom,
        ):
            print(f"  {kw.custom:20} ({kw.original})")
        print()
        return True, debug

    if command == "functions":
        print("\nBuiltin Functions:")
        for func in sorted(
            config.builtin_functions.values(),
            key=lambda item: item.name,
        ):
            arity = "variadic" if func.arity == -1 else f"{func.arity} args"
            status = "" if func.enabled else " [DISABLED]"
            print(f"  {func.name:20} ({arity}){status}")
        print()
        return True, debug

    if command == "vars":
        if variables:
            print("\nVariables:")
            for name, value in sorted(variables.items()):
                print(f"  {name} = {value}")
            print()
        else:
            print("\nNo variables defined\n")
        return True, debug

    if command == "clear":
        variables.clear()
        print("Variables cleared\n")
        return True, debug

    if command == "debug":
        new_debug = not debug
        print(f"Debug mode: {'ON' if new_debug else 'OFF'}\n")
        return True, new_debug

    print(f"Unknown command: .{command}")
    print("Type .help for available commands\n")
    return True, debug

def _execute_repl_line(
    line: str,
    variables: dict[str, Any],
    keyword_prefixes: Sequence[str],
    custom_keywords: Sequence[str],
    debug: bool,
) -> None:
    """Translate and execute a line within the REPL session."""
    try:
        translated = _translate_with_keywords(line, custom_keywords)
        if debug:
            print(f"[DEBUG] Translated: {translated}")
        safe_globals = {"__builtins__": SAFE_BUILTINS.copy()}

        stripped_line = line.strip()
        has_assignment = (
            re.match(r'.*(?<![=!<>+\-*/])=(?!=).*', stripped_line) is not None
        )
        starts_with_keyword = stripped_line.startswith(tuple(keyword_prefixes))

        if has_assignment or starts_with_keyword:
            # Statement: just exec, don't try to get a value
            exec(  # pylint: disable=exec-used
                translated,
                safe_globals,
                variables,
            )
        else:
            # Expression: try to evaluate and display result
            try:
                result = ast.literal_eval(translated)
            except (ValueError, SyntaxError):
                try:
                    result = eval(  # pylint: disable=eval-used
                        translated,
                        safe_globals,
                        variables,
                    )
                except SyntaxError:
                    # Not an expression — fall back to exec
                    exec(  # pylint: disable=exec-used
                        translated,
                        safe_globals,
                        variables,
                    )
                    result = None
            if result is not None:
                print(result)
    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"Error: {error}")
        if debug:
            traceback.print_exc()

def _run_repl_session(config: LanguageConfig, debug: bool) -> int:
    """Run the interactive REPL session."""
    LanguageRuntime.load_config(config=config)
    custom_keywords = tuple(LanguageRuntime.get_custom_keywords())
    keyword_prefixes = custom_keywords
    variables: dict[str, Any] = {}

    print("=" * 70)
    print("HB Language Construction Set - REPL Mode")
    print(f"Language: {config.name} v{config.version}")
    print("=" * 70)
    print("\nCommands:")
    print("  .help       - Show this help")
    print("  .info       - Show language info")
    print("  .keywords   - List all keywords")
    print("  .functions  - List all functions")
    print("  .vars       - Show current variables")
    print("  .clear      - Clear all variables")
    print("  .debug      - Toggle debug mode")
    print("  .exit       - Exit REPL")
    print("\nEnter code to execute:\n")

    while True:
        try:
            prompt = ">>> " if not debug else "[DEBUG] >>> "
            line = input(prompt).strip()

            if not line:
                continue

            if line.startswith("."):
                continue_loop, debug = _handle_repl_command(
                    line[1:].lower(), config, variables, debug
                )
                if not continue_loop:
                    break
                continue

            _execute_repl_line(
                line, variables, keyword_prefixes, custom_keywords, debug
            )

        except EOFError:
            print("\nGoodbye!")
            break
        except KeyboardInterrupt:
            print("\n(Use .exit to quit)")
            continue

    return 0

def _resolve_repl_config(file_arg: Optional[str]) -> Optional[LanguageConfig]:
    """Resolve the configuration to use for the REPL."""
    if not file_arg:
        print("Using default configuration")
        return LanguageConfig()

    filepath = Path(file_arg)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        return None

    config = _load_config_from_path(filepath, "Error loading config: ")
    if config:
        print(f"Loaded configuration: {config.name}")
    return config

def _run_batch_script(
    script_path: Path,
    custom_keywords: Sequence[str],
    show_translation: bool,
    show_vars: bool,
    debug: bool,
) -> int:
    """Execute a batch script after translating custom keywords."""
    if not script_path.exists():
        print(f"Error: Script file not found: {script_path}")
        return 1

    print(f"Executing batch script: {script_path}")
    print("=" * 70)

    try:
        code = script_path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"Error reading script: {error}")
        return 1

    translated = _translate_with_keywords(code, custom_keywords)

    if show_translation:
        print("\nTranslated Python code:")
        print("-" * 70)
        print(translated)
        print("-" * 70)
        print()

    namespace: dict[str, Any] = {}
    try:
        exec(  # pylint: disable=exec-used
            translated,
            {"__builtins__": SAFE_BUILTINS.copy()},
            namespace,
        )
    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"\nError executing script: {error}")
        if debug:
            traceback.print_exc()
        return 1

    print("\n" + "=" * 70)
    print("Execution completed successfully")

    if show_vars:
        print("\nFinal variables:")
        for name, value in sorted(namespace.items()):
            if not name.startswith("__"):
                print(f"  {name} = {value}")

    return 0

def _process_batch_directory(
    input_dir: Path,
    custom_keywords: Sequence[str],
    output_dir: Optional[str],
    pattern: Optional[str],
) -> int:
    """Translate files in a directory and write Python outputs."""
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Error: Input directory not found: {input_dir}")
        return 1

    target_dir = Path(output_dir) if output_dir else input_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    glob_pattern = pattern or "*.txt"
    files = list(input_dir.glob(glob_pattern))
    if not files:
        print(f"No files found matching pattern: {glob_pattern}")
        return 1

    success_count = 0
    error_count = 0

    for file_path in files:
        print(f"\nProcessing: {file_path.name}")
        try:
            code = file_path.read_text(encoding="utf-8")
            translated = _translate_with_keywords(code, custom_keywords)
            output_file = target_dir / f"{file_path.stem}.py"
            output_file.write_text(translated, encoding="utf-8")
            print(f"  -> Saved to: {output_file}")
            success_count += 1
        except OSError as error:
            print(f"  -> Error: {error}")
            error_count += 1

    print("\n" + "=" * 70)
    print("Batch processing complete:")
    print(f"  Success: {success_count}")
    print(f"  Errors: {error_count}")

    return 0 if error_count == 0 else 1

def cmd_repl(args):
    """Interactive REPL mode for testing language features."""
    if readline is None:
        print("Warning: readline support unavailable; history disabled")

    if args.grammar:
        from parsercraft.parser.grammar import GrammarParser
        from parsercraft.runtime.repl import REPL

        grammar_path = Path(args.grammar)
        if not grammar_path.exists():
            print(f"Error: Grammar file not found: {grammar_path}")
            return 1
        try:
            grammar = GrammarParser().parse(
                grammar_path.read_text(encoding="utf-8")
            )
        except ValueError as error:
            print(f"Error parsing grammar: {error}")
            return 1
        REPL(grammar=grammar).run()
        return 0

    config = _resolve_repl_config(args.file)
    if config is None:
        return 1

    return _run_repl_session(config, args.debug)

def cmd_batch(args):
    """Execute batch processing of language files."""
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: Configuration file not found: {filepath}")
        return 1

    config = _load_config_from_path(filepath, "Error loading config: ")
    if config is None:
        return 1

    LanguageRuntime.load_config(config=config)
    custom_keywords = tuple(LanguageRuntime.get_custom_keywords())

    if args.script:
        return _run_batch_script(
            Path(args.script),
            custom_keywords,
            args.show_translation,
            args.show_vars,
            args.debug,
        )

    if args.input_dir:
        return _process_batch_directory(
            Path(args.input_dir),
            custom_keywords,
            args.output_dir,
            args.pattern,
        )

    print("Error: Specify --script FILE or --input-dir DIR")
    return 1

def cmd_test(args):
    """Translate, run, and verify test cases."""
    tests_path = Path(args.tests)
    cases = _load_test_cases(tests_path)
    if cases is None:
        return 1

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        return 1

    config = _load_config_from_path(config_path, "Error loading config: ")
    if config is None:
        return 1

    LanguageRuntime.load_config(config=config)
    custom_keywords = tuple(LanguageRuntime.get_custom_keywords())

    base_dir = tests_path.parent
    failures = 0

    for index, case in enumerate(cases, start=1):
        name = case.get("name") or f"case {index}"
        passed, details = _run_test_case(
            case,
            base_dir,
            custom_keywords,
            args.show_translation,
            args.debug,
        )

        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {name}")
        for detail in details:
            print(f"  {detail}")

        if not passed:
            failures += 1
            if args.stop_on_fail:
                break

    total = len(cases)
    print(
        f"\nSummary: {total - failures}/{total} passed, {failures} failed"
    )

    return 0 if failures == 0 else 1

def cmd_translate(args):
    """Translate a source file using a language configuration."""
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        return 1

    config = _load_config_from_path(config_path, "Error loading config: ")
    if config is None:
        return 1

    LanguageRuntime.load_config(config=config)
    custom_keywords = tuple(LanguageRuntime.get_custom_keywords())

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return 1

    try:
        source = input_path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"Error reading input file: {error}")
        return 1

    translated = _translate_with_keywords(source, custom_keywords)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            output_path.write_text(translated, encoding="utf-8")
        except OSError as error:
            print(f"Error writing output file: {error}")
            return 1
        print(f"✓ Translated source saved to: {output_path}")
    else:
        print(translated)

    return 0

