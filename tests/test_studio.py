"""Tests for the headless language-studio controller."""

from pathlib import Path

import pytest

from lashon.ide.studio import (
    GRAMMAR_FILENAME,
    PROJECT_FILENAME,
    LanguageStudio,
    StudioProject,
    peg_to_rules,
    rules_to_peg,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent / "projects" / "aurora"


@pytest.fixture
def studio():
    control = LanguageStudio()
    control.open_project(PROJECT_ROOT)
    return control


class TestProjectModel:
    def test_sample_project_is_discoverable(self):
        assert LanguageStudio.sample_project_path() == PROJECT_ROOT

    def test_project_loads_metadata_and_samples(self, studio):
        project = studio.project
        assert project is not None
        assert project.name == "Aurora"
        assert project.sample_path is not None
        assert project.sample_path.name == "hello.aur"
        assert len(project.sample_files()) == 3
        assert project.summary()["rules"] == 18

    def test_rules_round_trip(self):
        rules = {"program": "statement+", "statement": "'x' ';'"}
        assert peg_to_rules(rules_to_peg(rules)) == rules

    def test_peg_to_rules_rejects_garbage(self):
        with pytest.raises(ValueError):
            peg_to_rules("this is not a rule")


class TestGrammar:
    def test_validate_aurora(self, studio):
        result = studio.validate_grammar()
        assert result.ok
        assert "18 rules" in result.text

    def test_grammar_reports_unsupported_token(self, studio):
        result = studio.validate_grammar("program <- INDENT")
        assert not result.ok
        assert any("INDENT" in d.message for d in result.diagnostics)

    def test_malformed_grammar_is_reported(self, studio):
        result = studio.validate_grammar("program <- NUMBER )")
        assert not result.ok
        assert result.diagnostics

    def test_highlight_keywords(self, studio):
        studio.validate_grammar()
        keywords = set(studio.highlight_keywords())
        assert {"fn", "if", "while", "print", "true", "false"} <= keywords


class TestPipeline:
    @pytest.mark.parametrize("sample,expected", [
        ("hello.aur", "Hello, Aurora!"),
        ("fibonacci.aur", "3628800"),
        ("fizzbuzz.aur", "FizzBuzz"),
    ])
    def test_samples_parse_and_run(self, studio, sample, expected):
        source = (PROJECT_ROOT / "samples" / sample).read_text(encoding="utf-8")
        result = studio.run(source)
        assert result.ok, result.error
        assert expected in result.text

    def test_fizzbuzz_output_length(self, studio):
        source = (PROJECT_ROOT / "samples" / "fizzbuzz.aur").read_text(
            encoding="utf-8"
        )
        lines = studio.run(source).text.splitlines()
        assert len(lines) == 15
        assert lines[-1] == "FizzBuzz"

    def test_ast_tree_is_nested(self, studio):
        source = (PROJECT_ROOT / "samples" / "hello.aur").read_text(
            encoding="utf-8"
        )
        parsed = studio.parse(source)
        assert parsed.ok
        tree = studio.ast_tree(parsed.value)
        assert tree[0]["label"] == "program"
        assert tree[0]["children"]

    def test_generate_all_backends(self, studio):
        source = (PROJECT_ROOT / "samples" / "fibonacci.aur").read_text(
            encoding="utf-8"
        )
        results = studio.generate_all(source)
        assert set(results) == {"python", "c", "wasm", "llvm"}
        assert all(result.ok for result in results.values())
        assert "def fib" in results["python"].text
        assert "int main" in results["c"].text
        assert results["wasm"].text.startswith("(module")
        assert "LLVM IR" in results["llvm"].text
        assert results["wasm"].supported is True
        assert results["wasm"].warnings == []
        assert results["python"].supported is True

    def test_parse_error_is_reported(self, studio):
        result = studio.parse("fn broken( {")
        assert not result.ok
        assert result.error

    def test_transpile_error_is_reported(self, studio):
        source = (PROJECT_ROOT / "samples" / "hello.aur").read_text(
            encoding="utf-8"
        )
        result = studio.transpile(source)
        assert result.ok
        assert result.text.startswith("print(")


class TestProjectLifecycle:
    def test_new_project_scaffolds_and_runs(self, tmp_path):
        control = LanguageStudio()
        project = control.new_project("Tiny Language", tmp_path)

        assert (project.root / PROJECT_FILENAME).exists()
        assert (project.root / GRAMMAR_FILENAME).exists()
        assert (project.root / "samples" / "hello.aur").exists()
        assert (project.root / "README.md").exists()

        assert control.validate_grammar().ok
        result = control.run()
        assert result.ok
        assert "Hello from Tiny Language!" in result.text

    def test_save_updates_grammar_rules(self, tmp_path):
        control = LanguageStudio()
        project = control.new_project("Editable", tmp_path)
        control.set_grammar_text(
            "program <- statement+\n"
            'statement <- "print" NUMBER ";"\n'
        )
        control.save_project()

        reopened = StudioProject.from_path(project.root)
        assert reopened.config["grammar"]["rules"]["statement"] == (
            '"print" NUMBER ";"'
        )
        assert "program <- statement+" in reopened.grammar_text

    def test_saving_invalid_grammar_fails(self, tmp_path):
        control = LanguageStudio()
        control.new_project("Broken", tmp_path)
        control.set_grammar_text("program <- NUMBER )")
        with pytest.raises(ValueError):
            control.save_project()

    def test_open_accepts_config_file(self):
        control = LanguageStudio()
        project = control.open_project(PROJECT_ROOT / PROJECT_FILENAME)
        assert project.name == "Aurora"
        assert project.root == PROJECT_ROOT


def _packaged_sample_root() -> Path:
    import lashon.ide
    return Path(lashon.ide.__file__).parent / "samples" / "aurora"


def test_packaged_sample_is_in_sync():
    packaged = _packaged_sample_root()
    relative_files = [
        "language.yaml", "grammar.peg", "README.md",
        "samples/hello.aur", "samples/fibonacci.aur", "samples/fizzbuzz.aur",
    ]
    for relative in relative_files:
        assert (packaged / relative).read_text(encoding="utf-8") == (
            PROJECT_ROOT / relative
        ).read_text(encoding="utf-8"), relative


def test_packaged_sample_loads_and_runs():
    control = LanguageStudio()
    project = control.open_project(_packaged_sample_root())
    assert project.name == "Aurora"
    assert control.validate_grammar().ok
    assert "Hello, Aurora!" in control.run().text


def test_ide_entry_point_explains_missing_display(monkeypatch, capsys):
    """A headless machine gets a pointer to the CLI, not a Tcl traceback."""
    import sys

    from lashon.ide import studio_app

    monkeypatch.setattr(studio_app, "_display_available", lambda: False)
    monkeypatch.setattr(sys, "argv", ["lashon-ide", str(PROJECT_ROOT)])

    with pytest.raises(SystemExit) as exit_info:
        studio_app.main()

    assert exit_info.value.code == 1
    message = capsys.readouterr().err
    assert "needs a graphical display" in message
    assert "lashon run" in message


def test_theme_feeds_the_editor_and_headers():
    from lashon.ide import theme

    green = theme.get_palette("green")
    colors = theme.editor_colors(green)
    assert colors["background"] == green.bg
    assert colors["keyword"] == green.accent
    assert colors["error"] == green.red
    assert {"gutter_bg", "gutter_fg"} <= set(colors)

    header = theme.rule("PIPELINE", width=24)
    assert header.startswith("── PIPELINE ")
    assert len(header) == 24


def test_settings_round_trip(tmp_path, monkeypatch):
    from lashon.ide import settings

    monkeypatch.setenv("LASHON_CONFIG_DIR", str(tmp_path))
    assert settings.load() == {}
    settings.save(theme="amber", other=1)
    assert settings.get("theme") == "amber"
    assert settings.load() == {"other": 1, "theme": "amber"}
    assert settings.settings_path() == tmp_path / "studio.json"

    monkeypatch.delenv("LASHON_CONFIG_DIR")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert settings.settings_path() == (
        tmp_path / "xdg" / "lashon" / "studio.json"
    )


def test_palette_can_be_switched_before_building_widgets(tmp_path, monkeypatch):
    from lashon.ide import settings, studio_app, theme

    monkeypatch.setenv("LASHON_CONFIG_DIR", str(tmp_path))
    try:
        studio_app._apply_palette("amber")
        assert studio_app.PALETTE.name == "amber"
        assert studio_app.BG == theme.get_palette("amber").bg
        assert studio_app.ACCENT == theme.get_palette("amber").accent

        studio_app._apply_palette(None)
        assert studio_app.PALETTE.name == theme.DEFAULT

        settings.save(theme="dark")
        studio_app._apply_palette(settings.get("theme"))
        assert studio_app.PALETTE.name == "dark"
    finally:
        studio_app._apply_palette(theme.DEFAULT)


LOGO_ROOT = Path(__file__).resolve().parent.parent / "projects" / "logo"


def test_project_can_declare_its_own_sample_extension():
    project = StudioProject.from_path(LOGO_ROOT)
    assert project.sample_path is not None
    assert project.sample_path.suffix == ".logo"
    assert project.sample_path.stem == "hello"
    assert [p.name for p in project.sample_files()] == [
        "circles.logo", "hello.logo", "spiral.logo", "square.logo",
    ]


def test_logo_project_runs_and_draws():
    control = LanguageStudio()
    control.open_project(LOGO_ROOT)
    assert control.validate_grammar().ok
    result = control.run()
    assert result.ok, result.error
    assert control.last_graphics.strokes() == 4
    assert "hello, Logo" in result.text
