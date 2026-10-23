#!/usr/bin/env python3
"""
ParserCraft CLI

Command-line interface for creating, editing, running, and managing custom
programming language configurations and programs.

Language Configuration Commands:
    parsercraft init NAME [--directory DIR] [--force]
    parsercraft create [--preset PRESET] [--output FILE]
    parsercraft edit FILE
    parsercraft validate FILE
    parsercraft info [FILE]
    parsercraft export FILE [--format markdown|json|yaml]
    parsercraft import FILE [--scope runtime|project|user]
    parsercraft list-presets
    parsercraft convert FILE --to FORMAT
    parsercraft diff FILE1 FILE2
    parsercraft update FILE [--set KEY VALUE] [--merge FILE]
    parsercraft delete FILE [--keyword KW] [--function FN]
    parsercraft translate FILE [--config CONFIG]

Execution Commands:
    parsercraft run FILE [--config CONFIG | --grammar GRAMMAR] [--json]
    parsercraft repl [FILE] [--debug]
    parsercraft batch FILE [--script SCRIPT]
    parsercraft test FILE [--cases FILE]
    parsercraft test-run FILE

Code Generation Commands:
    parsercraft codegen-c FILE [--config CONFIG] [--output FILE]
    parsercraft codegen-wasm FILE [--config CONFIG] [--output FILE]
    parsercraft codegen-llvm FILE [--config CONFIG] [--output FILE]

Type System Commands:
    parsercraft type-check FILE [--config CONFIG]
    parsercraft generics FILE
    parsercraft check-protocol FILE

Module System Commands:
    parsercraft module-info FILE
    parsercraft module-deps FILE
    parsercraft module-cycles FILE

Tooling Commands:
    parsercraft lsp [--port PORT] [--stdio]
    parsercraft extension [--output DIR]
    parsercraft package-search QUERY
    parsercraft package-install PACKAGE
    parsercraft refactor-rename FILE --old NAME --new NAME
    parsercraft format FILE
    parsercraft debug-launch FILE

Presets:
    - python_like    : Python-style syntax
    - js_like        : JavaScript-style syntax
    - lisp_like      : Lisp-style syntax
    - functional     : Functional (ML-style) syntax
    - basic_like     : BASIC-style syntax
    - minimal        : Minimal functional language

Examples:
    # Create a new Python-like language
    parsercraft create --preset python_like --output my_lang.yaml

    # Validate a configuration file
    parsercraft validate my_lang.yaml

    # Run an interactive REPL with a language config
    parsercraft repl my_lang.yaml

    # Generate C code from a source file
    parsercraft codegen-c program.src --output program.c

    # Start the LSP server on stdio
    parsercraft lsp --stdio

See Also:
    parsercraft-ide    Launch the Tkinter IDE
    parsercraft-repl   Launch the standalone REPL
"""
# pylint: disable=too-many-lines,import-outside-toplevel

import argparse
import sys

from parsercraft import __version__
from parsercraft.tooling.commands import (
    cmd_batch,
    cmd_check_protocol,
    cmd_codegen_c,
    cmd_codegen_llvm,
    cmd_codegen_wasm,
    cmd_convert,
    cmd_create,
    cmd_debug_launch,
    cmd_delete,
    cmd_diff,
    cmd_edit,
    cmd_export,
    cmd_extension,
    cmd_format,
    cmd_generics,
    cmd_import,
    cmd_info,
    cmd_init,
    cmd_list_presets,
    cmd_lsp,
    cmd_module_cycles,
    cmd_module_deps,
    cmd_module_info,
    cmd_package_install,
    cmd_package_search,
    cmd_refactor_rename,
    cmd_repl,
    cmd_run,
    cmd_test,
    cmd_test_run,
    cmd_translate,
    cmd_type_check,
    cmd_update,
    cmd_validate,
)


