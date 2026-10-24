"""
Lashon IDE — Code Editor Module

Provides a Tkinter-based code editor with:
- Line numbers
- Syntax highlighting (configurable per-language)
- Undo/redo (handled by Tkinter Text widget)
- Find/replace
- Configurable tab width
"""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import font as tkfont
from typing import Any, Callable, Dict, List, Optional


class LineNumbers(tk.Canvas):
    """Line number margin for the code editor."""

    def __init__(self, parent: tk.Widget, text_widget: tk.Text,
                 colors: Optional[Dict[str, str]] = None, **kwargs):
        super().__init__(
            parent, width=50,
            bg=(colors or CodeEditor.DEFAULT_COLORS)["gutter_bg"],
            highlightthickness=0, **kwargs,
        )
        self.text_widget = text_widget
        self._colors = colors or CodeEditor.DEFAULT_COLORS
        self._font = tkfont.Font(family="Courier New", size=11)

    def redraw(self, _event: Any = None) -> None:
        self.delete("all")
        i = self.text_widget.index("@0,0")
        while True:
            dline = self.text_widget.dlineinfo(i)
            if dline is None:
                break
            line_num = int(str(i).split(".")[0])
            self.create_text(
                45, dline[1] + 2,
                anchor="ne", text=str(line_num),
                fill=self._colors["gutter_fg"], font=self._font,
            )
            i = self.text_widget.index(f"{i}+1line")


