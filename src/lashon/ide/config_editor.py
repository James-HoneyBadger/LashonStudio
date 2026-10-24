#!/usr/bin/env python3
"""Visual configuration editor (Tk).

A small GUI for editing keyword mappings and functions. It lives in the IDE
package because it is a widget, not part of the config model.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from lashon.config.language_config import KeywordMapping, LanguageConfig


class VisualConfigEditor(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        config: Optional[LanguageConfig] = None,
        on_save: Optional[Callable[[LanguageConfig], None]] = None,
    ):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        self.master = master
        self.config_obj = config or LanguageConfig()
        self.on_save = on_save
        self._build_ui()

    def _build_ui(self) -> None:
        top_widget = self.winfo_toplevel()
        if isinstance(top_widget, tk.Tk):
            top_widget.title("Visual Configuration Editor")
            top_widget.geometry("700x500")

        # Top bar
        top = ttk.Frame(self)
        top.pack(fill="x", pady=4)
        btn_add = ttk.Button(
            top,
            text="Add Keyword",
            command=self._add_keyword,
        )
        btn_add.pack(side="left", padx=4)
        btn_edit = ttk.Button(
            top,
            text="Edit Keyword",
            command=self._edit_keyword,
        )
        btn_edit.pack(side="left", padx=4)
        btn_remove = ttk.Button(
            top,
            text="Remove Keyword",
            command=self._remove_keyword,
        )
        btn_remove.pack(side="left", padx=4)
        btn_save = ttk.Button(
            top,
            text="Save",
            command=self._save,
        )
        btn_save.pack(side="right", padx=4)

        # Keyword list
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True)
        self.kw_list = tk.Listbox(main)
        self.kw_list.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(main, orient="vertical", command=self.kw_list.yview)
        self.kw_list.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        self._refresh_keywords()

    def _refresh_keywords(self) -> None:
        self.kw_list.delete(0, tk.END)
        for km in self.config_obj.keyword_mappings.values():
            self.kw_list.insert(tk.END, f"{km.original} → {km.custom} ({km.category})")

    def _add_keyword(self) -> None:
        self._keyword_dialog()

    def _edit_keyword(self) -> None:
        sel = self.kw_list.curselection()
        if not sel:
            messagebox.showinfo("Edit Keyword", "Select a keyword to edit")
            return
        index = sel[0]
        key = list(self.config_obj.keyword_mappings.keys())[index]
        km = self.config_obj.keyword_mappings[key]
        self._keyword_dialog(km=km)

    def _remove_keyword(self) -> None:
        sel = self.kw_list.curselection()
        if not sel:
            messagebox.showinfo("Remove Keyword", "Select a keyword to remove")
            return
        index = sel[0]
        key = list(self.config_obj.keyword_mappings.keys())[index]
        del self.config_obj.keyword_mappings[key]
        self._refresh_keywords()

    def _keyword_dialog(self, km: Optional[KeywordMapping] = None) -> None:
        win = tk.Toplevel(self.master)
        win.title("Keyword")
        win.geometry("360x220")
        ttk.Label(win, text="Original:").grid(
            row=0, column=0, padx=6, pady=6, sticky="w"
        )
        ttk.Label(win, text="Custom:").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        ttk.Label(win, text="Category:").grid(
            row=2, column=0, padx=6, pady=6, sticky="w"
        )

        orig_var = tk.StringVar(value=(km.original if km else ""))
        cust_var = tk.StringVar(value=(km.custom if km else ""))
        cat_var = tk.StringVar(value=(km.category if km else "general"))
        ttk.Entry(win, textvariable=orig_var).grid(
            row=0, column=1, padx=6, pady=6, sticky="ew"
        )
        ttk.Entry(win, textvariable=cust_var).grid(
            row=1, column=1, padx=6, pady=6, sticky="ew"
        )
        ttk.Entry(win, textvariable=cat_var).grid(
            row=2, column=1, padx=6, pady=6, sticky="ew"
        )

        def save():
            o = orig_var.get().strip()
            c = cust_var.get().strip()
            cat = cat_var.get().strip() or "general"
            if not o or not c:
                messagebox.showerror(
                    "Error",
                    "Original and Custom are required",
                )
                return
            self.config_obj.keyword_mappings[o] = KeywordMapping(o, c, cat)
            self._refresh_keywords()
            win.destroy()

        ttk.Button(win, text="Save", command=save).grid(
            row=3, column=0, padx=6, pady=10
        )
        ttk.Button(win, text="Cancel", command=win.destroy).grid(
            row=3, column=1, padx=6, pady=10
        )
        win.columnconfigure(1, weight=1)

    def _save(self) -> None:
        try:
            # Persist via LanguageConfig.save (yaml/json based on support)
            from tkinter import filedialog

            path = filedialog.asksaveasfilename(
                title="Save Config",
                defaultextension=".yaml",
                filetypes=[
                    ("YAML", "*.yaml"),
                    ("JSON", "*.json"),
                    ("All Files", "*.*"),
                ],
            )
            if path:
                self.config_obj.save(path)
                messagebox.showinfo("Saved", f"Configuration saved to {path}")
                if self.on_save:
                    try:
                        self.on_save(self.config_obj)
                    except (  # pylint: disable=broad-exception-caught
                        Exception
                    ) as cb_err:
                        messagebox.showwarning(
                            "Update Warning",
                            f"Saved, but IDE update failed: {cb_err}",
                        )
        except (OSError, ValueError) as e:
            messagebox.showerror("Error", f"Failed to save: {e}")


def open_visual_editor(
    config: Optional[LanguageConfig] = None,
    on_save: Optional[Callable[[LanguageConfig], None]] = None,
) -> None:
    root = tk.Tk()
    VisualConfigEditor(root, config, on_save)
    root.mainloop()
