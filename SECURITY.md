# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 4.x | ✅ |
| 3.x and older | ❌ |

## Reporting a vulnerability

Do **not** open a public issue for security problems. Report privately via
GitHub Security Advisories:

<https://github.com/James-HoneyBadger/LashonStudioStudio/security/advisories/new>

Include:

- affected version and Python version,
- a minimal reproduction (grammar/config + source),
- impact (code execution, file access, crash, denial of service),
- any suggested fix.

You can expect an acknowledgement within a few days. Please allow time for a fix
before public disclosure.

## Security model

Lashon is a **language construction framework, not a sandbox**:

- Generated Python is executed with `exec`; program source has full Python
  privileges.
- The REPL, `transpile_and_exec`, `batch`, and the Studio's Run action all execute
  code.
- `FFIBridge` calls native libraries through `ctypes`; native bugs can crash or
  corrupt the interpreter.
- The config REPL uses a restricted builtin set (`SAFE_BUILTINS`), which reduces
  accidental damage but is **not** a security boundary.
- The LSP, formatter, and refactorer read files you point them at; they do not
  restrict paths.
- Package registry features are local-only today; there is no download or
  signature verification path.

Treat language files, configs, and packages as trusted code. If you need
isolation, run generated programs in a subprocess or container with OS-level
restrictions.

## Dependency surface

Runtime: PyYAML. Development: pytest, ruff. There is no network I/O in the
library outside of the (unused) package-registry placeholders.
