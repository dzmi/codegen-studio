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
        self._toolbar_mode = False
        self._full_geometry = None
        self._drag_x = 0
        self._drag_y = 0
        root.title("Codegen Studio")
        root.geometry(_s.get("window_geometry", "1100x700+200+100"))
        self._build_menu()
        self._build_toolbar()
        self._build_main()
        self._build_statusbar()
        if project_path:
            self.open_project(project_path)
        if _s.get("mode", "window") == "toolbar":
            self.root.after(120, self.enter_toolbar_mode)


    def _build_menu(self):
        m = tk.Menu(self.root)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label="Открыть проект…", command=self.open_project_dialog)
        f.add_command(label="Обновить дерево", command=self.refresh_tree)
        f.add_separator()
        f.add_command(label="Выход", command=self.root.quit)
        m.add_cascade(label="Файл", menu=f)
        e = tk.Menu(m, tearoff=0)
        e.add_command(label="Быстрый дамп JSON", command=self.quick_dump_json)
        e.add_command(label="Экспорт JSON…", command=self.export_json_dialog)
        e.add_command(label="Экспорт ZIP…", command=self.export_zip_dialog)
        e.add_separator()
        e.add_command(label="Копировать структуру", command=self.copy_structure)
        e.add_command(label="Промпт для ИИ…", command=self._prompts_dialog)
        m.add_cascade(label="Экспорт", menu=e)
        g = tk.Menu(m, tearoff=0)
        g.add_command(label="Статус", command=self.git_status)
        g.add_command(label="Коммит…", command=self.git_commit_dialog)
        g.add_command(label="История", command=self.git_log)
        g.add_command(label="Init", command=self.git_init)
        m.add_cascade(label="Git", menu=g)
        self.root.config(menu=m)

    def _build_toolbar(self):
        self.toolbar_bar = tk.Frame(self.root, relief=tk.RAISED, bd=1, bg="#f0f0f0")
        self.toolbar_bar.pack(side=tk.TOP, fill=tk.X)
        h = tk.Label(self.toolbar_bar, text="\u28ff", cursor="fleur", bg="#dcdcdc",
                     padx=8, pady=4, font=("Arial", 12, "bold"))
        h.pack(side=tk.LEFT)
        self._toolbar_handle = h
        self.project_label = tk.Label(self.toolbar_bar, text="— проект не открыт —",
                                      bg="#f0f0f0", fg="#333",
                                      font=("Arial", 9, "bold"), padx=6)
        self.project_label.pack(side=tk.LEFT)
        self._proj_sep = tk.Frame(self.toolbar_bar, bg="#c0c0c0", width=1)
        self._proj_sep.pack(side=tk.LEFT, fill=tk.Y, padx=4)

        def _tip(widget, text):
            tip = {"win": None}
            def enter(e):
                try:
                    tip["win"] = tk.Toplevel(widget)
                    tip["win"].wm_overrideredirect(True)
                    tip["win"].wm_geometry(f"+{e.x_root+8}+{e.y_root+22}")
                    tk.Label(tip["win"], text=text, bg="#ffffcc", relief=tk.SOLID,
                             bd=1, padx=6, pady=2, font=("Arial", 9)).pack()
                except Exception:
                    pass
            def leave(e):
                try:
                    if tip["win"]:
                        tip["win"].destroy()
                        tip["win"] = None
                except Exception:
                    pass
            widget.bind("<Enter>", enter, add="+")
            widget.bind("<Leave>", leave, add="+")

        def btn(txt, cmd, tip=""):
            b = tk.Button(self.toolbar_bar, text=txt, command=cmd, bd=0, relief=tk.FLAT,
                          bg="#f0f0f0", activebackground="#d0d0d0", padx=8, pady=4,
                          font=("Arial", 9), cursor="hand2")
            b.pack(side=tk.LEFT, padx=1)
            if tip:
                _tip(b, tip)
            return b

        btn("\U0001F4C1 Проект", self.open_project_dialog, "Открыть папку проекта")
        btn("\U0001F4E5 JSON", self._json_dialog, "Вставить JSON-инструкции и применить (шаг 1)")
        btn("\U0001F4AC Промпт", self._prompts_dialog, "Скопировать промпт для внешней LLM с контекстом проекта")
        btn("\u2705 Применить", self.apply_from_clipboard, "Применить JSON из буфера обмена")
        btn("\u26a1 Дамп", self.quick_dump_json, "Быстрый JSON-дамп в папку dumps/")
        btn("\U0001F4BE Git", self.git_commit_dialog, "Git commit")
        btn("\u2699", self.open_settings_dialog, "Настройки")

        # Spacer — тянется, служит для перетаскивания окна
        self._spacer = tk.Frame(self.toolbar_bar, bg="#f0f0f0", cursor="fleur")
        self._spacer.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.backend_label = tk.Label(self.toolbar_bar, text="", fg="gray",
                                      bg="#f0f0f0", font=("Arial", 8), padx=4)
        self.backend_label.pack(side=tk.RIGHT, padx=4)

        self.mode_btn = tk.Button(self.toolbar_bar, text="\u25a3", command=self._toggle_mode,
                                  bd=0, relief=tk.FLAT, bg="#f0f0f0", activebackground="#d0d0d0",
                                  padx=8, pady=4, font=("Arial", 11), cursor="hand2")
        self.mode_btn.pack(side=tk.RIGHT, padx=1)
        _tip(self.mode_btn, "Свернуть в полоску / развернуть в окно")

        close_btn = tk.Button(self.toolbar_bar, text="\u2715", command=self.root.destroy,
                              bd=0, relief=tk.FLAT, bg="#f0f0f0", activebackground="#d0d0d0",
                              padx=8, pady=4, font=("Arial", 10), cursor="hand2")
        close_btn.pack(side=tk.RIGHT, padx=1)
        _tip(close_btn, "Закрыть")

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
        self.nb.add(ff, text="📄 Файл")
        self.editor = scrolledtext.ScrolledText(ff, wrap=tk.NONE, font=("Courier New", 10))
        self.editor.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        syntax_highlighter.setup_tags(self.editor)
        self.editor.config(state=tk.DISABLED)
        jf = ttk.Frame(self.nb)
        self.nb.add(jf, text="📥 JSON")
        self.json_text = scrolledtext.ScrolledText(jf, wrap=tk.WORD, font=("Courier New", 9))
        self.json_text.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        jb = ttk.Frame(jf)
        jb.pack(fill=tk.X, pady=2, padx=3)
        ttk.Button(jb, text="📋 Вставить", command=self._paste_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(jb, text="🔍 Проверить", command=self.validate_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(jb, text="✅ Применить", command=self.apply_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(jb, text="🗑 Очистить", command=lambda: self.json_text.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=2)
        prf = ttk.Frame(self.nb)
        self.nb.add(prf, text="💬 Промпт")
        pt = ttk.Frame(prf)
        pt.pack(fill=tk.X, padx=3, pady=3)
        ttk.Label(pt, text="Промпт:").pack(side=tk.LEFT)
        self.prompt_combo = ttk.Combobox(pt, values=list_prompts(), state="readonly", width=25)
        self.prompt_combo.pack(side=tk.LEFT, padx=5)
        self.prompt_combo.current(0)
        self.prompt_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_prompt_text())
        ttk.Button(pt, text="📋 Копировать", command=self._copy_prompt).pack(side=tk.LEFT, padx=2)
        ttk.Button(pt, text="📎+Дерево", command=self._copy_prompt_with_structure).pack(side=tk.LEFT, padx=2)
        ttk.Button(pt, text="📎+Файл", command=self._copy_prompt_with_file).pack(side=tk.LEFT, padx=2)
        self.prompt_text = scrolledtext.ScrolledText(prf, wrap=tk.WORD, font=("Courier New", 9), height=10)
        self.prompt_text.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        self._refresh_prompt_text()
        gf = ttk.Frame(self.nb)
        self.nb.add(gf, text="🔧 Git")
        gb = ttk.Frame(gf)
        gb.pack(fill=tk.X, pady=3, padx=3)
        ttk.Button(gb, text="Статус", command=self.git_status).pack(side=tk.LEFT, padx=2)
        ttk.Button(gb, text="Коммит", command=self.git_commit_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(gb, text="История", command=self.git_log).pack(side=tk.LEFT, padx=2)
        ttk.Button(gb, text="Init", command=self.git_init).pack(side=tk.LEFT, padx=2)
        self.git_text = scrolledtext.ScrolledText(gf, wrap=tk.WORD, font=("Courier New", 9))
        self.git_text.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        lf = ttk.Frame(self.nb)
        self.nb.add(lf, text="📝 Лог")
        self.log_text = scrolledtext.ScrolledText(lf, wrap=tk.WORD, font=("Arial", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        self.nb.select(0)

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
        text = get_prompt(self.prompt_combo.get())
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
            messagebox.showinfo("Инфо", "Сначала откройте проект")
            return
        out = default_dump_path(self.project_path, "json")
        try:
            n = export_json(self.project_path, out)
            self.log(f"⚡ Дамп: {n} файлов → dumps/{Path(out).name}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
            self.log(f"❌ Дамп: {e}")

    def _update_project_label(self):
        try:
            if self.project_path:
                name = Path(self.project_path).name or self.project_path
                self.project_label.config(text=f"\U0001F4C2 {name}", fg="#0a5c2a")
                self.root.title(f"Codegen Studio — {name}")
            else:
                self.project_label.config(text="— проект не открыт —", fg="#666")
        except Exception:
            pass


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
        self.current_file = file_path
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                self.current_content = f.read()
        except Exception as e:
            self.current_content = f"[Ошибка чтения: {e}]"
        self.editor.config(state=tk.NORMAL)
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", self.current_content)
        lang = "python" if file_path.endswith(".py") else "text"
        syntax_highlighter.apply_highlight(self.editor, self.current_content, lang)
        self.editor.config(state=tk.DISABLED)
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
            messagebox.showerror("Ошибка JSON", str(e))
            return None, None
        try:
            actions = normalize_actions(data)
        except Exception as e:
            get_logger("errors").error("normalize_actions failed: %s", e)
            self.log(f"❌ normalize: {e}")
            messagebox.showerror("Ошибка", f"Не удалось разобрать: {e}")
            return None, None
        return data, actions

    def validate_json(self):
        if not self.project_path:
            messagebox.showinfo("Инфо", "Сначала откройте проект")
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
            messagebox.showinfo("Инфо", "Сначала откройте проект")
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
            messagebox.showerror("Ошибки валидации", "\n".join(errors))
            return
        sim = simulate(actions, self.project_path)
        if sim.errors:
            for e in sim.errors:
                logger.error("simulation: %s", e)
            self.log(f"❌ Симуляция: {len(sim.errors)} ошибок (см. errors.log)")
            messagebox.showerror("Ошибки симуляции", "\n".join(sim.errors))
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
            messagebox.showerror("Ошибка", "\n".join(errs))

    def export_json_dialog(self):

        if not self.project_path:
            messagebox.showinfo("Инфо", "Сначала откройте проект")
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
            messagebox.showinfo("Инфо", "Сначала откройте проект")
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
        self.root.clipboard_append(get_prompt(self.prompt_combo.get()))
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
        text = get_prompt(self.prompt_combo.get()) + "\n\n### Структура проекта:\n" + "\n".join(lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.log("📋 Промпт + структура скопированы")

    def _copy_prompt_with_file(self):
        if not self.current_file:
            messagebox.showinfo("Инфо", "Откройте файл в дереве")
            return
        rel = str(Path(self.current_file).relative_to(self.project_path)).replace("\\", "/")
        text = get_prompt(self.prompt_combo.get()) + f"\n\n### Файл: {rel}\n```python\n{self.current_content}\n```"
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
        if messagebox.askyesno("Git", "Инициализировать репозиторий?"):
            if self.git.init():
                self.log("✅ Git init")
                messagebox.showinfo("Git", "Репозиторий инициализирован")
            else:
                messagebox.showerror("Git", "Не удалось")

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
        # КРИТИЧНО: явная ширина и высота, иначе окно схлопывается до квадрата
        self.root.geometry(f"850x46+{int(x)}+{int(y)}")
        self.root.update_idletasks()
        self._make_draggable()
        self._toolbar_mode = True
        self.mode_btn.config(text="\u25a3")
        self._s.set("mode", "toolbar")
        self._s.save()
        self.log("Режим: toolbar (850x46)")

    def exit_toolbar_mode(self):
        if not self._toolbar_mode:
            return
        self.root.overrideredirect(False)
        self.root.attributes("-topmost", False)
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        geom = self._s.get("window_geometry", "1100x700+200+100")
        self.root.geometry(geom)
        self.root.minsize(600, 400)
        self._toolbar_mode = False
        self.mode_btn.config(text="\u25a3")
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
        win.title("JSON — вставить и применить")
        win.geometry("900x600")
        win.transient(self.root)
        win.lift()
        win.focus_force()

        header = tk.Frame(win, bg="#e8f4ff")
        header.pack(fill=tk.X)
        tk.Label(header, text="Как использовать", font=("Arial", 11, "bold"),
                 bg="#e8f4ff", anchor=tk.W).pack(fill=tk.X, padx=12, pady=(8, 2))
        tk.Label(header, text="1\ufe0f\u20e3 Вставь JSON-инструкцию (уже вставлена из буфера, если есть)",
                 bg="#e8f4ff", anchor=tk.W, fg="#333").pack(fill=tk.X, padx=12)
        tk.Label(header, text="2\ufe0f\u20e3 Нажми «\u2705 Применить» — откроется окно сравнения",
                 bg="#e8f4ff", anchor=tk.W, fg="#333").pack(fill=tk.X, padx=12)
        tk.Label(header, text="3\ufe0f\u20e3 Проверь diff и подтверди изменения",
                 bg="#e8f4ff", anchor=tk.W, fg="#333").pack(fill=tk.X, padx=12, pady=(0, 8))

        clip_status = tk.Label(win, text="", fg="green", font=("Arial", 9), anchor=tk.W)
        clip_status.pack(fill=tk.X, padx=12, pady=(4, 0))

        frame = tk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)
        tk.Label(frame, text="JSON-инструкция:", anchor=tk.W,
                 font=("Arial", 9, "bold")).pack(fill=tk.X)
        txt = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=("Courier New", 10), undo=True)
        txt.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

        try:
            clip = self.root.clipboard_get().strip()
            if clip:
                txt.insert("1.0", clip)
                clip_status.config(text="\u2713 JSON загружен из буфера обмена")
        except Exception:
            pass

        bf = tk.Frame(win)
        bf.pack(fill=tk.X, padx=12, pady=(0, 10))

        def do_paste():
            try:
                txt.delete("1.0", tk.END)
                txt.insert("1.0", self.root.clipboard_get())
                clip_status.config(text="\u2713 Обновлено из буфера", fg="green")
            except Exception:
                clip_status.config(text="\u26a0 Буфер обмена пуст или недоступен", fg="orange")

        def do_apply():
            content = txt.get("1.0", tk.END).strip()
            if not content:
                clip_status.config(text="\u26a0 Сначала вставь JSON", fg="red")
                return
            win.destroy()
            self.json_text.delete("1.0", tk.END)
            self.json_text.insert("1.0", content)
            self.apply_json()

        tk.Button(bf, text="\U0001F4CB Из буфера", command=do_paste,
                  font=("Arial", 10), padx=10, pady=6).pack(side=tk.LEFT)
        tk.Button(bf, text="\u274c Отмена", command=win.destroy,
                  font=("Arial", 10), padx=10, pady=6).pack(side=tk.RIGHT, padx=4)
        tk.Button(bf, text="\u2705 ПРИМЕНИТЬ", command=do_apply,
                  font=("Arial", 10, "bold"), padx=14, pady=6,
                  bg="#4CAF50", fg="white", activebackground="#45a049",
                  activeforeground="white").pack(side=tk.RIGHT, padx=4)

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
        win.title("Настройки Codegen Studio")
        win.geometry("440x320")
        win.transient(self.root)
        mode_var = tk.StringVar(value=self._s.get("mode", "window"))
        top_var = tk.BooleanVar(value=self._s.get("always_on_top", True))
        tk.Label(win, text="Режим окна:", anchor=tk.W, font=("Arial", 10, "bold")).pack(fill=tk.X, padx=10, pady=(10, 2))
        tk.Radiobutton(win, text="\U0001F5D4  Обычное окно", variable=mode_var, value="window").pack(anchor=tk.W, padx=25)
        tk.Radiobutton(win, text="\U0001F4CC  Компактный toolbar (перетаскиваемый)", variable=mode_var, value="toolbar").pack(anchor=tk.W, padx=25)
        tk.Checkbutton(win, text="Toolbar поверх всех окон", variable=top_var).pack(anchor=tk.W, padx=10, pady=10)
        def do_save():
            self._s.set("mode", mode_var.get())
            self._s.set("always_on_top", top_var.get())
            self._s.save()
            current = "toolbar" if self._toolbar_mode else "window"
            target = mode_var.get()
            if current != target:
                if target == "toolbar":
                    self.enter_toolbar_mode()
                else:
                    self.exit_toolbar_mode()
            elif self._toolbar_mode:
                self.root.attributes("-topmost", bool(top_var.get()))
            win.destroy()
        bf = tk.Frame(win)
        bf.pack(fill=tk.X, pady=10, padx=10)
        tk.Button(bf, text="\u2714 Сохранить", command=do_save).pack(side=tk.RIGHT, padx=2)
        tk.Button(bf, text="Отмена", command=win.destroy).pack(side=tk.RIGHT, padx=2)
        tk.Label(win, text=f"{self._s.settings_file()}", fg="gray", font=("Arial", 8)).pack(side=tk.BOTTOM, pady=6)
        win.wait_window()

    def _prompts_dialog(self):
        """Диалог: выбор промпта + контекст + превью + копирование."""
        win = tk.Toplevel(self.root)
        win.title("Промпты для ИИ")
        win.geometry("900x720")
        win.transient(self.root)
        win.lift()
        win.focus_force()

        tk.Label(win, text="1. Выбери промпт:", anchor=tk.W,
                 font=("Arial", 10, "bold")).pack(fill=tk.X, padx=12, pady=(10, 2))
        prompt_var = tk.StringVar()
        prompts = list_prompts()
        combo = ttk.Combobox(win, textvariable=prompt_var, values=prompts,
                             state="readonly", width=50)
        combo.pack(fill=tk.X, padx=12, pady=2)
        if prompts:
            combo.current(0)

        tk.Label(win, text="2. Что добавить к промпту:", anchor=tk.W,
                 font=("Arial", 10, "bold")).pack(fill=tk.X, padx=12, pady=(10, 2))
        mode_var = tk.StringVar(value="prompt")
        mf = tk.Frame(win)
        mf.pack(fill=tk.X, padx=24)
        tk.Radiobutton(mf, text="Только промпт", variable=mode_var, value="prompt").pack(anchor=tk.W)
        tk.Radiobutton(mf, text="Промпт + дерево проекта", variable=mode_var, value="prompt_tree").pack(anchor=tk.W)
        tk.Radiobutton(mf, text="Промпт + текущий файл", variable=mode_var, value="prompt_file").pack(anchor=tk.W)
        tk.Radiobutton(mf, text="Промпт + дерево + текущий файл", variable=mode_var, value="prompt_both").pack(anchor=tk.W)

        ctx_var = tk.BooleanVar(value=True)
        tk.Checkbutton(win, text="Добавить блок 'Краткая выжимка для ИИ' из docs/PROJECT_CONTEXT.md",
                       variable=ctx_var).pack(anchor=tk.W, padx=24, pady=(6, 0))

        tk.Label(win, text="3. Превью (что попадёт в буфер):", anchor=tk.W,
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
            base = get_prompt(prompt_var.get())
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
            status.config(text=f"Символов: {len(text)}")

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
        tk.Button(bf, text="КОПИРОВАТЬ В БУФЕР", command=do_copy,
                  font=("Arial", 10, "bold"), padx=14, pady=6,
                  bg="#4CAF50", fg="white", activebackground="#45a049",
                  activeforeground="white").pack(side=tk.LEFT)
        tk.Button(bf, text="Закрыть", command=win.destroy,
                  font=("Arial", 10), padx=10, pady=6).pack(side=tk.RIGHT)

        refresh_preview()
        win.wait_window()

    def _show_diff_dialog(self, sim):
        """Окно сравнения: поиск, список изменений, подсветка diff."""
        import difflib

        win = tk.Toplevel(self.root)
        win.title("Сравнение изменений")
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
        tk.Label(top, text="🔍 Поиск:", bg="#f5f5f5").pack(side=tk.LEFT, padx=(10, 4), pady=6)
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
        ttk.Label(left, text="Файлы и изменения:",
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
        ttk.Label(lo, text="Старый код:").pack(anchor=tk.W)
        old_t = tk.Text(lo, wrap=tk.NONE, font=("Courier New", 10),
                        state=tk.DISABLED, bg="#fafafa")
        old_t.pack(fill=tk.BOTH, expand=True)
        syntax_highlighter.setup_tags(old_t)
        old_t.tag_configure("diff_del", background="#ffcccc")
        old_t.tag_configure("diff_mod", background="#ffe0b2")

        no = ttk.Frame(diff_pane)
        diff_pane.add(no, weight=1)
        ttk.Label(no, text="Новый код:").pack(anchor=tk.W)
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
                new_t.insert("1.0", ent["content"])
                syntax_highlighter.apply_highlight(new_t, ent["content"], "python")
            else:
                new_t.insert("1.0", f"[Папка будет создана: {ent['name']}/]")

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
        ttk.Button(btns, text="❌ Отмена", command=win.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btns, text="✅ Применить изменения", command=do_apply).pack(side=tk.RIGHT, padx=4)
        total_ops = sum(len(e["changes"]) for e in entries if e["kind"] == "change")
        total_files = len([e for e in entries if e["kind"] == "change"])
        total_new = len([e for e in entries if e["kind"] in ("create", "create_dir")])
        ttk.Label(btns,
                  text=f"Файлов: {total_files}  |  Изменений: {total_ops}  |  Созданий: {total_new}",
                  foreground="#666").pack(side=tk.LEFT, padx=10)

        search_entry.focus_set()
        self.root.wait_window(win)
        return result["ok"]

