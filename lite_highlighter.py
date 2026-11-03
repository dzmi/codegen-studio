# -*- coding: utf-8 -*-
"""Подсветка синтаксиса через Pygments (fallback — без подсветки)."""
import tkinter as tk

try:
    from pygments import lex
    from pygments.lexers import get_lexer_by_name
    from pygments.token import Token
    HAS_PYGMENTS = True
except ImportError:
    HAS_PYGMENTS = False


TAGS_MAP = {
    "Keyword":  {"foreground": "#0000cc", "font": ("Courier New", 10, "bold")},
    "String":   {"foreground": "#007700"},
    "Comment":  {"foreground": "#888888", "font": ("Courier New", 10, "italic")},
    "Number":   {"foreground": "#8800aa"},
    "Function": {"foreground": "#cc5500", "font": ("Courier New", 10, "bold")},
    "Class":    {"foreground": "#994400", "font": ("Courier New", 10, "bold")},
    "Operator": {"foreground": "#333333"},
}


def setup_tags(widget):
    for name, cfg in TAGS_MAP.items():
        try:
            widget.tag_configure(name, **cfg)
        except Exception:
            pass


def _token_to_tag(tok):
    if tok in Token.Keyword or tok in Token.Keyword.Constant: return "Keyword"
    if tok in Token.String: return "String"
    if tok in Token.Comment: return "Comment"
    if tok in Token.Number: return "Number"
    if tok in Token.Name.Function: return "Function"
    if tok in Token.Name.Class: return "Class"
    if tok in Token.Operator: return "Operator"
    return None


def apply_highlight(widget, code, language="python"):
    if not HAS_PYGMENTS or not code:
        return
    for tag in TAGS_MAP:
        try:
            widget.tag_remove(tag, "1.0", tk.END)
        except Exception:
            pass
    try:
        lexer = get_lexer_by_name(language)
        tokens = list(lex(code, lexer))
    except Exception:
        return
    line, col = 1, 0
    for tok_type, tok_text in tokens:
        start = f"{line}.{col}"
        parts = tok_text.split("\n")
        if len(parts) == 1:
            col += len(tok_text)
        else:
            line += len(parts) - 1
            col = len(parts[-1])
        end = f"{line}.{col}"
        tag = _token_to_tag(tok_type)
        if tag:
            try:
                widget.tag_add(tag, start, end)
            except Exception:
                pass
