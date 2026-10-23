# Contributing to ParserCraft

Thanks for helping. This guide covers environment setup, standards, and the
review checklist. For architecture and API context, see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/TECHNICAL_REFERENCE.md](docs/TECHNICAL_REFERENCE.md).

---

## Setup

```bash
git clone https://github.com/James-HoneyBadger/ParserCraft.git
cd ParserCraft
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -q          # 322 passing
python -m pytest -q --cov --cov-fail-under=45
ruff check src tests
```

Requirements: Python 3.10+ (3.14 used in CI), PyYAML. Tkinter is needed only for
the Studio and its GUI tests.

No install is required to run tests from a checkout: `pyproject.toml` sets
`pythonpath = ["src"]` and `testpaths = ["tests"]`.

---

## Standards

- **Python style:** `ruff check src tests` must pass. The configured rule set is
  `E4`, `E7`, `E9`, `F`, `I` with line length 120.
- **Types:** annotate public functions and classes; avoid `Any` where a precise
  type is practical.
- **Errors:** raise specific exceptions with actionable messages; user-facing CLI
  errors return exit code 1 instead of tracebacks.
- **Comments:** explain non-obvious decisions only. Prefer clear names.
- **Dependencies:** runtime dependencies require justification — the framework
  currently needs only PyYAML.
- **Backends:** keep `translate_source_ast(ast)` as the entry point and document
  fidelity limitations in the docstring.

---

## Tests

- Add a regression test for every bug fix.
- Keep existing tests passing; do not weaken assertions to make a change fit.
- Toolchain-dependent tests (C, LLVM) should skip when the compiler is missing.
- CI gates: ruff, docs link/example checks, Python 3.10–3.14, a 45% coverage
  floor on 3.12, Windows/macOS smoke tests, and `python -m build` + `twine
  check`.
- GUI tests must skip without a display.
- Run targeted tests first, then the full suite:

```bash
python -m pytest tests/test_codegen.py -q
python -m pytest -q
```

- Coverage helper:

```bash
pip install pytest-cov
python -m pytest tests/ --cov=src/parsercraft --cov-report=term-missing
```

---

## Documentation

- Every user-visible change needs a docs update in `docs/` (index:
  [docs/README.md](docs/README.md)).
- Verify snippets by running them; docs claim what the code actually does,
  including limitations.
- Relative links must resolve, including anchors.
- CLI changes require an update to
  [docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md) and its maturity table.

---

## Commit and PR checklist

- [ ] `ruff check src tests` clean
- [ ] `python -m pytest -q` green (report the count)
- [ ] Docs updated (and links checked)
- [ ] New behaviour covered by tests
- [ ] No secrets, caches, or build artifacts committed
- [ ] Commit messages describe the behaviour change, not just the files touched

Example:

```
fix(codegen): emit string formats and loop bodies in C

- track declared variables to avoid re-declaring in loops
- unwrap block nodes and emit else branches
- add regression tests for functions, branches, and loops
```

---

## Reporting issues

Include:

1. ParserCraft version (`parsercraft --version`) and Python version.
2. Minimal grammar/config plus the smallest source input that reproduces it.
3. The exact command and full output/traceback.
4. Expected vs actual behaviour.

Open issues at
<https://github.com/James-HoneyBadger/ParserCraft/issues>. For security reports,
follow [SECURITY.md](SECURITY.md) instead of filing a public issue.

---

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
