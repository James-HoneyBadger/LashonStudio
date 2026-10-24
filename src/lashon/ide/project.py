"""
Lashon IDE — Project Management

Handles loading/saving language configuration projects,
managing files, and coordinating between editor and runtime.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ProjectFile:
    """A file within a Lashon project."""
    path: str
    content: str = ""
    is_config: bool = False
    modified: bool = False


@dataclass
class Project:
    """A Lashon language project."""
    name: str = "Untitled Language"
    root_dir: str = ""
    config_path: str = ""
    source_files: List[ProjectFile] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    grammar_text: str = ""

    def save(self, path: Optional[str] = None) -> None:
        """Save project to disk."""
        save_path = path or self.config_path
        if not save_path:
            return

        ext = os.path.splitext(save_path)[1].lower()
        if ext in (".yaml", ".yml"):
            with open(save_path, "w") as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
        else:
            with open(save_path, "w") as f:
                json.dump(self.config, f, indent=2)

        self.config_path = save_path

    @classmethod
    def load(cls, path: str) -> Project:
        """Load a project from a config file."""
        ext = os.path.splitext(path)[1].lower()
        with open(path) as f:
            if ext in (".yaml", ".yml"):
                config = yaml.safe_load(f) or {}
            else:
                config = json.load(f)

        name = config.get("name", config.get("language_name", Path(path).stem))
        grammar_text = ""
        if "grammar" in config and "rules" in config["grammar"]:
            lines = []
            for rule_name, pattern in config["grammar"]["rules"].items():
                lines.append(f"{rule_name} <- {pattern}")
            grammar_text = "\n".join(lines)

        return cls(
            name=name,
            root_dir=os.path.dirname(os.path.abspath(path)),
            config_path=path,
            config=config,
            grammar_text=grammar_text,
        )

    def add_source_file(self, path: str, content: str = "") -> ProjectFile:
        """Add a source file to the project."""
        pf = ProjectFile(path=path, content=content)
        self.source_files.append(pf)
        return pf

    def get_keywords(self) -> List[str]:
        """Extract keywords from the language config."""
        keywords = []
        kw_section = self.config.get("keywords", {})
        if isinstance(kw_section, dict):
            keywords.extend(kw_section.keys())
            keywords.extend(v for v in kw_section.values() if isinstance(v, str))
        builtin_kw = self.config.get("builtin_keywords", [])
        if isinstance(builtin_kw, list):
            keywords.extend(builtin_kw)
        return keywords or [
            "def", "class", "if", "else", "while", "for", "return",
            "import", "print", "True", "False", "None",
        ]


class ProjectManager:
    """Manages project lifecycle: create, open, save, recent history."""

    def __init__(self, workspace_dir: str = ""):
        self.workspace_dir = workspace_dir or os.path.expanduser("~/.lashon")
        self.recent_projects: List[str] = []
        self._load_recent()

    def create_project(self, name: str, directory: str,
                       preset: str = "python_like") -> Project:
        """Create a new language project with a preset config."""
        os.makedirs(directory, exist_ok=True)

        config = self._get_preset(preset)
        config["name"] = name

        config_path = os.path.join(directory, f"{name.lower().replace(' ', '_')}.yaml")
        project = Project(
            name=name,
            root_dir=directory,
            config_path=config_path,
            config=config,
        )
        project.save()
        self._add_recent(config_path)
        return project

    def open_project(self, path: str) -> Project:
        """Open an existing project."""
        project = Project.load(path)
        self._add_recent(path)
        return project

    def _get_preset(self, preset: str) -> Dict[str, Any]:
        """Get a preset language configuration."""
        presets = {
            "python_like": {
                "name": "MyLanguage",
                "description": "A Python-like custom language",
                "file_extension": ".mylang",
                "keywords": {
                    "def": "def",
                    "class": "class",
                    "if": "if",
                    "else": "else",
                    "while": "while",
                    "for": "for",
                    "return": "return",
                    "import": "import",
                },
                "grammar": {
                    "start": "program",
                    "rules": {
                        "program": "statement*",
                        "statement": "assignment / if_stmt / while_stmt / function_def / expr_stmt",
                        "assignment": "IDENT '=' expr ';'",
                        "if_stmt": "'if' expr ':' block ('else' ':' block)?",
                        "while_stmt": "'while' expr ':' block",
                        "function_def": "'def' IDENT '(' param_list? ')' ':' block",
                        "param_list": "IDENT (',' IDENT)*",
                        "block": "statement+",
                        "expr": "term (('+' / '-') term)*",
                        "term": "factor (('*' / '/') factor)*",
                        "factor": "NUMBER / STRING / IDENT / '(' expr ')'",
                        "expr_stmt": "expr ';'",
                    },
                },
            },
            "c_like": {
                "name": "MyLanguage",
                "description": "A C-like custom language",
                "file_extension": ".mylang",
                "keywords": {
                    "int": "int",
                    "float": "float",
                    "char": "char",
                    "void": "void",
                    "if": "if",
                    "else": "else",
                    "while": "while",
                    "for": "for",
                    "return": "return",
                },
                "grammar": {
                    "start": "program",
                    "rules": {
                        "program": "declaration*",
                        "declaration": "function_def / var_decl",
                        "function_def": "type_name IDENT '(' params? ')' '{' statement* '}'",
                        "var_decl": "type_name IDENT ('=' expr)? ';'",
                        "type_name": "'int' / 'float' / 'char' / 'void'",
                        "params": "type_name IDENT (',' type_name IDENT)*",
                        "statement": "var_decl / if_stmt / while_stmt / return_stmt / expr_stmt",
                        "if_stmt": "'if' '(' expr ')' '{' statement* '}' ('else' '{' statement* '}')?",
                        "while_stmt": "'while' '(' expr ')' '{' statement* '}'",
                        "return_stmt": "'return' expr? ';'",
                        "expr_stmt": "expr ';'",
                        "expr": "comparison",
                        "comparison": "addition (('==' / '!=' / '<' / '>') addition)*",
                        "addition": "multiplication (('+' / '-') multiplication)*",
                        "multiplication": "unary (('*' / '/') unary)*",
                        "unary": "('-' / '!') unary / primary",
                        "primary": "NUMBER / STRING / IDENT / '(' expr ')'",
                    },
                },
            },
            "minimal": {
                "name": "MinLang",
                "description": "A minimal expression language",
                "file_extension": ".min",
                "grammar": {
                    "start": "program",
                    "rules": {
                        "program": "statement*",
                        "statement": "IDENT '=' expr ';'",
                        "expr": "term (('+' / '-') term)*",
                        "term": "NUMBER / IDENT / '(' expr ')'",
                    },
                },
            },
        }
        return presets.get(preset, presets["python_like"]).copy()

    def _add_recent(self, path: str) -> None:
        abs_path = os.path.abspath(path)
        if abs_path in self.recent_projects:
            self.recent_projects.remove(abs_path)
        self.recent_projects.insert(0, abs_path)
        self.recent_projects = self.recent_projects[:10]
        self._save_recent()

    def _load_recent(self) -> None:
        recent_file = os.path.join(self.workspace_dir, "recent.json")
        if os.path.exists(recent_file):
            try:
                with open(recent_file) as f:
                    self.recent_projects = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.recent_projects = []

    def _save_recent(self) -> None:
        os.makedirs(self.workspace_dir, exist_ok=True)
        recent_file = os.path.join(self.workspace_dir, "recent.json")
        try:
            with open(recent_file, "w") as f:
                json.dump(self.recent_projects, f)
        except OSError as error:
            logger.warning("Could not save recent projects to %s: %s", recent_file, error)
