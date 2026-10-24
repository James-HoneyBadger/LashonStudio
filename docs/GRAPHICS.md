# Graphics

Most languages built with Lashon compute and print. Some draw. Lashon gives
those languages a **canvas**: a recorded list of drawing commands that the
Studio, the REPL, and the CLI can all paint, with no screen required to run the
program.

```
program → AST → Python (turtle.* calls) → host canvas → Studio tab / SVG / ASCII
```

---

## Why a recording instead of Python's `turtle`

The Python backend has always emitted `turtle.forward(...)` and friends. That
code imported Python's own `turtle` module, which opens a Tk window the moment a
program moves the pen — a second window the Studio could not see, and a hard
failure on a machine without a display.

Generated code now asks the host for a surface:

```python
from lashon.runtime.graphics import attach as _lashon_attach
turtle = _lashon_attach()
```

`attach()` returns whatever surface the host installed
([`Graphics`](../src/lashon/runtime/graphics.py)):

| Host | Surface |
|---|---|
| Studio **Canvas** tab | the surface painted after each run |
| `lashon-repl --canvas` / `:canvas show` | a window beside the prompt |
| `lashon run --canvas out.svg` | an SVG file |
| `python program.py` | a per-process recorder (no window, no display) |

---

## The statement vocabulary

Rule **names** are the contract between a grammar and the Python backend. A
grammar that uses these names gets drawing for free:

| Rule name | Emitted Python | Meaning |
|---|---|---|
| `turtle_move` | `turtle.forward(n)` / `turtle.backward(n)` | move along the heading |
| `turtle_turn` | `turtle.left(n)` / `turtle.right(n)` | turn in degrees |
| `turtle_pen` | `turtle.penup()` / `pendown()` / `home()` | pen state |
| `turtle_pos` | `turtle.goto(x, y)`, `turtle.color(...)`, `turtle.circle(r)` | absolute moves and shapes |
| `color_stmt` | `turtle.color(_cga(n))` | CGA colour 0–15 |
| `cls_stmt` | `turtle.clear()` | erase the surface |

`projects/logo/grammar.peg` is a complete worked example:

```
turtle_move <- ('FORWARD' / 'FD' / 'BACK' / 'BK') expr ';'
turtle_turn <- ('LEFT' / 'LT' / 'RIGHT' / 'RT') expr ';'
```

```bash
lashon run projects/logo/samples/spiral.logo \
      --config projects/logo/language.yaml --canvas spiral.svg
```

> Keyword literals arrive in the AST as `Operator` nodes. That is why the
> backend matches on `Operator('FD')` rather than an identifier.

---

## The `Graphics` API

`Graphics` accepts the turtle API a generated program uses, plus a few helpers:

| Method | Effect |
|---|---|
| `forward` / `backward` (`fd`, `bk`) | move, recording a line when the pen is down |
| `left` / `right` (`lt`, `rt`), `setheading` | turn |
| `goto` / `setpos` / `home` | absolute moves |
| `penup` / `pendown` (`pu`, `pd`), `isdown` | pen state |
| `color` / `pencolor`, `width` / `pensize` | pen appearance |
| `circle`, `dot`, `write` | shapes and text |
| `bgcolor`, `clear`, `reset` | surface control |
| `speed`, `tracer`, `hideturtle`, `begin_fill`, `end_fill`, `done` | accepted no-ops |
| `bounds`, `strokes`, `is_empty`, `summary` | introspection |
| `to_svg`, `to_ascii`, `to_dict` | export |

Coordinates are turtle coordinates: the origin is the centre of the surface
and **`y` grows upwards**. Front ends flip the axis when they paint.

```python
from lashon.runtime.graphics import Graphics, attach, capture

surface = Graphics()
with capture(surface):
    attach().forward(100)      # what generated code calls
    attach().right(90)
    attach().forward(60)

print(surface.summary())       # canvas: 2 strokes, 100×60 units
print(surface.ops[0])          # {'op': 'line', 'x1': 0.0, ...}
print(surface.to_svg()[:40])   # <svg xmlns="http://www.w3.org/2000/svg" …
```

Colours accept a CGA index (`2`), a name (`"red"`), an `(r, g, b)` triple, or a
hex string; `normalize_color()` maps them all to something paintable.

---

## Where you see it

### Studio

The **Canvas** tab sits between Console and Variables and repaints after every
run. Programs that draw switch to it automatically and log
`canvas: N strokes, W×H units`; programs that only print stay on the console.
See [STUDIO_GUIDE.md](STUDIO_GUIDE.md).

### REPL

```bash
lashon-repl --config projects/logo/language.yaml --canvas
```

`--canvas` opens a window that repaints after each statement. Inside the REPL:

| Command | Effect |
|---|---|
| `:canvas` | stroke count, bounds, and available sub-commands |
| `:canvas ascii` | text preview, works over SSH |
| `:canvas save out.svg` | write the drawing |
| `:canvas show` | open (or refresh) the window |
| `:canvas clear` | start a new surface |

### CLI

```bash
lashon run prog.logo --config lang.yaml --canvas out.svg   # SVG file
lashon run prog.logo --config lang.yaml --ascii-canvas     # terminal preview
lashon run prog.logo --config lang.yaml --json             # includes "canvas"
```

`--json` reports the drawing next to the variables:

```json
{"variables": {}, "canvas": {"ops": [{"op": "line", "x1": 0.0, "y1": 0.0,
 "x2": 100.0, "y2": 0.0, "color": "#33ff66", "width": 1.0}], "bounds": {}}}
```

---

## Backends

The canvas belongs to the **interpreter runtime**, not to code generation. The
C, WASM, and LLVM backends describe computation, so a drawing program is
executed by the Python pipeline (or the REPL/Studio). Grammar validation, AST
inspection, linting, and every other backend keep working on the same grammar.

The Rust core (`lashon-rs`) evaluates computation and does not draw yet: for a
drawing language use `lashon run`, `lashon-repl`, or the Studio.

---

## Adding drawing to an existing language

1. Name your statement rules `turtle_move`, `turtle_turn`, `turtle_pen`,
   `turtle_pos`, `cls_stmt`, or reuse an existing name in the table above.
2. Make the keyword a `Operator` node by writing it as a PEG literal
   (`'FORWARD'`), and give the argument as an `expr`.
3. Run it in the Studio: the Canvas tab paints immediately.
4. Declare `source_extension: ".logo"` in `language.yaml` if your samples use
   your own file extension, so the Studio lists them.
