"""Smoke tests for the Tkinter studio window.

These are skipped when no display is available (e.g. CI).
"""

from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")

from lashon.ide.app import LashonIDE  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent / "projects" / "aurora"


def _display_available() -> bool:
    try:
        root = tk.Tk()
    except tk.TclError:
        return False
    root.destroy()
    return True


pytestmark = pytest.mark.skipif(
    not _display_available(), reason="Tk display not available"
)


@pytest.fixture
def app():
    application = LashonIDE(str(PROJECT_ROOT))
    application.update()
    yield application
    application.destroy()


def test_window_loads_aurora(app):
    assert "Aurora" in app.title()
    assert [app.editor_tabs.tab(i, "text") for i in range(3)] == [
        "hello.aur", "grammar.peg", "language.yaml",
    ]
    assert app.project_tree.get_children()


def test_run_program_fills_console(app):
    app._run_program()
    app.update()
    console = app.console.get("1.0", "end")
    assert "Hello, Aurora!" in console
    assert "Run complete" in app.status_label.cget("text")


def test_generate_all_fills_backends(app):
    app._generate_all()
    app.update()
    assert "int main" in app.code_views["c"].get("1.0", "end")
    wasm = app.code_views["wasm"].get("1.0", "end")
    assert "(module" in wasm
    assert "(func $main" in wasm
    assert "(data" in wasm
    assert "LLVM" in app.code_views["llvm"].get("1.0", "end")
    assert app.code_views["python"].get("1.0", "end").startswith("print(")


def test_parse_builds_ast_tree(app):
    app._parse_source()
    app.update()
    assert app.ast_tree.get_children()
    root = app.ast_tree.get_children()[0]
    assert app.ast_tree.item(root, "text") == "program"


def test_switching_to_fibonacci_sample_runs(app):
    samples_root = None
    for item in app.project_tree.get_children():
        for child in app.project_tree.get_children(item):
            if app.project_tree.item(child, "text") == "▸ samples":
                samples_root = child
    assert samples_root is not None
    for item in app.project_tree.get_children(samples_root):
        if "fibonacci" in app.project_tree.item(item, "text"):
            app.project_tree.selection_set(item)
            app.update()
            break
    app._run_program()
    app.update()
    assert "3628800" in app.console.get("1.0", "end")


def test_parse_failure_fills_problems_panel(app):
    app.source_editor.set_text("x = 1 ;\ny = ;\n")
    app._parse_source()
    app.update()

    problems = app.problems_tree.get_children()
    assert problems
    severity, location, message = app.problems_tree.item(problems[0])["values"]
    assert severity == "ERROR"
    assert location == "2:1"
    assert "line 2" in str(message)

    assert app.source_editor.text.tag_ranges("error")


def test_problem_selection_jumps_to_source(app):
    app.source_editor.set_text("x = 1 ;\ny = ;\n")
    app._parse_source()
    app.update()

    app.problems_tree.selection_set(app.problems_tree.get_children()[0])
    app._select_problem()
    app.update()
    assert app.source_editor.text.index("insert").startswith("2.")


def test_command_palette_lists_commands(app):
    app._show_palette()
    app.update()
    toplevels = [
        child for child in app.winfo_children()
        if child.winfo_class() == "Toplevel"
    ]
    assert toplevels, "palette window should open"
    assert toplevels[0].title() == "Command Palette"
    toplevels[0].destroy()


def test_quick_open_lists_project_files(app):
    app._quick_open()
    app.update()
    toplevels = [
        child for child in app.winfo_children()
        if child.winfo_class() == "Toplevel"
    ]
    assert toplevels, "quick open should open"
    assert toplevels[0].title() == "Quick Open"
    toplevels[0].destroy()
