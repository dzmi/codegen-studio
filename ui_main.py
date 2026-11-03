# -*- coding: utf-8 -*-
"""GUI Codegen Studio."""
import difflib
import json
import os
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, scrolledtext, ttk

from codegen_core import normalize_actions, validate, simulate, apply_simulation
from exporter import export_json, export_zip, read_gitignore, should_include, default_dump_path
from git_py import GitPy
from logger import get_logger
from prompts import list_prompts, get_prompt
import lite_highlighter as syntax_highlighter


class StudioWindow:
    def __init__(self, root, project_path=None):
        self.root = root
        self.project_path = project_path
        self.current_file = None
        self.current_content = ""
        self.git = None
        self.simulation = None
        import settings_manager as _s
        self._s = _s
        self.lang = _s.get("language", "ru")
        self._toolbar_mode = False
        self._full_geometry = None
        self._drag_x = 0
        self._drag_y = 0
        root.title("Codegen Studio v1.1")
        root.geometry(_s.get("window_geometry", "1300x800+100+50"))
        root.protocol("WM_DELETE_WINDOW", self._on_close_main)
        self._build_menu()
        self._build_toolbar()
        self._build_main()
        self._build_statusbar()
        if project_path:
            self.open_project(project_path)
        if _s.get("mode", "window") == "toolbar":
            self.root.after(120, self.enter_toolbar_mode)

    def _t(self, key):
        from i18n import TRANSLATIONS
        lang = getattr(self, "lang", "ru")
        return TRANSLATIONS.get(lang, TRANSLATIONS["ru"]).get(key, key)

    def _tip(self, widget, text):
        tip = {"win": None}
        def enter(e):
            try:
                tip["win"] = tk.Toplevel(widget)
                tip["win"].wm_overrideredirect(True)
                tip["win"].wm_geometry(f"+{e.x_root+8}+{e.y_root+22}")
                tk.Label(tip["win"], text=text, bg="#ffffe1", fg="#000", relief=tk.SOLID, bd=1, padx=6, pady=2, font=("Segoe UI", 9)).pack()
            except Exception: pass
        def leave(e):
            try:
                if tip["win"]: tip["win"].destroy(); tip["win"] = None
            except Exception: pass
        widget.bind("<Enter>", enter, add="+")
        widget.bind("<Leave>", leave, add="+")


    def _build_menu(self):
        m = tk.Menu(self.root)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label=self._t("item_open_proj"), command=self.open_project_dialog)
        f.add_command(label=self._t("item_refresh_tree"), command=self.refresh_tree)
        f.add_separator()
        f.add_command(label=self._t("item_docs"), command=self._docs_dialog)
        f.add_separator()
        f.add_command(label=self._t("item_exit"), command=self._on_close_main)
        m.add_cascade(label=self._t("menu_file"), menu=f)

        e = tk.Menu(m, tearoff=0)
        e.add_command(label=self._t("item_export_proj"), command=self._dump_dialog)
        e.add_separator()
        e.add_command(label=self._t("item_copy_struct"), command=self.copy_structure)
        e.add_command(label=self._t("item_prompt_ai"), command=self._prompts_dialog)
        m.add_cascade(label=self._t("menu_export"), menu=e)

        g = tk.Menu(m, tearoff=0)
        g.add_command(label=self._t("git_status"), command=self.git_status)
        g.add_command(label=self._t("git_commit"), command=self.git_commit_dialog)
        g.add_command(label=self._t("git_log"), command=self.git_log)
        g.add_command(label=self._t("git_init"), command=self.git_init)
        m.add_cascade(label=self._t("menu_git"), menu=g)

        h = tk.Menu(m, tearoff=0)
        h.add_command(label=self._t("item_about"), command=self._show_about)
        m.add_cascade(label=self._t("menu_help"), menu=h)
        self.root.config(menu=m)

    def _build_toolbar(self):
        self.toolbar_bar = ttk.Frame(self.root)
        self.toolbar_bar.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)
        h = tk.Label(self.toolbar_bar, text="\u28ff", cursor="fleur", bg="#dcdcdc", padx=6, pady=2, font=("Segoe UI", 11, "bold"), relief=tk.GROOVE, bd=1)
        h.pack(side=tk.LEFT, padx=(0, 4), pady=2)
        self._toolbar_handle = h
        self.project_label = tk.Label(self.toolbar_bar, text="\U0001F4C2 AI_lite", bg="#e8f4ff", fg="#004080", relief=tk.SUNKEN, bd=1, font=("Segoe UI", 10, "bold"), padx=6, pady=2)
        self.project_label.pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Separator(self.toolbar_bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)

        def btn(txt, cmd, tip="", width=11):
            b = ttk.Button(self.toolbar_bar, text=txt, command=cmd, width=width)
            b.pack(side=tk.LEFT, padx=2, pady=2)
            if tip: self._tip(b, tip)
            return b

        btn(self._t("btn_project"), self.open_project_dialog, self._t("tip_open"))
        btn(self._t("btn_prompt"), self._prompts_dialog, self._t("tip_prompt"))
        ttk.Separator(self.toolbar_bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)
        
        b_json = tk.Button(self.toolbar_bar, text=self._t("btn_json"), command=self._json_dialog, bg="#4CAF50", fg="white", activebackground="#45a049", activeforeground="white", font=("Segoe UI", 10, "bold"), relief=tk.RAISED, bd=1, padx=8, pady=2, cursor="hand2")
        b_json.pack(side=tk.LEFT, padx=2, pady=2)
        self._tip(b_json, self._t("tip_json"))
        
        btn(self._t("btn_apply"), self.apply_from_clipboard, self._t("tip_apply"))
        ttk.Separator(self.toolbar_bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)
        
        self.btn_export = btn(self._t("btn_export"), self._dump_dialog, self._t("tip_export"))
        self.btn_docs = btn(self._t("btn_docs"), self._docs_dialog, self._t("tip_docs"))
        self.btn_git = btn(self._t("btn_git"), self.git_commit_dialog, self._t("tip_git"))
        
        b_settings = ttk.Button(self.toolbar_bar, text="\u2699", command=self.open_settings_dialog, width=3)
        b_settings.pack(side=tk.LEFT, padx=2, pady=2)
        self._tip(b_settings, self._t("tip_settings"))

        self._spacer = tk.Frame(self.toolbar_bar, bg="#f0f0f0", cursor="fleur")
        self._spacer.pack(side=tk.LEFT, fill=tk.X, expand=True)

        close_btn = ttk.Button(self.toolbar_bar, text="\u2715", command=self._on_close_main, width=3)
        close_btn.pack(side=tk.RIGHT, padx=(2, 4), pady=2)
        self._tip(close_btn, self._t("tip_close"))

        self.mode_btn = ttk.Button(self.toolbar_bar, text="\u25f1", command=self._toggle_mode, width=3)
        self.mode_btn.pack(side=tk.RIGHT, padx=1, pady=2)
        self._tip(self.mode_btn, self._t("tip_mode"))

        self.backend_label = tk.Label(self.toolbar_bar, text="Git: none", fg="#555", bg="#ffffff", relief=tk.SUNKEN, bd=1, font=("Segoe UI", 8), padx=4, pady=2)
        self.backend_label.pack(side=tk.RIGHT, padx=4, pady=2)



    def _build_main(self):
        pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_pane = pane
        pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        left = ttk.Frame(pane)
        pane.add(left, weight=1)
        self.tree = ttk.Treeview(left, selectmode="browse")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        right = ttk.Frame(pane)
        pane.add(right, weight=3)
        self.nb = ttk.Notebook(right)
        self.nb.pack(fill=tk.BOTH, expand=True)
        ff = ttk.Frame(self.nb)
        self.nb.add(ff, text=self._t("tab_file"))
        find_bar = ttk.Frame(ff)
        find_bar.pack(fill=tk.X, padx=3, pady=(3, 0))

        # 1. Правая часть (действия с файлом)
        tk.Button(find_bar, text="🎨", command=self._highlight_editor, bd=1, padx=6, pady=0).pack(side=tk.RIGHT, padx=1)
        tk.Button(find_bar, text="↪️", command=lambda: self.editor.edit_redo(), bd=1, padx=6, pady=0).pack(side=tk.RIGHT, padx=1)
        tk.Button(find_bar, text="↩️", command=lambda: self.editor.edit_undo(), bd=1, padx=6, pady=0).pack(side=tk.RIGHT, padx=1)
        tk.Button(find_bar, text="💾 Сохранить", command=self._save_editor_file, bd=1, padx=8, pady=0).pack(side=tk.RIGHT, padx=4)

        # 2. Левая часть (поиск)
        ttk.Label(find_bar, text="🔍").pack(side=tk.LEFT)
        self.find_var = tk.StringVar()
        self.find_entry = ttk.Entry(find_bar, textvariable=self.find_var, width=25)
        self.find_entry.pack(side=tk.LEFT, padx=3, fill=tk.Y)
        self.find_entry.bind("<Return>", lambda e: self._find_in_editor(forward=True))
        self.find_entry.bind("<Shift-Return>", lambda e: self._find_in_editor(forward=False))
        self.find_var.trace_add("write", lambda *a: self._find_in_editor(forward=True))
        tk.Button(find_bar, text="◀", command=lambda: self._find_in_editor(forward=False), bd=1, padx=6, pady=0).pack(side=tk.LEFT, padx=1)
        tk.Button(find_bar, text="▶", command=lambda: self._find_in_editor(forward=True), bd=1, padx=6, pady=0).pack(side=tk.LEFT, padx=1)
        tk.Button(find_bar, text="✕", command=self._clear_find, bd=1, padx=6, pady=0).pack(side=tk.LEFT, padx=1)
        self.find_count_label = ttk.Label(find_bar, text="", foreground="#666")
        self.find_count_label.pack(side=tk.LEFT, padx=6)
        self.editor = scrolledtext.ScrolledText(ff, wrap=tk.NONE, font=("Courier New", 10), undo=True)
        self.editor.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        syntax_highlighter.setup_tags(self.editor)
        self.editor.tag_configure("find_hit", background="#FFE082", foreground="black")
        self.editor.tag_configure("find_current", background="#FF8A65", foreground="white")
        self.editor_modified = False
        self.editor.bind("<KeyRelease>", self._on_editor_change)
        self.editor.bind("<Control-s>", lambda e: self._save_editor_file())
        self._bind_zoom(self.editor)
        jf = ttk.Frame(self.nb)
        self.nb.add(jf, text=self._t("tab_json"))
        self.json_text = scrolledtext.ScrolledText(jf, wrap=tk.WORD, font=("Courier New", 9))
        self.json_text.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        jb = ttk.Frame(jf)
        jb.pack(fill=tk.X, pady=2, padx=3)
        ttk.Button(jb, text="📋 Вставить", command=self._paste_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(jb, text="🔍 Проверить", command=self.validate_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(jb, text="✅ Применить", command=self.apply_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(jb, text="🗑 Очистить", command=lambda: self.json_text.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=2)
        prf = ttk.Frame(self.nb)
        self.nb.add(prf, text=self._t("tab_prompt"))
        pt = ttk.Frame(prf)
        pt.pack(fill=tk.X, padx=3, pady=3)
        ttk.Label(pt, text="Промпт:").pack(side=tk.LEFT)
        self.prompt_combo = ttk.Combobox(pt, values=list(self._get_merged_prompts().keys()), state="readonly", width=25)
        self.prompt_combo.pack(side=tk.LEFT, padx=5)
        self.prompt_combo.current(0)
        self.prompt_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_prompt_text())
        def edit_from_main():
            self._edit_single_prompt(self.prompt_combo.get())
            self._refresh_prompt_text()
        ttk.Button(pt, text="✏️ Редактировать", command=edit_from_main).pack(side=tk.LEFT, padx=2)
        ttk.Button(pt, text="📋 Копировать", command=self._copy_prompt).pack(side=tk.LEFT, padx=2)
        ttk.Button(pt, text="📎+Дерево", command=self._copy_prompt_with_structure).pack(side=tk.LEFT, padx=2)
        ttk.Button(pt, text="📎+Файл", command=self._copy_prompt_with_file).pack(side=tk.LEFT, padx=2)
        self.prompt_text = scrolledtext.ScrolledText(prf, wrap=tk.WORD, font=("Courier New", 9), height=10)
        self.prompt_text.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        self._refresh_prompt_text()
        gf = ttk.Frame(self.nb)
        self.nb.add(gf, text=self._t("tab_git"))
        gb = ttk.Frame(gf)
        gb.pack(fill=tk.X, pady=3, padx=3)
        ttk.Button(gb, text="Статус", command=self.git_status).pack(side=tk.LEFT, padx=2)
        ttk.Button(gb, text="Коммит", command=self.git_commit_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(gb, text="История", command=self.git_log).pack(side=tk.LEFT, padx=2)
        ttk.Button(gb, text="Init", command=self.git_init).pack(side=tk.LEFT, padx=2)
        self.git_text = scrolledtext.ScrolledText(gf, wrap=tk.WORD, font=("Courier New", 9))
        self.git_text.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        lf = ttk.Frame(self.nb)
        self.nb.add(lf, text=self._t("tab_log"))
        self.log_text = scrolledtext.ScrolledText(lf, wrap=tk.WORD, font=("Arial", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        self.nb.select(0)
        self.root.bind("<Control-f>", lambda e: self._focus_find() if hasattr(self, "find_entry") else None)

    def _build_statusbar(self):
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar = ttk.Label(self.status_frame, text="Готов", anchor=tk.W)
        self.status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.status_progress = ttk.Progressbar(self.status_frame, mode="indeterminate", length=80)

    def log(self, msg):
        try:
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
        except Exception:
            pass
        try:
            self.status_bar.config(text=msg.split("\n", 1)[0][:120])
        except Exception:
            pass
        try:
            get_logger("ui").info(msg)
        except Exception:
            pass

    def _paste_json(self):
        try:
            self.json_text.delete("1.0", tk.END)
            self.json_text.insert("1.0", self.root.clipboard_get())
            self.log("📋 JSON вставлен из буфера")
        except Exception:
            pass

    def _refresh_prompt_text(self):
        merged = self._get_merged_prompts()
        text = merged.get(self.prompt_combo.get(), "")
        self.prompt_text.config(state=tk.NORMAL)
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", text)
        self.prompt_text.config(state=tk.DISABLED)

    def open_project_dialog(self):
        p = filedialog.askdirectory(title="Выберите папку проекта")
        if p:
            self.open_project(p)

    def open_project(self, path):
        self.project_path = os.path.abspath(path)
        try:
            from logger import setup
            setup(self.project_path)
        except Exception:
            pass
        self.git = GitPy(self.project_path)
        self._ensure_gitignore()
        self.log(f"Открыт проект: {self.project_path}")
        self.backend_label.config(text=f"Git: {self.git.backend()}")
        self._update_project_label()
        self.refresh_tree()

    def _ensure_gitignore(self):
        if not self.project_path:
            return
        (Path(self.project_path) / "dumps").mkdir(exist_ok=True)
        (Path(self.project_path) / "logs").mkdir(exist_ok=True)
        gi = Path(self.project_path) / ".gitignore"
        entries = ["__pycache__/", "*.pyc", "logs/", "dumps/", "*.codegen.bak"]
        existing = ""
        if gi.exists():
            try:
                existing = gi.read_text(encoding="utf-8")
            except Exception:
                pass
        lines = [ln.strip() for ln in existing.splitlines()]
        to_add = [e for e in entries if e not in lines]
        if to_add:
            try:
                with gi.open("a", encoding="utf-8") as f:
                    if existing and not existing.endswith("\n"):
                        f.write("\n")
                    for e in to_add:
                        f.write(e + "\n")
            except Exception:
                pass

    def quick_dump_json(self):
        if not self.project_path:
            messagebox.showinfo(self._t("msg_info"), "Open project first / Сначала откройте проект")
            return
        out = default_dump_path(self.project_path, "json")
        try:
            n = export_json(self.project_path, out)
            self.log(f"⚡ Дамп: {n} файлов → dumps/{Path(out).name}")
        except Exception as e:
            self._error("Ошибка экспорта", str(e))
            self.log(f"❌ Дамп: {e}")

    def _update_project_label(self):
        try:
            if self.project_path:
                name = Path(self.project_path).name or self.project_path
                self.project_label.config(text=f"\U0001F4C2 {name}", fg="#0a5c2a")
            else:
                self.project_label.config(text="— проект не открыт —", fg="#666")
        except Exception:
            pass
        self._update_title()


    def _gitignore_rules(self):
        return read_gitignore(self.project_path) if self.project_path else []

    def refresh_tree(self):
        if not self.project_path:
            return
        for i in self.tree.get_children():
            self.tree.delete(i)
        root = Path(self.project_path)
        rules = self._gitignore_rules()
        root_node = self.tree.insert("", "end", text="📁 " + root.name, open=True)
        self._add_children(root, root_node, rules)

    def _add_children(self, path, parent, rules):
        try:
            items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return
        for p in items:
            if not should_include(p, self.project_path, rules):
                continue
            if p.is_dir():
                node = self.tree.insert(parent, "end", text="📁 " + p.name)
                self._add_children(p, node, rules)
            else:
                self.tree.insert(parent, "end", text="📄 " + p.name, values=(str(p),))

    def _on_editor_change(self, event=None):
        if not getattr(self, 'editor_modified', False):
            self.editor_modified = True
            self._update_title()
        # Умная задержка (debounce) для подсветки
        if not hasattr(self, '_hl_after'):
            self._hl_after = None
        if self._hl_after:
            self.root.after_cancel(self._hl_after)
        self._hl_after = self.root.after(800, self._highlight_editor)

    def _save_editor_file(self):
        if not self.current_file:
            return
        try:
            content = self.editor.get("1.0", tk.END).rstrip("\n") + "\n"
            Path(self.current_file).write_text(content, encoding="utf-8")
            self.current_content = content
            self.editor_modified = False
            self._update_title()
            self.log(f"Сохранён {Path(self.current_file).name}")
            self._highlight_editor()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{e}", parent=self.root)

    def _highlight_editor(self):
        content = self.editor.get("1.0", tk.END)
        lang = "python" if (self.current_file or "").endswith(".py") else "text"
        syntax_highlighter.apply_highlight(self.editor, content, lang)

    def _update_title(self):
        if not self.project_path:
            self.root.title("Codegen Studio v1.1")
            return
        name = Path(self.project_path).name
        fname = Path(self.current_file).name if self.current_file else ""
        mod = " *" if getattr(self, 'editor_modified', False) else ""
        if fname:
            self.root.title(f"Codegen Studio v1.1 — {name} / {fname}{mod}")
        else:
            self.root.title(f"Codegen Studio v1.1 — {name}{mod}")

    def _on_close_main(self):
        if getattr(self, 'editor_modified', False) and self.current_file:
            ans = messagebox.askyesnocancel(self._t("msg_unsaved"), self._t("msg_unsaved_text"), parent=self.root)
            if ans is None:
                return
            if ans:
                self._save_editor_file()
        self.root.destroy()


    def _bind_zoom(self, widget, base_size=10):
        """Zoom в редакторе: Ctrl+Wheel, Ctrl+/-/0."""
        try:
            f = widget.cget("font")
            if isinstance(f, tuple) and len(f) >= 2:
                family, size = f[0], int(f[1])
            elif isinstance(f, str):
                parts = f.split()
                family = parts[0] if parts else "Courier New"
                size = int(parts[1]) if len(parts) > 1 else base_size
            else:
                family, size = "Courier New", base_size
        except Exception:
            family, size = "Courier New", base_size

        state = {"family": family, "size": size, "base": size}

        def apply():
            widget.config(font=(state["family"], state["size"]))

        def zin(event=None):
            state["size"] = min(state["size"] + 1, 40)
            apply()
            return "break"

        def zout(event=None):
            state["size"] = max(state["size"] - 1, 6)
            apply()
            return "break"

        def zreset(event=None):
            state["size"] = state["base"]
            apply()
            return "break"

        def wheel(event):
            if event.delta > 0:
                return zin()
            return zout()

        widget.bind("<Control-MouseWheel>", wheel)
        widget.bind("<Control-Button-4>", zin)
        widget.bind("<Control-Button-5>", zout)
        widget.bind("<Control-plus>", zin)
        widget.bind("<Control-equal>", zin)
        widget.bind("<Control-minus>", zout)
        widget.bind("<Control-0>", zreset)
        widget._zoom_state = state


    def _get_custom_prompts_path(self):
        if not self.project_path:
            return None
        d = Path(self.project_path) / ".codegen_studio"
        d.mkdir(exist_ok=True)
        return d / "custom_prompts.json"

    def _load_custom_prompts(self):
        path = self._get_custom_prompts_path()
        if path and path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _get_merged_prompts(self):
        import prompts
        base = dict(prompts.PROMPTS)
        base.update(self._load_custom_prompts())
        return base

    def _save_custom_prompt(self, name, text):
        path = self._get_custom_prompts_path()
        if not path:
            return
        data = self._load_custom_prompts()
        data[name] = text
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log(f"Сохранен кастомный промпт: {name}")
        except Exception as e:
            self.log(f"Ошибка сохранения промпта: {e}")

    def _edit_single_prompt(self, name):
        merged = self._get_merged_prompts()
        current_text = merged.get(name, "")
        win = tk.Toplevel(self.root)
        win.title(f"{self._t('edit_prompt_title')} {name}")
        win.geometry("800x600")
        win.transient(self.root)
        win.grab_set()
        tk.Label(win, text=self._t("edit_prompt_text"), font=("Segoe UI", 10, "bold"), anchor=tk.W).pack(fill=tk.X, padx=10, pady=5)
        txt = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Consolas", 10), undo=True)
        txt.insert("1.0", current_text)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        syntax_highlighter.setup_tags(txt)
        syntax_highlighter.apply_highlight(txt, current_text, "markdown")
        def apply_hl(event=None):
            syntax_highlighter.apply_highlight(txt, txt.get("1.0", tk.END), "markdown")
        txt.bind("<KeyRelease>", apply_hl)

        bf = tk.Frame(win)
        bf.pack(fill=tk.X, padx=10, pady=10)
        def do_save():
            new_text = txt.get("1.0", tk.END).rstrip("\n")
            self._save_custom_prompt(name, new_text)
            win.destroy()
        ttk.Button(bf, text=self._t("edit_prompt_undo"), command=lambda: txt.edit_undo()).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text=self._t("edit_prompt_redo"), command=lambda: txt.edit_redo()).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text=self._t("edit_prompt_hl"), command=apply_hl).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text=self._t("msg_cancel"), command=win.destroy).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bf, text=self._t("msg_save"), command=do_save).pack(side=tk.RIGHT, padx=2)
        win.wait_window()

    def _focus_find(self):
        self.find_entry.focus_set()
        self.find_entry.select_range(0, tk.END)

    def _find_in_editor(self, forward=True):
        if not hasattr(self, "find_entry"):
            return
        q = self.find_var.get()
        self.editor.tag_remove("find_hit", "1.0", tk.END)
        self.editor.tag_remove("find_current", "1.0", tk.END)
        if not q:
            if hasattr(self, "find_count_label"):
                self.find_count_label.config(text="")
            return
        content = self.editor.get("1.0", tk.END)
        ql = q.lower()
        cl = content.lower()
        hits = []
        start = 0
        while True:
            idx = cl.find(ql, start)
            if idx == -1:
                break
            hits.append(idx)
            start = idx + 1
        for h in hits:
            s = f"1.0+{h}c"
            e = f"1.0+{h + len(q)}c"
            self.editor.tag_add("find_hit", s, e)
        if not hits:
            self.find_count_label.config(text="0/0", foreground="red")
            return
        cur = self.editor.index(tk.INSERT)
        cur_char = len(self.editor.get("1.0", cur))
        if forward:
            nxt = next((h for h in hits if h > cur_char), hits[0])
        else:
            nxt = next((h for h in reversed(hits) if h < cur_char), hits[-1])
        s = f"1.0+{nxt}c"
        e = f"1.0+{nxt + len(q)}c"
        self.editor.tag_add("find_current", s, e)
        self.editor.see(s)
        self.editor.mark_set(tk.INSERT, s)
        num = hits.index(nxt) + 1
        self.find_count_label.config(text=f"{num}/{len(hits)}", foreground="#333")

    def _clear_find(self):
        self.find_var.set("")
        self.editor.tag_remove("find_hit", "1.0", tk.END)
        self.editor.tag_remove("find_current", "1.0", tk.END)
        if hasattr(self, "find_count_label"):
            self.find_count_label.config(text="")
        self.editor.focus_set()


    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        if not vals:
            return
        file_path = vals[0]
        if not os.path.isfile(file_path):
            return
        if getattr(self, 'editor_modified', False) and self.current_file:
            ans = messagebox.askyesnocancel(self._t("msg_unsaved"), self._t("msg_unsaved_text"), parent=self.root)
            if ans is None:
                return
            if ans:
                self._save_editor_file()
        self.current_file = file_path
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                self.current_content = f.read()
        except Exception as e:
            self.current_content = f"[Ошибка чтения: {e}]"
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", self.current_content)
        self.editor.edit_reset()
        self.editor_modified = False
        self._update_title()
        lang = "python" if file_path.endswith(".py") else "text"
        syntax_highlighter.apply_highlight(self.editor, self.current_content, lang)
        if not self._toolbar_mode:
            self.nb.select(0)

    def copy_structure(self):
        if not self.project_path:
            return
        root = Path(self.project_path)
        rules = self._gitignore_rules()
        lines = [f"Проект: {self.project_path}", ""]
        for p in root.rglob("*"):
            if p.is_file() and should_include(p, root, rules):
                lines.append(str(p.relative_to(root)).replace("\\", "/"))
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))
        self.log("📋 Структура проекта скопирована")

    def _parse_json_input(self):
        text = self.json_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Пусто", "Вставьте JSON-инструкции")
            return None, None
        if text.startswith("```"):
            lines = text.splitlines()[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            get_logger("errors").error("JSON parse failed: %s", e)
            self.log(f"❌ JSON parse: {e}")
            self._error("Ошибка JSON", str(e))
            return None, None
        try:
            actions = normalize_actions(data)
        except Exception as e:
            get_logger("errors").error("normalize_actions failed: %s", e)
            self.log(f"❌ normalize: {e}")
            self._error("Ошибка разбора", f"Не удалось разобрать: {e}")
            return None, None
        return data, actions

    def validate_json(self):
        if not self.project_path:
            messagebox.showinfo(self._t("msg_info"), "Open project first / Сначала откройте проект")
            return
        _, actions = self._parse_json_input()
        if actions is None:
            return
        errors, warnings = validate(actions, self.project_path)
        logger = get_logger("errors")
        for e in errors:
            logger.error("validation: %s", e)
        for w in warnings:
            logger.warning("validation-warn: %s", w)
        msg = []
        if errors:
            msg.append("❌ Ошибки:")
            msg.extend(f"  • {e}" for e in errors)
        if warnings:
            msg.append("⚠️ Предупреждения:")
            msg.extend(f"  • {w}" for w in warnings)
        if not msg:
            msg = ["✅ Валидация пройдена"]
        self.log("\n".join(msg))
        messagebox.showinfo("Валидация", "\n".join(msg))

    def simulate_json(self):
        self.apply_json()

    def apply_json(self):
        if not self.project_path:
            messagebox.showinfo(self._t("msg_info"), "Open project first / Сначала откройте проект")
            return
        _, actions = self._parse_json_input()
        if actions is None:
            return
        logger = get_logger("errors")
        errors, _ = validate(actions, self.project_path)
        if errors:
            for e in errors:
                logger.error("validation: %s", e)
            self.log(f"❌ Валидация: {len(errors)} ошибок (см. errors.log)")
            self._error("Ошибки валидации", "\n".join(errors))
            return
        sim = simulate(actions, self.project_path)
        if sim.errors:
            for e in sim.errors:
                logger.error("simulation: %s", e)
            self.log(f"❌ Симуляция: {len(sim.errors)} ошибок (см. errors.log)")
            self._error("Ошибки симуляции", "\n".join(sim.errors))
            return
        if not sim.changes and not sim.creations:
            if sim.warnings:
                logger.warning("simulation warnings:\n" + "\n".join(sim.warnings))
                self.log(f"⚠️ Симуляция: нет изменений, но {len(sim.warnings)} предупреждений")
                for w in sim.warnings:
                    self.log(f"   • {w}")
                messagebox.showwarning(
                    "Нет изменений",
                    "Действия не применились, но валидация пропустила их.\n\n"
                    "Причины:\n" + "\n".join(f"• {w}" for w in sim.warnings[:20]) +
                    ("\n\n... (см. Лог)" if len(sim.warnings) > 20 else "")
                )
            else:
                logger.info("simulation: нет изменений")
                self.log("ℹ️ Симуляция: нет изменений")
                messagebox.showinfo("Симуляция", "Нет изменений")
            return
        self.log(f"👁 Симуляция: {len(sim.changes)} изменений, {len(sim.creations)} созданий")
        if not self._show_diff_dialog(sim):
            logger.info("apply: отменено пользователем")
            self.log("❌ Отменено пользователем")
            return
        success, applied, created, errs = apply_simulation(sim, self.project_path)
        if success:
            for fp in applied:
                logger.info("apply-ok: %s", fp)
            self.log(f"✅ Применено: {len(applied)} файлов, {len(created)} созданий")
            messagebox.showinfo("Готово", f"Изменено: {len(applied)}\nСоздано: {len(created)}")
            self.simulation = None
            self.refresh_tree()
            if self.current_file and os.path.exists(self.current_file):
                self._on_tree_select(None)
        else:
            for e in errs:
                logger.error("apply-failed: %s", e)
            self.log(f"❌ Ошибка применения: {len(errs)} (см. errors.log)")
            self._error("Ошибка применения", "\n".join(errs))

    def export_json_dialog(self):

        if not self.project_path:
            messagebox.showinfo(self._t("msg_info"), "Open project first / Сначала откройте проект")
            return
        dumps_dir = Path(self.project_path) / "dumps"
        dumps_dir.mkdir(exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"{Path(self.project_path).name}_dump_{ts}.json"
        out = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile=default_name,
            initialdir=str(dumps_dir),
            filetypes=[("JSON", "*.json")],
        )
        if not out:
            return
        try:
            n = export_json(self.project_path, out)
            self.log(f"📤 JSON: {n} файлов → {out}")
            messagebox.showinfo("Готово", f"Экспортировано: {n}\n{Path(out).name}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def export_zip_dialog(self):
        if not self.project_path:
            messagebox.showinfo(self._t("msg_info"), "Open project first / Сначала откройте проект")
            return
        dumps_dir = Path(self.project_path) / "dumps"
        dumps_dir.mkdir(exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"{Path(self.project_path).name}_{ts}.zip"
        out = filedialog.asksaveasfilename(
            defaultextension=".zip",
            initialfile=default_name,
            initialdir=str(dumps_dir),
            filetypes=[("ZIP", "*.zip")],
        )
        if not out:
            return
        try:
            n = export_zip(self.project_path, out)
            self.log(f"📦 ZIP: {n} файлов → {out}")
            messagebox.showinfo("Готово", f"Заархивировано: {n}\n{Path(out).name}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _copy_prompt(self):
        self.root.clipboard_clear()
        merged = self._get_merged_prompts()
        self.root.clipboard_append(merged.get(self.prompt_combo.get(), ""))
        self.log(f"📋 Промпт '{self.prompt_combo.get()}' скопирован")

    def _copy_prompt_with_structure(self):
        if not self.project_path:
            return
        root = Path(self.project_path)
        rules = self._gitignore_rules()
        lines = []
        for p in root.rglob("*"):
            if p.is_file() and should_include(p, root, rules):
                lines.append(str(p.relative_to(root)).replace("\\", "/"))
        merged = self._get_merged_prompts()
        text = merged.get(self.prompt_combo.get(), "") + "\n\n### Структура проекта:\n" + "\n".join(lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.log("📋 Промпт + структура скопированы")

    def _copy_prompt_with_file(self):
        if not self.current_file:
            messagebox.showinfo(self._t("msg_info"), "Open file in tree / Откройте файл в дереве")
            return
        rel = str(Path(self.current_file).relative_to(self.project_path)).replace("\\", "/")
        merged = self._get_merged_prompts()
        text = merged.get(self.prompt_combo.get(), "") + f"\n\n### Файл: {rel}\n```python\n{self.current_content}\n```"
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.log(f"📋 Промпт + файл {rel} скопированы")

    def git_status(self):
        if not self.git:
            return
        self.git_text.delete("1.0", tk.END)
        self.git_text.insert("1.0", self.git.status())
        self.log("🔧 Git status")

    def git_commit_dialog(self):
        if not self.git:
            return
        msg = simpledialog.askstring("Git commit", "Сообщение коммита:")
        if not msg:
            return
        ok, err = self.git.commit(msg)
        if ok:
            self.log(f"✅ Коммит: {msg}")
            messagebox.showinfo("Git", "Коммит создан")
        else:
            messagebox.showerror("Git", err)
            self.log(f"❌ Git: {err}")

    def git_log(self):
        if not self.git:
            return
        self.git_text.delete("1.0", tk.END)
        for c in self.git.log():
            self.git_text.insert(tk.END, f"{c['hash']}  {c['date'][:16]}  {c['message']}\n")
        self.log("🔧 Git log")

    def git_init(self):
        if not self.git:
            return
        if self.git.is_repo():
            messagebox.showinfo("Git", "Репозиторий уже инициализирован.")
            return
        if messagebox.askyesno("Git", "Инициализировать репозиторий?"):
            ok, err = self.git.init()
            if ok:
                self.log("✅ Git init")
                self.backend_label.config(text=f"Git: {self.git.backend()}")
                messagebox.showinfo("Git", "Репозиторий инициализирован")
            else:
                self._error("Git init", err)

    def enter_toolbar_mode(self):
        if self._toolbar_mode:
            return
        try:
            self._full_geometry = self.root.geometry()
            self._s.set("window_geometry", self._full_geometry)
        except Exception:
            pass
        for w in (self.main_pane, self.status_frame):
            try:
                w.pack_forget()
            except Exception:
                pass
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", bool(self._s.get("always_on_top", True)))
        x, y = self._s.get("toolbar_pos", [100, 100])
        self.root.geometry(f"780x44+{int(x)}+{int(y)}")
        if hasattr(self, 'btn_export'):
            self.btn_export.pack_forget()
            self.btn_docs.pack_forget()
            self.btn_git.pack_forget()
        self.root.update_idletasks()
        self._make_draggable()
        self._toolbar_mode = True
        self._s.set("mode", "toolbar")
        self._s.save()
        self.log("Режим: toolbar (780x44)")

    def exit_toolbar_mode(self):
        if not self._toolbar_mode:
            return
        self.root.overrideredirect(False)
        self.root.attributes("-topmost", False)
        if hasattr(self, 'btn_export'):
            self.btn_export.pack(side=tk.LEFT, padx=1, pady=2)
            self.btn_docs.pack(side=tk.LEFT, padx=1, pady=2)
            self.btn_git.pack(side=tk.LEFT, padx=1, pady=2)
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        geom = self._s.get("window_geometry", "1100x700+200+100")
        self.root.geometry(geom)
        self.root.minsize(600, 400)
        self._toolbar_mode = False
        self._s.set("mode", "window")
        self._s.save()
        self.log("Режим: window")

    def _toggle_mode(self):
        if self._toolbar_mode:
            self.exit_toolbar_mode()
        else:
            self.enter_toolbar_mode()

    def _make_draggable(self):
        def on_press(e):
            self._drag_x = e.x_root - self.root.winfo_x()
            self._drag_y = e.y_root - self.root.winfo_y()
        def on_drag(e):
            x = e.x_root - self._drag_x
            y = e.y_root - self._drag_y
            self.root.geometry(f"+{x}+{y}")
        def on_release(e):
            try:
                self._s.set("toolbar_pos", [self.root.winfo_x(), self.root.winfo_y()])
                self._s.save()
            except Exception:
                pass
        widgets = [self.toolbar_bar, self._toolbar_handle, getattr(self, "_spacer", None),
                   getattr(self, "backend_label", None)]
        for w in widgets:
            if w is None:
                continue
            w.bind("<Button-1>", on_press, add="+")
            w.bind("<B1-Motion>", on_drag, add="+")
            w.bind("<ButtonRelease-1>", on_release, add="+")

    def _json_dialog(self):
        win = tk.Toplevel(self.root)
        win.title(self._t("json_title"))
        win.geometry("900x600")
        win.transient(self.root)
        win.lift()
        win.focus_force()

        header = tk.Frame(win, bg="#e8f4ff")
        header.pack(fill=tk.X)
        tk.Label(header, text=self._t("json_how"), font=("Arial", 11, "bold"), bg="#e8f4ff", anchor=tk.W).pack(fill=tk.X, padx=12, pady=(8, 2))
        tk.Label(header, text=self._t("json_step1"), bg="#e8f4ff", anchor=tk.W, fg="#333").pack(fill=tk.X, padx=12)
        tk.Label(header, text=self._t("json_step2"), bg="#e8f4ff", anchor=tk.W, fg="#333").pack(fill=tk.X, padx=12)
        tk.Label(header, text=self._t("json_step3"), bg="#e8f4ff", anchor=tk.W, fg="#333").pack(fill=tk.X, padx=12, pady=(0, 8))

        clip_status = tk.Label(win, text="", fg="green", font=("Arial", 9), anchor=tk.W)
        clip_status.pack(fill=tk.X, padx=12, pady=(4, 0))

        frame = tk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)
        tk.Label(frame, text="JSON:", anchor=tk.W, font=("Arial", 9, "bold")).pack(fill=tk.X)
        txt = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=("Courier New", 10), undo=True)
        txt.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

        try:
            clip = self.root.clipboard_get().strip()
            if clip:
                txt.insert("1.0", clip)
                clip_status.config(text="✓ JSON loaded from clipboard")
        except Exception:
            pass

        bf = tk.Frame(win)
        bf.pack(fill=tk.X, padx=12, pady=(0, 10))

        def do_paste():
            try:
                txt.delete("1.0", tk.END)
                txt.insert("1.0", self.root.clipboard_get())
                clip_status.config(text="✓ Updated from clipboard", fg="green")
            except Exception:
                clip_status.config(text="⚠ Clipboard empty or unavailable", fg="orange")

        def do_apply():
            content = txt.get("1.0", tk.END).strip()
            if not content:
                clip_status.config(text="⚠ Insert JSON first", fg="red")
                return
            win.destroy()
            self.json_text.delete("1.0", tk.END)
            self.json_text.insert("1.0", content)
            self.apply_json()

        tk.Button(bf, text=self._t("json_paste"), command=do_paste, font=("Arial", 10), padx=10, pady=6).pack(side=tk.LEFT)
        tk.Button(bf, text=self._t("msg_cancel"), command=win.destroy, font=("Arial", 10), padx=10, pady=6).pack(side=tk.RIGHT, padx=4)
        tk.Button(bf, text=self._t("json_apply"), command=do_apply, font=("Arial", 10, "bold"), padx=14, pady=6, bg="#4CAF50", fg="white", activebackground="#45a049", activeforeground="white").pack(side=tk.RIGHT, padx=4)

        txt.focus_set()
        win.wait_window()

    def apply_from_clipboard(self):
        try:
            content = self.root.clipboard_get().strip()
        except Exception:
            content = ""
        if not content or not (content.startswith("{") or content.startswith("```")):
            self._json_dialog()
            return
        self.json_text.delete("1.0", tk.END)
        self.json_text.insert("1.0", content)
        self.apply_json()

    def open_settings_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("Настройки / Settings")
        win.geometry("440x380")
        win.transient(self.root)
        win.grab_set()
        
        tk.Label(win, text=self._t("settings_lang"), anchor=tk.W, font=("Arial", 10, "bold")).pack(fill=tk.X, padx=10, pady=(10, 2))
        lang_var = tk.StringVar(value=self._s.get("language", "ru"))
        lf = tk.Frame(win)
        lf.pack(fill=tk.X, padx=25)
        tk.Radiobutton(lf, text="Русский", variable=lang_var, value="ru").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(lf, text="English", variable=lang_var, value="en").pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(win, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=10)
        
        mode_var = tk.StringVar(value=self._s.get("mode", "window"))
        top_var = tk.BooleanVar(value=self._s.get("always_on_top", True))
        tk.Label(win, text="Режим окна / Window mode:", anchor=tk.W, font=("Arial", 10, "bold")).pack(fill=tk.X, padx=10, pady=(10, 2))
        tk.Radiobutton(win, text="\U0001F5D4  Обычное окно / Normal window", variable=mode_var, value="window").pack(anchor=tk.W, padx=25)
        tk.Radiobutton(win, text="\U0001F4CC  Компактный toolbar / Compact toolbar", variable=mode_var, value="toolbar").pack(anchor=tk.W, padx=25)
        tk.Checkbutton(win, text="Поверх всех окон / Always on top", variable=top_var).pack(anchor=tk.W, padx=10, pady=10)
        
        def do_save():
            self._s.set("language", lang_var.get())
            self._s.set("mode", mode_var.get())
            self._s.set("always_on_top", top_var.get())
            self._s.save()
            current = "toolbar" if self._toolbar_mode else "window"
            target = mode_var.get()
            if current != target:
                if target == "toolbar": self.enter_toolbar_mode()
                else: self.exit_toolbar_mode()
            elif self._toolbar_mode:
                self.root.attributes("-topmost", bool(top_var.get()))
            messagebox.showinfo("Info", self._t("restart_req"), parent=win)
            win.destroy()
            
        bf = tk.Frame(win)
        bf.pack(fill=tk.X, pady=10, padx=10)
        tk.Button(bf, text="\u2714 OK", command=do_save).pack(side=tk.RIGHT, padx=2)
        tk.Button(bf, text="Cancel", command=win.destroy).pack(side=tk.RIGHT, padx=2)
        win.wait_window()

    def _prompts_dialog(self):
        """Диалог: выбор промпта + контекст + превью + копирование."""
        win = tk.Toplevel(self.root)
        win.title(self._t("pr_title"))
        win.geometry("900x720")
        win.transient(self.root)
        win.lift()
        win.focus_force()

        tk.Label(win, text=self._t("pr_1"), anchor=tk.W,
                 font=("Arial", 10, "bold")).pack(fill=tk.X, padx=12, pady=(10, 2))
        prompt_var = tk.StringVar()
        merged_prompts = self._get_merged_prompts()
        prompts = list(merged_prompts.keys())
        combo = ttk.Combobox(win, textvariable=prompt_var, values=prompts,
                             state="readonly", width=50)
        combo.pack(fill=tk.X, padx=12, pady=2)
        if prompts:
            combo.current(0)

        def edit_current():
            self._edit_single_prompt(prompt_var.get())
            refresh_preview()

        btn_edit = tk.Button(win, text="✏️ Редактировать выбранный промпт", command=edit_current)
        btn_edit.pack(anchor=tk.W, padx=12, pady=2)

        tk.Label(win, text=self._t("pr_2"), anchor=tk.W,
                 font=("Arial", 10, "bold")).pack(fill=tk.X, padx=12, pady=(10, 2))
        mode_var = tk.StringVar(value="prompt")
        mf = tk.Frame(win)
        mf.pack(fill=tk.X, padx=24)
        tk.Radiobutton(mf, text=self._t("pr_only"), variable=mode_var, value="prompt").pack(anchor=tk.W)
        tk.Radiobutton(mf, text=self._t("pr_tree"), variable=mode_var, value="prompt_tree").pack(anchor=tk.W)
        tk.Radiobutton(mf, text=self._t("pr_file"), variable=mode_var, value="prompt_file").pack(anchor=tk.W)
        tk.Radiobutton(mf, text=self._t("pr_both"), variable=mode_var, value="prompt_both").pack(anchor=tk.W)

        ctx_var = tk.BooleanVar(value=True)
        tk.Checkbutton(win, text=self._t("pr_ctx"),
                       variable=ctx_var).pack(anchor=tk.W, padx=24, pady=(6, 0))

        tk.Label(win, text=self._t("pr_preview"), anchor=tk.W,
                 font=("Arial", 10, "bold")).pack(fill=tk.X, padx=12, pady=(10, 2))
        preview = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Courier New", 9), height=18)
        preview.pack(fill=tk.BOTH, expand=True, padx=12, pady=2)
        status = tk.Label(win, text="", fg="green", anchor=tk.W, font=("Arial", 9))
        status.pack(fill=tk.X, padx=12)

        def get_context():
            if not self.project_path:
                return ""
            ctx_path = Path(self.project_path) / "docs" / "PROJECT_CONTEXT.md"
            if not ctx_path.exists():
                return ""
            try:
                content = ctx_path.read_text(encoding="utf-8")
            except Exception:
                return ""
            m = re.search(r'##\s*Краткая выжимка для ИИ.*?\n(.*?)(?:\n##|\Z)',
                          content, re.DOTALL | re.IGNORECASE)
            if m:
                return m.group(1).strip()
            return content.replace("<!-- END OF DOC -->", "").strip()[:1500]

        def get_tree():
            if not self.project_path:
                return ""
            root = Path(self.project_path)
            rules = self._gitignore_rules()
            lines = ["### Структура проекта:"]
            for p in sorted(root.rglob("*")):
                if p.is_file() and should_include(p, root, rules):
                    lines.append("- " + str(p.relative_to(root)).replace("\\", "/"))
            return "\n".join(lines) if len(lines) > 1 else ""

        def get_current_file_block():
            if not self.current_file:
                return ""
            try:
                rel = str(Path(self.current_file).relative_to(self.project_path)).replace("\\", "/")
            except Exception:
                rel = os.path.basename(self.current_file)
            return f"### Файл: {rel}\n```python\n{self.current_content}\n```"

        def compose():
            parts = []
            base = self._get_merged_prompts().get(prompt_var.get(), "")
            if not base:
                return ""
            if ctx_var.get():
                ctx = get_context()
                if ctx:
                    parts.append("### Контекст проекта\n" + ctx)
            parts.append(base)
            mode = mode_var.get()
            if mode in ("prompt_tree", "prompt_both"):
                t = get_tree()
                if t:
                    parts.append(t)
            if mode in ("prompt_file", "prompt_both"):
                f = get_current_file_block()
                if f:
                    parts.append(f)
            return "\n\n".join(parts)

        def refresh_preview(*args):
            preview.config(state=tk.NORMAL)
            preview.delete("1.0", tk.END)
            text = compose()
            preview.insert("1.0", text)
            preview.config(state=tk.DISABLED)
            status.config(text=f"{self._t('pr_chars')} {len(text)}")

        combo.bind("<<ComboboxSelected>>", refresh_preview)
        mode_var.trace_add("write", refresh_preview)
        ctx_var.trace_add("write", refresh_preview)

        if not self.project_path:
            mode_var.set("prompt")
            for child in mf.winfo_children():
                child.configure(state=tk.DISABLED)

        def do_copy():
            text = compose()
            if not text:
                status.config(text="Нечего копировать", fg="red")
                return
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                status.config(text=f"Скопировано ({len(text)} символов)", fg="green")
                self.log(f"Скопирован промпт '{prompt_var.get()}' ({len(text)} симв.)")
            except Exception as e:
                status.config(text=f"Ошибка: {e}", fg="red")

        bf = tk.Frame(win)
        bf.pack(fill=tk.X, padx=12, pady=10)
        tk.Button(bf, text=self._t("pr_copy"), command=do_copy,
                  font=("Arial", 10, "bold"), padx=14, pady=6,
                  bg="#4CAF50", fg="white", activebackground="#45a049",
                  activeforeground="white").pack(side=tk.LEFT)
        tk.Button(bf, text="Закрыть", command=win.destroy,
                  font=("Arial", 10), padx=10, pady=6).pack(side=tk.RIGHT)

        refresh_preview()
        win.wait_window()

    def _open_folder(self, path):
        import subprocess, sys
        if not path or not os.path.isdir(path):
            self.log(f"Папка не существует: {path}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self.log(f"Не удалось открыть папку: {e}")

    def _dump_dialog(self):
        if not self.project_path:
            messagebox.showinfo(self._t("msg_info"), "Open project first / Сначала откройте проект")
            return
        from datetime import datetime
        dumps_dir = Path(self.project_path) / "dumps"
        dumps_dir.mkdir(exist_ok=True)
        project_name = Path(self.project_path).name
        win = tk.Toplevel(self.root)
        win.title(self._t("exp_title"))
        win.geometry("720x680")
        win.transient(self.root)
        win.grab_set()
        
        tk.Label(win, text=f"{self._t('exp_proj')} {project_name}", font=("Segoe UI", 11, "bold"), anchor=tk.W).pack(fill=tk.X, padx=12, pady=4)
        info_files = tk.Label(win, text="Анализ...", font=("Segoe UI", 9), anchor=tk.W, fg="#555")
        info_files.pack(fill=tk.X, padx=12, pady=2)
        
        tk.Label(win, text=self._t("exp_fmt"), font=("Segoe UI", 10, "bold"), anchor=tk.W).pack(fill=tk.X, padx=12, pady=4)
        format_var = tk.StringVar(value="json")
        fframe = tk.Frame(win)
        fframe.pack(fill=tk.X, padx=28)
        tk.Radiobutton(fframe, text=self._t("exp_fmt_json"), variable=format_var, value="json").pack(anchor=tk.W)
        tk.Radiobutton(fframe, text=self._t("exp_fmt_zip"), variable=format_var, value="zip").pack(anchor=tk.W)
        
        tk.Label(win, text=self._t("exp_where"), font=("Segoe UI", 10, "bold"), anchor=tk.W).pack(fill=tk.X, padx=12, pady=4)
        where_var = tk.StringVar(value="dumps")
        wframe = tk.Frame(win)
        wframe.pack(fill=tk.X, padx=28)
        tk.Radiobutton(wframe, text=f"В папку dumps/  ({dumps_dir})", variable=where_var, value="dumps").pack(anchor=tk.W)
        tk.Radiobutton(wframe, text="Выбрать папку вручную…", variable=where_var, value="manual").pack(anchor=tk.W)
        
        path_preview = tk.Label(win, text="", fg="#0a5c2a", anchor=tk.W, font=("Consolas", 9), wraplength=680, justify=tk.LEFT)
        path_preview.pack(fill=tk.X, padx=12, pady=4)
        
        def update_preview(*args):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            if format_var.get() == "json":
                name = f"{project_name}_dump_{ts}.json"
            else:
                name = f"{project_name}_{ts}.zip"
            if where_var.get() == "dumps":
                full = str(dumps_dir / name)
            else:
                full = f"<выбрать вручную>\\{name}"
            path_preview.config(text=f"📄 {full}")
        format_var.trace_add("write", update_preview)
        where_var.trace_add("write", update_preview)
        update_preview()
        
        tk.Label(win, text=self._t("exp_not_incl"), font=("Segoe UI", 10, "bold"), anchor=tk.W).pack(fill=tk.X, padx=12, pady=4)
        tk.Label(win, text=self._t("exp_not_incl_text"), font=("Segoe UI", 9), anchor=tk.W, fg="#aa3333", justify=tk.LEFT).pack(fill=tk.X, padx=12, pady=2)
        
        tk.Label(win, text=self._t("exp_preview"), font=("Segoe UI", 10, "bold"), anchor=tk.W).pack(fill=tk.X, padx=12, pady=4)
        preview_txt = scrolledtext.ScrolledText(win, height=10, font=("Consolas", 9), bg="#fafafa", state=tk.DISABLED)
        preview_txt.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        
        try:
            from exporter import _collect_files
            files = _collect_files(self.project_path)
            total = len(files)
            info_files.config(text=f"Файлов в экспорт: {total}")
            preview_txt.config(state=tk.NORMAL)
            for p, rel in files[:12]:
                preview_txt.insert(tk.END, rel + "\n")
            if total > 12:
                preview_txt.insert(tk.END, f"... и ещё {total - 12} файлов\n")
            preview_txt.config(state=tk.DISABLED)
        except Exception as e:
            info_files.config(text=f"Ошибка анализа: {e}", fg="red")
            
        def do_export():
            fmt = format_var.get()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            if fmt == "json":
                fname = f"{project_name}_dump_{ts}.json"
            else:
                fname = f"{project_name}_{ts}.zip"
            if where_var.get() == "dumps":
                out = str(dumps_dir / fname)
            else:
                ext = ".json" if fmt == "json" else ".zip"
                out = filedialog.asksaveasfilename(defaultextension=ext, initialfile=fname, initialdir=str(dumps_dir), filetypes=[("JSON" if fmt == "json" else "ZIP", f"*{ext}")], title="Куда сохранить экспорт?")
                if not out:
                    return
            try:
                n = export_json(self.project_path, out) if fmt == "json" else export_zip(self.project_path, out)
                self.log(f"📤 Экспорт: {n} файлов → {out}")
                win.destroy() # Закрываем окно настроек сразу после экспорта
                ans = messagebox.askyesno(self._t("exp_done"), f"{self._t('exp_files')} {n}\n{self._t('exp_saved_to')}\n{out}\n\n{self._t('exp_open_q')}")
                if ans:
                    self._open_folder(os.path.dirname(out))
            except Exception as e:
                self._error("Ошибка экспорта", str(e))
                self.log(f"❌ Экспорт: {e}")
                
        bf = tk.Frame(win)
        bf.pack(fill=tk.X, padx=12, pady=8)
        tk.Button(bf, text=self._t("exp_open_dumps"), command=lambda: self._open_folder(str(dumps_dir))).pack(side=tk.LEFT)
        tk.Button(bf, text="Закрыть", command=win.destroy).pack(side=tk.RIGHT, padx=4)
        tk.Button(bf, text=self._t("exp_export"), bg="#4CAF50", fg="white", activebackground="#45a049", activeforeground="white", font=("Segoe UI", 10, "bold"), padx=14, pady=6, command=do_export).pack(side=tk.RIGHT, padx=4)
        win.wait_window()


    def _open_folder(self, path):
        import subprocess, sys
        if not path or not os.path.isdir(path):
            self.log(f"Папка не существует: {path}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self.log(f"Не удалось открыть папку: {e}")

    def _dump_dialog(self):
        if not self.project_path:
            messagebox.showinfo(self._t("msg_info"), "Open project first / Сначала откройте проект")
            return
        from datetime import datetime
        dumps_dir = Path(self.project_path) / "dumps"
        dumps_dir.mkdir(exist_ok=True)
        project_name = Path(self.project_path).name
        win = tk.Toplevel(self.root)
        win.title(self._t("exp_title"))
        win.geometry("720x680")
        win.transient(self.root)
        win.grab_set()
        tk.Label(win, text=f"{self._t('exp_proj')} {project_name}",
                 font=("Arial", 11, "bold"), anchor=tk.W).pack(fill=tk.X, padx=12, pady=4)
        info_files = tk.Label(win, text="Анализ...", font=("Arial", 9), anchor=tk.W, fg="#555")
        info_files.pack(fill=tk.X, padx=12, pady=2)
        tk.Label(win, text=self._t("exp_fmt"), font=("Arial", 10, "bold"), anchor=tk.W).pack(fill=tk.X, padx=12, pady=4)
        format_var = tk.StringVar(value="json")
        fframe = tk.Frame(win)
        fframe.pack(fill=tk.X, padx=28)
        tk.Radiobutton(fframe, text=self._t("exp_fmt_json"),
                       variable=format_var, value="json").pack(anchor=tk.W)
        tk.Radiobutton(fframe, text=self._t("exp_fmt_zip"),
                       variable=format_var, value="zip").pack(anchor=tk.W)
        tk.Label(win, text=self._t("exp_where"), font=("Arial", 10, "bold"), anchor=tk.W).pack(fill=tk.X, padx=12, pady=4)
        where_var = tk.StringVar(value="dumps")
        wframe = tk.Frame(win)
        wframe.pack(fill=tk.X, padx=28)
        tk.Radiobutton(wframe, text=f"В папку dumps/  ({dumps_dir})",
                       variable=where_var, value="dumps").pack(anchor=tk.W)
        tk.Radiobutton(wframe, text="Выбрать папку вручную…",
                       variable=where_var, value="manual").pack(anchor=tk.W)
        path_preview = tk.Label(win, text="", fg="#0a5c2a", anchor=tk.W,
                                font=("Courier New", 9), wraplength=680, justify=tk.LEFT)
        path_preview.pack(fill=tk.X, padx=12, pady=4)
        def update_preview(*args):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            if format_var.get() == "json":
                name = f"{project_name}_dump_{ts}.json"
            else:
                name = f"{project_name}_{ts}.zip"
            if where_var.get() == "dumps":
                full = str(dumps_dir / name)
            else:
                full = f"<выбрать вручную>\\{name}"
            path_preview.config(text=f"📄 {full}")
        format_var.trace_add("write", update_preview)
        where_var.trace_add("write", update_preview)
        update_preview()
        tk.Label(win, text=self._t("exp_not_incl"), font=("Arial", 10, "bold"), anchor=tk.W).pack(fill=tk.X, padx=12, pady=4)
        tk.Label(win, text=self._t("exp_not_incl_text"),
                 font=("Arial", 9), anchor=tk.W, fg="#aa3333", justify=tk.LEFT).pack(fill=tk.X, padx=12, pady=2)
        tk.Label(win, text=self._t("exp_preview"), font=("Arial", 10, "bold"), anchor=tk.W).pack(fill=tk.X, padx=12, pady=4)
        preview_txt = scrolledtext.ScrolledText(win, height=10, font=("Courier New", 9), bg="#fafafa", state=tk.DISABLED)
        preview_txt.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        try:
            from exporter import _collect_files
            files = _collect_files(self.project_path)
            total = len(files)
            info_files.config(text=f"Файлов в экспорт: {total}")
            preview_txt.config(state=tk.NORMAL)
            for p, rel in files[:12]:
                preview_txt.insert(tk.END, rel + "\n")
            if total > 12:
                preview_txt.insert(tk.END, f"... и ещё {total - 12} файлов\n")
            preview_txt.config(state=tk.DISABLED)
        except Exception as e:
            info_files.config(text=f"Ошибка анализа: {e}", fg="red")
        result_frame = tk.Frame(win)
        result_frame.pack(fill=tk.X, padx=12, pady=4)
        def do_export():
            fmt = format_var.get()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            if fmt == "json":
                fname = f"{project_name}_dump_{ts}.json"
            else:
                fname = f"{project_name}_{ts}.zip"
            if where_var.get() == "dumps":
                out = str(dumps_dir / fname)
            else:
                ext = ".json" if fmt == "json" else ".zip"
                out = filedialog.asksaveasfilename(defaultextension=ext, initialfile=fname,
                                                   initialdir=str(dumps_dir),
                                                   filetypes=[("JSON" if fmt == "json" else "ZIP", f"*{ext}")],
                                                   title="Куда сохранить экспорт?")
                if not out:
                    return
            try:
                n = export_json(self.project_path, out) if fmt == "json" else export_zip(self.project_path, out)
                self.log(f"📤 Экспорт: {n} файлов → {out}")
                for w in result_frame.winfo_children():
                    w.destroy()
                size_kb = os.path.getsize(out) / 1024 if os.path.exists(out) else 0
                box = tk.LabelFrame(result_frame, text="✅ Готово", fg="#0a5c2a")
                box.pack(fill=tk.X, pady=4)
                tk.Label(box, text=f"Файлов: {n}   Размер: {size_kb:.1f} KB", font=("Arial", 9), anchor=tk.W).pack(fill=tk.X, padx=6, pady=2)
                tk.Label(box, text=out, font=("Courier New", 9), fg="#005a9e", anchor=tk.W, wraplength=680, justify=tk.LEFT).pack(fill=tk.X, padx=6)
                btns = tk.Frame(box)
                btns.pack(fill=tk.X, padx=6, pady=4)
                tk.Button(btns, text="📂 Открыть папку", command=lambda: self._open_folder(os.path.dirname(out))).pack(side=tk.LEFT, padx=2)
                tk.Button(btns, text="📄 Открыть файл", command=lambda: os.startfile(out) if hasattr(os, "startfile") else None).pack(side=tk.LEFT, padx=2)
                def copy_path():
                    self.root.clipboard_clear()
                    self.root.clipboard_append(out)
                tk.Button(btns, text="📋 Путь в буфер", command=copy_path).pack(side=tk.LEFT, padx=2)
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
                self.log(f"❌ Экспорт: {e}")
        bf = tk.Frame(win)
        bf.pack(fill=tk.X, padx=12, pady=8)
        tk.Button(bf, text=self._t("exp_open_dumps"), command=lambda: self._open_folder(str(dumps_dir))).pack(side=tk.LEFT)
        tk.Button(bf, text="Отмена", command=win.destroy).pack(side=tk.RIGHT, padx=4)
        tk.Button(bf, text=self._t("exp_export"), bg="#4CAF50", fg="white",
                  activebackground="#45a049", activeforeground="white",
                  font=("Arial", 10, "bold"), padx=14, pady=6,
                  command=do_export).pack(side=tk.RIGHT, padx=4)
        win.wait_window()


    def _docs_dialog(self):
        if not self.project_path:
            messagebox.showinfo(self._t("msg_info"), "Open project first / Сначала откройте проект")
            return
        docs_dir = Path(self.project_path) / "docs"
        if not docs_dir.exists():
            messagebox.showinfo("Инфо", f"Папка docs/ не найдена:\n{docs_dir}")
            return
        win = tk.Toplevel(self.root)
        win.title(self._t("docs_title"))
        win.geometry("1200x780")
        win.transient(self.root)

        main = ttk.PanedWindow(win, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left = ttk.Frame(main)
        main.add(left, weight=1)
        ttk.Label(left, text=self._t("docs_files"), font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=3, pady=2)
        lb = tk.Listbox(left, font=("Courier New", 10))
        lb.pack(fill=tk.BOTH, expand=True, padx=3, pady=2)

        right = ttk.Frame(main)
        main.add(right, weight=4)

        state = {"modified": False, "path": None}

        rtb = ttk.Frame(right)
        rtb.pack(fill=tk.X, padx=3, pady=2)
        title_lbl = ttk.Label(rtb, text="", font=("Arial", 10, "bold"))
        title_lbl.pack(side=tk.LEFT)

        view = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=("Courier New", 10),
                                         state=tk.NORMAL, undo=True, bg="#ffffff")
        view.pack(fill=tk.BOTH, expand=True, padx=3, pady=2)
        syntax_highlighter.setup_tags(view)
        self._bind_zoom(view)

        def mark_modified(*args):
            if not state["modified"]:
                state["modified"] = True
                cur = title_lbl.cget("text").rstrip(" *")
                title_lbl.config(text=cur + " *")

        def save_current():
            if not state["path"]:
                return
            try:
                content = view.get("1.0", tk.END).rstrip("\n") + "\n"
                Path(state["path"]).write_text(content, encoding="utf-8")
                state["modified"] = False
                title_lbl.config(text=title_lbl.cget("text").rstrip(" *"))
                self.log(f"Сохранён документ: {Path(state['path']).name}")
                syntax_highlighter.apply_highlight(view, content, "markdown")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{e}", parent=win)

        def apply_hl():
            syntax_highlighter.apply_highlight(view, view.get("1.0", tk.END), "markdown")

        ttk.Button(rtb, text="🎨 Подсветка", command=apply_hl).pack(side=tk.RIGHT, padx=2)
        ttk.Button(rtb, text="↪️ Redo", command=lambda: view.edit_redo()).pack(side=tk.RIGHT, padx=2)
        ttk.Button(rtb, text="↩️ Undo", command=lambda: view.edit_undo()).pack(side=tk.RIGHT, padx=2)
        ttk.Button(rtb, text="💾 Сохранить", command=save_current).pack(side=tk.RIGHT, padx=2)

        view.bind("<KeyRelease>", mark_modified)
        win.bind("<Control-s>", lambda e: save_current())

        files_ref = {"list": []}

        def load_file(path):
            if state["modified"]:
                ans = messagebox.askyesnocancel("Не сохранено",
                    "Текущий файл изменён. Сохранить перед переключением?", parent=win)
                if ans is None:
                    return
                if ans:
                    save_current()
            try:
                text = Path(path).read_text(encoding="utf-8")
            except Exception as e:
                text = f"[Ошибка чтения: {e}]"
            state["path"] = path
            state["modified"] = False
            title_lbl.config(text=f"{Path(path).name} ({len(text)} симв.)")
            view.delete("1.0", tk.END)
            view.insert("1.0", text)
            view.edit_reset()
            syntax_highlighter.apply_highlight(view, text, "markdown")

        def refresh_list(*args):
            lb.delete(0, tk.END)
            files = list(docs_dir.glob("*.md")) + list(docs_dir.glob("*.txt"))
            order = ["INDEX.md", "README.md", "USER_GUIDE.md", "WORKFLOW.md", "JSON_FORMAT.md",
                     "DIFF_DIALOG.md", "SETTINGS.md", "ARCHITECTURE.md", "EXTENDING.md",
                     "TROUBLESHOOTING.md", "PROJECT_CONTEXT.md", "CHANGELOG.md", "GUIDELINES.md"]
            def key(p):
                try:
                    return (order.index(p.name), p.name)
                except ValueError:
                    return (999, p.name)
            files.sort(key=key)
            for p in files:
                lb.insert(tk.END, f"📄 {p.name}")
            if files:
                lb.selection_set(0)
                load_file(files[0])
            files_ref["list"] = files

        def on_select(event=None):
            sel = lb.curselection()
            if not sel:
                return
            files = files_ref["list"]
            if sel[0] < len(files):
                load_file(files[sel[0]])

        lb.bind("<<ListboxSelect>>", on_select)
        refresh_list()

        bf = tk.Frame(win)
        bf.pack(fill=tk.X, padx=5, pady=6)
        ttk.Button(bf, text=self._t("docs_update"), command=refresh_list).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text=self._t("docs_open_dir"), command=lambda: self._open_folder(str(docs_dir))).pack(side=tk.LEFT, padx=2)

        def open_external():
            import subprocess
            p = state.get("path")
            if not p:
                return
            try:
                if sys.platform == "win32":
                    os.startfile(p)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", p])
                else:
                    subprocess.Popen(["xdg-open", p])
            except Exception as e:
                self.log(f"Не удалось открыть файл: {e}")

        ttk.Button(bf, text=self._t("docs_open_ext"), command=open_external).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text=self._t("msg_close"), command=win.destroy).pack(side=tk.RIGHT, padx=2)

        def on_close():
            if state["modified"]:
                ans = messagebox.askyesnocancel("Не сохранено",
                    "Закрыть без сохранения изменений?", parent=win)
                if ans is None:
                    return
                if ans:
                    save_current()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)
        win.wait_window()

    def _show_about(self):
        win = tk.Toplevel(self.root)
        win.title(self._t("about_title"))
        win.geometry("620x480")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)
        
        tk.Label(win, text="Codegen Studio", font=("Segoe UI", 22, "bold"), fg="#004080").pack(pady=(25, 5))
        tk.Label(win, text=self._t("about_version"), font=("Segoe UI", 12), fg="#666").pack(pady=(0, 15))
        
        desc = self._t("about_desc")
        tk.Label(win, text=desc, justify=tk.LEFT, font=("Segoe UI", 10), wraplength=550, fg="#333").pack(padx=20, pady=10, anchor=tk.W)
        
        tk.Label(win, text="Technologies: Python 3.10+, Tkinter, Pygments, Dulwich", font=("Segoe UI", 9, "italic"), fg="#555").pack(pady=5)
        
        bf = tk.Frame(win)
        bf.pack(fill=tk.X, pady=15, padx=20)
        
        info_text = "Codegen Studio v1.1\nOffline tool for applying JSON instructions.\nNo built-in AI, with diff support and Git."
        
        def copy_info():
            self.root.clipboard_clear()
            self.root.clipboard_append(info_text)
            messagebox.showinfo("Info", "Info copied / Информация скопирована", parent=win)
            
        tk.Button(bf, text="📋 Copy info / Копировать", command=copy_info, font=("Segoe UI", 9), padx=10, pady=4).pack(side=tk.LEFT)
        tk.Button(bf, text="Close / Закрыть", command=win.destroy, font=("Segoe UI", 9), padx=15, pady=4).pack(side=tk.RIGHT)
        
        win.wait_window()


    def _error(self, title, message, parent=None):
        try:
            get_logger("errors").error("%s: %s", title, message)
        except Exception:
            pass
        win = tk.Toplevel(parent or self.root)
        win.title(f"{self._t('msg_error')}: {title}")
        win.geometry("700x400")
        win.transient(self.root)
        win.grab_set()
        tk.Label(win, text="Copy the text below and send to developer / Скопируйте текст:", font=("Segoe UI", 10), anchor=tk.W).pack(fill=tk.X, padx=10, pady=(10, 2))
        txt = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Consolas", 10), bg="#fdfdfd")
        txt.insert("1.0", message)
        txt.config(state=tk.DISABLED)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        def copy_and_close():
            self.root.clipboard_clear()
            self.root.clipboard_append(message)
            win.destroy()
        tk.Button(win, text=self._t("err_copy_close"), command=copy_and_close, bg="#4CAF50", fg="white", font=("Segoe UI", 10, "bold"), pady=6).pack(fill=tk.X, padx=10, pady=10)
        win.wait_window()

    def _show_diff_dialog(self, sim):
        """Окно сравнения: поиск, список изменений, подсветка diff."""
        import difflib

        win = tk.Toplevel(self.root)
        win.title(self._t("diff_title"))
        win.geometry("1300x760")
        win.transient(self.root)
        win.grab_set()

        # --- Подготовка данных ---
        entries = []
        for fp, (old_c, new_c) in sim.changes.items():
            old_lines = old_c.splitlines()
            new_lines = new_c.splitlines()
            matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
            changes = [op for op in matcher.get_opcodes() if op[0] != "equal"]
            entries.append({
                "kind": "change", "name": fp,
                "old": old_c, "new": new_c,
                "old_lines": old_lines, "new_lines": new_lines,
                "changes": changes,
            })
        for c in sim.creations:
            name = c.get("file") or c.get("path")
            is_dir = c.get("is_dir")
            entries.append({
                "kind": "create_dir" if is_dir else "create",
                "name": name,
                "content": c.get("content", ""),
                "changes": [],
            })

        # --- Верхняя панель поиска ---
        top = tk.Frame(win, bg="#f5f5f5", relief=tk.RAISED, bd=1)
        top.pack(fill=tk.X)
        tk.Label(top, text=self._t("diff_search"), bg="#f5f5f5").pack(side=tk.LEFT, padx=(10, 4), pady=6)
        search_var = tk.StringVar()
        search_entry = tk.Entry(top, textvariable=search_var, width=32)
        search_entry.pack(side=tk.LEFT, padx=2, pady=6)
        nav_label = tk.Label(top, text="0/0", bg="#f5f5f5", fg="#666", width=8)
        nav_label.pack(side=tk.LEFT, padx=4)

        # --- Основная область ---
        main = ttk.PanedWindow(win, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Левая: Treeview файлов и изменений
        left = ttk.Frame(main)
        main.add(left, weight=1)
        ttk.Label(left, text=self._t("diff_files"),
                  font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=3, pady=2)
        lb_frame = ttk.Frame(left)
        lb_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=2)
        files_tree = ttk.Treeview(lb_frame, show="tree", selectmode="browse")
        files_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_l = ttk.Scrollbar(lb_frame, orient="vertical", command=files_tree.yview)
        sb_l.pack(side=tk.RIGHT, fill=tk.Y)
        files_tree.configure(yscrollcommand=sb_l.set)

        item_to_entry = {}
        first_file_item = None
        for i, ent in enumerate(entries):
            if ent["kind"] == "change":
                ops_count = len(ent["changes"])
                label = f"✏ {ent['name']}  ({ops_count} изм.)"
                file_item = files_tree.insert(
                    "", "end", text=label, values=("file", str(i)), open=(i == 0))
                item_to_entry[file_item] = (i, None)
                if first_file_item is None:
                    first_file_item = file_item
                for j, op in enumerate(ent["changes"]):
                    tag, i1, i2, j1, j2 = op
                    if tag == "replace":
                        op_label = f"стр. {j1+1}: изменить ({i2-i1}→{j2-j1} стр.)"
                        icon = "✏"
                    elif tag == "insert":
                        op_label = f"стр. {j1+1}: добавить {j2-j1} стр."
                        icon = "➕"
                    else:
                        op_label = f"стр. {i1+1}: удалить {i2-i1} стр."
                        icon = "➖"
                    ch_item = files_tree.insert(
                        file_item, "end",
                        text=f"  {icon} {op_label}",
                        values=("change", str(i), str(j)))
                    item_to_entry[ch_item] = (i, j)
            elif ent["kind"] == "create":
                it = files_tree.insert(
                    "", "end", text=f"🆕 {ent['name']}",
                    values=("create", str(i)))
                item_to_entry[it] = (i, None)
            elif ent["kind"] == "create_dir":
                it = files_tree.insert(
                    "", "end", text=f"📁 {ent['name']}/",
                    values=("dir", str(i)))
                item_to_entry[it] = (i, None)

        # Правая часть: старый / новый
        right = ttk.Frame(main)
        main.add(right, weight=3)
        diff_pane = ttk.PanedWindow(right, orient=tk.HORIZONTAL)
        diff_pane.pack(fill=tk.BOTH, expand=True)

        lo = ttk.Frame(diff_pane)
        diff_pane.add(lo, weight=1)
        ttk.Label(lo, text=self._t("diff_old")).pack(anchor=tk.W)
        old_t = tk.Text(lo, wrap=tk.NONE, font=("Courier New", 10),
                        state=tk.DISABLED, bg="#fafafa")
        old_t.pack(fill=tk.BOTH, expand=True)
        syntax_highlighter.setup_tags(old_t)
        old_t.tag_configure("diff_del", background="#ffcccc")
        old_t.tag_configure("diff_mod", background="#ffe0b2")

        no = ttk.Frame(diff_pane)
        diff_pane.add(no, weight=1)
        ttk.Label(no, text=self._t("diff_new")).pack(anchor=tk.W)
        new_t = tk.Text(no, wrap=tk.NONE, font=("Courier New", 10),
                        state=tk.DISABLED, bg="#fafafa")
        new_t.pack(fill=tk.BOTH, expand=True)
        syntax_highlighter.setup_tags(new_t)
        new_t.tag_configure("diff_add", background="#ccffcc")
        new_t.tag_configure("diff_mod", background="#ffe0b2")

        old_t.tag_configure("find_hit", background="#FFA500", foreground="black")
        new_t.tag_configure("find_hit", background="#FFA500", foreground="black")

        # Синхронный скролл
        def _on_wheel(event):
            delta = 0
            if getattr(event, "num", None) == 4:
                delta = -1
            elif getattr(event, "num", None) == 5:
                delta = 1
            elif getattr(event, "delta", 0):
                delta = -1 * (event.delta // 120)
            if delta:
                old_t.yview_scroll(delta, "units")
                new_t.yview_scroll(delta, "units")
                return "break"
        for w in (old_t, new_t):
            w.bind("<MouseWheel>", _on_wheel)
            w.bind("<Button-4>", _on_wheel)
            w.bind("<Button-5>", _on_wheel)

        # --- Подсветка всех изменений в файле ---
        def _highlight_changes(ent):
            old_t.tag_remove("diff_del", "1.0", tk.END)
            old_t.tag_remove("diff_mod", "1.0", tk.END)
            new_t.tag_remove("diff_add", "1.0", tk.END)
            new_t.tag_remove("diff_mod", "1.0", tk.END)
            for tag, i1, i2, j1, j2 in ent["changes"]:
                if tag == "replace":
                    for ln in range(i1, i2):
                        old_t.tag_add("diff_mod", f"{ln+1}.0", f"{ln+1}.end")
                    for ln in range(j1, j2):
                        new_t.tag_add("diff_mod", f"{ln+1}.0", f"{ln+1}.end")
                elif tag == "delete":
                    for ln in range(i1, i2):
                        old_t.tag_add("diff_del", f"{ln+1}.0", f"{ln+1}.end")
                elif tag == "insert":
                    for ln in range(j1, j2):
                        new_t.tag_add("diff_add", f"{ln+1}.0", f"{ln+1}.end")

        # --- Выбор в дереве ---
        current = {"entry": None}

        def on_select(evt=None):
            sel = files_tree.selection()
            if not sel:
                return
            item = sel[0]
            if item not in item_to_entry:
                return
            i, j = item_to_entry[item]
            ent = entries[i]
            current["entry"] = ent

            # Всегда показываем обе панели
            if lo not in diff_pane.panes():
                diff_pane.insert(0, lo, weight=1)

            old_t.config(state=tk.NORMAL)
            new_t.config(state=tk.NORMAL)
            old_t.delete("1.0", tk.END)
            new_t.delete("1.0", tk.END)

            if ent["kind"] == "change":
                old_t.insert("1.0", ent["old"])
                new_t.insert("1.0", ent["new"])
                syntax_highlighter.apply_highlight(old_t, ent["old"], "python")
                syntax_highlighter.apply_highlight(new_t, ent["new"], "python")
                _highlight_changes(ent)
                if j is not None:
                    tag, i1, i2, j1, j2 = ent["changes"][j]
                    try:
                        old_t.see(f"{i1+1}.0")
                        new_t.see(f"{j1+1}.0")
                    except Exception:
                        pass
            elif ent["kind"] == "create":
                old_t.insert("1.0", "[Новый файл]\n\nСтарого кода нет.")
                new_t.insert("1.0", ent["content"])
                syntax_highlighter.apply_highlight(new_t, ent["content"], "python")
            else:
                old_t.insert("1.0", "[Новая папка]")
                new_t.insert("1.0", f"Папка будет создана: {ent['name']}/")

            old_t.config(state=tk.DISABLED)
            new_t.config(state=tk.DISABLED)

        files_tree.bind("<<TreeviewSelect>>", on_select)

        # --- Поиск ---
        def _collect_hits(q):
            hits = []
            if not q:
                return hits
            ql = q.lower()
            for i, ent in enumerate(entries):
                if ent["kind"] == "change":
                    for ln, text in enumerate(ent["new_lines"], 1):
                        if ql in text.lower():
                            hits.append((i, ln))
                elif ent["kind"] == "create":
                    for ln, text in enumerate(ent["content"].splitlines(), 1):
                        if ql in text.lower():
                            hits.append((i, ln))
            return hits

        def _jump_to_hit(idx, hits):
            if not hits:
                return
            i, ln = hits[idx]
            # Найти item файла (первый child или сам файл)
            target_item = None
            for item, (ei, ej) in item_to_entry.items():
                if ei == i and ej is None:
                    target_item = item
                    break
            if target_item:
                files_tree.selection_set(target_item)
                files_tree.see(target_item)
                on_select()
            # Прокрутить new_t
            try:
                new_t.see(f"{ln}.0")
                new_t.tag_remove("find_hit", "1.0", tk.END)
                line_text = new_t.get(f"{ln}.0", f"{ln}.end")
                new_t.tag_add("find_hit", f"{ln}.0", f"{ln}.{len(line_text)}")
            except Exception:
                pass
            nav_label.config(text=f"{idx+1}/{len(hits)}", fg="#333")

        search_state = {"hits": [], "idx": -1}

        def do_find(forward=True):
            q = search_var.get().strip()
            if not q:
                nav_label.config(text="0/0")
                return
            hits = _collect_hits(q)
            if not hits:
                nav_label.config(text="0/0", fg="red")
                search_state["hits"] = []
                search_state["idx"] = -1
                return
            # Найти текущую позицию
            sel = files_tree.selection()
            cur_i = -1
            if sel:
                ci = item_to_entry.get(sel[0], (-1, None))[0]
                cur_i = ci
            if forward:
                nxt = 0
                for k, (i, _ln) in enumerate(hits):
                    if i > cur_i:
                        nxt = k
                        break
                else:
                    nxt = (search_state.get("idx", -1) + 1) % len(hits)
            else:
                nxt = (search_state.get("idx", 0) - 1) % len(hits)
            search_state["hits"] = hits
            search_state["idx"] = nxt
            _jump_to_hit(nxt, hits)

        search_entry.bind("<Return>", lambda e: do_find(True))
        search_entry.bind("<Shift-Return>", lambda e: do_find(False))
        tk.Button(top, text="◀", width=2, command=lambda: do_find(False)).pack(side=tk.LEFT, padx=1, pady=6)
        tk.Button(top, text="▶", width=2, command=lambda: do_find(True)).pack(side=tk.LEFT, padx=1, pady=6)
        tk.Button(top, text="✕", width=2, command=lambda: (
            search_var.set(""),
            nav_label.config(text="0/0"),
            new_t.tag_remove("find_hit", "1.0", tk.END),
            old_t.tag_remove("find_hit", "1.0", tk.END),
            search_entry.focus_set()
        )).pack(side=tk.LEFT, padx=1, pady=6)

        # --- Выбрать первый файл ---
        if first_file_item:
            files_tree.selection_set(first_file_item)
            on_select()

        # --- Кнопки внизу ---
        btns = ttk.Frame(win)
        btns.pack(fill=tk.X, padx=5, pady=8)
        result = {"ok": False}
        def do_apply():
            result["ok"] = True
            win.destroy()
        ttk.Button(btns, text=self._t("msg_cancel"), command=win.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btns, text=self._t("diff_apply"), command=do_apply).pack(side=tk.RIGHT, padx=4)
        total_ops = sum(len(e["changes"]) for e in entries if e["kind"] == "change")
        total_files = len([e for e in entries if e["kind"] == "change"])
        total_new = len([e for e in entries if e["kind"] in ("create", "create_dir")])
        ttk.Label(btns,
                  text=f"Файлов: {total_files}  |  Изменений: {total_ops}  |  Созданий: {total_new}",
                  foreground="#666").pack(side=tk.LEFT, padx=10)

        search_entry.focus_set()
        self.root.wait_window(win)
        return result["ok"]

