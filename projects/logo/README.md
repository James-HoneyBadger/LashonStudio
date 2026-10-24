# Logo — a drawing language

A turtle-graphics dialect that exists to exercise the part of Lashon that text
programs cannot: **the canvas**.

```bash
lashon run projects/logo/samples/spiral.logo \
      --config projects/logo/language.yaml --canvas spiral.svg
lashon-ide projects/logo        # Canvas tab paints on Run; Ctrl+R for the REPL
lashon-repl --config projects/logo/language.yaml --canvas
```

## The language

| Statement | Meaning |
|---|---|
| `FORWARD n ;` / `FD n ;` | move `n` units along the heading, drawing |
| `BACK n ;` / `BK n ;` | move backwards |
| `LEFT n ;` / `LT n ;` | turn left `n` degrees |
| `RIGHT n ;` / `RT n ;` | turn right `n` degrees |
| `PENUP ;` / `PU ;` | lift the pen |
| `PENDOWN ;` / `PD ;` | lower the pen |
| `HOME ;` | back to the centre, heading north |
| `SETXY x , y ;` | jump to a point |
| `SETCOLOR n ;` / `COLOR n ;` | pen colour, CGA index 0–15 |
| `CIRCLE r ;` | circle of radius `r` centred to the left of the heading |
| `CLS ;` | clear the canvas |
| `SAY "text" ;` | print a line to the console |
| `REPEAT n … END` | repeat a block `n` times |

Comments start with `//`. Every statement ends with `;`.

## How the drawing reaches the screen

Rule names are the contract with the Python backend:

```
turtle_move → turtle.forward(...)      turtle_turn → turtle.left(...)
turtle_pen  → turtle.penup()/...       turtle_pos  → turtle.goto(...)/circle(...)
```

Generated Python asks Lashon for a surface with
`from lashon.runtime.graphics import attach`, so the same program draws on
whatever host is running it — the Studio canvas, the REPL window, an SVG file
— or on a headless recorder when there is no host at all. Python's own
`turtle` window is never opened.

## Samples

| File | What it draws |
|---|---|
| `hello.logo` | a square, the smallest complete program |
| `square.logo` | the same square with a colour |
| `star.logo` | a five-point star (144° turns) |
| `spiral.logo` | a vortex: 72 long steps with 175° turns |
| `circles.logo` | three concentric circles |

## Notes

- `projects/logo/language.yaml` is generated from `grammar.peg` by the Studio;
  edit either one and press **Save Project**.
- The C, WASM, and LLVM backends describe programs, not drawings; the canvas is
  a property of the interpreter runtime.
