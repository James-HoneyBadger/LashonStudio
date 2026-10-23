"""ParserCraft Studio — a full language-design workbench.

Layout:
    project sidebar | source / grammar / language editors
                    | console / variables / generated backends / AST

All behaviour lives in :class:`parsercraft.ide.studio.LanguageStudio`; this
module only wires it to Tkinter widgets.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Dict, Optional

import yaml

from parsercraft.ide.editor import CodeEditor
from parsercraft.ide.studio import (
    LanguageStudio,
    StudioProject,
    StudioResult,
)

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BG = "#0d1117"
PANEL = "#161b22"
PANEL_ALT = "#21262d"
BORDER = "#30363d"
FG = "#c9d1d9"
MUTED = "#8b949e"
ACCENT = "#58a6ff"
GREEN = "#3fb950"
RED = "#f85149"
YELLOW = "#d29922"

UI_FONT = ("DejaVu Sans", 10)
UI_FONT_BOLD = ("DejaVu Sans", 10, "bold")
TITLE_FONT = ("DejaVu Sans", 17, "bold")
MONO_FONT = ("Courier New", 10)

BACKENDS = ("python", "c", "wasm", "llvm")
BACKEND_TITLES = {
    "python": "Python",
    "c": "C",
    "wasm": "WASM",
    "llvm": "LLVM IR",
}


class ParserCraftIDE(tk.Tk):
    """ParserCraft Studio main window."""

    def __init__(self, project_path: Optional[str] = None,
                 source_path: Optional[str] = None):
        super().__init__()
        self.title("ParserCraft Studio")
        self.geometry("1440x900")
        self.minsize(1120, 720)
        self.configure(bg=BG)

        self.studio = LanguageStudio()
        self.project: Optional[StudioProject] = None
        self._tree_paths: Dict[str, tuple[str, Optional[Path]]] = {}
        self._loading = False
        self._auto_validate_job: Optional[str] = None

        self._configure_theme()
        self._build_menu()
        self._build_header()
        self._build_body()
        self._build_status_bar()
        self._bind_shortcuts()

        self._initial_load(project_path, source_path)

    # ------------------------------------------------------------------
    # Theme / construction
    # ------------------------------------------------------------------

    def _configure_theme(self) -> None:
        try:
            self.tk.call("tk", "scaling", 1.1)
        except tk.TclError:  # pragma: no cover - platform dependent
            pass
        self.option_add("*Font", UI_FONT)

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:  # pragma: no cover - theme availability
            pass

        style.configure(".", background=BG, foreground=FG,
                        fieldbackground=PANEL, bordercolor=BORDER)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=MUTED,
                        padding=(16, 8), borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", PANEL_ALT)],
                  foreground=[("selected", ACCENT)])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL,
                        foreground=FG, rowheight=25, borderwidth=0)
        style.configure("Treeview.Heading", background=PANEL_ALT,
                        foreground=MUTED, borderwidth=0)
        style.map("Treeview",
                  background=[("selected", "#1f6feb")],
                  foreground=[("selected", "#ffffff")])
        style.configure("Vertical.TScrollbar", background=PANEL_ALT,
                        troughcolor=BG, borderwidth=0, arrowcolor=MUTED)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self, tearoff=0)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Project…", accelerator="Ctrl+N",
                              command=self._new_project)
        file_menu.add_command(label="Open Project…", accelerator="Ctrl+O",
                              command=self._open_project)
        file_menu.add_command(label="Open Language Config…",
                              command=self._open_config)
        file_menu.add_separator()
        file_menu.add_command(label="Save Project", accelerator="Ctrl+S",
                              command=self._save_project)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo", accelerator="Ctrl+Z",
                              command=lambda: self._edit_event("<<Undo>>"))
        edit_menu.add_command(label="Redo", accelerator="Ctrl+Y",
                              command=lambda: self._edit_event("<<Redo>>"))
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", accelerator="Ctrl+X",
                              command=lambda: self._edit_event("<<Cut>>"))
        edit_menu.add_command(label="Copy", accelerator="Ctrl+C",
                              command=lambda: self._edit_event("<<Copy>>"))
        edit_menu.add_command(label="Paste", accelerator="Ctrl+V",
                              command=lambda: self._edit_event("<<Paste>>"))
        menubar.add_cascade(label="Edit", menu=edit_menu)

        run_menu = tk.Menu(menubar, tearoff=0)
        run_menu.add_command(label="Validate Grammar", accelerator="Ctrl+Shift+V",
                             command=self._validate_grammar)
        run_menu.add_command(label="Parse Source", accelerator="F6",
                             command=self._parse_source)
        run_menu.add_command(label="Run Program", accelerator="F5",
                             command=self._run_program)
        run_menu.add_separator()
        run_menu.add_command(label="Generate All Backends", accelerator="F7",
                             command=self._generate_all)
        menubar.add_cascade(label="Run", menu=run_menu)

        sample_menu = tk.Menu(menubar, tearoff=0)
        sample_menu.add_command(label="Open Aurora Reference Project",
                                command=self._load_sample_project)
        menubar.add_cascade(label="Samples", menu=sample_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About ParserCraft Studio",
                              command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=16, pady=(12, 0))

        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left")
        tk.Label(brand, text="◆ ParserCraft Studio", bg=BG, fg=ACCENT,
                 font=TITLE_FONT).pack(anchor="w")
        tk.Label(
            brand,
            text="Design a grammar · parse source · run it · emit four backends",
            bg=BG, fg=MUTED, font=UI_FONT,
        ).pack(anchor="w")

        self.project_label = tk.Label(
            header, text="No project", bg=BG, fg=FG, font=UI_FONT_BOLD
        )
        self.project_label.pack(side="right", anchor="e")

        toolbar = tk.Frame(self, bg=PANEL, highlightthickness=1,
                           highlightbackground=BORDER)
        toolbar.pack(fill="x", padx=16, pady=(10, 10))

        self._tool_button(toolbar, "＋ New", self._new_project)
        self._tool_button(toolbar, "⌂ Open", self._open_project)
        self._tool_button(toolbar, "▣ Save", self._save_project)
        self._separator(toolbar)
        self._tool_button(toolbar, "✓ Validate", self._validate_grammar)
        self._tool_button(toolbar, "◈ Parse", self._parse_source)
        self._tool_button(toolbar, "▶ Run", self._run_program, accent=True)
        self._tool_button(toolbar, "⇩ Generate all", self._generate_all)
        self._separator(toolbar)
        self._tool_button(toolbar, "Aurora sample", self._load_sample_project)

    def _tool_button(self, parent: tk.Widget, text: str, command,
                     accent: bool = False) -> tk.Button:
        background = ACCENT if accent else PANEL_ALT
        foreground = BG if accent else FG
        button = tk.Button(
            parent, text=text, command=command,
            bg=background, fg=foreground,
            activebackground=ACCENT, activeforeground=BG,
            relief="flat", bd=0, padx=12, pady=6,
            font=UI_FONT_BOLD, cursor="hand2",
        )
        button.pack(side="left", padx=(8, 0), pady=6)
        return button

    @staticmethod
    def _separator(parent: tk.Widget) -> None:
        tk.Frame(parent, bg=BORDER, width=1, height=24).pack(
            side="left", padx=12, pady=8
        )

    def _build_body(self) -> None:
        body = tk.PanedWindow(self, orient="horizontal", bg=BORDER,
                              sashwidth=6, bd=0, sashrelief="flat")
        body.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        sidebar = tk.Frame(body, bg=PANEL)
        self._build_sidebar(sidebar)
        body.add(sidebar, width=260, minsize=190)

        right = tk.PanedWindow(body, orient="vertical", bg=BORDER,
                               sashwidth=6, bd=0, sashrelief="flat")
        body.add(right, minsize=700)

        self.editor_tabs = ttk.Notebook(right)
        right.add(self.editor_tabs, height=560)

        self.source_editor = self._create_editor("Source", [])
        self.grammar_editor = self._create_editor(
            "Grammar", ["IDENT", "NUMBER", "STRING", "NEWLINE", "EOF"]
        )
        self.language_editor = self._create_editor("Language", [])

        for editor in (
            self.source_editor, self.grammar_editor, self.language_editor
        ):
            editor.text.bind(
                "<KeyRelease>",
                lambda _event, ed=editor: self._update_cursor(ed),
                add="+",
            )
            editor.text.bind(
                "<ButtonRelease-1>",
                lambda _event, ed=editor: self._update_cursor(ed),
                add="+",
            )

        self.source_editor.on_change(
            lambda: self._on_editor_changed("source")
        )
        self.grammar_editor.on_change(
            lambda: self._on_editor_changed("grammar")
        )
        self.language_editor.on_change(
            lambda: self._on_editor_changed("language")
        )

        self.output_tabs = ttk.Notebook(right)
        right.add(self.output_tabs, height=260)
        self._build_output_tabs()

    def _build_sidebar(self, parent: tk.Widget) -> None:
        tk.Label(parent, text="PROJECT", bg=PANEL, fg=MUTED,
                 font=("DejaVu Sans", 9, "bold"), anchor="w").pack(
            fill="x", padx=14, pady=(14, 6)
        )
        self.project_tree = ttk.Treeview(parent, show="tree",
                                         selectmode="browse")
        self.project_tree.pack(fill="both", expand=True, padx=8)
        self.project_tree.bind("<<TreeviewSelect>>", self._open_tree_item)

        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=12,
                                                  pady=10)
        self.project_info = tk.Label(
            parent, text="Open a project to begin.", bg=PANEL, fg=MUTED,
            justify="left", anchor="nw", font=UI_FONT, wraplength=225,
        )
        self.project_info.pack(fill="x", padx=14, pady=(0, 14))

    def _create_editor(self, title: str, keywords: list[str]) -> CodeEditor:
        frame = tk.Frame(self.editor_tabs, bg=BG)
        self.editor_tabs.add(frame, text=title)
        editor = CodeEditor(frame, keywords=keywords)
        editor.pack(fill="both", expand=True)
        return editor

    def _build_output_tabs(self) -> None:
        self.console = self._add_text_tab("Console")
        for level, color in (("info", FG), ("success", GREEN),
                             ("error", RED), ("warning", YELLOW),
                             ("command", ACCENT)):
            self.console.tag_configure(level, foreground=color)

        variables_frame = tk.Frame(self.output_tabs, bg=BG)
        self.output_tabs.add(variables_frame, text="Variables")
        self.variables_tree = ttk.Treeview(
            variables_frame, columns=("name", "value"), show="headings"
        )
        self.variables_tree.heading("name", text="Name")
        self.variables_tree.heading("value", text="Value")
        self.variables_tree.column("name", width=180, anchor="w")
        self.variables_tree.column("value", width=560, anchor="w")
        self.variables_tree.pack(fill="both", expand=True)

        self.code_views: Dict[str, tk.Text] = {}
        for backend in BACKENDS:
            self.code_views[backend] = self._add_text_tab(
                BACKEND_TITLES[backend]
            )

        ast_frame = tk.Frame(self.output_tabs, bg=BG)
        self.output_tabs.add(ast_frame, text="AST")
        self.ast_tree = ttk.Treeview(ast_frame, show="tree")
        ast_scroll = ttk.Scrollbar(ast_frame, orient="vertical",
                                   command=self.ast_tree.yview)
        self.ast_tree.configure(yscrollcommand=ast_scroll.set)
        ast_scroll.pack(side="right", fill="y")
        self.ast_tree.pack(fill="both", expand=True)

    def _add_text_tab(self, title: str) -> tk.Text:
        frame = tk.Frame(self.output_tabs, bg=PANEL)
        self.output_tabs.add(frame, text=title)
        text = tk.Text(
            frame, wrap="none", bg=PANEL, fg=FG, font=MONO_FONT,
            insertbackground=FG, selectbackground="#264f78",
            state="disabled", padx=10, pady=8,
        )
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        return text

    def _build_status_bar(self) -> None:
        status = tk.Frame(self, bg=PANEL, highlightthickness=1,
                          highlightbackground=BORDER)
        status.pack(fill="x", side="bottom")
        self.status_label = tk.Label(
            status, text="Ready", bg=PANEL, fg=FG, anchor="w",
            font=UI_FONT, padx=12, pady=4,
        )
        self.status_label.pack(side="left")
        self.detail_label = tk.Label(
            status, text="", bg=PANEL, fg=MUTED, anchor="e",
            font=UI_FONT, padx=12, pady=4,
        )
        self.detail_label.pack(side="right")

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-n>", lambda _e: self._new_project())
        self.bind("<Control-o>", lambda _e: self._open_project())
        self.bind("<Control-s>", lambda _e: self._save_project())
        self.bind("<Control-Shift-V>", lambda _e: self._validate_grammar())
        self.bind("<Control-Shift-v>", lambda _e: self._validate_grammar())
        self.bind("<F5>", lambda _e: self._run_program())
        self.bind("<F6>", lambda _e: self._parse_source())
        self.bind("<F7>", lambda _e: self._generate_all())

    # ------------------------------------------------------------------
    # Loading / saving
    # ------------------------------------------------------------------

    def _initial_load(self, project_path: Optional[str],
                      source_path: Optional[str]) -> None:
        loaded = False
        if project_path:
            loaded = self._load_project(project_path)
        else:
            sample = LanguageStudio.sample_project_path()
            if sample is not None:
                loaded = self._load_project(sample)

        if not loaded:
            self._log("Welcome to ParserCraft Studio.", "info")
            self._log("Open a project or load the Aurora sample to begin.",
                      "info")
            self._set_status("Ready — no project loaded")

        if source_path:
            self._load_source_file(Path(source_path))

    def _load_project(self, path: str | Path) -> bool:
        try:
            project = self.studio.open_project(path)
        except Exception as error:
            self._log(f"Could not open project: {error}", "error")
            self._set_status("Open failed", "error")
            return False

        self.project = project
        self._loading = True
        self.grammar_editor.set_text(project.grammar_text)
        self.language_editor.set_text(
            yaml.safe_dump(project.config, sort_keys=False, allow_unicode=True)
        )
        self.source_editor.set_text(self.studio.current_source)
        self.source_editor.set_keywords(self.studio.highlight_keywords())
        self._loading = False

        self._retitle_editor_tabs()
        self._refresh_project_tree()
        self._update_project_info()
        self.title(f"ParserCraft Studio — {project.name}")
        self.project_label.config(
            text=f"{project.name}  ·  {project.config.get('version', '')}"
        )

        self._log(f"Opened project: {project.name} ({project.root})", "success")
        self._validate_grammar(log_success=False)
        self._set_status(f"Loaded {project.name}")
        return True

    def _retitle_editor_tabs(self) -> None:
        sample_name = (
            self.project.sample_path.name
            if self.project and self.project.sample_path else "source"
        )
        self.editor_tabs.tab(0, text=sample_name)
        self.editor_tabs.tab(1, text="grammar.peg")
        self.editor_tabs.tab(2, text="language.yaml")

    def _refresh_project_tree(self) -> None:
        self.project_tree.delete(*self.project_tree.get_children())
        self._tree_paths.clear()
        if self.project is None:
            return

        root = self.project_tree.insert(
            "", "end", text=f"◆ {self.project.name}", open=True
        )
        language_item = self.project_tree.insert(
            root, "end", text="⚙ language.yaml"
        )
        grammar_item = self.project_tree.insert(
            root, "end", text="λ grammar.peg"
        )
        self._tree_paths[language_item] = ("language", self.project.config_path)
        self._tree_paths[grammar_item] = (
            "grammar", self.project.root / "grammar.peg"
        )

        samples_root = self.project_tree.insert(
            root, "end", text="▸ samples", open=True
        )
        for sample in self.project.sample_files():
            item = self.project_tree.insert(
                samples_root, "end", text=f"• {sample.name}"
            )
            self._tree_paths[item] = ("source", sample)

    def _update_project_info(self) -> None:
        if self.project is None:
            self.project_info.config(text="Open a project to begin.")
            return
        summary = self.project.summary()
        self.project_info.config(
            text=(
                f"{summary['rules']} grammar rules\n"
                f"{summary['keywords']} keywords\n"
                f"{summary['samples']} sample programs\n\n"
                f"{summary['root']}"
            )
        )
        self._update_cursor(self.source_editor)

    def _open_tree_item(self, _event: Any = None) -> None:
        selection = self.project_tree.selection()
        if not selection:
            return
        kind, path = self._tree_paths.get(selection[0], ("", None))
        if kind == "language":
            self.editor_tabs.select(2)
        elif kind == "grammar":
            self.editor_tabs.select(1)
        elif kind == "source" and path is not None:
            self._load_source_file(path)

    def _load_source_file(self, path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as error:
            self._log(f"Could not read {path}: {error}", "error")
            return
        self.source_editor.set_text(content)
        self.studio.current_source = content
        self.editor_tabs.tab(0, text=path.name)
        self.editor_tabs.select(0)
        self._set_status(f"Opened {path.name}")

    def _sync_documents(self) -> bool:
        """Apply the language YAML and grammar editors to the studio."""
        if self.project is None:
            return False

        yaml_text = self.language_editor.get_text().strip()
        if yaml_text:
            try:
                data = yaml.safe_load(yaml_text)
            except yaml.YAMLError as error:
                self._log(f"Language YAML error: {error}", "error")
                self._set_status("Invalid language YAML", "error")
                return False
            if not isinstance(data, dict):
                self._log("Language YAML must contain a mapping.", "error")
                return False
            self.project.config = data

        self.studio.set_grammar_text(self.grammar_editor.get_text())
        self.studio.current_source = self.source_editor.get_text()
        return True

    def _save_project(self) -> None:
        if self.project is None:
            self._log("No project is open.", "warning")
            return
        if not self._sync_documents():
            return
        if not self._validate_grammar(log_success=False):
            self._log("Fix grammar errors before saving.", "error")
            return
        try:
            self.studio.save_project()
        except Exception as error:
            self._log(f"Save failed: {error}", "error")
            self._set_status("Save failed", "error")
            return
        # Reload the normalized YAML so the editor reflects persisted state.
        self._loading = True
        self.language_editor.set_text(
            yaml.safe_dump(self.project.config, sort_keys=False,
                           allow_unicode=True)
        )
        self._loading = False
        self._refresh_project_tree()
        self._update_project_info()
        self._log(f"Saved {self.project.config_path}", "success")
        self._set_status("Project saved", "success")

    # ------------------------------------------------------------------
    # Editor events
    # ------------------------------------------------------------------

    def _on_editor_changed(self, which: str) -> None:
        if self._loading:
            return
        if which == "grammar":
            self.studio.set_grammar_text(self.grammar_editor.get_text())
            if self._auto_validate_job:
                self.after_cancel(self._auto_validate_job)
            self._auto_validate_job = self.after(800, self._auto_validate)
            self._set_status("Grammar modified")
        elif which == "source":
            self._set_status("Source modified")
        else:
            self._set_status("Language config modified")

    def _auto_validate(self) -> None:
        self._auto_validate_job = None
        if self.project is None:
            return
        result = self.studio.validate_grammar(self.grammar_editor.get_text())
        if result.ok:
            self.source_editor.set_keywords(self.studio.highlight_keywords())
            self._set_status("Grammar OK", "success")
            self._update_project_info()
        else:
            self._set_status("Grammar error", "error")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _load_sample_project(self) -> None:
        sample = LanguageStudio.sample_project_path()
        if sample is None:
            messagebox.showinfo(
                "Sample project",
                "The Aurora reference project was not found in this checkout.",
                parent=self,
            )
            return
        self._load_project(sample)

    def _new_project(self) -> None:
        directory = filedialog.askdirectory(
            parent=self, title="Choose a folder for the new language project"
        )
        if not directory:
            return
        name = simpledialog.askstring(
            "New language", "Language name:", parent=self,
            initialvalue="MyLanguage",
        )
        if not name:
            return
        try:
            project = self.studio.new_project(name, directory)
        except Exception as error:
            self._log(f"Could not create project: {error}", "error")
            return
        self._load_project(project.root)

    def _open_project(self) -> None:
        directory = filedialog.askdirectory(
            parent=self, title="Open language project"
        )
        if directory:
            self._load_project(directory)

    def _open_config(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Open language configuration",
            filetypes=[("Language config", "*.yaml *.yml *.json"),
                       ("All files", "*.*")],
        )
        if path:
            self._load_project(path)

    def _validate_grammar(self, log_success: bool = True) -> bool:
        if self.project is None:
            return False
        if not self._sync_documents():
            return False
        result = self.studio.validate_grammar(self.grammar_editor.get_text())
        if result.ok:
            self.source_editor.set_keywords(self.studio.highlight_keywords())
            self._update_project_info()
            self._set_status(
                f"Grammar OK — {result.elapsed_ms:.1f} ms", "success"
            )
            if log_success:
                self._log(result.text, "success")
            return True
        for diagnostic in result.diagnostics:
            self._log(diagnostic.message, "error")
        self._set_status("Grammar invalid", "error")
        return False

    def _parse_source(self) -> None:
        if self.project is None or not self._sync_documents():
            return
        result = self.studio.parse(self.source_editor.get_text())
        if not result.ok:
            self._report_failure(result, "Parse failed")
            return
        self._fill_ast(result.value)
        self.output_tabs.select(6)
        self._log(
            f"Parse OK — {result.elapsed_ms:.1f} ms", "success"
        )
        self._set_status("Parse OK", "success")

    def _run_program(self) -> None:
        if self.project is None or not self._sync_documents():
            return
        self._log("▶ Running program…", "command")
        result = self.studio.run(self.source_editor.get_text())
        if result.text:
            for line in result.text.splitlines():
                self._log(line, "info")
        if not result.ok:
            self._report_failure(result, "Run failed")
            return

        self._set_code("python", self.studio.last_python)
        self._fill_variables(result.value or {})
        parse_result = self.studio.parse(self.source_editor.get_text())
        if parse_result.ok:
            self._fill_ast(parse_result.value)
        self.output_tabs.select(0)
        self._log(f"Finished in {result.elapsed_ms:.1f} ms", "success")
        self._set_status("Run complete", "success")

    def _generate_all(self) -> None:
        if self.project is None or not self._sync_documents():
            return
        source = self.source_editor.get_text()
        results = self.studio.generate_all(source)
        for backend, result in results.items():
            if result.ok:
                text = result.text
                for warning in result.warnings:
                    text = f"// WARNING: {warning}\n{text}"
                self._set_code(backend, text)
            else:
                self._set_code(backend, f"// {backend} generation failed\n"
                                       f"// {result.error}")
        partial = [
            name for name, result in results.items()
            if result.ok and not result.supported
        ]
        for name in partial:
            self._log(f"{name} output is partial — see its pane", "warning")

        failures = [name for name, result in results.items() if not result.ok]
        if failures:
            self._log(
                "Generation failed for: " + ", ".join(failures), "error"
            )
            self._set_status("Generation failed", "error")
        else:
            self._log(
                "Generated Python, C, WASM, and LLVM IR", "success"
            )
            self._set_status("All backends generated", "success")
        self.output_tabs.select(2)

    def _report_failure(self, result: StudioResult, context: str) -> None:
        self._log(f"{context}: {result.error}", "error")
        for diagnostic in result.diagnostics:
            if diagnostic.message != result.error:
                for line in diagnostic.message.splitlines():
                    self._log(line, "error")
        self._set_status(context, "error")

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def _log(self, message: str, level: str = "info") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console.config(state="normal")
        self.console.insert("end", f"[{timestamp}] {message}\n", level)
        self.console.see("end")
        self.console.config(state="disabled")

    def _set_code(self, backend: str, text: str) -> None:
        widget = self.code_views[backend]
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.config(state="disabled")

    def _fill_variables(self, namespace: Dict[str, Any]) -> None:
        self.variables_tree.delete(*self.variables_tree.get_children())
        for name, value in sorted(namespace.items()):
            self.variables_tree.insert("", "end", values=(name, repr(value)))

    def _fill_ast(self, ast) -> None:
        self.ast_tree.delete(*self.ast_tree.get_children())
        data = self.studio.ast_tree(ast)[0]

        def insert(parent: str, node: dict, depth: int) -> None:
            item = self.ast_tree.insert(
                parent, "end", text=node["label"], open=depth < 2
            )
            for child in node["children"]:
                insert(item, child, depth + 1)

        insert("", data, 0)

    def _update_cursor(self, editor: CodeEditor) -> None:
        """Show cursor position alongside project summary."""
        try:
            line, column = editor.text.index("insert").split(".")
        except (tk.TclError, ValueError):  # pragma: no cover - widget teardown
            return
        if self.project is not None:
            summary = self.project.summary()
            prefix = (
                f"rules {summary['rules']}  ·  samples {summary['samples']}"
            )
        else:
            prefix = "no project"
        self.detail_label.config(
            text=f"{prefix}  ·  Ln {line}, Col {int(column) + 1}"
        )

    def _set_status(self, text: str, level: str = "info") -> None:
        colors = {"info": FG, "success": GREEN, "error": RED,
                  "warning": YELLOW}
        self.status_label.config(text=text, fg=colors.get(level, FG))

    def _edit_event(self, event: str) -> None:
        widget = self.focus_get()
        if isinstance(widget, tk.Text):
            widget.event_generate(event)

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About ParserCraft Studio",
            "ParserCraft Studio 4.0\n\n"
            "Design PEG grammars, parse source into an AST, run programs,\n"
            "and emit Python, C, WebAssembly, and LLVM IR.\n\n"
            "The studio is a thin shell around parsercraft.ide.studio.",
            parent=self,
        )


def main() -> None:
    """Launch ParserCraft Studio.

    Usage:
        parsercraft-ide [project-directory-or-config] [source-file]
    """
    import argparse

    parser = argparse.ArgumentParser(description="ParserCraft Studio")
    parser.add_argument(
        "project", nargs="?", default=None,
        help="Project directory or language configuration file",
    )
    parser.add_argument(
        "source", nargs="?", default=None, help="Source file to open",
    )
    args = parser.parse_args()

    app = ParserCraftIDE(args.project, args.source)
    app.mainloop()


if __name__ == "__main__":  # pragma: no cover - GUI entry point
    main()
