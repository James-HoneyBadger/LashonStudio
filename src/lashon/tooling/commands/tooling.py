"""Editor, packaging, formatting, and debug CLI commands."""

from __future__ import annotations

import sys
from pathlib import Path

from lashon.config import LanguageConfig
from lashon.tooling.commands.common import CONFIG_LOAD_ERRORS


def cmd_lsp(args):
    """Start Language Server Protocol server."""
    from lashon.tooling.lsp.lsp_server import create_lsp_server

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        return 1

    grammar_path = getattr(args, "grammar", None)
    if not grammar_path:
        candidate = config_path.parent / "grammar.peg"
        if candidate.is_file():
            grammar_path = str(candidate)

    try:
        server = create_lsp_server(str(config_path), grammar_path)
        print(
            f"\u2713 LSP Server started for {server.config.name}",
            file=sys.stderr,
        )
        print(f"  Port: {args.port}", file=sys.stderr)
        print(
            f"  Mode: {'stdio' if args.stdio else 'socket'}", file=sys.stderr
        )
        if args.stdio:
            server.run_stdio()
        else:
            # Socket mode not yet implemented
            print(
                "Socket mode not yet implemented. Please use --stdio.",
                file=sys.stderr,
            )
            return 1

        return 0
    except CONFIG_LOAD_ERRORS as error:
        print(f"Error loading config: {error}", file=sys.stderr)
        return 1

def cmd_extension(args):
    """Generate VS Code extension."""
    from lashon.packaging.vscode_integration import generate_vscode_extension

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        return 1

    try:
        config = LanguageConfig.load(config_path)
        generate_vscode_extension(
            config=config,
            output_dir=args.output,
            publisher=args.publisher,
            version=args.version,
        )
        print(f"✓ VS Code extension generated in: {args.output}")
        print("\nNext steps:")
        print(f"  1. cd {args.output}")
        print("  2. npm install")
        print("  3. npm run compile")
        print("  4. npx vsce package")
        print("  5. code --install-extension <generated .vsix>")
        return 0
    except CONFIG_LOAD_ERRORS as error:
        print(f"Error loading config: {error}")
        return 1

def cmd_check_protocol(args):
    """Explain how to check protocol conformance (CLI not implemented)."""
    print(
        "check-protocol is not implemented: protocol conformance needs a "
        "language-specific type model.",
        file=sys.stderr,
    )
    print(
        "Use lashon.types.ProtocolChecker "
        "(register_protocol, conforms_to_protocol) directly.",
        file=sys.stderr,
    )
    return 2

def cmd_package_search(args):
    """Explain that remote package search is unavailable."""
    print(
        "package-search is not implemented: there is no remote registry "
        "backend.",
        file=sys.stderr,
    )
    print(
        "Use lashon.packaging.PackageRegistry with locally registered "
        "packages.",
        file=sys.stderr,
    )
    return 2

def cmd_package_install(args):
    """Explain that remote package installation is unavailable."""
    print(
        "package-install is not implemented: packages are resolved from a "
        "local PackageRegistry only.",
        file=sys.stderr,
    )
    print(
        "Register packages with PackageRegistry.register_package and resolve "
        "them from Python.",
        file=sys.stderr,
    )
    return 2

def cmd_refactor_rename(args):
    """Rename symbol."""
    from lashon.tooling.lsp.lsp_advanced import RefactoringEngine

    try:
        with open(args.file, encoding="utf-8") as f:
            source = f.read()

        refactor = RefactoringEngine()
        refactor.build_symbol_table(source)

        edits = refactor.rename(args.old_name, args.new_name, source)

        print(f"Renaming: {args.old_name} -> {args.new_name}")
        print("=" * 70)

        if not edits:
            print(f"Symbol '{args.old_name}' not found")
            return 1

        print(f"Found {len(edits)} occurrence(s)")

        # Apply edits
        lines = source.split("\n")
        edits.sort(key=lambda e: (e.line, e.start_col), reverse=True)
        for edit in edits:
            line = lines[edit.line]
            lines[edit.line] = (
                line[: edit.start_col] + edit.new_text + line[edit.end_col:]
            )

        result = "\n".join(lines)

        output_file = args.output or args.file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)

        print(f"✓ Refactoring complete: {output_file}")

        return 0

    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"Error: {error}")
        return 1

def cmd_format(args):
    """Format source code."""
    from lashon.tooling.lsp.lsp_advanced import CodeFormatter

    try:
        with open(args.file, encoding="utf-8") as f:
            source = f.read()

        formatter = CodeFormatter(tab_size=args.tab_size)
        formatted = formatter.format(source)

        if getattr(args, "check", False):
            if formatted != source:
                print(f"Would reformat: {args.file}")
                return 1
            print(f"✓ Already formatted: {args.file}")
            return 0

        output_file = args.output or (args.file if args.in_place else None)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(formatted)
            print(f"✓ Formatted: {output_file}")
        else:
            print(formatted)

        return 0

    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"Error: {error}")
        return 1

def cmd_test_run(args):
    """Run a project's pytest suite."""
    import pytest

    target = Path(args.path) if args.path else Path("tests")
    if not target.exists():
        print(f"Error: Test path not found: {target}")
        return 1

    pytest_args = [str(target), "-q"]
    if args.verbose:
        pytest_args.append("-v")
    if args.coverage:
        try:
            import pytest_cov  # noqa: F401
        except ImportError:
            print(
                "Error: --coverage requires pytest-cov "
                "(pip install pytest-cov)"
            )
            return 1
        pytest_args.extend(["--cov", "--cov-report=term-missing"])

    print(f"Running pytest on {target}")
    return int(pytest.main(pytest_args))

def cmd_debug_launch(args):
    """Start a DAP server for the given program."""
    from lashon.tooling.debug.dap_server import DAPServer

    path = Path(args.file)
    if not path.exists():
        print(f"Error: Program not found: {path}", file=sys.stderr)
        return 1

    server = DAPServer(port=args.port)
    server._program = str(path)
    server._config = args.config
    server._grammar = args.grammar
    if args.breakpoint:
        try:
            server.initial_breakpoints = {
                int(value) for value in args.breakpoint
            }
        except ValueError:
            print("Error: breakpoints must be line numbers", file=sys.stderr)
            return 1

    print(f"Debugging {path}", file=sys.stderr)
    print(
        f"DAP listening on tcp://{server.host}:{args.port}",
        file=sys.stderr,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0

