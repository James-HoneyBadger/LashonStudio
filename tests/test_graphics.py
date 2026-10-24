"""Tests for the recorded drawing surface used by turtle-style languages."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lashon.codegen import transpile_and_exec, transpile_to_python
from lashon.parser import GrammarParser, PEGInterpreter
from lashon.runtime.graphics import Graphics, attach, capture, normalize_color
from lashon.runtime.repl import REPL
from lashon.tooling.cli import main

LOGO_ROOT = Path(__file__).resolve().parent.parent / "projects" / "logo"


def _compiled():
    grammar = GrammarParser().parse(
        (LOGO_ROOT / "grammar.peg").read_text(encoding="utf-8")
    )
    return grammar


def _run_logo(source: str, canvas: Graphics | None = None) -> Graphics:
    ast = PEGInterpreter(_compiled()).parse(source)
    surface = canvas if canvas is not None else Graphics()
    transpile_and_exec(ast, graphics=surface)
    return surface


# -- the recorder -------------------------------------------------------


def test_forward_and_turn_record_a_line():
    surface = Graphics()
    surface.forward(100)
    surface.right(90)
    surface.forward(50)

    assert [op["op"] for op in surface.ops] == ["line", "line"]
    first, second = surface.ops
    assert (first["x1"], first["y1"], first["x2"], first["y2"]) == (
        0.0, 0.0, 100.0, 0.0,
    )
    assert second["y2"] == pytest.approx(-50.0)
    assert surface.strokes() == 2
    assert "2 strokes" in surface.summary()


def test_penup_stops_drawing_but_still_moves():
    surface = Graphics()
    surface.penup()
    surface.forward(100)
    surface.pendown()
    surface.forward(100)

    assert len(surface.ops) == 1
    assert surface.ops[0]["x1"] == 100.0
    assert surface.position == (200.0, 0.0)


def test_home_and_goto_move_without_drawing_when_the_pen_is_up():
    surface = Graphics()
    surface.penup()
    surface.goto(10, 20)
    surface.home()
    assert surface.ops == []
    assert surface.position == (0.0, 0.0)


def test_colors_accept_cga_names_and_rgb():
    assert normalize_color(2) == "#00aa00"
    assert normalize_color("red") == "red"
    assert normalize_color((255, 0, 16)) == "#ff0010"
    assert normalize_color(99) == "#aaaaaa"

    surface = Graphics()
    surface.color(4)
    surface.forward(10)
    assert surface.ops[0]["color"] == "#aa0000"


def test_circle_and_dot_add_shapes():
    surface = Graphics()
    surface.circle(20)
    surface.dot(10)

    circle, dot = surface.ops
    assert circle["op"] == "circle"
    assert circle["r"] == pytest.approx(20.0)
    assert dot["fill"] is not None
    # A circle of radius 20 at heading 0 is centred 20 units ahead-left.
    assert surface.bounds() == pytest.approx((-20.0, -5.0, 20.0, 40.0))


def test_clear_and_reset_erase_the_surface():
    surface = Graphics()
    surface.forward(10)
    surface.clear()
    assert surface.ops[-1] == {"op": "clear"}
    assert surface.position == (0.0, 0.0)

    surface.color(3)
    surface.reset()
    assert surface.ops[-1] == {"op": "clear"}
    assert surface.ops[-2]["op"] == "line" or surface._color == "#33ff66"


def test_turtle_api_noops_are_available():
    surface = Graphics()
    for call in (surface.speed, surface.tracer, surface.hideturtle,
                 surface.begin_fill, surface.end_fill, surface.done,
                 surface.update, surface.title, surface.setup):
        call()
    surface.speed(0)
    surface.tracer(0, 0)
    assert surface.is_empty()


# -- capture ------------------------------------------------------------


def test_capture_routes_attach_to_the_host_surface():
    surface = Graphics()
    outside = attach()
    with capture(surface) as active:
        assert active is surface
        assert attach() is surface
        attach().forward(10)
    assert attach() is outside
    assert surface.strokes() == 1


def test_surface_active_context_manager_is_reentrant():
    outer, inner = Graphics(), Graphics()
    with outer.active():
        outer.attach_seen = attach()
        with inner.active():
            assert attach() is inner
        assert attach() is outer
    assert outer.attach_seen is outer


# -- export -------------------------------------------------------------


def test_svg_contains_the_drawing_and_escapes_text():
    surface = Graphics()
    surface.forward(100)
    surface.right(90)
    surface.forward(100)
    surface.write("<hello & goodbye>")

    svg = surface.to_svg()
    assert svg.startswith("<svg")
    assert svg.count("<line") == 2
    assert "&lt;hello &amp; goodbye&gt;" in svg
    assert 'fill="#000000"' in svg


def test_ascii_preview_draws_a_square():
    surface = Graphics()
    for _ in range(4):
        surface.forward(100)
        surface.right(90)

    preview = surface.to_ascii(24, 8).splitlines()
    assert len(preview) == 8
    assert preview[0].startswith("###")
    assert preview[0].endswith("#")
    assert preview[-1].startswith("#####")


def test_empty_surface_reports_itself():
    surface = Graphics()
    assert surface.is_empty()
    assert surface.summary() == "canvas empty"
    assert surface.to_ascii() == "(empty canvas)"
    assert surface.to_dict()["ops"] == []


# -- code generation ----------------------------------------------------


def test_generated_python_uses_the_host_canvas_not_turtles_window():
    ast = PEGInterpreter(_compiled()).parse("FD 10 ;")
    code = transpile_to_python(ast)

    assert "from lashon.runtime.graphics import attach" in code
    assert "turtle = _lashon_attach()" in code
    assert "import turtle" not in code


def test_logo_program_draws_through_the_pipeline():
    surface = _run_logo(
        "CLS ;\nCOLOR 10 ;\nREPEAT 4 FD 100 ; RT 90 ; END\n"
    )
    assert surface.strokes() == 4
    assert surface.ops[0] == {"op": "clear"}
    assert surface.ops[1]["color"] == "#55ff55"
    assert surface.bounds() == pytest.approx((0.0, -100.0, 100.0, 0.0))


def test_cls_emits_a_clear_call():
    ast = PEGInterpreter(_compiled()).parse("CLS ;")
    assert "turtle.clear()" in transpile_to_python(ast)


def test_logo_samples_all_draw():
    grammar = _compiled()
    for sample in sorted((LOGO_ROOT / "samples").glob("*.logo")):
        surface = Graphics()
        ast = PEGInterpreter(grammar).parse(
            sample.read_text(encoding="utf-8")
        )
        transpile_and_exec(ast, graphics=surface)
        assert not surface.is_empty(), sample.name
        assert surface.to_svg().count("<") > 2


# -- CLI ----------------------------------------------------------------


def _run_cli(monkeypatch, *argv) -> int:
    monkeypatch.setattr(sys, "argv", ["lashon", *argv])
    return main()


def test_run_writes_the_canvas_to_svg(tmp_path, monkeypatch, capsys):
    target = tmp_path / "square.svg"
    exit_code = _run_cli(
        monkeypatch,
        "run", str(LOGO_ROOT / "samples" / "square.logo"),
        "--config", str(LOGO_ROOT / "language.yaml"),
        "--canvas", str(target),
    )

    assert exit_code == 0
    assert "square" in capsys.readouterr().out  # the SAY statement
    assert target.read_text(encoding="utf-8").count("<line") == 4


def test_run_prints_an_ascii_preview(tmp_path, monkeypatch, capsys):
    exit_code = _run_cli(
        monkeypatch,
        "run", str(LOGO_ROOT / "samples" / "square.logo"),
        "--config", str(LOGO_ROOT / "language.yaml"),
        "--ascii-canvas",
    )

    assert exit_code == 0
    assert "###" in capsys.readouterr().err


def test_run_json_reports_the_canvas(tmp_path, monkeypatch, capsys):
    import json

    exit_code = _run_cli(
        monkeypatch,
        "run", str(LOGO_ROOT / "samples" / "square.logo"),
        "--config", str(LOGO_ROOT / "language.yaml"),
        "--json",
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["canvas"]["ops"]
    assert payload["canvas"]["bounds"]["right"] >= 0


# -- REPL ---------------------------------------------------------------


def test_repl_canvas_command_reports_and_saves(tmp_path, capsys):
    repl = REPL(grammar=_compiled())
    repl._eval("FD 100 ;")  # pylint: disable=protected-access
    assert repl.graphics.strokes() == 1

    repl._handle_command(":canvas")  # pylint: disable=protected-access
    assert "1 strokes" in capsys.readouterr().out

    target = tmp_path / "repl.svg"
    repl._handle_command(  # pylint: disable=protected-access
        f":canvas save {target}"
    )
    assert target.exists()
    assert "<line" in target.read_text(encoding="utf-8")

    repl._handle_command(":canvas clear")  # pylint: disable=protected-access
    assert repl.graphics.is_empty()


def test_repl_keeps_one_surface_across_statements(capsys):
    repl = REPL(grammar=_compiled())
    repl._eval("FD 100 ;")  # pylint: disable=protected-access
    repl._eval("RT 90 ;")  # pylint: disable=protected-access
    repl._eval("FD 100 ;")  # pylint: disable=protected-access
    assert repl.graphics.strokes() == 2


def test_repl_without_a_host_falls_back_to_text(capsys):
    repl = REPL(grammar=_compiled())
    repl._eval("FD 100 ;")  # pylint: disable=protected-access
    repl._handle_command(":canvas show")  # pylint: disable=protected-access
    captured = capsys.readouterr()
    assert "No drawing window here" in captured.err
    assert "#" in captured.out
