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


def test_pipeline_panel_tracks_each_stage(app):
    assert set(app.pipeline_labels) == {
        "Grammar", "Parse", "Run", "Python", "C", "WASM", "LLVM IR"
    }
    # Loading the sample project validates its grammar, so only later stages
    # are guaranteed idle at startup.
    assert app.pipeline_labels["Run"].cget("text").startswith("○")
    assert app.pipeline_labels["WASM"].cget("text").startswith("○")

    app._validate_grammar()
    app.update()
    assert app.pipeline_labels["Grammar"].cget("text").startswith("✓")

    app._run_program()
    app.update()
    assert app.pipeline_labels["Run"].cget("text").startswith("✓")

    app._generate_all()
    app.update()
    for stage in ("Python", "C", "WASM", "LLVM IR"):
        assert app.pipeline_labels[stage].cget("text").startswith("✓")

    app.source_editor.set_text("x = ;\n")
    app._parse_source()
    app.update()
    assert app.pipeline_labels["Parse"].cget("text").startswith("✗")


def test_theme_palettes_are_distinct():
    from lashon.ide import theme

    assert theme.names() == ["green", "amber", "dark"]
    accents = {theme.get_palette(name).accent for name in theme.names()}
    assert len(accents) == 3
    assert theme.get_palette("nonsense").name == "green"


def test_env_theme_repaints_the_window(tmp_path, monkeypatch):
    from lashon.ide import studio_app, theme

    monkeypatch.setenv("LASHON_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("LASHON_THEME", "amber")
    application = LashonIDE(str(PROJECT_ROOT))
    try:
        application.update()
        assert studio_app.PALETTE.name == "amber"
        assert application.cget("bg") == theme.get_palette("amber").bg
        assert application.theme_var.get() == "amber"
    finally:
        application.destroy()
        monkeypatch.delenv("LASHON_THEME")
        studio_app._apply_palette(theme.DEFAULT)


def test_saved_theme_is_used_when_no_env_is_set(tmp_path, monkeypatch):
    from lashon.ide import settings, studio_app, theme

    monkeypatch.setenv("LASHON_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("LASHON_THEME", raising=False)
    settings.save(theme="dark")
    application = LashonIDE(str(PROJECT_ROOT))
    try:
        application.update()
        assert application.cget("bg") == theme.get_palette("dark").bg
        assert application.theme_var.get() == "dark"
    finally:
        application.destroy()
        studio_app._apply_palette(theme.DEFAULT)


def test_theme_menu_persists_the_choice(tmp_path, monkeypatch):
    from lashon.ide import settings, studio_app, theme

    monkeypatch.setenv("LASHON_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("LASHON_THEME", raising=False)
    application = LashonIDE(str(PROJECT_ROOT))
    restarts = []
    try:
        application.update()
        application._restart_with_theme = restarts.append
        application._choose_theme("dark")
        assert restarts == ["dark"]
        assert settings.get("theme") == "dark"
        assert application.theme_var.get() == "dark"

        application._choose_theme(studio_app.PALETTE.name)
        assert restarts == ["dark"], "re-picking the active theme must not restart"
    finally:
        application.destroy()
        studio_app._apply_palette(theme.DEFAULT)


LOGO_ROOT = Path(__file__).resolve().parent.parent / "projects" / "logo"


def test_canvas_tab_paints_what_the_program_draws():
    application = LashonIDE(str(LOGO_ROOT))
    try:
        application.update()
        assert application.output_tabs.tab(
            application.output_tabs.index("end") - 1, "text"
        ) == "AST"
        application.source_editor.set_text(
            (LOGO_ROOT / "samples" / "spiral.logo").read_text(encoding="utf-8")
        )
        application._run_program()
        application.update()

        assert application.studio.last_graphics.strokes() > 10
        assert len(application.graphics_canvas.find_all()) > 10
        selected = application.output_tabs.tab(
            application.output_tabs.select(), "text"
        )
        assert selected == "Canvas"
    finally:
        application.destroy()


def test_canvas_stays_empty_for_text_programs(app):
    app._run_program()
    app.update()
    assert app.studio.last_graphics.is_empty()
    assert app.output_tabs.tab(app.output_tabs.select(), "text") == "Console"
