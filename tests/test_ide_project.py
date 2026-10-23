"""Tests for IDE project management (no Tk display required)."""

from pathlib import Path

from parsercraft.ide.project import Project, ProjectManager


def test_project_save_and_load_json(tmp_path):
    config_path = tmp_path / "project.json"
    project = Project(
        name="Demo",
        root_dir=str(tmp_path),
        config_path=str(config_path),
        config={"name": "Demo", "keywords": {"if": "when"}},
    )
    project.save()

    loaded = Project.load(str(config_path))
    assert loaded.name == "Demo"
    assert loaded.config["keywords"]["if"] == "when"
    assert loaded.root_dir == str(tmp_path)


def test_project_load_builds_grammar_text(tmp_path):
    config_path = tmp_path / "project.yaml"
    config_path.write_text(
        "name: Tiny\n"
        "grammar:\n"
        "  rules:\n"
        "    program: statement+\n"
        "    statement: 'IDENT \";\"'\n",
        encoding="utf-8",
    )
    loaded = Project.load(str(config_path))
    assert "program <- statement+" in loaded.grammar_text


def test_project_add_source_file():
    project = Project()
    source = project.add_source_file("main.src", "x = 1")
    assert source.path == "main.src"
    assert project.source_files == [source]


def test_project_get_keywords_from_config():
    project = Project(config={"keywords": {"if": "when", "else": "otherwise"}})
    keywords = project.get_keywords()
    assert "if" in keywords
    assert "when" in keywords


def test_project_get_keywords_falls_back_to_defaults():
    assert "def" in Project().get_keywords()


def test_project_manager_creates_and_opens(tmp_path):
    manager = ProjectManager(workspace_dir=str(tmp_path / "workspace"))
    project = manager.create_project(
        "Demo Language", str(tmp_path / "project"), "python_like"
    )

    assert Path(project.config_path).exists()
    assert project.config["name"] == "Demo Language"
    assert str(project.config_path) in manager.recent_projects

    # A fresh manager reads the persisted recent-projects list.
    reopened_manager = ProjectManager(workspace_dir=str(tmp_path / "workspace"))
    assert str(project.config_path) in reopened_manager.recent_projects

    opened = reopened_manager.open_project(project.config_path)
    assert opened.name == "Demo Language"
