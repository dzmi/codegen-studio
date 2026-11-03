# -*- coding: utf-8 -*-
"""Настройки Codegen Studio в ~/.codegen_studio/settings.json."""
import json
import os

DEFAULTS = {
    "mode": "window",
    "language": "ru",
    "always_on_top": True,
    "toolbar_pos": [100, 100],
    "window_geometry": "1300x800+100+50",
}

_SETTINGS_DIR = os.path.join(os.path.expanduser("~"), ".codegen_studio")
_SETTINGS_FILE = os.path.join(_SETTINGS_DIR, "settings.json")
_cache = None


def _load():
    global _cache
    if _cache is not None:
        return _cache
    os.makedirs(_SETTINGS_DIR, exist_ok=True)
    data = dict(DEFAULTS)
    if os.path.exists(_SETTINGS_FILE):
        try:
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                data.update(stored)
        except Exception:
            pass
    _cache = data
    return _cache


def get(key, default=None):
    return _load().get(key, default)


def set(key, value):
    data = _load()
    data[key] = value
    return data


def save():
    data = _load()
    try:
        os.makedirs(_SETTINGS_DIR, exist_ok=True)
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def settings_file():
    return _SETTINGS_FILE
