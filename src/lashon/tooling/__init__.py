"""
lashon.tooling — Developer tools for language authoring
and IDE integration.

This subpackage provides:

CLI (``lashon.tooling.cli.main``)
    30+ subcommands for the full language lifecycle:  create, validate,
    edit, info, export, import, diff, convert, update, list-presets,
    repl, batch, test, translate, delete, lsp, extension, type-check,
    module-info, module-deps, module-cycles, codegen-c, codegen-wasm,
    codegen-llvm, refactor-rename, format, debug-launch, test-run.

ErrorLocalizer
    Produce human-readable, optionally localised error messages with
    source-context display::

        loc = ErrorLocalizer(locale="es")
        msg = loc.format_error("unexpected_token", token="END", expected=";")

lsp/ — Language Server Protocol
    LSP server providing syntax highlighting, hover, completion, and
    go-to-definition for any language defined in Lashon.
    Start with:  ``lashon lsp --stdio``

debug/ — Debug Adapter Protocol
    DAP-compatible debugger adapter.  Launch with:
    ``lashon debug-launch program.src``
"""

from lashon.tooling.error_localization import ErrorLocalizer, ErrorMessage

__all__ = [
    "ErrorLocalizer",
    "ErrorMessage",
]
