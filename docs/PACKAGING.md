# Packaging and Distribution

This page covers packaging **ParserCraft itself**, generating artifacts **for the
languages you build** (VS Code extensions, reference docs), and the local
package registry/semver helpers.

---

## ParserCraft distribution

### Layout

```
pyproject.toml      PEP 621 metadata, entry points, package data, tool config
MANIFEST.in         sdist-only extras (docs, configs, projects, samples)
src/parsercraft/    the package
src/codex/          CodeEx IDE (legacy second IDE, `codex` entry point)
```

There is no `setup.py`: packaging is fully declarative, and the version is
single-sourced from `parsercraft.__version__` via
`[tool.setuptools.dynamic]`.

### Build

```bash
python -m build                 # dist/parsercraft-4.0.0-py3-none-any.whl + .tar.gz
# or
python -m pip wheel . -w dist
```

`build` and `twine` are in the `release` extra:

```bash
pip install -e ".[release]"
python -m build
twine check dist/*
```

### Install

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"         # editable + pytest + ruff
pip install -e .                # runtime only
```

### Entry points

| Command | Target | Purpose |
|---|---|---|
| `parsercraft` | `parsercraft.tooling.cli:main` | full CLI |
| `parsercraft-ide` | `parsercraft.ide.app:main` | Studio (Tkinter) |
| `parsercraft-repl` | `parsercraft.runtime.repl:main` | REPL entry point |
| `codex` | `codex.codex:main` | CodeEx IDE (legacy, separate package) |

### Package data

- `parsercraft`: `*.json`, `*.yaml`
- `parsercraft.ide`: the packaged Aurora sample (`samples/aurora/**`)

The Studio looks for sample projects in this order:

1. `$PARSERCRAFT_SAMPLE_PROJECT` (if set)
2. `<repo>/projects/aurora`
3. `parsercraft/ide/samples/aurora` (installed wheel)

`MANIFEST.in` additionally ships `docs/`, `configs/`, `demos/`, `projects/`, and
`tests/` in the sdist so source distributions can run the suite.

### Requirements

- Python `>=3.10` (tested through 3.14)
- `PyYAML>=6.0` at runtime
- `pytest>=7` and `ruff>=0.6` in the `dev` extra
- Tkinter for the Studio (bundled with python.org installers; `python3-tk` on
  Debian/Ubuntu)

### Verifying a wheel

```bash
python -m build
python -m venv /tmp/check && /tmp/check/bin/pip install dist/*.whl
/tmp/check/bin/parsercraft list-presets
/tmp/check/bin/python -c "from parsercraft.ide.studio import LanguageStudio; print(LanguageStudio().sample_project_path())"
```

The second command must print a path inside the installed package — that proves
the Aurora sample shipped.

---

## VS Code extension

### Generate

```bash
parsercraft extension --config projects/aurora/language.yaml \
  --output ./aurora-vscode --publisher my-org --version 1.0.0
```

This writes:

| File | Contents |
|---|---|
| `package.json` | language id/aliases/extension, grammar contribution, LSP command |
| `language-configuration.json` | comments, brackets, auto-closing pairs |
| `syntaxes/language.tmLanguage.json` | TextMate grammar with comments/strings/numbers/keywords/functions/variables |
| `extension.ts` | `LanguageClient` bootstrap using the `out/server.js` module |
| `README.md`, `.gitignore` | basic scaffolding |

### What you still need

The generator does **not** produce a compiled extension or a language-server
entry point. To ship it:

1. Add an `out/server.js` (or point `serverModule` elsewhere) that starts a
   ParserCraft LSP process. A simple approach is a Node script that spawns
   `parsercraft lsp --config language.yaml --stdio` and bridges streams, since
   the server's stdio loop is the supported transport.
2. Add `package.json` dependencies (`vscode-languageclient`, `typescript`) and a
   `tsconfig.json`.
3. Compile (`npm install && npm run compile`) so `main` (`./out/extension.js`)
   exists.
4. Press `F5` in VS Code (Extension Development Host) or package with `vsce`.

Language id and file extension are derived from the config name
(`Aurora` → id `aurora`, extension `.aur`).

---

## Reference documentation generator

`DocumentationGenerator` renders a language reference from a `LanguageConfig`.

```python
from parsercraft.config import LanguageConfig
from parsercraft.packaging import DocumentationGenerator

config = LanguageConfig.load("projects/aurora/language.yaml")
docs = DocumentationGenerator()

markdown = docs.generate_markdown(config)   # str
html = docs.generate_html(config)           # str
docs.save_markdown(config, "REFERENCE.md")
docs.save_html(config, "reference.html")
```

The output contains version/description/author metadata, a table of contents,
and tables for keywords, built-in functions (with arity/status/description),
operators, syntax options, and examples. Timestamps are generated at call time,
so generated files change on every run — commit them deliberately or generate
in CI.

---

## Package registry and semver

`PackageRegistry` is an **in-memory/local** registry: there is no network
backend, and the `package-search`/`package-install` CLI commands exit 2 with an
explanation.

```python
from pathlib import Path
from parsercraft.packaging import PackageRegistry, Package
from parsercraft.packaging.package_registry import Version

registry = PackageRegistry()

# Register explicitly
registry.register_package(Package(
    name="aurora-stdlib",
    version=Version.parse("1.2.0"),
    description="Standard library for Aurora",
    dependencies={"aurora-core": "^1.0.0"},
))

# Record a local package directory for future resolution
registry.register_local(Path("./packages"))   # appends to registry.local_paths

pkg = registry.resolve("aurora-stdlib", "^1.0.0")     # Package | None
deps = registry.resolve_dependencies(pkg, include_dev=False)
problems = registry.check_conflicts(deps)

lock = registry.create_lock_file(deps)
# {'version': '1.0', 'packages': {...}, 'timestamp': '...'}

loaded = registry.load_lock_file("parsercraft.lock")
```

### Version and constraints

```python
from parsercraft.packaging.package_registry import Version

v = Version.parse("1.2.3-beta.1")
v.major, v.minor, v.patch, v.prerelease      # 1, 2, 3, 'beta.1'
Version.parse("1.2.3") > Version.parse("1.2.3-beta.1")   # True
```

Prereleases participate in ordering and equality; build metadata is parsed but
ignored. `Version` is hashable and comparable.

Constraint syntax (`VersionConstraint.parse`):

| Form | Meaning |
|---|---|
| `1.2.3` | caret by default: `>=1.2.3 <2.0.0` |
| `^1.2.3` | same as above |
| `~1.2.3` | `>=1.2.3 <1.3.0` |
| `>=1.2.3`, `>1.2.3`, `<=1.2.3`, `<1.2.3` | comparisons |
| `==1.2.3` | exact match |

**All constraints require a full `major.minor.patch`.** `~1.2`, `1.x`, and `*`
raise `ValueError: Invalid version: ...`.

### Limits

- No registry server, authentication, download, or integrity verification;
  `integrity` is a stored string.
- `register_local` only records the directory in `local_paths`; it does not scan
  or register packages found there. Register `Package` objects explicitly.
- Resolution picks the highest matching registered version and does not do
  backtracking; `check_conflicts` only reports mismatches for dependencies that
  are already resolved.
- Lock files are JSON dictionaries; they are not interoperable with npm or pip.

---

## Documentation site

The docs are built with MkDocs Material:

```bash
pip install -e ".[docs]"
mkdocs serve          # http://127.0.0.1:8000
mkdocs build          # static site in site/
```

`.github/workflows/docs.yml` builds and deploys to GitHub Pages on pushes that
touch `docs/`, `mkdocs.yml`, or `pyproject.toml`. The site landing page is
[docs/index.md](index.md); the full index lives there too.

## Publishing a language (not a Python package)

If you want to distribute a *language* rather than ParserCraft:

1. Ship a project directory like `projects/aurora`: `language.yaml`,
   `grammar.peg`, `samples/`, and a README.
2. Users open it with `parsercraft-ide` (Studio) or run
   `parsercraft repl language.yaml` / `parsercraft codegen-c ...`.
3. Optionally generate a VS Code extension (above) and a reference
   (`DocumentationGenerator`).
4. Keep the grammar in one place. The Studio writes `grammar.peg` back into
   `language.yaml` on save, so hand edits to `language.yaml` alone can be
   overwritten the next time the Grammar tab is saved.

---

## See also

- [INSTALL.md](INSTALL.md) — environments and platform notes.
- [LSP_AND_DEBUGGING.md](LSP_AND_DEBUGGING.md) — the server the extension talks
  to.
- [CLI_REFERENCE.md](CLI_REFERENCE.md#packaging-helpers) — command status.
