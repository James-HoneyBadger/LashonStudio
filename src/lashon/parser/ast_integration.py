"""Deprecated location — :mod:`lashon.codegen.ast_integration` is canonical.

Kept so existing ``from lashon.parser.ast_integration import ...`` imports
keep working; the adapters now live with the code generators they feed.
"""

from lashon.codegen.ast_integration import *  # noqa: F401,F403
from lashon.codegen.ast_integration import __all__  # noqa: F401
