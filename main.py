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
        StudioWindow_Patched = PatchedStudio
        app = StudioWindow_Patched(root, project_path=get_last_project())
        root.mainloop()
    except Exception:
        traceback.print_exc()
        try:
            from tkinter import messagebox
            messagebox.showerror("Codegen Studio", traceback.format_exc())
        except Exception:
            pass


if __name__ == "__main__":
    main()
