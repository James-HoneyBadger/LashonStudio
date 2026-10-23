"""ParserCraft Language Studio — headless controller.

The studio keeps a language project (metadata + PEG grammar + samples) and
exposes the complete construction pipeline without depending on Tkinter:

    validate grammar → parse source → inspect AST → run → generate backends

The GUI in :mod:`parsercraft.ide.app` is a thin shell around this class, which
keeps the interesting behaviour testable.
"""

from __future__ import annotations

import io
import json
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

from parsercraft.codegen.codegen_c import CCodeGenerator
from parsercraft.codegen.codegen_wasm import WasmGenerator
from parsercraft.codegen.llvm_ir import LLVMIRGenerator
from parsercraft.codegen.python_transpiler import PythonTranspiler
from parsercraft.config.language_config import LanguageConfig
from parsercraft.parser.grammar import (
    Grammar,
    GrammarParser,
    PEGInterpreter,
    PEGNode,
    PEGNodeType,
    SourceAST,
)

PROJECT_FILENAME = "language.yaml"
GRAMMAR_FILENAME = "grammar.peg"
SAMPLES_DIR = "samples"
SAMPLE_EXTENSIONS = (".aur", ".lang", ".src", ".pcr")

_STARTER_RULES: Dict[str, str] = {
    "program": "statement+",
    "statement": (
        "function_def / if_stmt / while_stmt / return_stmt / "
        "print_stmt / assignment / expr_stmt"
    ),
    "function_def": "'fn' IDENT '(' param_list? ')' block",
    "block": "'{' statement* '}'",
    "param_list": "IDENT (',' IDENT)*",
    "if_stmt": "'if' comparison block ('else' block)?",
    "while_stmt": "'while' comparison block",
    "return_stmt": "'return' expr ';'",
    "print_stmt": "'print' expr ';'",
    "assignment": "IDENT '=' expr ';'",
    "expr_stmt": "call ';'",
    "comparison": "expr ('==' / '!=' / '<=' / '>=' / '<' / '>') expr",
    "expr": "term (('+' / '-') term)*",
    "term": "factor (('*' / '/' / '%') factor)*",
    "factor": "call / NUMBER / STRING / boolean / IDENT / '(' expr ')'",
    "call": "IDENT '(' arg_list? ')'",
    "arg_list": "expr (',' expr)*",
    "boolean": "'true' / 'false'",
}


# ---------------------------------------------------------------------------
# Results and diagnostics
# ---------------------------------------------------------------------------

@dataclass
class Diagnostic:
    """A single studio diagnostic."""

    severity: str  # "error" | "warning" | "info"
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.severity.upper()}: {self.message}"


@dataclass
class StudioResult:
    """Outcome of a studio operation."""

    ok: bool
    text: str = ""
    error: str = ""
    diagnostics: List[Diagnostic] = field(default_factory=list)
    elapsed_ms: float = 0.0
    value: Any = None
    #: False when the backend emitted a deliberately partial translation.
    supported: bool = True
    warnings: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:  # pragma: no cover - trivial
        return self.ok

    @classmethod
    def failure(cls, error: str, elapsed_ms: float = 0.0,
                diagnostics: Optional[Iterable[Diagnostic]] = None) -> "StudioResult":
        diags = list(diagnostics or [])
        if not diags:
            diags = [Diagnostic("error", error)]
        return cls(False, error=error, diagnostics=diags, elapsed_ms=elapsed_ms)


# ---------------------------------------------------------------------------
# Grammar / config conversion
# ---------------------------------------------------------------------------

def rules_to_peg(rules: Dict[str, str]) -> str:
    """Render a ``grammar.rules`` mapping as editable PEG text."""
    width = max((len(name) for name in rules), default=0)
    return "\n".join(
        f"{name.ljust(width)} <- {pattern}" for name, pattern in rules.items()
    )


def peg_to_rules(text: str) -> Dict[str, str]:
    """Convert editable PEG text into a ``grammar.rules`` mapping.

    Supports continuation lines (indented or starting with ``|``) in the same
    way as :class:`~parsercraft.parser.grammar.GrammarParser`.
    """
    rules: Dict[str, str] = {}
    current: Optional[str] = None
    parts: List[str] = []

    def flush() -> None:
        nonlocal current, parts
        if current is not None:
            rules[current] = " ".join(part for part in parts if part).strip()
        current, parts = None, []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "<-" in line:
            flush()
            name, pattern = line.split("<-", 1)
            current = name.strip()
            parts = [pattern.strip()]
        elif current is not None:
            parts.append(line)
        else:
            raise ValueError(
                f"Invalid grammar line (expected 'rule <- pattern'): {raw_line!r}"
            )
    flush()

    if not rules:
        raise ValueError("Grammar is empty")
    return rules


