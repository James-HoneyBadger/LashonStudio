"""ParserCraft IDE entry point.

The Studio implementation lives in :mod:`parsercraft.ide.studio_app`. This
module preserves the historical ``parsercraft.ide.app:main`` console entry
point while keeping the GUI code in its own module.
"""

from parsercraft.ide.studio_app import ParserCraftIDE, main

__all__ = ["ParserCraftIDE", "main"]


if __name__ == "__main__":  # pragma: no cover - GUI entry point
    main()
