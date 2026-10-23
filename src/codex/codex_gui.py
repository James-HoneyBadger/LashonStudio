#!/usr/bin/env python3
"""
CodeEx GUI - Professional IDE for ParserCraft Applications

Multi-panel integrated development environment for writing applications
in ParserCraft-generated custom programming languages.

Features:
- Multi-file project management
- Editor with syntax highlighting
- Real-time code execution with custom interpreters
- Integrated console and debugging output
- Code templates and snippets
- Project file browser
- Output and error tracking
- Language configuration management

See Also:
    - ParserCraft IDE: For creating custom language configurations
    - Documentation: docs/guides/CODEX_USER_GUIDE.md
"""

import json
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import TclError, filedialog, messagebox, scrolledtext, ttk
from typing import Any, Dict, Optional

# Ensure parent modules are in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from codex.codex_components import (  # noqa: E402 pylint: disable=wrong-import-position
    CodeExConsole,
    CodeExEditor,
    CodeExMenu,
    CodeExProjectExplorer,
)
from parsercraft.config.language_config import (  # noqa: E402 pylint: disable=wrong-import-position
    LanguageConfig,
)
from parsercraft.runtime.interpreter_generator import (  # noqa: E402 pylint: disable=wrong-import-position
    InterpreterGenerator,
    InterpreterPackage,
)