class CodeEditor(tk.Frame):
    """Code editor widget with line numbers and syntax highlighting."""

    # Default color scheme
    DEFAULT_COLORS = {
        "background": "#1e1e1e",
        "foreground": "#d4d4d4",
        "keyword": "#569cd6",
        "string": "#ce9178",
        "number": "#b5cea8",
        "comment": "#6a9955",
        "operator": "#d4d4d4",
        "function": "#dcdcaa",
        "type": "#4ec9b0",
        "error": "#f44747",
        "cursor": "#ffffff",
        "selection": "#264f78",
        "current_line": "#2a2d2e",
        "gutter_bg": "#2b2b2b",
        "gutter_fg": "#888888",
    }

    def __init__(self, parent: tk.Widget, keywords: Optional[List[str]] = None,
                 colors: Optional[Dict[str, str]] = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.colors = {**self.DEFAULT_COLORS, **(colors or {})}
        self.keywords = keywords or [
            "def", "class", "if", "elif", "else", "while", "for", "in",
            "return", "import", "from", "as", "try", "except", "finally",
            "with", "yield", "lambda", "pass", "break", "continue",
            "and", "or", "not", "is", "True", "False", "None",
            "print", "let", "var", "const", "fn", "func", "function",
        ]
        self._on_change_callback: Optional[Callable] = None
        self._setup_widgets()
        self._setup_tags()
        self._bind_events()

    def _setup_widgets(self) -> None:
        self._font = tkfont.Font(family="Courier New", size=11)

        # Scrollbar
        self._scrollbar = tk.Scrollbar(self, orient="vertical")
        self._scrollbar.pack(side="right", fill="y")

        # Text widget
        self.text = tk.Text(
            self,
            wrap="none",
            font=self._font,
            bg=self.colors["background"],
            fg=self.colors["foreground"],
            insertbackground=self.colors["cursor"],
            selectbackground=self.colors["selection"],
            undo=True,
            maxundo=100,
            padx=8,
            pady=4,
            tabs=self._font.measure("    "),
        )

        # Line numbers
        self.line_numbers = LineNumbers(self, self.text, self.colors)
        self.line_numbers.pack(side="left", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        # Link scrollbar
        self._scrollbar.config(command=self.text.yview)
        self.text.config(yscrollcommand=self._scrollbar.set)

    def _setup_tags(self) -> None:
        """Configure syntax highlighting tags."""
        self.text.tag_configure("keyword", foreground=self.colors["keyword"], font=(self._font.cget("family"), self._font.cget("size"), "bold"))
        self.text.tag_configure("string", foreground=self.colors["string"])
        self.text.tag_configure("number", foreground=self.colors["number"])
        self.text.tag_configure("comment", foreground=self.colors["comment"], font=(self._font.cget("family"), self._font.cget("size"), "italic"))
        self.text.tag_configure("operator", foreground=self.colors["operator"])
        self.text.tag_configure("function", foreground=self.colors["function"])
        self.text.tag_configure("type", foreground=self.colors["type"])
        self.text.tag_configure("error", underline=True, underlinefg=self.colors["error"])

    def _bind_events(self) -> None:
        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<KeyRelease>", self._on_key)
        self.text.bind("<Configure>", lambda e: self.line_numbers.redraw())
        self.text.bind("<MouseWheel>", lambda e: self.after_idle(self.line_numbers.redraw))
        self.text.bind("<Button-1>", lambda e: self.after_idle(self.line_numbers.redraw))

    def _on_modified(self, _event: Any = None) -> None:
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.highlight_syntax()
            self.line_numbers.redraw()
            if self._on_change_callback:
                self._on_change_callback()

    def _on_key(self, event: Any = None) -> None:
        self.after_idle(self.line_numbers.redraw)

        # Auto-indent on Enter
        if event and event.keysym == "Return":
            self._auto_indent()

    def _auto_indent(self) -> None:
        """Match indentation of the previous line."""
        cursor = self.text.index("insert")
        line_num = int(cursor.split(".")[0])
        if line_num > 1:
            prev_line = self.text.get(f"{line_num - 1}.0", f"{line_num - 1}.end")
            indent = len(prev_line) - len(prev_line.lstrip())
            # Increase indent after block/collection openers
            if prev_line.rstrip().endswith((":", "{", "[", "(")):
                indent += 4
            if indent > 0:
                self.text.insert("insert", " " * indent)

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    def get_text(self) -> str:
        """Get the editor content."""
        return self.text.get("1.0", "end-1c")

    def set_text(self, content: str) -> None:
        """Replace all editor content."""
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.highlight_syntax()
        self.line_numbers.redraw()

    def set_keywords(self, keywords: List[str]) -> None:
        """Update the keyword list for highlighting."""
        self.keywords = keywords
        self.highlight_syntax()

    def on_change(self, callback: Callable) -> None:
        """Register a callback for content changes."""
        self._on_change_callback = callback

    def highlight_syntax(self) -> None:
        """Apply syntax highlighting to the entire editor content."""
        # Remove existing tags
        for tag in ("keyword", "string", "number", "comment", "function", "type", "operator"):
            self.text.tag_remove(tag, "1.0", "end")

        content = self.get_text()
        if not content.strip():
            return

        # Operators (applied first so comments/strings can override)
        for match in re.finditer(r'[+\-*/%<>=!&|^~?:]+', content):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.text.tag_add("operator", start, end)

        # Comments (line comments)
        for match in re.finditer(r'(#|//).*$', content, re.MULTILINE):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.text.tag_add("comment", start, end)

        # Strings
        for match in re.finditer(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')', content):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.text.tag_add("string", start, end)

        # Numbers
        for match in re.finditer(r'\b\d+(\.\d+)?\b', content):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.text.tag_add("number", start, end)

        # Keywords
        if self.keywords:
            kw_pattern = r'\b(' + '|'.join(
                re.escape(k) for k in self.keywords
            ) + r')\b'
            for match in re.finditer(kw_pattern, content):
                start = f"1.0+{match.start()}c"
                end = f"1.0+{match.end()}c"
                self.text.tag_add("keyword", start, end)

        # Function names (word before parenthesis)
        for match in re.finditer(r'\b(\w+)\s*\(', content):
            name = match.group(1)
            if name not in self.keywords:
                start = f"1.0+{match.start()}c"
                end = f"1.0+{match.start() + len(name)}c"
                self.text.tag_add("function", start, end)

    def mark_error(self, line: int, col: int, length: int = 1) -> None:
        """Mark an error at a specific position."""
        start = f"{line}.{col}"
        end = f"{line}.{col + length}"
        self.text.tag_add("error", start, end)

    def clear_errors(self) -> None:
        """Clear all error markers."""
        self.text.tag_remove("error", "1.0", "end")

    def find(self, query: str, case_sensitive: bool = False) -> int:
        """Find and highlight all occurrences. Returns count."""
        self.text.tag_remove("search", "1.0", "end")
        self.text.tag_configure("search", background="#515c6a")

        if not query:
            return 0

        count = 0
        start = "1.0"
        while True:
            pos = self.text.search(query, start, stopindex="end",
                                   nocase=not case_sensitive)
            if not pos:
                break
            end = f"{pos}+{len(query)}c"
            self.text.tag_add("search", pos, end)
            start = end
            count += 1

        return count
