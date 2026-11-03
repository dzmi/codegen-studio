#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codegen Studio — мини-приложение без ИИ."""
import os
import sys
import traceback

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".codegen_studio")
LAST = os.path.join(CONFIG_DIR, "last_project.txt")


def get_last_project():
    if os.path.exists(LAST):
        try:
            with open(LAST, "r", encoding="utf-8") as f:
                p = f.read().strip()
            if p and os.path.isdir(p):
                return p
        except Exception:
            pass
    return None


def save_last_project(path):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(LAST, "w", encoding="utf-8") as f:
            f.write(path)
    except Exception:
        pass


def main():
    import tkinter as tk
    try:
        from ui_main import StudioWindow

        class PatchedStudio(StudioWindow):
            def open_project(self, path):
                super().open_project(path)
                save_last_project(path)

        root = tk.Tk()
        from logger import setup
        import os
        setup(os.path.dirname(os.path.abspath(__file__)))
        StudioWindow_Patched = PatchedStudio
        app = StudioWindow_Patched(root, project_path=get_last_project())
        root.mainloop()
    except Exception:
        import traceback
        err_text = traceback.format_exc()
        traceback.print_exc()
        try:
            import tkinter as tk2
            from tkinter import scrolledtext as sc2
            w = tk2.Tk()
            w.title("Ошибка запуска Codegen Studio")
            w.geometry("800x500")
            tk2.Label(w, text="Приложение упало. Скопируйте трейсбек:", font=("Segoe UI", 10)).pack(pady=5)
            txt = sc2.ScrolledText(w, wrap=tk2.WORD, font=("Consolas", 10))
            txt.insert("1.0", err_text)
            txt.pack(fill=tk2.BOTH, expand=True, padx=10, pady=5)
            def cp():
                w.clipboard_clear()
                w.clipboard_append(err_text)
                w.destroy()
            tk2.Button(w, text="📋 КОПИРОВАТЬ И ЗАКРЫТЬ", command=cp, bg="#e74c3c", fg="white", font=("Segoe UI", 10, "bold"), pady=5).pack(pady=10)
            w.mainloop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
