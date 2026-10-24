"""Run the REPL with a drawing window beside the prompt.

The REPL itself lives in :mod:`lashon.runtime.repl` and stays free of Tk, so
the console can run anywhere. This adapter — the entry point behind
``lashon-repl`` — installs a canvas host, which is what makes ``:canvas show``
and ``--canvas`` paint the drawing while the prompt keeps running.
"""

from __future__ import annotations

import sys
from typing import Any, Optional

from lashon.runtime.repl import run_repl


class TkCanvasHost:
    """Shows a :class:`lashon.runtime.graphics.Graphics` in a Tk window."""

    def __init__(self) -> None:
        self._root: Any = None
        self._window: Any = None

    def _ensure_root(self) -> Any:
        if self._root is None:
            import tkinter as tk

            self._root = tk.Tk()
            self._root.withdraw()
        return self._root

    def show(self, graphics: Any) -> None:
        """Open the window, or refresh it if it is already open."""
        from lashon.ide.canvas_view import CanvasWindow

        root = self._ensure_root()
        if self._window is None:
            self._window = CanvasWindow(root, graphics)
        else:
            self._window.graphics = graphics
            self._window.deiconify()
            self._window.refresh()
        if self._root is not None:
            self._root.update()

    def refresh(self, graphics: Any) -> None:
        """Repaint an open window; do nothing when it is closed."""
        if self._window is None:
            return
        self._window.graphics = graphics
        self._window.refresh()
        if self._root is not None:
            self._root.update()


def main(argv: Optional[list[str]] = None) -> int:
    """``lashon-repl`` — the REPL with a canvas host attached."""
    return run_repl(argv=argv, canvas_host=TkCanvasHost())


if __name__ == "__main__":  # pragma: no cover - console entry point
    sys.exit(main())


__all__ = ["TkCanvasHost", "main"]
