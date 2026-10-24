"""Deprecated alias for :mod:`lashon`.

ParserCraft was renamed to Lashon Studio. This module exists so existing
``import parsercraft`` statements keep working for one release; it re-exports
the public API and warns once. Migrate to ``import lashon``.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
import warnings

import lashon as _lashon
from lashon import *  # noqa: F403
from lashon import __version__  # noqa: F401

__all__ = list(getattr(_lashon, "__all__", []))

warnings.warn(
    "The 'parsercraft' package was renamed to 'lashon' (Lashon Studio); "
    "import 'lashon' instead.",
    DeprecationWarning,
    stacklevel=2,
)

class _AliasLoader(importlib.abc.Loader):
    """Import the ``lashon`` module and alias it under the old name."""

    def __init__(self, target: str):
        self.target = target

    def create_module(self, spec):
        return importlib.import_module(self.target)

    def exec_module(self, module) -> None:  # already executed by create_module
        return None


class _AliasFinder(importlib.abc.MetaPathFinder):
    """Map ``parsercraft.<path>`` onto ``lashon.<path>`` for every submodule."""

    prefix = "parsercraft."
    replacement = "lashon."

    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(self.prefix):
            return None
        counterpart = self.replacement + fullname[len(self.prefix):]
        try:
            if importlib.util.find_spec(counterpart) is None:
                return None
        except (ImportError, AttributeError, ValueError):
            return None
        return importlib.util.spec_from_loader(
            fullname, _AliasLoader(counterpart)
        )


if not any(isinstance(finder, _AliasFinder) for finder in sys.meta_path):
    sys.meta_path.append(_AliasFinder())


def __getattr__(name: str):
    """Forward every other attribute (submodules, helpers) to :mod:`lashon`."""
    try:
        return getattr(_lashon, name)
    except AttributeError as error:
        raise AttributeError(f"module 'parsercraft' has no attribute {name!r}") from error
