"""Argument parser construction for the ``lashon`` console script."""

from __future__ import annotations

import argparse

from lashon import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the full command-line parser."""
    parser = argparse.ArgumentParser(
        description="Language Configuration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create from preset
  lashon create --preset python_like --output my_lang.yaml

  # Create interactively
  lashon create --interactive

  # Validate configuration
  lashon validate my_lang.yaml

  # Show info
  lashon info my_lang.yaml

  # Export documentation
  lashon export my_lang.yaml --format markdown

  # List available presets
  lashon list-presets

  # Convert between formats
  lashon convert my_lang.yaml --to json

  # Compare configurations
  lashon diff config1.yaml config2.yaml

  # Update configuration
  lashon update my_lang.yaml --set metadata.author "Your Name"

  # Delete elements
  lashon delete my_lang.yaml --keyword obsolete --function deprecated
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
    validate_parser.add_argument(
        "--json", action="store_true", help="Emit JSON"
    )

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
    diff_parser.add_argument(
        "--exit-code", action="store_true",
        help="Exit 1 when the configurations differ",
    )

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
    lsp_parser.add_argument(
        "--grammar",
        help="PEG grammar for real syntax diagnostics "
        "(default: grammar.peg next to the config)",
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
        "--publisher", default="lashon", help="Extension publisher name"
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

    # Doctor command
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check the environment and toolchains",
    )
    doctor_parser.add_argument(
        "--json", action="store_true", help="Emit JSON"
    )
    doctor_parser.add_argument(
        "--strict", action="store_true",
        help="Fail on warnings as well as errors",
    )

    # Init command
    init_parser = subparsers.add_parser(
        "init",
        help="Scaffold a new language project",
    )
    init_parser.add_argument(
        "name",
        help="Language name (becomes the directory name; no path separators)",
    )
    init_parser.add_argument(
        "--directory", "-d", default=".",
        help="Parent directory (default: current directory)",
    )
    init_parser.add_argument(
        "--force", action="store_true",
        help="Overwrite an existing project directory",
    )
    init_parser.add_argument(
        "--template", "-t", default="aurora",
        choices=["aurora", "calculator", "minimal"],
        help="Starting grammar template (default: aurora)",
    )
    init_parser.add_argument(
        "--with-vscode", action="store_true",
        help="Add .vscode run configuration",
    )
    init_parser.add_argument(
        "--with-ci", action="store_true",
        help="Add a GitHub Actions workflow",
    )

    # Playground command
    play_parser = subparsers.add_parser(
        "play",
        help="Serve a browser playground for a language project",
    )
    play_parser.add_argument(
        "project", nargs="?", default=".",
        help="Project directory or language config (default: .)",
    )
    play_parser.add_argument(
        "--port", "-p", type=int, default=8000, help="Port (default: 8000)"
    )
    play_parser.add_argument(
        "--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)"
    )
    play_parser.add_argument(
        "--open", action="store_true", help="Open the page in a browser"
    )
    play_parser.add_argument(
        "--verbose", action="store_true", help="Log HTTP requests"
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
    run_parser.add_argument(
        "--watch", action="store_true",
        help="Re-run when the source or grammar changes",
    )
    run_parser.add_argument(
        "--canvas", metavar="FILE",
        help="Write whatever the program draws to FILE (.svg)",
    )
    run_parser.add_argument(
        "--ascii-canvas", action="store_true",
        help="Print a text preview of the drawing",
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
        "--grammar", "-g", help="PEG grammar file (overrides --config)"
    )
    codegen_c_parser.add_argument(
        "--output", "-o", help="Output C file"
    )
    codegen_c_parser.add_argument(
        "--source-map", action="store_true",
        help="Emit #line directives so compiler errors point at your source",
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
        "--grammar", "-g", help="PEG grammar file (overrides --config)"
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
        "--grammar", "-g", help="PEG grammar file (overrides --config)"
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
    format_parser.add_argument(
        "--check", action="store_true",
        help="Exit 1 if the file would change",
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

    # Lint command
    lint_parser = subparsers.add_parser(
        "lint", help="Check config, grammar, and types"
    )
    lint_parser.add_argument("config", help="Language configuration file")
    lint_parser.add_argument(
        "--input", "--source", "-i", dest="input",
        help="Optional source file to validate too",
    )
    lint_parser.add_argument("--json", action="store_true", help="Emit JSON")

    # Demo command
    demo_parser = subparsers.add_parser(
        "demo", help="Run a guided pipeline demo"
    )
    demo_parser.add_argument(
        "--no-backends", action="store_true",
        help="Skip C/WASM/LLVM output",
    )

    # Config get/set
    config_parser = subparsers.add_parser(
        "config", help="Get or set nested configuration values"
    )
    config_sub = config_parser.add_subparsers(dest="config_command")
    config_get = config_sub.add_parser("get", help="Print a value")
    config_get.add_argument("file", help="Language configuration file")
    config_get.add_argument("key", help="Dotted key, e.g. syntax_options.require_semicolons")
    config_get.add_argument("--json", action="store_true", help="Emit JSON")
    config_set = config_sub.add_parser("set", help="Set a value")
    config_set.add_argument("file", help="Language configuration file")
    config_set.add_argument("key", help="Dotted key")
    config_set.add_argument("value", help="Value (JSON or string)")
    config_set.add_argument("--output", "-o", help="Write to another file")

    return parser