class CodeExIDE(ttk.Frame):
    """Main CodeEx IDE interface."""

    def __init__(self, master):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        self.root = master.winfo_toplevel()

        # State
        self.current_project: Optional[str] = None
        self.current_interpreter: Optional[InterpreterPackage] = None
        self.current_file: Optional[str] = None
        self.interpreter_generator = InterpreterGenerator()
        self.projects_dir = Path.home() / ".codex" / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self._execution_history = []

        # Attribute initialization (prevents W0201 warnings)
        self.interpreter_var: tk.StringVar = tk.StringVar(value="Select interpreter...")
        self.interpreter_combo: Optional[ttk.Combobox] = None
        self.status_label: Optional[ttk.Label] = None
        self.project_label: Optional[ttk.Label] = None

        # Load settings
        self.settings = self._load_settings()

        # Build UI
        self._build_ui()
        self._setup_menus()
        self._load_recent_projects()

    def _build_ui(self):
        """Build main UI layout."""
        # Create toolbar
        self._create_toolbar()

        # Create main paned window
        main_paned = ttk.PanedWindow(self, orient="horizontal")
        main_paned.pack(fill="both", expand=True)

        # Left panel: Project explorer
        left_paned = ttk.PanedWindow(main_paned, orient="vertical")
        main_paned.add(left_paned, weight=1)

        self.project_explorer = CodeExProjectExplorer(left_paned)
        left_paned.add(self.project_explorer, weight=1)

        # Center panel: Editor
        center_paned = ttk.PanedWindow(main_paned, orient="vertical")
        main_paned.add(center_paned, weight=3)

        self.editor = CodeExEditor(center_paned)
        center_paned.add(self.editor, weight=2)

        # Console
        self.console = CodeExConsole(center_paned)
        center_paned.add(self.console, weight=1)

        # Status bar
        self._create_status_bar()

    def _create_toolbar(self):
        """Create toolbar with buttons."""
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=5, pady=5)

        # Project buttons
        ttk.Button(toolbar, text="New Project", command=self.new_project).pack(
            side="left", padx=2
        )
        ttk.Button(toolbar, text="Open Project", command=self.open_project).pack(
            side="left", padx=2
        )
        ttk.Button(toolbar, text="Save", command=self.save_file).pack(
            side="left", padx=2
        )

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=5)

        # Language/Interpreter selector
        ttk.Label(toolbar, text="Interpreter:").pack(side="left", padx=5)
        self.interpreter_combo = ttk.Combobox(
            toolbar, textvariable=self.interpreter_var, state="readonly", width=20
        )
        self.interpreter_combo.pack(side="left", padx=5)
        self.interpreter_combo.bind(
            "<<ComboboxSelected>>", self._on_interpreter_selected
        )

        ttk.Button(
            toolbar, text="Load Interpreter", command=self.load_interpreter
        ).pack(side="left", padx=2)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=5)

        # Execution buttons
        ttk.Button(toolbar, text="▶ Run", command=self.run_code).pack(
            side="left", padx=2
        )
        ttk.Button(toolbar, text="⏹ Stop", command=self.stop_execution).pack(
            side="left", padx=2
        )

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=5)

        # Theme toggle
        ttk.Button(toolbar, text="🌙 Theme", command=self.toggle_theme).pack(
            side="right", padx=2
        )
        ttk.Button(toolbar, text="❓ Help", command=self.show_help).pack(
            side="right", padx=2
        )

    def _create_status_bar(self):
        """Create status bar."""
        status_frame = ttk.Frame(self)
        status_frame.pack(fill="x", side="bottom")

        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.pack(side="left", padx=5)

        self.project_label = ttk.Label(status_frame, text="No project loaded")
        self.project_label.pack(side="left", padx=5)

    def _setup_menus(self):
        """Setup menu bar."""
        self.menu = CodeExMenu(self.root, self)
        self.root.config(menu=self.menu)

    def _load_settings(self) -> Dict[str, Any]:
        """Load user settings."""
        settings_file = Path.home() / ".codex" / "settings.json"
        if settings_file.exists():
            with open(settings_file, encoding="utf-8") as f:
                return json.load(f)
        return {
            "theme": "light",
            "font_size": 11,
            "recent_projects": [],
        }

    def _save_settings(self):
        """Save user settings."""
        settings_file = Path.home() / ".codex" / "settings.json"
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2)

    def _load_recent_projects(self):
        """Load recent projects list."""
        recent = self.settings.get("recent_projects", [])
        self.interpreter_combo["values"] = recent if recent else ["No recent projects"]

    def _on_interpreter_selected(self, _event: Optional[tk.Event] = None) -> None:
        """Handle interpreter selection."""
        selected = self.interpreter_var.get()
        interpreter = self.interpreter_generator.get_interpreter(selected)
        if interpreter:
            self.current_interpreter = interpreter
            if self.status_label:
                self.status_label.config(text=f"Loaded: {selected}")

    def new_project(self):
        """Create new project."""
        dialog = NewProjectDialog(self.root)
        if dialog.result:
            project_name = dialog.result["name"]
            project_path = self.projects_dir / project_name
            project_path.mkdir(parents=True, exist_ok=True)

            # Create project structure
            (project_path / "src").mkdir(exist_ok=True)
            (project_path / "examples").mkdir(exist_ok=True)
            (project_path / "tests").mkdir(exist_ok=True)

            # Create project metadata
            metadata = {
                "name": project_name,
                "created": datetime.now().isoformat(),
                "interpreter": dialog.result.get("interpreter", ""),
                "description": dialog.result.get("description", ""),
            }

            with open(project_path / "project.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            self.current_project = str(project_path)
            self.project_label.config(text=f"Project: {project_name}")
            messagebox.showinfo("Success", f"Project created: {project_name}")

    def open_project(self):
        """Open existing project."""
        project_path = filedialog.askdirectory(
            initialdir=str(self.projects_dir), title="Select CodeEx project"
        )
        if project_path:
            self.current_project = project_path
            project_name = Path(project_path).name
            self.project_label.config(text=f"Project: {project_name}")

            # Load project metadata
            metadata_file = Path(project_path) / "project.json"
            if metadata_file.exists():
                with open(metadata_file, encoding="utf-8") as f:
                    metadata = json.load(f)
                    interpreter_name = metadata.get("interpreter", "")
                    if interpreter_name:
                        self.interpreter_var.set(interpreter_name)

    def load_interpreter(self):
        """Load interpreter from ParserCraft config."""
        config_file = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("YAML", "*.yaml"), ("All", "*.*")],
            title="Select ParserCraft language configuration",
        )
        if config_file:
            try:
                config = LanguageConfig.load(config_file)
                interpreter = self.interpreter_generator.generate(config)
                self.current_interpreter = interpreter
                self.status_label.config(text=f"Loaded interpreter: {config.name}")

                # Add to dropdown
                values = list(self.interpreter_combo["values"])
                if config.name not in values:
                    values.append(config.name)
                    self.interpreter_combo["values"] = values

                self.interpreter_var.set(config.name)
                messagebox.showinfo("Success", f"Interpreter loaded: {config.name}")
            except (OSError, IOError, ValueError, AttributeError) as e:
                messagebox.showerror("Error", f"Failed to load interpreter:\n{e}")

    def save_file(self):
        """Save current file."""
        if not self.current_file:
            self.current_file = filedialog.asksaveasfilename(
                initialdir=str(self.projects_dir / self.current_project or "."),
                filetypes=[("ParserCraft", "*.cc"), ("All", "*.*")],
            )

        if self.current_file:
            content = self.editor.get_content()
            with open(self.current_file, "w", encoding="utf-8") as f:
                f.write(content)
            self.status_label.config(text=f"Saved: {Path(self.current_file).name}")

    def run_code(self):
        """Execute current code."""
        if not self.current_interpreter:
            messagebox.showwarning("Warning", "No interpreter loaded")
            return

        code = self.editor.get_content()
        if not code:
            messagebox.showwarning("Warning", "No code to execute")
            return

        try:
            result = self.current_interpreter.execute(code)

            # Track execution history
            exec_info = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "status": result["status"],
                "interpreter": self.current_interpreter.name,
            }
            self._execution_history.append(exec_info)

            # Display result
            self.console.clear()
            if result["status"] == "success":
                self.console.write(result["output"], "output")
                self.status_label.config(text="Execution successful")
            else:
                self.console.write("\n".join(result["errors"]), "error")
                self.status_label.config(text="Execution failed")

        except (RuntimeError, TypeError, ValueError) as e:
            self.console.write(str(e), "error")
            self.status_label.config(text="Error during execution")

    def stop_execution(self):
        """Stop code execution."""
        self.status_label.config(text="Execution stopped")

    def toggle_theme(self):
        """Toggle color theme."""
        current = self.settings.get("theme", "light")
        new_theme = "dark" if current == "light" else "light"
        self.settings["theme"] = new_theme
        self._save_settings()
        messagebox.showinfo("Theme", f"Switched to {new_theme} theme")

    def show_help(self):
        """Show help dialog."""
        help_text = """
        CodeEx - ParserCraft Execution Environment

        Getting Started:
        1. Create a new project (File → New Project)
        2. Load a ParserCraft interpreter (Load Interpreter button)
        3. Write code in the editor
        4. Click Run to execute

        Features:
        - Multi-interpreter support
        - Project management
        - Integrated console
        - Syntax highlighting
        - Real-time execution

        Keyboard Shortcuts:
        Ctrl+N: New file
        Ctrl+O: Open file
        Ctrl+S: Save file
        Ctrl+R: Run code
        F5: Run code
        Ctrl+Q: Quit

        For more information, visit the documentation.
        """
        messagebox.showinfo("Help", help_text)

    def undo_action(self):
        """Undo last editor action."""
        try:
            self.editor.text.edit_undo()
            self.status_label.config(text="Undo complete")
        except tk.TclError:
            self.status_label.config(text="Nothing to undo")

    def redo_action(self):
        """Redo last undone action."""
        try:
            self.editor.text.edit_redo()
            self.status_label.config(text="Redo complete")
        except tk.TclError:
            self.status_label.config(text="Nothing to redo")

    def cut_text(self):
        """Cut selected text to clipboard."""
        try:
            self.editor.text.event_generate("<<Cut>>")
            self.status_label.config(text="Text cut")
        except (AttributeError, TclError) as e:
            self.status_label.config(text=f"Cut failed: {e}")

    def copy_text(self):
        """Copy selected text to clipboard."""
        try:
            self.editor.text.event_generate("<<Copy>>")
            self.status_label.config(text="Text copied")
        except (AttributeError, TclError) as e:
            self.status_label.config(text=f"Copy failed: {e}")

    def paste_text(self):
        """Paste text from clipboard."""
        try:
            self.editor.text.event_generate("<<Paste>>")
            self.status_label.config(text="Text pasted")
        except (AttributeError, TclError) as e:
            self.status_label.config(text=f"Paste failed: {e}")

    def create_language_config(self):
        """Create a new language configuration file."""
        template = {
            "name": "MyLanguage",
            "version": "1.0.0",
            "description": "My custom language",
            "keywords": ["print", "var", "if", "else", "while"],
            "functions": {
                "print": {"params": ["value"], "description": "Print output"}
            },
            "operators": ["+", "-", "*", "/", "=", "==", "!="],
            "comments": "#",
            "string_delimiters": ["'", '"'],
        }

        save_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("YAML", "*.yaml")],
            title="Save language configuration",
        )

        if save_path:
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(template, f, indent=2)
                messagebox.showinfo(
                    "Success", f"Configuration template created:\n{save_path}"
                )
                self.status_label.config(text=f"Created: {Path(save_path).name}")
            except (OSError, IOError, ValueError) as e:
                messagebox.showerror("Error", f"Failed to create config:\n{e}")

    def interpreter_settings(self):
        """Open interpreter settings dialog."""
        if not self.current_interpreter:
            messagebox.showwarning("Warning", "No interpreter loaded")
            return

        config = self.current_interpreter.config
        info = f"""
        Interpreter Settings

        Name: {config.name}
        Keywords: {len(config.keywords)} defined
        Functions: {len(config.functions)} defined
        Operators: {len(config.operators)} defined

        Settings:
        - Case Sensitive: {config.case_sensitive}
        - File Extension: {config.file_extension}
        - Indent Style: {config.indent_style}
        - Indent Size: {config.indent_size}
        """
        messagebox.showinfo("Interpreter Settings", info)

    def recent_executions(self):
        """Show recent executions."""
        if not hasattr(self, "_execution_history"):
            self._execution_history = []

        if not self._execution_history:
            messagebox.showinfo("Recent Executions", "No executions recorded yet")
            return

        history_text = "Recent Executions (last 10):\n\n"
        for i, exec_info in enumerate(self._execution_history[-10:], 1):
            history_text += f"{i}. {exec_info['time']} - {exec_info['status']}\n"

        messagebox.showinfo("Recent Executions", history_text)

    def zoom_in(self):
        """Increase editor font size."""
        current_size = int(self.editor.text.cget("font").split()[-1])
        new_size = min(current_size + 2, 24)
        self.editor.text.config(font=("Courier", new_size))
        self.status_label.config(text=f"Font size: {new_size}")

    def zoom_out(self):
        """Decrease editor font size."""
        current_size = int(self.editor.text.cget("font").split()[-1])
        new_size = max(current_size - 2, 8)
        self.editor.text.config(font=("Courier", new_size))
        self.status_label.config(text=f"Font size: {new_size}")

    def toggle_console(self):
        """Toggle console visibility."""
        if hasattr(self, "console"):
            current_state = self.console.winfo_viewable()
            if current_state:
                self.console.pack_forget()
                self.status_label.config(text="Console hidden")
            else:
                self.console.pack(fill="both", expand=True, padx=5, pady=5)
                self.status_label.config(text="Console shown")

    def toggle_explorer(self):
        """Toggle project explorer visibility."""
        if hasattr(self, "project_explorer"):
            current_state = self.project_explorer.winfo_viewable()
            if current_state:
                self.project_explorer.pack_forget()
                self.status_label.config(text="Explorer hidden")
            else:
                self.project_explorer.pack(fill="both", expand=True)
                self.status_label.config(text="Explorer shown")

    def show_getting_started(self):
        """Show getting started guide."""
        guide = """
        Getting Started with CodeEx

        Step 1: Create a Project
        - Click File → New Project
        - Enter a project name (e.g., 'MyProject')
        - Add optional description
        - Click Create

        Step 2: Load a Language
        - Click 'Load Interpreter' button
        - Navigate to configs/examples/
        - Select a language config (e.g., python_like.yaml)
        - Language is now loaded

        Step 3: Write Code
        - Type code in the editor
        - Syntax highlighting applies automatically
        - Use line numbers for reference

        Step 4: Execute Code
        - Press Ctrl+R or click ▶ Run
        - Output appears in console
        - Errors shown in red

        Step 5: Save Your Work
        - Press Ctrl+S
        - Choose location in project
        - File is saved

        Keyboard Shortcuts:
        Ctrl+N - New Project
        Ctrl+O - Open Project
        Ctrl+S - Save File
        Ctrl+R - Run Code
        Ctrl+Z - Undo
        Ctrl+Shift+Z - Redo
        """
        messagebox.showinfo("Getting Started", guide)

    def show_user_guide(self):
        """Show user guide."""
        guide = """
        CodeEx User Guide - Features Overview

        PROJECT MANAGEMENT
        - Create projects with structure
        - Open existing projects
        - Organize code in src/ folder
        - Store examples in examples/
        - Keep tests in tests/

        EDITOR FEATURES
        - Syntax highlighting
        - Line number display
        - Undo/Redo (Ctrl+Z, Ctrl+Shift+Z)
        - Cut/Copy/Paste
        - Text selection and editing

        EXECUTION
        - Load ParserCraft interpreters
        - Execute code (Ctrl+R)
        - View output in console
        - See error messages
        - Inspect variables

        MENUS
        File: Project management
        Edit: Text editing operations
        Interpreter: Language selection
        Run: Code execution
        View: Display options
        Help: Documentation

        For complete guide, see CODEX_USER_GUIDE.md
        """
        messagebox.showinfo("User Guide", guide)

    def show_api_reference(self):
        """Show API reference."""
        api_ref = """
        CodeEx API Reference

        CODEX IDE METHODS
        - new_project() - Create new project
        - open_project() - Load existing project
        - load_interpreter() - Import language config
        - save_file() - Save current file
        - run_code() - Execute code
        - stop_execution() - Halt execution

        INTERPRETER METHODS
        - execute(code) - Run code and return result
        - to_dict() - Serialize to dictionary
        - to_json() - Serialize to JSON
        - to_pickle() - Serialize to binary

        RESULT FORMAT
        {
            "status": "success" or "error",
            "output": "program output",
            "errors": ["error messages"],
            "variables": {...}
        }

        For detailed API, see CODEX_DEVELOPER_GUIDE.md
        """
        messagebox.showinfo("API Reference", api_ref)

    def show_about_parsercraft(self):
        """Show about ParserCraft dialog."""
        about = """
        ParserCraft - Language Construction System
        Version 4.0

        A comprehensive system for creating custom
        programming languages without deep knowledge
        of compiler theory.

        Features:
        - Language definition framework
        - Code execution engine
        - IDE with syntax highlighting
        - Integration with CodeEx

        For more information, visit the project
        documentation or run:
        python -c "import parsercraft; help(parsercraft)"
        """
        messagebox.showinfo("About ParserCraft", about)


