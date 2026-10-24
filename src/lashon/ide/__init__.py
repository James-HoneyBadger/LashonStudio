"""IDE modules — editor, project management, and main application."""

from lashon.ide.app import LashonIDE
from lashon.ide.editor import CodeEditor, LineNumbers
from lashon.ide.project import Project, ProjectManager

__all__ = [
    "CodeEditor",
    "LineNumbers",
    "Project",
    "ProjectManager",
    "LashonIDE",
]
