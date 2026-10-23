"""Parse throughput benchmark: pure-Python engine vs the native backend.

    python benchmarks/parse_bench.py [--lines 2000] [--repeat 5]

The native backend is optional; without it the script still reports the
Python numbers and explains how to build it.
"""

from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

from parsercraft.parser import GrammarParser, PEGInterpreter, native

ROOT = Path(__file__).resolve().parents[1]
GRAMMAR = ROOT / "projects" / "aurora" / "grammar.peg"


def generate(lines: int) -> str:
    return "".join(f"x{i} = {i} * 2 ;\n" for i in range(lines))


def measure(call, repeat: int) -> tuple[float, float]:
    call()
    samples = []
    for _ in range(repeat):
        start = time.perf_counter()
        call()
        samples.append(time.perf_counter() - start)
    best = min(samples)
    return best, statistics.median(samples)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lines", type=int, default=2000)
    parser.add_argument("--repeat", type=int, default=5)
    args = parser.parse_args()

    grammar = GrammarParser().parse(GRAMMAR.read_text(encoding="utf-8"))
    source = generate(args.lines)
    size = len(source) / 1024

    python_best, python_median = measure(
        lambda: PEGInterpreter(grammar).parse(source), args.repeat
    )
    print(f"source                {size:.0f} KB / {args.lines} lines")
    print(
        f"python engine         {python_best * 1000:7.1f} ms  "
        f"{size / python_best:7.0f} KB/s (median {python_median * 1000:.1f} ms)"
    )

    if not native.available():
        print("native backend        not built — run scripts/build_native.sh")
        return

    module = native._load()
    grammar_json = native.grammar_to_json(grammar)
    rust_best, _ = measure(lambda: module.parse(grammar_json, source), args.repeat)
    end_best, end_median = measure(
        lambda: PEGInterpreter(grammar, backend="native").parse(source), args.repeat
    )

    print(
        f"native match + JSON   {rust_best * 1000:7.1f} ms  "
        f"{size / rust_best:7.0f} KB/s ({python_best / rust_best:.1f}x python)"
    )
    print(
        f"native end to end     {end_best * 1000:7.1f} ms  "
        f"{size / end_best:7.0f} KB/s (median {end_median * 1000:.1f} ms, "
        f"{python_best / end_best:.1f}x python)"
    )
    print(
        "note: end-to-end pays for JSON decoding plus SourceAST construction "
        "in Python,\n      which is why it trails the raw engine speed."
    )


if __name__ == "__main__":
    main()
