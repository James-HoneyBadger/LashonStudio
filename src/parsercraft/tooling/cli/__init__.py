"""Command-line interface package.

``parser`` builds the argparse tree, ``dispatch`` maps a parsed command to its
handler. ``parsercraft.tooling.cli:main`` remains the console entry point.
"""

from __future__ import annotations

from parsercraft.tooling.cli.dispatch import main
from parsercraft.tooling.cli.parser import build_parser

__all__ = ["build_parser", "main"]
