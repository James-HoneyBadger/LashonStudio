"""Documentation health checks: links, anchors, and headline examples."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from parsercraft.codegen import transpile_and_exec
from parsercraft.parser import GrammarParser, PEGInterpreter

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def _markdown_files() -> list[Path]:
    return sorted([*ROOT.glob("*.md"), *DOCS.glob("*.md")])


def _slug(heading: str) -> str:
    text = heading.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return text.replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    headings = re.findall(r"^#{1,6}\s+(.*)$", text, re.MULTILINE)
    return {_slug(heading) for heading in headings}


def _links_without_code(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", "", text)
    return [m.group(1).split()[0] for m in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text)]


def _peg_blocks(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return re.findall(r"```peg\n(.*?)```", text, re.DOTALL)


def test_documentation_links_and_anchors_resolve():
    anchors = {path: _anchors(path) for path in _markdown_files()}
    broken: list[str] = []

    for path in _markdown_files():
        for link in _links_without_code(path):
            if link.startswith(("http://", "https://", "mailto:")):
                continue
            target_text, _, fragment = link.partition("#")
            target = (path.parent / target_text).resolve() if target_text else path
            if target_text and not target.exists():
                broken.append(f"{path.relative_to(ROOT)}: missing {link}")
                continue
            if fragment and target.suffix == ".md":
                if _slug(fragment.replace("-", " ")) not in anchors.get(target, set()):
                    broken.append(f"{path.relative_to(ROOT)}: missing anchor {link}")

    assert not broken, "Broken documentation links:\n" + "\n".join(broken)


def test_docs_index_lists_every_page():
    index = (DOCS / "README.md").read_text(encoding="utf-8")
    missing = [
        page.name
        for page in sorted(DOCS.glob("*.md"))
        if page.name != "README.md" and f"({page.name})" not in index
    ]
    assert not missing, f"docs/README.md does not link: {missing}"


def test_quickstart_mini_grammar_example_runs():
    grammar_text = _peg_blocks(DOCS / "QUICKSTART.md")[0]
    grammar = GrammarParser().parse(grammar_text)
    assert grammar.validate() == []

    ast = PEGInterpreter(grammar).parse("x = 2 + 3 * 4 ;")
    assert transpile_and_exec(ast) == {"x": 14}


def test_quickstart_control_flow_example_runs():
    grammar_text = _peg_blocks(DOCS / "QUICKSTART.md")[1]
    grammar = GrammarParser().parse(grammar_text)
    interpreter = PEGInterpreter(grammar)

    source = """
i = 0 ;
sum = 0 ;
while i < 5 {
  i = i + 1 ;
  sum = sum + i ;
}
"""
    assert transpile_and_exec(interpreter.parse(source)) == {"i": 5, "sum": 15}


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("hello", set()),
        ("fibonacci", {"fib", "fact"}),
        ("fizzbuzz", {"fizzbuzz"}),
    ],
)
def test_aurora_samples_parse_and_run(name: str, expected: set[str]):
    project = ROOT / "projects" / "aurora"
    grammar = GrammarParser().parse((project / "grammar.peg").read_text(encoding="utf-8"))
    source = (project / "samples" / f"{name}.aur").read_text(encoding="utf-8")

    ast = PEGInterpreter(grammar).parse(source)
    runtime = transpile_and_exec(ast)
    assert set(runtime) == expected
