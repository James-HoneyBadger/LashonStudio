"""An embedded REPL for Lashon Studio.

The Studio already runs whole programs. This panel adds the missing loop: type
one statement, see it evaluated against the project's grammar, watch the canvas
follow along. The engine is the same :class:`lashon.runtime.repl.REPL` the
terminal uses, so commands (``:vars``, ``:py``, ``:canvas``) behave identically.
"""

from __future__ import annotations

import io
import tkinter as tk
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Callable, List, Optional

from lashon.ide.theme import MONO_FONT, MONO_FONT_BOLD, Palette
from lashon.runtime.graphics import Graphics
from lashon.runtime.repl import REPL

BANNER = (
    "Interactive session — the grammar above, evaluated statement by "
    "statement.\n"
    ":help for commands, :canvas to inspect the drawing, Ctrl+R to focus here."
)


class ReplPanel(tk.Frame):
    """A transcript, a prompt, and a REPL bound to the current grammar."""

    def __init__(self, parent: tk.Misc, palette: Palette,
                 on_draw: Optional[Callable[[Graphics], None]] = None):
        super().__init__(parent, bg=palette.panel)
        self.palette = palette
        self._on_draw = on_draw
        self._history: List[str] = []
        self._history_index = 0
        self.repl = REPL()

        self.transcript = tk.Text(
            self, wrap="word", bg=palette.panel, fg=palette.fg,
            insertbackground=palette.accent, font=MONO_FONT,
            state="disabled", padx=10, pady=8, height=10,
        )
        self.transcript.tag_configure("info", foreground=palette.fg)
        self.transcript.tag_configure("echo", foreground=palette.accent,
                                      font=MONO_FONT_BOLD)
        self.transcript.tag_configure("result", foreground=palette.green)
        self.transcript.tag_configure("error", foreground=palette.red)
        self.transcript.tag_configure("hint", foreground=palette.muted)

        scroll = tk.Scrollbar(self, orient="vertical",
                              command=self.transcript.yview)
        self.transcript.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.transcript.pack(fill="both", expand=True)

        prompt_bar = tk.Frame(self, bg=palette.panel_alt)
        prompt_bar.pack(fill="x", side="bottom")
        tk.Label(
            prompt_bar, text=">>>", bg=palette.panel_alt, fg=palette.accent,
            font=MONO_FONT_BOLD, padx=10,
        ).pack(side="left")
        self.entry = tk.Entry(
            prompt_bar, bg=palette.bg, fg=palette.fg,
            insertbackground=palette.accent, font=MONO_FONT,
            relief="flat", highlightthickness=1,
            highlightbackground=palette.border,
            highlightcolor=palette.accent,
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 10),
                        pady=6)
        self.entry.bind("<Return>", self._submit)
        self.entry.bind("<Up>", lambda _event: self._recall(-1))
        self.entry.bind("<Down>", lambda _event: self._recall(1))
        self.entry.bind("<Control-l>", lambda _event: self.clear())

        self._write(BANNER, "hint")

    # -- grammar -------------------------------------------------------

    def use_grammar(self, grammar: Any) -> None:
        """Bind the session to ``grammar`` and start a fresh namespace."""
        self.repl = REPL(grammar=grammar)
        self.clear()
        self._write(BANNER, "hint")
        self._write(f"Grammar loaded: {len(getattr(grammar, 'rules', {}))} "
                    f"rules.", "hint")

    # -- output --------------------------------------------------------

    def _write(self, text: str, tag: str = "info") -> None:
        self.transcript.configure(state="normal")
        if not text.endswith("\n"):
            text += "\n"
        self.transcript.insert("end", text, tag)
        self.transcript.see("end")
        self.transcript.configure(state="disabled")

    def clear(self) -> None:
        """Empty the transcript."""
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.configure(state="disabled")

    def focus_prompt(self) -> None:
        self.entry.focus_set()

    # -- interaction ---------------------------------------------------

    def _submit(self, _event: Any = None) -> str:
        source = self.entry.get().strip()
        self.entry.delete(0, "end")
        if not source:
            return "break"
        self._history.append(source)
        self._history_index = len(self._history)
        self._write(f">>> {source}", "echo")
        self.evaluate(source)
        return "break"

    def evaluate(self, source: str) -> None:
        """Run one entry and report what it printed."""
        stdout, stderr = io.StringIO(), io.StringIO()
        if source.startswith(":"):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.repl._handle_command(source)  # pylint: disable=protected-access
        else:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.repl._eval(source)  # pylint: disable=protected-access

        printed = stdout.getvalue()
        if printed:
            self._write(printed.rstrip("\n"), "info")
        errors = stderr.getvalue()
        if errors:
            self._write(errors.rstrip("\n"), "error")

        if not printed and not errors:
            surface = self.repl.graphics
            summary = surface.summary()
            if summary == "canvas empty":
                self._write("(no output)", "result")
            else:
                self._write(summary, "result")

        if self._on_draw is not None:
            self._on_draw(self.repl.graphics)

    def _recall(self, step: int) -> str:
        """Walk the history with the arrow keys."""
        if not self._history:
            return "break"
        self._history_index = max(
            0, min(len(self._history), self._history_index + step)
        )
        self.entry.delete(0, "end")
        if self._history_index < len(self._history):
            self.entry.insert(0, self._history[self._history_index])
        return "break"

    @property
    def graphics(self) -> Graphics:
        """The session's drawing surface."""
        return self.repl.graphics
