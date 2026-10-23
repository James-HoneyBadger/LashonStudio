"""Command dispatch for the ``parsercraft`` console script.

The CLI is a thin shell: parse arguments, look up the handler, call it. All
behaviour lives in :mod:`parsercraft.tooling.commands`.
"""

from __future__ import annotations

import sys

from parsercraft.tooling.cli.parser import build_parser
from parsercraft.tooling.commands import (
    cmd_batch,
    cmd_check_protocol,
    cmd_codegen_c,
    cmd_codegen_llvm,
    cmd_codegen_wasm,
    cmd_config,
    cmd_convert,
    cmd_create,
    cmd_debug_launch,
    cmd_delete,
    cmd_demo,
    cmd_diff,
    cmd_doctor,
    cmd_edit,
    cmd_export,
    cmd_extension,
    cmd_format,
    cmd_generics,
    cmd_import,
    cmd_info,
    cmd_init,
    cmd_lint,
    cmd_list_presets,
    cmd_lsp,
    cmd_module_cycles,
    cmd_module_deps,
    cmd_module_info,
    cmd_package_install,
    cmd_package_search,
    cmd_play,
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


def main() -> int:
    """Main entry point for the CLI application."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "doctor": cmd_doctor,
        "config": cmd_config,
        "lint": cmd_lint,
        "demo": cmd_demo,
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
        "play": cmd_play,
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

    print(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":  # pragma: no cover - module entry point
    sys.exit(main())