class NewProjectDialog(tk.Toplevel):
    """Dialog for creating new project."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("New CodeEx Project")
        self.geometry("400x300")
        self.result = None

        # Name
        ttk.Label(self, text="Project Name:").grid(
            row=0, column=0, sticky="w", padx=10, pady=10
        )
        self.name_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.name_var, width=30).grid(
            row=0, column=1, padx=10, pady=10
        )

        # Description
        ttk.Label(self, text="Description:").grid(
            row=1, column=0, sticky="nw", padx=10, pady=10
        )
        self.desc_text = scrolledtext.ScrolledText(self, height=5, width=30)
        self.desc_text.grid(row=1, column=1, padx=10, pady=10)

        # Interpreter
        ttk.Label(self, text="Interpreter:").grid(
            row=2, column=0, sticky="w", padx=10, pady=10
        )
        self.interp_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.interp_var, width=30).grid(
            row=2, column=1, padx=10, pady=10
        )

        # Buttons
        button_frame = ttk.Frame(self)
        button_frame.grid(row=3, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Create", command=self._create).pack(
            side="left", padx=5
        )
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(
            side="left", padx=5
        )

        self.transient(parent)
        self.grab_set()

    def _create(self):
        """Create project with entered info."""
        if not self.name_var.get():
            messagebox.showwarning("Warning", "Project name is required")
            return

        self.result = {
            "name": self.name_var.get(),
            "description": self.desc_text.get("1.0", "end-1c"),
            "interpreter": self.interp_var.get(),
        }
        self.destroy()
