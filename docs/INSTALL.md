# ParserCraft — Installation & Setup

> Version 4.0.0 · Python 3.10+

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Install (Development)](#quick-install-development)
- [Production Install](#production-install)
- [Virtual Environment Setup](#virtual-environment-setup)
- [Optional Dependencies](#optional-dependencies)
- [Verifying the Installation](#verifying-the-installation)
- [Running the Test Suite](#running-the-test-suite)
- [Platform Notes](#platform-notes)
- [Upgrading](#upgrading)
- [Uninstalling](#uninstalling)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Requirement | Minimum | Recommended | Notes |
|---|---|---|---|
| Python | 3.10 | 3.12 – 3.14 | `python3 --version` to check; 3.14 is used in CI |
| pip | 22.0 | latest | `pip install --upgrade pip` |
| PyYAML | 6.0 | latest | Installed automatically |
| tkinter | any | — | Bundled with CPython; required for the IDE only |

No compiler or build tools are required. All code generation backends produce source-level output (Python, C, WAT, LLVM IR) rather than compiled binaries.

---

## Quick Install (Development)

Clone the repository and install in editable mode so changes to source files take effect immediately:

```bash
git clone https://github.com/James-HoneyBadger/ParserCraft.git
cd ParserCraft
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"     # includes pytest + ruff
```

This installs the `parsercraft`, `parsercraft-ide`, `parsercraft-repl`, and
`codex` entry-point commands. `pip install -e .` (without `[dev]`) is enough to
run the CLI, Studio, and REPL; the tests can also run from a checkout without
installing because `pyproject.toml` sets `pythonpath = ["src"]`.

---

## Production Install

For a clean, non-editable install:

```bash
pip install parsercraft
```

> **Note:** Until ParserCraft is published on PyPI, use the editable install from the cloned repository.

---

## Virtual Environment Setup

Using a virtual environment is strongly recommended to avoid polluting the system Python.

### Using `venv` (built-in)

```bash
python3 -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows PowerShell

pip install -e .
```

### Using `conda`

```bash
conda create -n parsercraft python=3.12
conda activate parsercraft
pip install -e .
```

### Deactivating

```bash
deactivate          # venv
conda deactivate    # conda
```

---

## Optional Dependencies

### Development extras

```bash
pip install -e ".[dev]"
```

Installs `pytest` and `ruff` for running the test suite and linting source.

### IDE extras

`tkinter` is bundled with CPython on most platforms. If it is missing:

```bash
# Fedora / RHEL / CentOS
sudo dnf install python3-tkinter

# Debian / Ubuntu
sudo apt install python3-tk

# macOS (Homebrew)
brew install python-tk
```

---

## Verifying the Installation

After installation, confirm the entry points are available:

```bash
parsercraft --version
# parsercraft 4.0.0

parsercraft list-presets
# Lists: python_like, js_like, ruby_like, ...

parsercraft-repl --help
# Usage information for the REPL launcher

parsercraft-ide --help
# Studio launcher (requires a display)
```

Quick smoke test from Python:

```python
from parsercraft.parser import GrammarParser, PEGInterpreter
from parsercraft.codegen import transpile_and_exec

grammar = GrammarParser().parse(
    'program <- statement+\n'
    'statement <- IDENT "=" expr ";"\n'
    'expr <- NUMBER'
)
ast = PEGInterpreter(grammar).parse("answer = 42 ;")
result = transpile_and_exec(ast)
assert result["answer"] == 42
print("Installation OK")
```

---

## Running the Test Suite

```bash
python -m pytest tests/ -v
```

Expected output: **335 tests passed**. The suite covers grammar parsing, all
four code-generation backends (including compile-and-run checks for C and LLVM
when toolchains are present), REPL, stdlib, FFI, error localization, incremental
parsing, types, modules, LSP, packaging, the debug adapter, and the Studio
(headless plus GUI when a display exists).

Run a single test module:

```bash
python -m pytest tests/test_grammar.py -v
```

Run with coverage (requires `pytest-cov`):

```bash
pip install pytest-cov
python -m pytest tests/ --cov=src/parsercraft --cov-report=term-missing
```

---

## Platform Notes

### Linux

All features are fully supported. `tkinter` may require a separate package (see [IDE extras](#optional-dependencies)).

### macOS

All features are supported. If `parsercraft-ide` fails to start with a display error, ensure you are not running in a headless terminal session.

```bash
# Confirm tkinter is available
python3 -c "import tkinter; tkinter._test()"
```

### Windows

- Use Command Prompt or PowerShell; Git Bash is supported but not required.
- Activate the virtual environment with `.venv\Scripts\activate`.
- `tkinter` is included with official CPython installers from python.org.
- Long path issues: enable long-path support in Windows settings or keep the project directory path short.

---

## Upgrading

```bash
# Editable install (development)
git pull
pip install -e .   # Re-installs if entry points changed

# PyPI install (production)
pip install --upgrade parsercraft
```

---

## Uninstalling

```bash
pip uninstall parsercraft
```

If installed in an editable mode, also remove the `.egg-link` or `__editable__` entry:

```bash
pip uninstall parsercraft
rm -rf src/parsercraft.egg-info
```

---

## Troubleshooting

### `parsercraft: command not found`

The script directory is not on your `PATH`. Check:

```bash
python -m parsercraft.tooling.cli --version   # always works
```

Or activate your virtual environment:
```bash
source .venv/bin/activate
parsercraft --version
```

### `ModuleNotFoundError: No module named 'yaml'`

PyYAML was not installed:

```bash
pip install PyYAML>=6.0
```

### `ModuleNotFoundError: No module named 'tkinter'`

See [IDE extras](#optional-dependencies) above.

### `ImportError` on Python 3.9 or older

ParserCraft uses `match` statements (Python 3.10+) and `X | Y` union types (Python 3.10+). Upgrade to Python 3.10 or later.

### Tests fail with `ImportError`

Run pytest from the repository root so `pythonpath = ["src"]` applies, or install
the package first:

```bash
python -m pytest -q
# or
pip install -e ".[dev]" && python -m pytest -q
```

### Tkinter IDE shows no window

On headless servers, set a display or use a remote desktop. The REPL and CLI do not require a display.

---

## Next steps

- [QUICKSTART.md](QUICKSTART.md) — build a language in ten minutes.
- [STUDIO_GUIDE.md](STUDIO_GUIDE.md) — tour the Studio.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — more failure modes.
- [docs/index.md](index.md) — the full documentation index.

*For further help, open an issue at [github.com/James-HoneyBadger/ParserCraft](https://github.com/James-HoneyBadger/ParserCraft/issues).*
