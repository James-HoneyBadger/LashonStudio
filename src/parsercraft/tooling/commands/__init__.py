"""CLI command implementations."""

from .codegen import cmd_codegen_c, cmd_codegen_llvm, cmd_codegen_wasm
from .config import (
    cmd_convert,
    cmd_create,
    cmd_delete,
    cmd_diff,
    cmd_edit,
    cmd_export,
    cmd_import,
    cmd_info,
    cmd_list_presets,
    cmd_update,
    cmd_validate,
)
from .config_tools import cmd_config
from .demo import cmd_demo
from .doctor import cmd_doctor
from .execution import (
    cmd_batch,
    cmd_repl,
    cmd_test,
    cmd_translate,
)
from .generics import cmd_generics
from .init import cmd_init
from .lint import cmd_lint
from .modules import cmd_module_cycles, cmd_module_deps, cmd_module_info
from .playground import cmd_play
from .run import cmd_run
from .tooling import (
    cmd_check_protocol,
    cmd_debug_launch,
    cmd_extension,
    cmd_format,
    cmd_lsp,
    cmd_package_install,
    cmd_package_search,
    cmd_refactor_rename,
    cmd_test_run,
)
from .typecheck import cmd_type_check

__all__ = [
    "cmd_batch",
    "cmd_check_protocol",
    "cmd_codegen_c",
    "cmd_codegen_llvm",
    "cmd_codegen_wasm",
    "cmd_config",
    "cmd_convert",
    "cmd_create",
    "cmd_debug_launch",
    "cmd_demo",
    "cmd_delete",
    "cmd_diff",
    "cmd_doctor",
    "cmd_edit",
    "cmd_export",
    "cmd_extension",
    "cmd_format",
    "cmd_generics",
    "cmd_import",
    "cmd_info",
    "cmd_init",
    "cmd_lint",
    "cmd_list_presets",
    "cmd_lsp",
    "cmd_module_cycles",
    "cmd_module_deps",
    "cmd_module_info",
    "cmd_package_install",
    "cmd_package_search",
    "cmd_play",
    "cmd_refactor_rename",
    "cmd_repl",
    "cmd_run",
    "cmd_test",
    "cmd_test_run",
    "cmd_translate",
    "cmd_type_check",
    "cmd_update",
    "cmd_validate",
]
