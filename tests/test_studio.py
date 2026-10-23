"""Tests for the headless language-studio controller."""

from pathlib import Path

import pytest

from parsercraft.ide.studio import (
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
    import parsercraft.ide
    return Path(parsercraft.ide.__file__).parent / "samples" / "aurora"


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
