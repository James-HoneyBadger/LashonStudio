"""IDE modules — editor, project management, and main application."""

from parsercraft.ide.app import ParserCraftIDE
from parsercraft.ide.editor import CodeEditor, LineNumbers
from parsercraft.ide.project import Project, ProjectManager

__all__ = [
    "CodeEditor",
    "LineNumbers",
    "Project",
    "ProjectManager",
    "ParserCraftIDE",
]