def _iter_peg_nodes(node: PEGNode) -> Iterable[PEGNode]:
    yield node
    for child in node.children:
        yield from _iter_peg_nodes(child)


# ---------------------------------------------------------------------------
# Project model
# ---------------------------------------------------------------------------

@dataclass
class StudioProject:
    """A language project on disk."""

    name: str
    root: Path
    config_path: Path
    config: Dict[str, Any]
    grammar_text: str
    sample_path: Optional[Path] = None

    @classmethod
    def from_path(cls, path: str | Path) -> "StudioProject":
        """Load a project from a directory or language-config file."""
        candidate = Path(path).expanduser().resolve()
        if candidate.is_file():
            root = candidate.parent
            config_path = candidate
        else:
            root = candidate
            config_path = cls._find_config(root)
            if config_path is None:
                raise FileNotFoundError(
                    f"No language config found in project directory: {root}"
                )

        data = cls._read_config(config_path)
        grammar_path = root / str(data.get("grammar_file", GRAMMAR_FILENAME))
        if grammar_path.exists():
            grammar_text = grammar_path.read_text(encoding="utf-8")
        else:
            rules = (data.get("grammar") or {}).get("rules") or {}
            grammar_text = rules_to_peg(rules)

        sample_path = cls._find_sample(root)
        name = str(data.get("name") or root.name)
        return cls(
            name=name,
            root=root,
            config_path=config_path,
            config=data,
            grammar_text=grammar_text,
            sample_path=sample_path,
        )

    @staticmethod
    def _find_config(root: Path) -> Optional[Path]:
        direct = [root / PROJECT_FILENAME, root / "language.yml"]
        candidates = [p for p in direct if p.exists()]
        candidates += sorted(root.glob("*.lang.yaml"))
        candidates += sorted(root.glob("*.yaml"))
        candidates += sorted(root.glob("*.lang.json"))
        candidates += sorted(root.glob("*.json"))
        for path in candidates:
            if not path.is_file():
                continue
            try:
                data = StudioProject._read_config(path)
            except (OSError, ValueError):
                continue
            if "grammar" in data or "keywords" in data:
                return path
        return None

    @staticmethod
    def _read_config(path: Path) -> Dict[str, Any]:
        content = path.read_text(encoding="utf-8")
        if path.suffix.lower() in (".yaml", ".yml"):
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError(f"Configuration root must be a mapping: {path}")
        return data

    @staticmethod
    def _find_sample(root: Path) -> Optional[Path]:
        samples_dir = root / SAMPLES_DIR
        if not samples_dir.is_dir():
            return None
        samples = sorted(
            p for p in samples_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SAMPLE_EXTENSIONS
        )
        if not samples:
            return None
        for sample in samples:
            if sample.stem.lower() == "hello":
                return sample
        return samples[0]

    def sample_files(self) -> List[Path]:
        """List all sample programs in the project."""
        samples_dir = self.root / SAMPLES_DIR
        if not samples_dir.is_dir():
            return []
        return sorted(
            p for p in samples_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SAMPLE_EXTENSIONS
        )

    def language_config(self) -> LanguageConfig:
        """Build a :class:`LanguageConfig` from the project config."""
        return LanguageConfig.from_dict(self.config)

    def save(self) -> None:
        """Persist the project, syncing grammar text into the config."""
        compiled = GrammarParser().parse(self.grammar_text)
        grammar_cfg = self.config.get("grammar") or {}
        if grammar_cfg.get("start"):
            compiled.start_rule = str(grammar_cfg["start"])
        errors = compiled.validate()
        if errors:
            raise ValueError(
                "Grammar validation failed: " + "; ".join(errors)
            )

        rules = peg_to_rules(self.grammar_text)
        grammar = self.config.setdefault("grammar", {})
        grammar["rules"] = rules
        grammar.setdefault("start", "program")
        grammar.setdefault("skip_whitespace", True)

        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / GRAMMAR_FILENAME).write_text(
            self.grammar_text.rstrip() + "\n", encoding="utf-8"
        )

        if self.config_path.suffix.lower() in (".yaml", ".yml"):
            content = yaml.safe_dump(
                self.config, sort_keys=False, allow_unicode=True
            )
        else:
            content = json.dumps(self.config, indent=2)
        self.config_path.write_text(content, encoding="utf-8")

        samples_dir = self.root / SAMPLES_DIR
        samples_dir.mkdir(exist_ok=True)

    def summary(self) -> Dict[str, Any]:
        """Return a small summary for the UI."""
        grammar_cfg = self.config.get("grammar") or {}
        return {
            "name": self.name,
            "version": self.config.get("version", "0.0.0"),
            "root": str(self.root),
            "rules": len(grammar_cfg.get("rules") or {}),
            "keywords": len(self.config.get("keywords") or {}),
            "samples": len(self.sample_files()),
        }


