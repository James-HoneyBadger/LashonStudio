"""Command-line interface package.

``parser`` builds the argparse tree, ``dispatch`` maps a parsed command to its
handler. ``lashon.tooling.cli:main`` remains the console entry point.
"""

from __future__ import annotations

from lashon.tooling.cli.dispatch import main
from lashon.tooling.cli.parser import build_parser

__all__ = ["build_parser", "main"]
