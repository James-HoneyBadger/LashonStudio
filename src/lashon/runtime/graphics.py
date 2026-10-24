"""A drawing surface for languages built with Lashon.

Generated Python draws through ``turtle.*`` calls. Instead of forcing a
display — Python's own ``turtle`` module opens a Tk window the moment you
move — those calls are routed to a *recorder*: a flat list of drawing
commands that any front end can replay.

Three front ends use it:

* the Studio's **Canvas** tab replays the recording after every run,
* the REPL keeps one surface alive across evaluations and can save it as
  SVG or show it in a window (``:canvas``),
* ``lashon run --canvas out.svg`` writes the drawing to a file.

A program run outside Lashon still works: :func:`attach` hands back a
per-process recorder, so generated Python never needs a screen.
"""

from __future__ import annotations

import math
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterator, List, Optional, Tuple

WIDTH = 640
HEIGHT = 400

#: CGA colours, the palette BASIC dialects number 0–15.
CGA: Dict[int, str] = {
    0: "#000000", 1: "#0000aa", 2: "#00aa00", 3: "#00aaaa",
    4: "#aa0000", 5: "#aa00aa", 6: "#aa5500", 7: "#aaaaaa",
    8: "#555555", 9: "#5555ff", 10: "#55ff55", 11: "#55ffff",
    12: "#ff5555", 13: "#ff55ff", 14: "#ffff55", 15: "#ffffff",
}

DEFAULT_PEN = "#33ff66"


def normalize_color(value: Any) -> str:
    """Turn a CGA index, RGB triple, or colour name into something paintable."""
    if isinstance(value, bool):
        return DEFAULT_PEN
    if isinstance(value, int):
        return CGA.get(value, "#aaaaaa")
    if isinstance(value, (tuple, list)) and len(value) >= 3:
        red, green, blue = (max(0, min(255, int(part))) for part in value[:3])
        return f"#{red:02x}{green:02x}{blue:02x}"
    text = str(value).strip().lower()
    return text or DEFAULT_PEN