# ---------------------------------------------------------------------------
# Studio controller
# ---------------------------------------------------------------------------

class LanguageStudio:
    """Drives grammar validation, parsing, execution, and code generation."""

    def __init__(self, project: Optional[StudioProject] = None):
        self.project = project
        self.grammar: Optional[Grammar] = None
        self.interpreter: Optional[PEGInterpreter] = None
        self.current_source: str = ""
        self.last_python: str = ""
        self._grammar_dirty = True

    # -- project lifecycle -------------------------------------------------

    @staticmethod
    def sample_project_path() -> Optional[Path]:
        """Locate the bundled Aurora reference project (source checkout)."""
        import os

        override = os.environ.get("PARSERCRAFT_SAMPLE_PROJECT")
        if override:
            path = Path(override).expanduser()
            if path.exists():
                return path

        here = Path(__file__).resolve()
        for parent in here.parents:
            candidate = parent / "projects" / "aurora"
            if candidate.is_dir():
                return candidate

        packaged = here.parent / "samples" / "aurora"
        return packaged if packaged.is_dir() else None

    def open_project(self, path: str | Path) -> StudioProject:
        """Open a project directory or language config."""
        self.project = StudioProject.from_path(path)
        self.invalidate_grammar()
        if self.project.sample_path:
            self.current_source = self.project.sample_path.read_text(
                encoding="utf-8"
            )
        return self.project

    def open_sample_project(self) -> StudioProject:
        """Open the bundled Aurora sample project."""
        path = self.sample_project_path()
        if path is None:
            raise FileNotFoundError("Bundled Aurora sample project not found")
        return self.open_project(path)

    def new_project(self, name: str, parent_dir: str | Path) -> StudioProject:
        """Scaffold a new language project inside ``parent_dir``."""
        slug = "".join(
            ch.lower() if ch.isalnum() else "-" for ch in name
        ).strip("-") or "my-language"
        root = Path(parent_dir).expanduser().resolve() / slug
        root.mkdir(parents=True, exist_ok=True)
        (root / SAMPLES_DIR).mkdir(exist_ok=True)

        config: Dict[str, Any] = {
            "name": name,
            "version": "0.1.0",
            "description": f"{name} — a language built with ParserCraft.",
            "author": "",
            "keywords": {
                "if": "if",
                "else": "else",
                "while": "while",
                "fn": "fn",
                "return": "return",
                "print": "print",
                "true": "true",
                "false": "false",
            },
            "syntax_options": {
                "single_line_comment": "//",
                "require_semicolons": True,
                "statement_terminator": ";",
            },
            "grammar": {
                "start": "program",
                "skip_whitespace": True,
                "comments": ["//.*"],
                "rules": dict(_STARTER_RULES),
            },
        }
        grammar_text = rules_to_peg(_STARTER_RULES)
        project = StudioProject(
            name=name,
            root=root,
            config_path=root / PROJECT_FILENAME,
            config=config,
            grammar_text=grammar_text,
            sample_path=root / SAMPLES_DIR / "hello.aur",
        )
        project.save()

        project.sample_path.write_text(
            '// Welcome to your new language!\n'
            'print "Hello from ' + name.replace('"', "'") + '!" ;\n',
            encoding="utf-8",
        )
        (root / "README.md").write_text(
            f"# {name}\n\n"
            f"A custom language created with ParserCraft Studio.\n\n"
            f"- `{PROJECT_FILENAME}` — keywords and grammar\n"
            f"- `{GRAMMAR_FILENAME}` — editable PEG grammar\n"
            f"- `{SAMPLES_DIR}/` — example programs\n\n"
            f"Open this directory in ParserCraft Studio to continue.\n",
            encoding="utf-8",
        )
        self.project = project
        self.invalidate_grammar()
        self.current_source = project.sample_path.read_text(encoding="utf-8")
        return project

    def save_project(self) -> None:
        """Persist the current project."""
        if self.project is None:
            raise ValueError("No project is open")
        self.project.save()

    def invalidate_grammar(self) -> None:
        """Mark the compiled grammar as stale."""
        self._grammar_dirty = True

    def set_grammar_text(self, text: str) -> None:
        """Update the editable grammar text."""
        if self.project is not None:
            self.project.grammar_text = text
        self.invalidate_grammar()

    def set_config(self, config: Dict[str, Any]) -> None:
        """Replace the project config (e.g. after editing YAML)."""
        if self.project is None:
            raise ValueError("No project is open")
        self.project.config = config
        self.invalidate_grammar()

    # -- grammar / parsing -------------------------------------------------

    def _apply_grammar_settings(self, grammar: Grammar) -> None:
        if self.project is None:
            return
        grammar_cfg = self.project.config.get("grammar") or {}
        if grammar_cfg.get("comments"):
            grammar.comment_patterns = list(grammar_cfg["comments"])
        if grammar_cfg.get("start"):
            grammar.start_rule = str(grammar_cfg["start"])
        if "skip_whitespace" in grammar_cfg:
            grammar.skip_whitespace = bool(grammar_cfg["skip_whitespace"])

    def validate_grammar(self, text: Optional[str] = None) -> StudioResult:
        """Parse and validate the current grammar text."""
        start = time.perf_counter()
        grammar_text = text if text is not None else (
            self.project.grammar_text if self.project else ""
        )
        grammar_text = grammar_text.strip()
        if not grammar_text:
            return StudioResult.failure("No grammar defined")

        try:
            grammar = GrammarParser().parse(grammar_text)
            self._apply_grammar_settings(grammar)
            errors = grammar.validate()
        except (ValueError, SyntaxError) as error:
            elapsed = (time.perf_counter() - start) * 1000
            return StudioResult.failure(str(error), elapsed)

        elapsed = (time.perf_counter() - start) * 1000
        diagnostics = [Diagnostic("error", message) for message in errors]
        if errors:
            return StudioResult(
                False,
                error="Grammar validation failed",
                diagnostics=diagnostics,
                elapsed_ms=elapsed,
            )

        self.grammar = grammar
        self.interpreter = PEGInterpreter(grammar)
        self._grammar_dirty = False
        if self.project is not None:
            self.project.grammar_text = grammar_text
        return StudioResult(
            True,
            text=f"Grammar OK — {len(grammar.rules)} rules",
            elapsed_ms=elapsed,
            value=grammar,
        )

    def _ensure_grammar(self) -> Optional[StudioResult]:
        if not self._grammar_dirty and self.interpreter is not None:
            return None
        result = self.validate_grammar()
        return None if result.ok else result

    def parse(self, source: Optional[str] = None) -> StudioResult:
        """Parse source text and return the AST."""
        start = time.perf_counter()
        failure = self._ensure_grammar()
        if failure is not None:
            return failure
        assert self.interpreter is not None

        source = source if source is not None else self.current_source
        self.current_source = source
        if not source.strip():
            return StudioResult.failure("No source code to parse")

        try:
            ast = self.interpreter.parse(source)
        except SyntaxError as error:
            elapsed = (time.perf_counter() - start) * 1000
            return StudioResult.failure(str(error), elapsed)
        except Exception as error:  # pragma: no cover - defensive
            elapsed = (time.perf_counter() - start) * 1000
            return StudioResult.failure(
                f"{type(error).__name__}: {error}", elapsed
            )

        elapsed = (time.perf_counter() - start) * 1000
        return StudioResult(
            True,
            text=ast.pretty(),
            elapsed_ms=elapsed,
            value=ast,
        )

    def transpile(self, source: Optional[str] = None) -> StudioResult:
        """Transpile source to Python without executing it."""
        parsed = self.parse(source)
        if not parsed.ok:
            return parsed
        ast: SourceAST = parsed.value
        try:
            python_code = PythonTranspiler().transpile(ast)
        except Exception as error:  # pragma: no cover - defensive
            return StudioResult.failure(
                f"{type(error).__name__}: {error}", parsed.elapsed_ms
            )
        self.last_python = python_code
        return StudioResult(
            True,
            text=python_code,
            elapsed_ms=parsed.elapsed_ms,
            value=python_code,
        )

    def run(self, source: Optional[str] = None) -> StudioResult:
        """Parse, transpile, and execute source, capturing stdout/stderr."""
        start = time.perf_counter()
        transpiled = self.transpile(source)
        if not transpiled.ok:
            return transpiled

        python_code: str = transpiled.value
        namespace: Dict[str, Any] = {}
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exec(python_code, namespace)  # noqa: S102
        except Exception as error:
            elapsed = (time.perf_counter() - start) * 1000
            return StudioResult(
                False,
                text=stdout.getvalue() + stderr.getvalue(),
                error=f"{type(error).__name__}: {error}",
                diagnostics=[Diagnostic("error", traceback.format_exc())],
                elapsed_ms=elapsed,
            )

        user_vars = {
            key: value for key, value in namespace.items()
            if not key.startswith("__")
        }
        elapsed = (time.perf_counter() - start) * 1000
        output = stdout.getvalue()
        if stderr.getvalue():
            output += stderr.getvalue()
        return StudioResult(
            True,
            text=output,
            elapsed_ms=elapsed,
            value=user_vars,
        )

    # -- code generation ---------------------------------------------------

    def generate(self, backend: str, source: Optional[str] = None) -> StudioResult:
        """Generate code for ``backend`` (python, c, wasm, llvm)."""
        backend = backend.lower()
        if backend == "python":
            return self.transpile(source)

        parsed = self.parse(source)
        if not parsed.ok:
            return parsed
        ast: SourceAST = parsed.value

        try:
            if backend == "c":
                text = CCodeGenerator().translate_source_ast(ast)
            elif backend == "wasm":
                text = WasmGenerator().translate_source_ast(ast).to_wat()
            elif backend == "llvm":
                text = LLVMIRGenerator().translate_source_ast(ast)
            else:
                return StudioResult.failure(f"Unknown backend: {backend}")
        except Exception as error:  # pragma: no cover - defensive
            return StudioResult.failure(
                f"{type(error).__name__}: {error}", parsed.elapsed_ms
            )

        warnings: List[str] = []
        supported = True
        if backend == "wasm":
            supported = False
            warnings.append(
                "WASM output is partial: function bodies, control flow, "
                "and prints are not emitted yet."
            )

        return StudioResult(
            True,
            text=text,
            elapsed_ms=parsed.elapsed_ms,
            value=text,
            supported=supported,
            warnings=warnings,
        )

    def generate_all(self, source: Optional[str] = None) -> Dict[str, StudioResult]:
        """Generate every backend for the current source."""
        return {
            backend: self.generate(backend, source)
            for backend in ("python", "c", "wasm", "llvm")
        }

    # -- UI helpers --------------------------------------------------------

    def highlight_keywords(self) -> List[str]:
        """Return keywords to highlight in the source editor."""
        words: set[str] = set()
        if self.project is not None:
            for mapping in self.project.config.get("keywords", {}).values():
                if isinstance(mapping, str):
                    words.add(mapping)
                elif isinstance(mapping, dict):
                    custom = mapping.get("custom")
                    if custom:
                        words.add(str(custom))

        grammar = self.grammar
        if grammar is None:
            try:
                text = self.project.grammar_text if self.project else ""
                if text.strip():
                    grammar = GrammarParser().parse(text)
            except (ValueError, SyntaxError):
                grammar = None

        if grammar is not None:
            for rule in grammar.rules.values():
                for node in _iter_peg_nodes(rule.pattern):
                    if (node.node_type == PEGNodeType.LITERAL
                            and isinstance(node.value, str)
                            and node.value.replace("_", "").isalnum()):
                        words.add(node.value)

        return sorted(words, key=lambda word: (-len(word), word))

    def ast_tree(self, ast: SourceAST) -> List[dict]:
        """Convert an AST to nested dictionaries for a Treeview."""
        def convert(node: SourceAST) -> dict:
            label = node.node_type
            if node.value is not None:
                label = f"{label}: {node.value!r}"
            return {
                "label": label,
                "children": [convert(child) for child in node.children],
            }

        return [convert(ast)]
