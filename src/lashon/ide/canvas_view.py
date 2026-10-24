"""Paint a :class:`lashon.runtime.graphics.Graphics` onto a Tk canvas.

The Studio's Canvas tab and the REPL's ``:canvas show`` window share this
renderer, so a drawing looks the same in both.
"""

from __future__ import annotations

import tkinter as tk
from typing import Optional

from lashon.ide.theme import Palette, get_palette
from lashon.runtime.graphics import Graphics


def render(canvas: tk.Canvas, graphics: Graphics,
           palette: Optional[Palette] = None) -> None:
    """Clear ``canvas`` and draw every recorded command, scaled to fit."""
    palette = palette or get_palette()
    width = max(1, canvas.winfo_width())
    height = max(1, canvas.winfo_height())
    canvas.delete("all")
    canvas.configure(bg=graphics.background or palette.bg)

    left, bottom, right, top = graphics.bounds()
    span_x = max(1.0, right - left)
    span_y = max(1.0, top - bottom)
    padding = 16
    scale = min(
        (width - 2 * padding) / span_x,
        (height - 2 * padding) / span_y,
    )
    offset_x = width / 2 - ((left + right) / 2) * scale
    offset_y = height / 2 + ((top + bottom) / 2) * scale

    def px(value: float) -> float:
        return offset_x + value * scale

    def py(value: float) -> float:
        return offset_y - value * scale

    background = graphics.background or palette.bg
    for op in graphics.ops:
        kind = op["op"]
        if kind == "clear":
            canvas.delete("all")
            canvas.configure(bg=background)
        elif kind == "bg":
            background = op["color"]
            canvas.configure(bg=background)
        elif kind == "line":
            canvas.create_line(
                px(op["x1"]), py(op["y1"]), px(op["x2"]), py(op["y2"]),
                fill=op["color"], width=max(1.0, op["width"] * scale),
                capstyle="round",
            )
        elif kind == "circle":
            radius = max(1.0, op["r"] * scale)
            canvas.create_oval(
                px(op["cx"]) - radius, py(op["cy"]) - radius,
                px(op["cx"]) + radius, py(op["cy"]) + radius,
                outline=op["color"],
                fill=op.get("fill") or "",
                width=max(1.0, op.get("width", 1.0)),
            )
        elif kind == "text":
            canvas.create_text(
                px(op["x"]), py(op["y"]), text=op["text"], anchor="sw",
                fill=op["color"], font=("Courier New", 11),
            )


class CanvasWindow(tk.Toplevel):
    """A standalone window that shows a drawing.

    Used by ``:canvas show`` in the REPL: the terminal keeps running while the
    window displays the latest surface.
    """

    def __init__(self, master: tk.Misc, graphics: Graphics,
                 palette: Optional[Palette] = None):
        super().__init__(master)
        self.graphics = graphics
        self.palette = palette or get_palette()
        self.title("Lashon Canvas")
        self.geometry("640x400")
        self.configure(bg=self.palette.bg)
        self.canvas = tk.Canvas(
            self, bg=self.palette.bg, highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.refresh())
        self.after(10, self.refresh)

    def refresh(self) -> None:
        """Repaint from the current recording."""
        render(self.canvas, self.graphics, self.palette)