class Graphics:
    """A recorded drawing surface with a turtle-compatible API.

    Coordinates are turtle coordinates: the origin sits at the centre of the
    surface and ``y`` grows upwards. Front ends flip that when they paint.
    """

    def __init__(self, width: int = WIDTH, height: int = HEIGHT,
                 background: str = "#000000"):
        self.width = int(width)
        self.height = int(height)
        self.background = normalize_color(background)
        self.ops: List[Dict[str, Any]] = []
        self._x = 0.0
        self._y = 0.0
        self._heading = 0.0
        self._pen_down = True
        self._color = DEFAULT_PEN
        self._pen_width = 1.0

    @contextmanager
    def active(self) -> Iterator["Graphics"]:
        """Route drawing calls in this block to this surface."""
        token = _active.set(self)
        try:
            yield self
        finally:
            _active.reset(token)

    # -- state ---------------------------------------------------------

    def __len__(self) -> int:
        return len(self.ops)

    def __repr__(self) -> str:
        return f"Graphics({len(self.ops)} ops, pen={self._color})"

    @property
    def position(self) -> Tuple[float, float]:
        return (self._x, self._y)

    @property
    def heading(self) -> float:
        return self._heading

    def clear(self) -> None:
        """Erase the surface."""
        self.ops.append({"op": "clear"})
        self._x = self._y = 0.0
        self._heading = 0.0
        self._pen_down = True

    #: ``turtle.reset`` restores the pen as well as the surface.
    def reset(self) -> None:
        self.clear()
        self._color = DEFAULT_PEN
        self._pen_width = 1.0
        self.background = "#000000"

    # -- motion --------------------------------------------------------

    def forward(self, distance: Any = 0) -> None:
        """Move the pen ``distance`` units along the current heading."""
        step = float(distance)
        radians = math.radians(self._heading)
        self._move_to(
            self._x + step * math.cos(radians),
            self._y + step * math.sin(radians),
        )

    fd = forward

    def backward(self, distance: Any = 0) -> None:
        self.forward(-float(distance))

    bk = backward
    back = backward

    def left(self, degrees: Any = 0) -> None:
        self._heading += float(degrees)

    lt = left

    def right(self, degrees: Any = 0) -> None:
        self._heading -= float(degrees)

    rt = right

    def setheading(self, degrees: Any = 0) -> None:
        self._heading = float(degrees)

    seth = setheading

    def home(self) -> None:
        self.goto(0, 0)
        self._heading = 0.0

    def goto(self, x: Any = 0, y: Any = None) -> None:
        """Move to ``(x, y)`` drawing a line when the pen is down."""
        if y is None:
            pair = x
            x, y = pair[0], pair[1]
        self._move_to(float(x), float(y))

    setpos = goto
    setposition = goto

    def _move_to(self, x: float, y: float) -> None:
        if self._pen_down:
            self.ops.append({
                "op": "line",
                "x1": self._x, "y1": self._y,
                "x2": x, "y2": y,
                "color": self._color, "width": self._pen_width,
            })
        self._x, self._y = x, y

    # -- pen -----------------------------------------------------------

    def penup(self) -> None:
        self._pen_down = False

    pu = penup
    up = penup

    def pendown(self) -> None:
        self._pen_down = True

    pd = pendown
    down = pendown

    def isdown(self) -> bool:
        return self._pen_down

    def color(self, *args: Any, **_kwargs: Any) -> None:
        """Set the pen colour: name, CGA index, or ``(r, g, b)``."""
        if args:
            self._color = normalize_color(args[0])

    pencolor = color

    def width(self, value: Any = 1) -> None:
        self._pen_width = max(1.0, float(value))

    pensize = width

    # -- shapes --------------------------------------------------------

    def circle(self, radius: Any = 0, extent: Any = None, steps: Any = None) -> None:
        """A circle centred ``radius`` units to the left of the heading."""
        span = 360.0 if extent is None else float(extent)
        del steps  # polygons are not worth the complexity here
        if span >= 360.0:
            radians = math.radians(self._heading)
            cx = self._x - float(radius) * math.sin(radians)
            cy = self._y + float(radius) * math.cos(radians)
            self.ops.append({
                "op": "circle", "cx": cx, "cy": cy, "r": abs(float(radius)),
                "color": self._color, "width": self._pen_width,
            })
            return
        segments = max(2, int(abs(span) / 10) + 1)
        for index in range(segments):
            self.forward(2 * math.pi * float(radius) * abs(span) / 360 / segments)
            self.left(span / segments)

    def dot(self, size: Any = 4) -> None:
        """A filled dot at the current position."""
        self.ops.append({
            "op": "circle", "cx": self._x, "cy": self._y,
            "r": max(1.0, float(size) / 2),
            "color": self._color, "width": 0.0, "fill": self._color,
        })

    def write(self, text: Any = "", move: bool = False, align: str = "left",
              font: Any = None) -> None:
        """Draw text at the current position."""
        del font
        self.ops.append({
            "op": "text", "x": self._x, "y": self._y,
            "text": str(text), "color": self._color, "align": align,
        })
        if move:
            self.forward(0)

    def bgcolor(self, value: Any = None) -> None:
        if value is None:
            return
        self.background = normalize_color(value)
        self.ops.append({"op": "bg", "color": self.background})

    # -- turtle API we accept but do not draw --------------------------

    def speed(self, *_args: Any, **_kwargs: Any) -> None:
        """Recording has no notion of speed."""

    def tracer(self, *_args: Any, **_kwargs: Any) -> None:
        """Nothing to trace when drawing is deferred."""

    def update(self) -> None:
        """Nothing to flush."""

    def hideturtle(self) -> None:
        """The cursor is not painted, so hiding it is a no-op."""

    ht = hideturtle
    showturtle = hideturtle
    st = hideturtle

    def begin_fill(self) -> None:
        """Fills are not supported; the outline still draws."""

    def end_fill(self) -> None:
        """Counterpart to :meth:`begin_fill`."""

    def done(self) -> None:
        """A recorded surface has no event loop to enter."""

    exitonclick = done
    bye = done

    def title(self, *_args: Any, **_kwargs: Any) -> None:
        """Window titles do not apply to a recording."""

    def setup(self, *_args: Any, **_kwargs: Any) -> None:
        """Geometry is fixed when the surface is created."""

    def shape(self, *_args: Any, **_kwargs: Any) -> None:
        """Cursor shapes do not apply to a recording."""

    # -- queries -------------------------------------------------------

    def bounds(self) -> Tuple[float, float, float, float]:
        """Bounding box ``(left, bottom, right, top)`` in turtle coordinates."""
        xs: List[float] = []
        ys: List[float] = []
        for op in self.ops:
            if op["op"] == "line":
                xs.extend((op["x1"], op["x2"]))
                ys.extend((op["y1"], op["y2"]))
            elif op["op"] == "circle":
                xs.extend((op["cx"] - op["r"], op["cx"] + op["r"]))
                ys.extend((op["cy"] - op["r"], op["cy"] + op["r"]))
            elif op["op"] == "text":
                xs.append(op["x"])
                ys.append(op["y"])
        if not xs:
            return (-1.0, -1.0, 1.0, 1.0)
        return (min(xs), min(ys), max(xs), max(ys))

    def strokes(self) -> int:
        """How many drawing commands were recorded."""
        return sum(
            1 for op in self.ops if op["op"] in ("line", "circle", "text")
        )

    def is_empty(self) -> bool:
        return self.strokes() == 0

    def summary(self) -> str:
        """A one-line description for logs and prompts."""
        if self.is_empty():
            return "canvas empty"
        left, bottom, right, top = self.bounds()
        return (
            f"canvas: {self.strokes()} strokes, "
            f"{right - left:.0f}×{top - bottom:.0f} units"
        )

    def to_dict(self) -> Dict[str, Any]:
        """A JSON-friendly view of the surface."""
        left, bottom, right, top = self.bounds()
        return {
            "width": self.width,
            "height": self.height,
            "background": self.background,
            "bounds": {"left": left, "bottom": bottom,
                       "right": right, "top": top},
            "ops": list(self.ops),
        }

    # -- export --------------------------------------------------------

    def to_svg(self, width: Optional[int] = None, height: Optional[int] = None,
               padding: int = 12) -> str:
        """Render the drawing as an SVG document, scaled to fit."""
        width = width or self.width
        height = height or self.height
        left, bottom, right, top = self.bounds()
        span_x = max(1.0, right - left)
        span_y = max(1.0, top - bottom)
        scale = min(
            (width - 2 * padding) / span_x,
            (height - 2 * padding) / span_y,
        )
        offset_x = width / 2 - ((left + right) / 2) * scale
        offset_y = height / 2 + ((top + bottom) / 2) * scale

        def sx(value: float) -> float:
            return offset_x + value * scale

        def sy(value: float) -> float:
            return offset_y - value * scale

        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">',
            f'<rect width="{width}" height="{height}" '
            f'fill="{self.background}"/>',
        ]
        background = self.background
        for op in self.ops:
            kind = op["op"]
            if kind == "clear":
                parts.append(
                    f'<rect width="{width}" height="{height}" fill="{background}"/>'
                )
            elif kind == "bg":
                background = op["color"]
            elif kind == "line":
                parts.append(
                    f'<line x1="{sx(op["x1"]):.2f}" y1="{sy(op["y1"]):.2f}" '
                    f'x2="{sx(op["x2"]):.2f}" y2="{sy(op["y2"]):.2f}" '
                    f'stroke="{op["color"]}" '
                    f'stroke-width="{max(1.0, op["width"] * scale):.2f}" '
                    f'stroke-linecap="round"/>'
                )
            elif kind == "circle":
                parts.append(
                    f'<circle cx="{sx(op["cx"]):.2f}" cy="{sy(op["cy"]):.2f}" '
                    f'r="{max(0.5, op["r"] * scale):.2f}" '
                    f'fill="{op.get("fill") or "none"}" '
                    f'stroke="{op["color"]}" '
                    f'stroke-width="{max(1.0, op["width"]):.2f}"/>'
                )
            elif kind == "text":
                parts.append(
                    f'<text x="{sx(op["x"]):.2f}" y="{sy(op["y"]):.2f}" '
                    f'fill="{op["color"]}" font-family="monospace" '
                    f'font-size="12">{_escape(op["text"])}</text>'
                )
        parts.append("</svg>")
        return "\n".join(parts)

    def to_ascii(self, columns: int = 64, rows: int = 24) -> str:
        """A text preview, for terminals without a graphics screen."""
        if self.is_empty():
            return "(empty canvas)"
        left, bottom, right, top = self.bounds()
        span_x = max(1e-6, right - left)
        span_y = max(1e-6, top - bottom)
        grid = [[" "] * columns for _ in range(rows)]

        def plot(x: float, y: float) -> None:
            column = round((x - left) / span_x * (columns - 1))
            row = round((top - y) / span_y * (rows - 1))
            if 0 <= row < rows and 0 <= column < columns:
                grid[row][column] = "#"

        for op in self.ops:
            if op["op"] == "line":
                dx = op["x2"] - op["x1"]
                dy = op["y2"] - op["y1"]
                steps = max(2, int(max(abs(dx), abs(dy)) * 2))
                for step in range(steps + 1):
                    ratio = step / steps
                    plot(op["x1"] + dx * ratio, op["y1"] + dy * ratio)
            elif op["op"] == "circle":
                for step in range(72):
                    angle = math.tau * step / 72
                    plot(
                        op["cx"] + op["r"] * math.cos(angle),
                        op["cy"] + op["r"] * math.sin(angle),
                    )
            elif op["op"] == "text":
                column = round((op["x"] - left) / span_x * (columns - 1))
                row = round((top - op["y"]) / span_y * (rows - 1))
                if 0 <= row < rows:
                    for index, character in enumerate(op["text"][:columns]):
                        if 0 <= column + index < columns:
                            grid[row][column + index] = character
        lines = ["".join(row).rstrip() for row in grid]
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


# ---------------------------------------------------------------------------
# Capture: which surface the generated code should draw on
# ---------------------------------------------------------------------------

_active: ContextVar[Optional[Graphics]] = ContextVar(
    "lashon_graphics", default=None
)
_default: Optional[Graphics] = None


def attach() -> Graphics:
    """Return the surface generated code should draw on.

    Called by generated programs as ``turtle = _lashon_attach()``. Inside a
    :func:`capture` block this is the host's surface; anywhere else the
    process shares one recorder so the drawing still runs headless.
    """
    active = _active.get()
    if active is not None:
        return active
    global _default
    if _default is None:
        _default = Graphics()
    return _default


@contextmanager
def capture(graphics: Optional[Graphics] = None) -> Iterator[Graphics]:
    """Send every drawing call in this block to ``graphics``."""
    surface = graphics if graphics is not None else Graphics()
    token = _active.set(surface)
    try:
        yield surface
    finally:
        _active.reset(token)
