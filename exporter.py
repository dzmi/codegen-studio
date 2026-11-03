# -*- coding: utf-8 -*-
"""Экспорт проекта в JSON/ZIP с учётом .gitignore и папок-исключений."""
import fnmatch
import json
import zipfile
from pathlib import Path

DEFAULT_EXCLUDES = {
    ".git", ".hg", ".svn",
    "__pycache__", "node_modules",
    "venv", ".venv", "env",
    ".idea", ".vscode",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "build", "dist", ".tox",
    "logs", "dumps", "archive",
    ".lmstudio_editor", ".lmstudio_cache",
    ".ropeproject",
}

TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".html", ".css", ".scss", ".less",
    ".json", ".yml", ".yaml", ".toml",
    ".txt", ".md", ".rst",
    ".ini", ".cfg", ".conf", ".xml",
    ".sql", ".sh", ".bat", ".ps1",
}

EXCLUDE_FILES = [
    ".env", ".env.*", "secrets.*", "credentials.*",
    "*.pyc", "*.pyo", "*.pyd",
    "*.bak", "*.codegen.bak",
    "*.pem", "*.key", "*.crt", "*.p12",
    "Thumbs.db", "desktop.ini", ".DS_Store",
    ".coverage",
]

SPECIAL_NAMES = {"Makefile", "Dockerfile", "Procfile", "LICENSE", "README"}


def read_gitignore(project_path):
    gi = Path(project_path) / ".gitignore"
    if not gi.exists():
        return []
    rules = []
    try:
        for line in gi.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rules.append(line.lstrip("/"))
    except Exception:
        pass
    return rules


def _matches_gitignore(rel_path, rules):
    for rule in rules:
        if rule.endswith("/"):
            if rel_path == rule[:-1] or rel_path.startswith(rule):
                return True
        if fnmatch.fnmatch(rel_path, rule) or fnmatch.fnmatch(Path(rel_path).name, rule):
            return True
    return False


def should_include(file_path, root, gitignore_rules, extra_excludes=None):
    p = Path(file_path)
    root_p = Path(root)
    try:
        rel = p.relative_to(root_p)
    except ValueError:
        return False
    rel_str = str(rel).replace("\\", "/")
    excluded = DEFAULT_EXCLUDES | (extra_excludes or set())
    for part in rel.parts[:-1]:
        if part in excluded:
            return False
    for pat in EXCLUDE_FILES:
        if fnmatch.fnmatch(p.name, pat):
            return False
    if _matches_gitignore(rel_str, gitignore_rules):
        return False
    return True


def _collect_files(project_path, selected_files=None):
    root = Path(project_path).resolve()
    rules = read_gitignore(project_path)
    selected = None
    if selected_files is not None:
        selected = {p.replace("\\", "/") for p in selected_files}
    out = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        if not should_include(p, root, rules):
            continue
        if selected is not None and rel not in selected:
            continue
        if p.suffix.lower() not in TEXT_EXTENSIONS and p.name not in SPECIAL_NAMES:
            continue
        out.append((p, rel))
    return out


def default_dump_path(project_path, kind="json"):
    """Возвращает путь по умолчанию: <project>/dumps/<name>_dump_<timestamp>.<ext>"""
    from datetime import datetime
    dumps = Path(project_path) / "dumps"
    dumps.mkdir(parents=True, exist_ok=True)
    name = Path(project_path).name
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if kind == "zip":
        return str(dumps / f"{name}_{ts}.zip")
    return str(dumps / f"{name}_dump_{ts}.json")



def export_json(project_path, output_path, selected_files=None):
    files = _collect_files(project_path, selected_files)
    data = {
        "project_name": Path(project_path).name,
        "root_path": str(Path(project_path).resolve()),
        "files": {},
    }
    for p, rel in files:
        try:
            data["files"][rel] = p.read_text(encoding="utf-8")
        except Exception as e:
            data["files"][rel] = f"[Ошибка чтения: {e}]"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return len(files)


def export_zip(project_path, output_path, selected_files=None):
    files = _collect_files(project_path, selected_files)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p, rel in files:
            z.write(p, rel)
    return len(files)
