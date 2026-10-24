"""Lashon IDE entry point.

The Studio implementation lives in :mod:`lashon.ide.studio_app`. This
module preserves the historical ``lashon.ide.app:main`` console entry
point while keeping the GUI code in its own module.
"""

from lashon.ide.studio_app import LashonIDE, main

__all__ = ["LashonIDE", "main"]


if __name__ == "__main__":  # pragma: no cover - GUI entry point
    main()
