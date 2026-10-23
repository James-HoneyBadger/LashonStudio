"""Deprecated location — :mod:`parsercraft.codegen.ast_integration` is canonical.

Kept so existing ``from parsercraft.parser.ast_integration import ...`` imports
keep working; the adapters now live with the code generators they feed.
"""

from parsercraft.codegen.ast_integration import *  # noqa: F401,F403
from parsercraft.codegen.ast_integration import __all__  # noqa: F401
