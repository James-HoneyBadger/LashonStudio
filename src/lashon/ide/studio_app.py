"""Lashon Studio — a full language-design workbench.

Layout:
    project sidebar | source / grammar / language editors
                    | console / variables / generated backends / AST

All behaviour lives in :class:`lashon.ide.studio.LanguageStudio`; this
module only wires it to Tkinter widgets.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
import os
import re
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Dict, Optional

import yaml

from lashon.ide import settings
from lashon.ide.editor import CodeEditor
from lashon.ide.studio import (
    LanguageStudio,
    StudioProject,
    StudioResult,
)
from lashon.ide.theme import (
    MONO_FONT,
    SECTION_FONT,
    TITLE_FONT,
    UI_FONT,
    UI_FONT_BOLD,
    editor_colors,
    get_palette,
    rule,
)
from lashon.ide.theme import (
    names as theme_names,
)

PALETTE = get_palette(os.environ.get("LASHON_THEME"))
BG = PALETTE.bg
PANEL = PALETTE.panel
PANEL_ALT = PALETTE.panel_alt
BORDER = PALETTE.border
FG = PALETTE.fg
MUTED = PALETTE.muted
ACCENT = PALETTE.accent
GREEN = PALETTE.green
RED = PALETTE.red
YELLOW = PALETTE.yellow


def _apply_palette(name: Optional[str]) -> None:
    """Select the palette used by everything built from here on."""
    global PALETTE, BG, PANEL, PANEL_ALT, BORDER, FG, MUTED
    global ACCENT, GREEN, RED, YELLOW

    PALETTE = get_palette(name)
    BG = PALETTE.bg
    PANEL = PALETTE.panel
    PANEL_ALT = PALETTE.panel_alt
    BORDER = PALETTE.border
    FG = PALETTE.fg
    MUTED = PALETTE.muted
    ACCENT = PALETTE.accent
    GREEN = PALETTE.green
    RED = PALETTE.red
    YELLOW = PALETTE.yellow

STAGES = ("Grammar", "Parse", "Run", "Python", "C", "WASM", "LLVM IR")
BACKENDS = ("python", "c", "wasm", "llvm")
BACKEND_TITLES = {
    "python": "Python",
    "c": "C",
    "wasm": "WASM",
    "llvm": "LLVM IR",
}


_POSITION_RE = re.compile(r"line (\d+), column (\d+)", re.IGNORECASE)


def _error_position(message: str) -> tuple[Optional[int], Optional[int]]:
    """Extract a 1-based (line, column) pair from a diagnostic message."""
    match = _POSITION_RE.search(message)
    if match is None:
        return None, None
    return int(match.group(1)), int(match.group(2))


class LashonIDE(tk.Tk):
    """Lashon Studio main window."""

    def __init__(self, project_path: Optional[str] = None,
                 source_path: Optional[str] = None):
        super().__init__()
        _apply_palette(
            os.environ.get("LASHON_THEME") or settings.get("theme")
        )
        self.title("Lashon Studio")
        self._window_height = max(720, min(900, self.winfo_screenheight() - 96))
        width = max(1120, min(1440, self.winfo_screenwidth() - 96))
        self.geometry(f"{width}x{self._window_height}+40+24")
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
                  background=[("selected", PANEL_ALT)],
                  foreground=[("selected", ACCENT)])
        style.configure("Vertical.TScrollbar", background=PANEL_ALT,
                        troughcolor=BG, borderwidth=0, arrowcolor=MUTED)

    def _menu(self, parent: tk.Misc) -> tk.Menu:
        """A menu that matches the tube instead of the desktop theme."""
        return tk.Menu(
            parent, tearoff=0, bg=PANEL, fg=FG,
            activebackground=ACCENT, activeforeground=BG,
            bd=0, relief="flat",
        )

    def _build_menu(self) -> None:
        menubar = self._menu(self)

        file_menu = self._menu(menubar)
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

        edit_menu = self._menu(menubar)
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

        run_menu = self._menu(menubar)
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

        sample_menu = self._menu(menubar)
        sample_menu.add_command(label="Open Aurora Reference Project",
                                command=self._load_sample_project)
        menubar.add_cascade(label="Samples", menu=sample_menu)

        view_menu = self._menu(menubar)
        self.theme_var = tk.StringVar(value=PALETTE.name)
        for name in theme_names():
            view_menu.add_radiobutton(
                label=get_palette(name).title,
                value=name,
                variable=self.theme_var,
                command=lambda chosen=name: self._choose_theme(chosen),
            )
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = self._menu(menubar)
        help_menu.add_command(label="About Lashon Studio",
                              command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _choose_theme(self, name: str) -> None:
        """Remember a palette and restart into it."""
        self.theme_var.set(name)
        if name == PALETTE.name:
            return
        settings.save(theme=name)
        self._log(f"Phosphor set to {name}; restarting to repaint…",
                  "command")
        self.update_idletasks()
        self._restart_with_theme(name)

    def _restart_with_theme(self, name: str) -> None:  # pragma: no cover - GUI
        self._sync_documents()
        command = [sys.executable, "-m", "lashon.ide.app"]
        if self.project is not None:
            command.append(str(self.project.root))
        command += ["--theme", name]
        self.destroy()
        os.execv(sys.executable, command)

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=16, pady=(12, 0))

        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left")
        title = tk.Canvas(brand, bg=BG, highlightthickness=0, bd=0, height=26)
        title.pack(anchor="w")
        title.create_text(2, 2, text="◆ LASHON STUDIO", fill=BORDER,
                          font=TITLE_FONT, anchor="nw")
        glow = title.create_text(0, 0, text="◆ LASHON STUDIO", fill=ACCENT,
                                 font=TITLE_FONT, anchor="nw")
        left, top, right, bottom = title.bbox(glow)
        title.configure(width=right + 6, height=bottom + 6)
        tk.Label(
            brand,
            text="design a grammar · parse source · run it · emit four backends",
            bg=BG, fg=MUTED, font=MONO_FONT,
        ).pack(anchor="w")

        self.project_label = tk.Label(
            header, text="No project", bg=BG, fg=FG, font=UI_FONT_BOLD
        )
        self.project_label.pack(side="right", anchor="e")
        tk.Label(
            header,
            text=f"CRT · {PALETTE.title.upper()}",
            bg=BG, fg=MUTED, font=SECTION_FONT,
        ).pack(side="right", anchor="e", padx=(0, 16))

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
        right.add(self.editor_tabs, height=self._pane_heights()[0])

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
        right.add(self.output_tabs, height=self._pane_heights()[1])
        right.paneconfigure(self.output_tabs, minsize=150)
        self._build_output_tabs()

    def _pane_heights(self) -> tuple[int, int]:
        """Split the work area between editor and output, screen permitting."""
        available = max(420, self._window_height - 210)
        return int(available * 0.63), int(available * 0.34)

    def _build_sidebar(self, parent: tk.Widget) -> None:
        tk.Label(parent, text=rule("PROJECT"), bg=PANEL, fg=MUTED,
                 font=SECTION_FONT, anchor="w").pack(
            fill="x", padx=14, pady=(14, 6)
        )
        self.project_tree = ttk.Treeview(parent, show="tree",
                                         selectmode="browse")
        self.project_tree.pack(fill="both", expand=True, padx=8)
        self.project_tree.bind("<<TreeviewSelect>>", self._open_tree_item)

        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=12,
                                                  pady=10)
        tk.Label(parent, text=rule("PIPELINE"), bg=PANEL, fg=MUTED,
                 font=SECTION_FONT, anchor="w").pack(
            fill="x", padx=14, pady=(0, 6)
        )
        self.pipeline_labels: Dict[str, tk.Label] = {}
        stages = tk.Frame(parent, bg=PANEL)
        stages.pack(fill="x", padx=14)
        for stage in STAGES:
            label = tk.Label(
                stages, text=f"○  {stage}", bg=PANEL, fg=MUTED,
                anchor="w", font=MONO_FONT,
            )
            label.pack(fill="x")
            self.pipeline_labels[stage] = label

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
        editor = CodeEditor(frame, keywords=keywords,
                            colors=editor_colors(PALETTE))
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

        problems_frame = tk.Frame(self.output_tabs, bg=BG)
        self.problems_frame = problems_frame
        self.output_tabs.add(problems_frame, text="Problems")
        self.problems_tree = ttk.Treeview(
            problems_frame,
            columns=("severity", "location", "message"),
            show="headings",
        )
        self.problems_tree.heading("severity", text="")
        self.problems_tree.heading("location", text="Location")
        self.problems_tree.heading("message", text="Problem")
        self.problems_tree.column("severity", width=40, anchor="center")
        self.problems_tree.column("location", width=120, anchor="w")
        self.problems_tree.column("message", width=680, anchor="w")
        self.problems_tree.tag_configure("error", foreground=RED)
        self.problems_tree.tag_configure("warning", foreground=YELLOW)
        self.problems_tree.bind(
            "<<TreeviewSelect>>", self._select_problem
        )
        self.problems_tree.pack(fill="both", expand=True)
        self._problem_targets: Dict[str, str] = {}

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
        self.clock_label = tk.Label(
            status, text="", bg=PANEL, fg=ACCENT, anchor="e",
            font=MONO_FONT, padx=12, pady=4,
        )
        self.clock_label.pack(side="right")
        self._tick_clock()

    def _tick_clock(self) -> None:
        try:
            self.clock_label.configure(text=datetime.now().strftime("%H:%M:%S"))
            self.after(1000, self._tick_clock)
        except tk.TclError:  # pragma: no cover - window already destroyed
            pass

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-Shift-P>", lambda _e: self._show_palette())
        self.bind("<Control-Shift-p>", lambda _e: self._show_palette())
        self.bind("<Control-p>", lambda _e: self._quick_open())
        self.bind("<F1>", lambda _e: self._show_shortcuts())
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
        self._boot_sequence()
        loaded = False
        if project_path:
            loaded = self._load_project(project_path)
        else:
            sample = LanguageStudio.sample_project_path()
            if sample is not None:
                loaded = self._load_project(sample)

        if not loaded:
            self._log("Welcome to Lashon Studio.", "info")
            self._log("Open a project or load the Aurora sample to begin.",
                      "info")
            self._set_status("Ready — no project loaded")

        if source_path:
            self._load_source_file(Path(source_path))

    def _boot_sequence(self) -> None:
        """Print the power-on banner, the way a CRT workstation would."""
        from lashon import __version__

        self._log(f"LASHON STUDIO {__version__} · CRT SERIES", "command")
        self._log(f"PHOSPHOR ............ {PALETTE.title.upper()}", "info")
        self._log("GRAMMAR ENGINE ...... READY", "info")
        self._log("BACKENDS ............ PYTHON · C · WASM · LLVM IR", "info")
        self._log("READY.", "success")

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
        self.title(f"Lashon Studio — {project.name}")
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
            self._clear_problems()
            self.grammar_editor.clear_errors()
            self.source_editor.set_keywords(self.studio.highlight_keywords())
            self._set_status("Grammar OK", "success")
            self._update_project_info()
        else:
            self._show_grammar_problems(result)
            self._set_status("Grammar error", "error")

    def _show_grammar_problems(self, result: StudioResult) -> None:
        """Surface grammar problems with markers in the grammar editor."""
        self._clear_problems()
        self.grammar_editor.clear_errors()
        messages = [result.error] if result.error else []
        messages.extend(
            diagnostic.message for diagnostic in result.diagnostics
            if diagnostic.message != result.error
        )
        for message in messages:
            line, column = _error_position(message)
            if line is not None:
                self.grammar_editor.mark_error(line, column, 1)
                self._add_problem(
                    "error", line, column, message, "grammar"
                )
            else:
                self._add_problem("error", None, None, message, "grammar")
        if messages:
            self.output_tabs.select(self.problems_frame)

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
            self._set_stage("Grammar", "ok")
            self._set_status(
                f"Grammar OK — {result.elapsed_ms:.1f} ms", "success"
            )
            if log_success:
                self._log(result.text, "success")
            return True
        self._set_stage("Grammar", "error")
        self._show_grammar_problems(result)
        for diagnostic in result.diagnostics:
            self._log(diagnostic.message, "error")
        if result.error:
            self._log(result.error, "error")
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
        self._set_stage("Parse", "ok")
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
        self._set_stage("Run", "ok")
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
                self._set_stage(BACKEND_TITLES[backend], "ok")
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
        self._clear_problems()
        self.source_editor.clear_errors()

        messages = [result.error] if result.error else []
        for diagnostic in result.diagnostics:
            if diagnostic.message != result.error:
                messages.append(diagnostic.message)

        self._set_stage("Parse", "error")
        self._set_stage("Run", "error")
        for message in messages:
            line, column = _error_position(message)
            if line is not None:
                self.source_editor.mark_error(line, column, 1)
                self._add_problem("error", line, column, message, "source")
            else:
                self._add_problem("error", None, None, message, "source")
        self.output_tabs.select(self.problems_frame)
        self._set_status(context, "error")

    # ------------------------------------------------------------------
    # Problems
    # ------------------------------------------------------------------

    def _clear_problems(self) -> None:
        self.problems_tree.delete(*self.problems_tree.get_children())
        self._problem_targets.clear()

    def _add_problem(
        self,
        severity: str,
        line: Optional[int],
        column: Optional[int],
        message: str,
        target: str,
    ) -> str:
        """Add a row to the Problems list and remember where it belongs."""
        location = f"line {line}" if line else ""
        if line and column:
            location = f"{line}:{column}"
        first_line = message.splitlines()[0]
        item = self.problems_tree.insert(
            "",
            "end",
            values=(severity.upper(), location, first_line),
            tags=(severity,),
        )
        encoded = f"{target}|{line or 1}|{column or 1}"
        self._problem_targets[item] = encoded
        return item

    def _select_problem(self, _event: Any = None) -> None:
        selection = self.problems_tree.selection()
        if not selection:
            return
        target, line, column = self._problem_targets[selection[0]].split("|")
        editor = (
            self.grammar_editor if target == "grammar" else self.source_editor
        )
        self.editor_tabs.select(editor.master)
        self._goto(editor, int(line), int(column))

    def _goto(self, editor: CodeEditor, line: int, column: int = 1) -> None:
        index = f"{max(line, 1)}.{max(column - 1, 0)}"
        editor.text.mark_set("insert", index)
        editor.text.see(index)
        editor.text.focus_set()

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

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    def _set_stage(self, stage: str, state: str) -> None:
        """Mark a pipeline stage idle (○), passing (✓) or failing (✗)."""
        marks = {"idle": ("○", MUTED), "ok": ("✓", GREEN), "error": ("✗", RED)}
        mark, colour = marks.get(state, marks["idle"])
        label = self.pipeline_labels.get(stage)
        if label is not None:
            label.config(text=f"{mark}  {stage}", fg=colour)

    def _reset_stages(self, *stages: str) -> None:
        for stage in stages:
            self._set_stage(stage, "idle")

    def _set_status(self, text: str, level: str = "info") -> None:
        colors = {"info": FG, "success": GREEN, "error": RED,
                  "warning": YELLOW}
        self.status_label.config(text=text, fg=colors.get(level, FG))

    def _edit_event(self, event: str) -> None:
        widget = self.focus_get()
        if isinstance(widget, tk.Text):
            widget.event_generate(event)

    # ------------------------------------------------------------------
    # Command palette / quick open
    # ------------------------------------------------------------------

    def _commands(self) -> list[tuple[str, str, Any]]:
        """Return the commands offered by the palette."""
        return [
            ("New Project…", "Ctrl+N", self._new_project),
            ("Open Project…", "Ctrl+O", self._open_project),
            ("Save Project", "Ctrl+S", self._save_project),
            ("Validate Grammar", "Ctrl+Shift+V", self._validate_grammar),
            ("Parse Source", "F6", self._parse_source),
            ("Run Program", "F5", self._run_program),
            ("Generate All Backends", "F7", self._generate_all),
            ("Open Aurora Reference Project", "",
             self._load_sample_project),
            ("Open Language Config…", "", self._open_config),
            ("Show Keyboard Shortcuts", "F1", self._show_shortcuts),
        ]

    def _show_palette(self) -> None:
        def run(label: str) -> None:
            for name, _accelerator, callback in self._commands():
                if name == label:
                    callback()
                    return

        self._show_picker(
            title="Command Palette",
            items=[f"{name}  ({accel})" if accel else name
                   for name, accel, _cb in self._commands()],
            on_accept=lambda label: run(label.split("  (")[0]),
        )

    def _quick_open(self) -> None:
        paths = sorted(
            (value[1] for value in self._tree_paths.values()
             if value[1] is not None),
            key=lambda path: path.name,
        )
        if not paths:
            self._set_status("No files in this project")
            return

        def accept(name: str) -> None:
            for path in paths:
                if path.name == name:
                    self._load_source_file(path)
                    return

        self._show_picker(
            title="Quick Open",
            items=[path.name for path in paths],
            on_accept=accept,
        )

    def _show_picker(
        self, title: str, items: list[str], on_accept: Any
    ) -> None:
        window = tk.Toplevel(self)
        window.title(title)
        window.configure(bg=PANEL)
        window.transient(self)
        window.geometry("520x320")

        entry = tk.Entry(
            window, bg=PANEL_ALT, fg=FG, insertbackground=FG,
            font=UI_FONT, relief="flat",
        )
        entry.pack(fill="x", padx=10, pady=10)
        entry.focus_set()

        listing = tk.Listbox(
            window, bg=PANEL, fg=FG, font=UI_FONT, relief="flat",
            selectbackground="#1f6feb", highlightthickness=0,
        )
        listing.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        shown: list[str] = []

        def refresh(_event: Any = None) -> None:
            query = entry.get().lower()
            shown.clear()
            listing.delete(0, "end")
            for item in items:
                if query in item.lower():
                    shown.append(item)
                    listing.insert("end", item)
            if shown:
                listing.selection_set(0)

        def accept(_event: Any = None) -> None:
            selection = listing.curselection()
            choice = shown[selection[0]] if selection else None
            window.destroy()
            if choice:
                on_accept(choice)

        entry.bind("<KeyRelease>", refresh)
        entry.bind("<Return>", accept)
        listing.bind("<Double-Button-1>", accept)
        window.bind("<Escape>", lambda _e: window.destroy())
        refresh()

    def _show_shortcuts(self) -> None:
        messagebox.showinfo(
            "Keyboard shortcuts",
            "Ctrl+N  New project\n"
            "Ctrl+O  Open project\n"
            "Ctrl+S  Save project\n"
            "Ctrl+P  Quick open file\n"
            "Ctrl+Shift+P  Command palette\n"
            "Ctrl+Shift+V  Validate grammar\n"
            "F5  Run program\n"
            "F6  Parse source\n"
            "F7  Generate all backends\n"
            "F1  This help",
            parent=self,
        )

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About Lashon Studio",
            "Lashon Studio 4.0\n\n"
            "Design PEG grammars, parse source into an AST, run programs,\n"
            "and emit Python, C, WebAssembly, and LLVM IR.\n\n"
            "The studio is a thin shell around lashon.ide.studio.",
            parent=self,
        )


def main() -> None:
    """Launch Lashon Studio.

    Usage:
        lashon-ide [project-directory-or-config] [source-file]
    """
    import argparse

    parser = argparse.ArgumentParser(description="Lashon Studio")
    parser.add_argument(
        "project", nargs="?", default=None,
        help="Project directory or language configuration file",
    )
    parser.add_argument(
        "source", nargs="?", default=None, help="Source file to open",
    )
    parser.add_argument(
        "--theme", choices=theme_names(), default=None,
        help="Palette: green (default), amber, or dark",
    )
    args = parser.parse_args()

    if args.theme:
        os.environ["LASHON_THEME"] = args.theme

    if not _display_available():
        print(
            "Lashon Studio needs a graphical display (X11/Wayland on Linux,\n"
            "Aqua on macOS, Win32 on Windows) and a Python build with tkinter.\n"
            "\n"
            "Headless alternatives with the same engine:\n"
            "  lashon run <file> --config <language.yaml>   run a program\n"
            "  lashon validate <language.yaml>              check a language\n"
            "  lashon lsp --config <language.yaml> --stdio  editor integration\n"
            "  lashon-rs run <grammar.peg> <program>        native, no Python\n",
            file=sys.stderr,
        )
        raise SystemExit(1)

    app = LashonIDE(args.project, args.source)
    app.mainloop()


def _display_available() -> bool:
    """True when Tk can open a window on this machine."""
    try:
        probe = tk.Tk()
    except tk.TclError:
        return False
    probe.destroy()
    return True


if __name__ == "__main__":  # pragma: no cover - GUI entry point
    main()
