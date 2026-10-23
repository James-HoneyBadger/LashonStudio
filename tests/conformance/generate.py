"""Regenerate the conformance corpus.

Run from the repository root::

    python tests/conformance/generate.py

Each case records a grammar, a source program, and either the AST the engine
must produce or the error substring it must report. The same corpus is used to
check the pure-Python engine and to validate an alternative (native) engine
against it.
"""

from __future__ import annotations

import json
from pathlib import Path

from parsercraft.parser.grammar import GrammarParser, PEGInterpreter

ROOT = Path(__file__).resolve().parents[2]

AURORA = (ROOT / "projects" / "aurora" / "grammar.peg").read_text(encoding="utf-8")
CALC = """
program  <- statement+
statement <- print_stmt / assignment
print_stmt <- 'print' expr ';'
assignment <- IDENT '=' expr ';'
expr     <- term (('+' / '-') term)*
term     <- factor (('*' / '/' / '%') factor)*
factor   <- NUMBER / STRING / IDENT / '(' expr ')'
""".strip()

CASES = [
    ("assignment", AURORA, "x = 1 ;\n"),
    ("arithmetic", CALC, "x = (1 + 2) * 3 % 4 ;\nprint x ;\n"),
    ("print-string", CALC, 'print "hello" ;\n'),
    ("fizzbuzz-step", AURORA, 'i = 3 ;\nif i % 15 == 0 {\n  print "FizzBuzz" ;\n} else {\n  print i ;\n}\n'),
    ("while-loop", AURORA, "i = 0 ;\nwhile i < 3 {\n  i = i + 1 ;\n}\nprint i ;\n"),
    ("function", AURORA, "fn twice(x) {\n  return x * 2 ;\n}\nprint twice(21) ;\n"),
    ("comments", AURORA, "// leading comment\nx = 1 ; // trailing\n/* block\n comment */\nprint x ;\n"),
    ("missing-semicolon", AURORA, "x = 1\n"),
    ("bad-expression", AURORA, "y = ;\n"),
]


def main() -> None:
    cases = []
    for name, grammar_text, source in CASES:
        grammar = GrammarParser().parse(grammar_text)
        entry = {"name": name, "grammar": grammar_text, "source": source}
        try:
            ast = PEGInterpreter(grammar).parse(source)
            entry["expect"] = {"ok": True, "ast": ast.to_dict()}
        except SyntaxError as error:
            entry["expect"] = {
                "ok": False,
                "error_contains": str(error).splitlines()[0],
            }
        cases.append(entry)

    out = Path(__file__).with_name("cases.json")
    out.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(cases)} cases to {out}")


if __name__ == "__main__":
    main()