def main():
    """Main entry point for the CLI application."""
    parser = argparse.ArgumentParser(
        description="Language Configuration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create from preset
  parsercraft create --preset python_like --output my_lang.yaml

  # Create interactively
  parsercraft create --interactive

  # Validate configuration
  parsercraft validate my_lang.yaml

  # Show info
  parsercraft info my_lang.yaml

  # Export documentation
  parsercraft export my_lang.yaml --format markdown

  # List available presets
  parsercraft list-presets

  # Convert between formats
  parsercraft convert my_lang.yaml --to json

  # Compare configurations
  parsercraft diff config1.yaml config2.yaml

  # Update configuration
  parsercraft update my_lang.yaml --set metadata.author "Your Name"

  # Delete elements
  parsercraft delete my_lang.yaml --keyword obsolete --function deprecated
        """,
    )

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Command to execute",
    )

    # Create command
    create_parser = subparsers.add_parser(
        "create",
        help="Create new configuration",
    )
    create_parser.add_argument("--preset", help="Start from preset")
    create_parser.add_argument(
        "--interactive", "-i", action="store_true", help="Interactive mode"
    )
    create_parser.add_argument(
        "--output", "-o", help="Output file (default: language_config.yaml)"
    )

    # Edit command
    edit_parser = subparsers.add_parser(
        "edit", help="Edit configuration in text editor"
    )
    edit_parser.add_argument("file", help="Configuration file to edit")

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate configuration",
    )
    validate_parser.add_argument("file", help="Configuration file to validate")

    # Info command
    info_parser = subparsers.add_parser(
        "info",
        help="Show configuration information",
    )
    info_parser.add_argument(
        "file", nargs="?", help="Configuration file (default: current runtime)"
    )

    # Export command
    export_parser = subparsers.add_parser(
        "export",
        help="Export configuration",
    )
    export_parser.add_argument("file", help="Configuration file to export")
    export_parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json", "yaml"],
        help="Export format",
    )
    export_parser.add_argument("--output", "-o", help="Output file")

    # List presets command
    subparsers.add_parser("list-presets", help="List available presets")

    # Convert command
    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert between formats",
    )
    convert_parser.add_argument("file", help="Configuration file to convert")
    convert_parser.add_argument(
        "--from",
        dest="from_format",
        help="Source format",
    )
    convert_parser.add_argument(
        "--to",
        dest="to_format",
        required=True,
        choices=["json", "yaml"],
        help="Target format",
    )
    convert_parser.add_argument("--output", "-o", help="Output file")

    # Diff command
    diff_parser = subparsers.add_parser(
        "diff",
        help="Compare two configurations",
    )
    diff_parser.add_argument("file1", help="First configuration file")
    diff_parser.add_argument("file2", help="Second configuration file")

    # Update command
    update_parser = subparsers.add_parser(
        "update",
        help="Update configuration",
    )
    update_parser.add_argument("file", help="Configuration file to update")
    update_parser.add_argument(
        "--set",
        action="append",
        nargs=2,
        metavar=("KEY", "VALUE"),
        help="Set key=value (can be used multiple times)",
    )
    update_parser.add_argument(
        "--merge",
        help="Merge with another config file",
    )
    update_parser.add_argument(
        "--output", "-o", help="Output file (default: update in place)"
    )

    # Delete command
    delete_parser = subparsers.add_parser(
        "delete",
        help="Delete config elements",
    )
    delete_parser.add_argument("file", help="Configuration file")
    delete_parser.add_argument(
        "--keyword", action="append", help="Delete keyword (can be repeated)"
    )
    delete_parser.add_argument(
        "--function", action="append", help="Delete function (can be repeated)"
    )
    delete_parser.add_argument(
        "--operator", action="append", help="Delete operator (can be repeated)"
    )
    delete_parser.add_argument(
        "--output", "-o", help="Output file (default: update in place)"
    )

    # Import command
    import_parser = subparsers.add_parser(
        "import",
        help="Import configuration for use",
    )
    import_parser.add_argument("file", help="Configuration file to import")
    import_parser.add_argument(
        "--scope",
        choices=["runtime", "project", "user"],
        help=(
            "Where to apply: runtime only, project (.langconfig), "
            "or user (~/.langconfig)"
        ),
    )

    # REPL command
    repl_parser = subparsers.add_parser("repl", help="Interactive REPL mode")
    repl_parser.add_argument(
        "file",
        nargs="?",
        help="Configuration file (optional)",
    )
    repl_parser.add_argument(
        "--grammar",
        help="PEG grammar file to use instead of a language config",
    )
    repl_parser.add_argument(
        "--debug", "-d", action="store_true", help="Enable debug mode"
    )

    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Batch process files")
    batch_parser.add_argument("file", help="Configuration file")
    batch_parser.add_argument("--script", "-s", help="Script file to execute")
    batch_parser.add_argument(
        "--input-dir", "-i", help="Input directory for batch processing"
    )
    batch_parser.add_argument(
        "--output-dir", "-o", help="Output directory (default: same as input)"
    )
    batch_parser.add_argument(
        "--pattern", "-p", help="File pattern to match (default: *.txt)"
    )
    batch_parser.add_argument(
        "--show-translation",
        action="store_true",
        help="Show translated Python code",
    )
    batch_parser.add_argument(
        "--show-vars", action="store_true", help="Show final variables"
    )
    batch_parser.add_argument(
        "--debug", "-d", action="store_true", help="Enable debug mode"
    )

    # Test command
    test_parser = subparsers.add_parser(
        "test",
        help="Translate, run, and verify test cases",
    )
    test_parser.add_argument(
        "--config", "-c", required=True, help="Configuration file"
    )
    test_parser.add_argument(
        "--tests", "-t", required=True, help="Test cases file (yaml/json)"
    )
    test_parser.add_argument(
        "--show-translation",
        action="store_true",
        help="Show translated Python code for each case",
    )
    test_parser.add_argument(
        "--stop-on-fail", action="store_true", help="Stop after first fail"
    )
    test_parser.add_argument(
        "--debug", "-d", action="store_true", help="Enable debug mode"
    )

    # Translate command
    translate_parser = subparsers.add_parser(
        "translate",
        help="Translate source code using a configuration",
    )
    translate_parser.add_argument(
        "--config", "-c", required=True, help="Configuration file"
    )
    translate_parser.add_argument(
        "--input", "-i", required=True, help="Source file to translate"
    )
    translate_parser.add_argument(
        "--output", "-o", help="Output file (default: stdout)"
    )

    # LSP server command
    lsp_parser = subparsers.add_parser(
        "lsp",
        help="Start Language Server Protocol server",
    )
    lsp_parser.add_argument(
        "--config", "-c", required=True, help="Language configuration file"
    )
    lsp_parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8080,
        help="Server port (default: 8080)",
    )
    lsp_parser.add_argument(
        "--stdio", action="store_true", help="Use stdio instead of socket"
    )

    # VS Code extension command
    extension_parser = subparsers.add_parser(
        "extension",
        help="Generate VS Code extension",
    )
    extension_parser.add_argument(
        "--config", "-c", required=True, help="Language configuration file"
    )
    extension_parser.add_argument(
        "--output",
        "-o",
        default=".vscode-ext",
        help="Output directory (default: .vscode-ext)",
    )
    extension_parser.add_argument(
        "--publisher", default="parsercraft", help="Extension publisher name"
    )
    extension_parser.add_argument(
        "--version", default="0.0.1", help="Extension version"
    )

    # Type checking command
    typecheck_parser = subparsers.add_parser(
        "type-check",
        help="Perform static type analysis",
    )
    typecheck_parser.add_argument(
        "--config", "-c", required=True, help="Language configuration file"
    )
    typecheck_parser.add_argument(
        "--input", "-i", required=True, help="Source file to analyze"
    )
    typecheck_parser.add_argument(
        "--level",
        choices=["lenient", "moderate", "strict", "very-strict"],
        default="moderate",
        help="Analysis strictness level (default: moderate)",
    )
    typecheck_parser.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="Treat warnings as errors",
    )
    typecheck_parser.add_argument(
        "--json", action="store_true",
        help="Emit diagnostics as JSON on stdout",
    )
    typecheck_parser.add_argument(
        "--debug", "-d", action="store_true", help="Enable debug mode"
    )

    # Module info command
    module_info_parser = subparsers.add_parser(
        "module-info",
        help="Show module information",
    )
    module_info_parser.add_argument("module", help="Module name")
    module_info_parser.add_argument(
        "--module-dir",
        "-d",
        help="Module directory (default: current directory)",
    )
    module_info_parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode"
    )

    # Module dependencies command
    module_deps_parser = subparsers.add_parser(
        "module-deps",
        help="Show module dependencies",
    )
    module_deps_parser.add_argument("module", help="Module name")
    module_deps_parser.add_argument(
        "--module-dir",
        "-d",
        help="Module directory (default: current directory)",
    )
    module_deps_parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode"
    )

    # Module cycles command
    module_cycles_parser = subparsers.add_parser(
        "module-cycles",
        help="Detect circular dependencies",
    )
    module_cycles_parser.add_argument(
        "--module-dir",
        "-d",
        help="Module directory (default: current directory)",
    )
    module_cycles_parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode"
    )

    # Generic types command
    generics_parser = subparsers.add_parser(
        "generics",
        help="Check generic type constraints",
    )
    generics_parser.add_argument("file", help="Source file to check")
    generics_parser.add_argument(
        "--check-variance", action="store_true", help="Check type variance"
    )
    generics_parser.add_argument(
        "--infer", action="store_true", help="Infer type arguments"
    )

    # Protocol checking command
    protocol_parser = subparsers.add_parser(
        "check-protocol",
        help="Check protocol conformance",
    )
    protocol_parser.add_argument("file", help="Source file to check")
    protocol_parser.add_argument(
        "--list-protocols", action="store_true", help="List all protocols"
    )
    protocol_parser.add_argument(
        "--protocol", help="Check specific protocol"
    )

    # Init command
    init_parser = subparsers.add_parser(
        "init",
        help="Scaffold a new language project",
    )
    init_parser.add_argument("name", help="Language name")
    init_parser.add_argument(
        "--directory", "-d", default=".",
        help="Parent directory (default: current directory)",
    )
    init_parser.add_argument(
        "--force", action="store_true",
        help="Overwrite an existing project directory",
    )

    # Run command
    run_parser = subparsers.add_parser(
        "run",
        help="Parse and execute a program",
    )
    run_parser.add_argument("file", help="Source file to execute")
    run_parser.add_argument(
        "--config", "-c",
        help="Language configuration file containing grammar.rules",
    )
    run_parser.add_argument(
        "--grammar", "-g",
        help="PEG grammar file (overrides --config)",
    )
    run_parser.add_argument(
        "--json", action="store_true",
        help="Print variables as JSON; program output goes to stderr",
    )
    run_parser.add_argument(
        "--show-python", action="store_true",
        help="Print generated Python to stderr before running",
    )
    run_parser.add_argument(
        "--sandbox", action="store_true",
        help="Run in an isolated subprocess with CPU/memory/file limits",
    )
    run_parser.add_argument(
        "--sandbox-timeout", type=float, default=10.0,
        help="Sandbox wall-clock timeout in seconds (default: 10)",
    )

    # Code generation commands
    codegen_c_parser = subparsers.add_parser(
        "codegen-c",
        help="Generate C code from source",
    )
    codegen_c_parser.add_argument("file", help="Source file")
    codegen_c_parser.add_argument(
        "--config", "-c", help="Language configuration file (grammar)"
    )
    codegen_c_parser.add_argument(
        "--output", "-o", help="Output C file"
    )

    # WASM code generation
    codegen_wasm_parser = subparsers.add_parser(
        "codegen-wasm",
        help="Generate WebAssembly from source",
    )
    codegen_wasm_parser.add_argument("file", help="Source file")
    codegen_wasm_parser.add_argument(
        "--config", "-c", help="Language configuration file (grammar)"
    )
    codegen_wasm_parser.add_argument(
        "--output", "-o", help="Output WAT file"
    )

    # LLVM IR code generation
    codegen_llvm_parser = subparsers.add_parser(
        "codegen-llvm",
        help="Generate LLVM IR from source",
    )
    codegen_llvm_parser.add_argument("file", help="Source file")
    codegen_llvm_parser.add_argument(
        "--config", "-c", help="Language configuration file (grammar)"
    )
    codegen_llvm_parser.add_argument(
        "--output", "-o", help="Output LLVM IR file"
    )

    # Package management commands
    package_search_parser = subparsers.add_parser(
        "package-search",
        help="Search for packages",
    )
    package_search_parser.add_argument("query", help="Search query")
    package_search_parser.add_argument(
        "--registry", default="local", help="Package registry"
    )

    package_install_parser = subparsers.add_parser(
        "package-install",
        help="Install package",
    )
    package_install_parser.add_argument("package", help="Package name@version")
    package_install_parser.add_argument(
        "--registry", default="local", help="Package registry"
    )
    package_install_parser.add_argument(
        "--save", action="store_true", help="Save to package.json"
    )

    # Refactoring commands
    refactor_rename_parser = subparsers.add_parser(
        "refactor-rename",
        help="Rename symbol",
    )
    refactor_rename_parser.add_argument("file", help="Source file")
    refactor_rename_parser.add_argument("old_name", help="Old name")
    refactor_rename_parser.add_argument("new_name", help="New name")
    refactor_rename_parser.add_argument(
        "--output", "-o", help="Output file"
    )

    # Code formatting
    format_parser = subparsers.add_parser(
        "format",
        help="Format source code",
    )
    format_parser.add_argument("file", help="Source file")
    format_parser.add_argument(
        "--output", "-o", help="Output file"
    )
    format_parser.add_argument(
        "--tab-size", type=int, default=4, help="Tab size"
    )
    format_parser.add_argument(
        "--in-place", action="store_true", help="Format in place"
    )

    # Testing framework
    test_run_parser = subparsers.add_parser(
        "test-run",
        help="Run tests",
    )
    test_run_parser.add_argument(
        "path", nargs="?", help="Test file or directory"
    )
    test_run_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    test_run_parser.add_argument(
        "--coverage", action="store_true", help="Generate coverage report"
    )

    # Debug support
    debug_launch_parser = subparsers.add_parser(
        "debug-launch",
        help="Launch debugger",
    )
    debug_launch_parser.add_argument("file", help="Program to debug")
    debug_launch_parser.add_argument(
        "--port", type=int, default=5678, help="Debug port"
    )
    debug_launch_parser.add_argument(
        "--breakpoint", "-b", action="append", help="Set breakpoint at line"
    )
    debug_launch_parser.add_argument(
        "--config", "-c", help="Language configuration (grammar.rules)"
    )
    debug_launch_parser.add_argument(
        "--grammar", "-g", help="PEG grammar file (overrides --config)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Dispatch to command handler
    commands = {
        "init": cmd_init,
        "create": cmd_create,
        "edit": cmd_edit,
        "validate": cmd_validate,
        "info": cmd_info,
        "export": cmd_export,
        "list-presets": cmd_list_presets,
        "convert": cmd_convert,
        "diff": cmd_diff,
        "update": cmd_update,
        "delete": cmd_delete,
        "import": cmd_import,
        "run": cmd_run,
        "repl": cmd_repl,
        "batch": cmd_batch,
        "test": cmd_test,
        "translate": cmd_translate,
        "lsp": cmd_lsp,
        "extension": cmd_extension,
        "type-check": cmd_type_check,
        "module-info": cmd_module_info,
        "module-deps": cmd_module_deps,
        "module-cycles": cmd_module_cycles,
        "generics": cmd_generics,
        "check-protocol": cmd_check_protocol,
        "codegen-c": cmd_codegen_c,
        "codegen-wasm": cmd_codegen_wasm,
        "codegen-llvm": cmd_codegen_llvm,
        "package-search": cmd_package_search,
        "package-install": cmd_package_install,
        "refactor-rename": cmd_refactor_rename,
        "format": cmd_format,
        "test-run": cmd_test_run,
        "debug-launch": cmd_debug_launch,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
