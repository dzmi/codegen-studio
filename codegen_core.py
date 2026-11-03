# -*- coding: utf-8 -*-
"""Ядро: валидация, симуляция и применение JSON-инструкций."""
import ast
import os
try:
    from logger import get_logger
except Exception:
    def get_logger(_n=None):
        import logging
        return logging.getLogger("codegen")
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class Action:
    type: str
    file: Optional[str] = None
    old: Optional[str] = None
    new: Optional[str] = None
    anchor: Optional[str] = None
    content: Optional[str] = None
    path: Optional[str] = None
    module: Optional[str] = None
    alias: Optional[str] = None
    symbol: Optional[str] = None
    new_name: Optional[str] = None
    new_code: Optional[str] = None
    name: Optional[str] = None
    body: Optional[str] = None
    is_dir: bool = False


@dataclass
class SimulationResult:
    changes: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    creations: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def normalize_actions(data):
    raw = data.get("actions", [])
    if not raw and ("modify" in data or "create" in data):
        for mod in data.get("modify", []):
            pf = mod.get("file")
            for act in mod.get("actions", []):
                if pf and "file" not in act:
                    act["file"] = pf
                raw.append(act)
        raw.extend(data.get("create", []))
    actions = []
    for d in raw:
        if d.get("type") == "delete_block" and "block" in d and "old" not in d:
            d["old"] = d.pop("block")
        actions.append(Action(
            type=d.get("type"),
            file=d.get("file") or d.get("path"),
            old=d.get("old"),
            new=d.get("new"),
            anchor=d.get("anchor"),
            content=d.get("content"),
            path=d.get("path") or d.get("file"),
            module=d.get("module"),
            alias=d.get("alias"),
            symbol=d.get("symbol"),
            new_name=d.get("new_name"),
            new_code=d.get("new_code"),
            name=d.get("name"),
            body=d.get("body"),
            is_dir=d.get("is_dir", False),
        ))
    return actions


def _find_symbol_code(file_path, symbol):
    if not file_path or not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception:
        return None
    lines = source.splitlines()
    parts = symbol.split(".")
    tgt_class = parts[0] if len(parts) > 1 else None
    tgt_name = parts[-1]

    def code_of(node):
        try:
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
        except Exception:
            return None

    if tgt_class is None:
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == tgt_name:
                return code_of(node)
    else:
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == tgt_class:
                if tgt_name == tgt_class:
                    return code_of(node)
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name == tgt_name:
                        return code_of(sub)
    return None



def _safe_path(project_path, rel_path):
    if not rel_path:
        return None
    try:
        root = os.path.realpath(project_path)
        full = os.path.realpath(os.path.join(root, rel_path))
        if not (full == root or full.startswith(root + os.sep)):
            return None
        return full
    except Exception:
        return None

def validate(actions, project_path):
    errors, warnings = [], []
    for a in actions:
        if not a.type:
            errors.append("Отсутствует поле 'type'")
            continue
        if a.type in ("replace_block", "insert_after", "insert_before",
                      "delete_block", "add_import") and not a.file:
            errors.append(f"{a.type}: отсутствует 'file'")
            continue
        if a.file and a.type not in ("create_file", "create_directory"):
            full = _safe_path(project_path, a.file)
            if not full:
                errors.append(f"{a.type}: путь '{a.file}' выходит за пределы проекта или некорректен")
                continue
            if not os.path.exists(full):
                errors.append(f"{a.type}: файл '{a.file}' не найден")
                continue
        if a.type == "replace_block":
            if not a.old or not a.old.strip():
                errors.append("replace_block: пустой 'old'")
            if a.new is None:
                errors.append("replace_block: отсутствует 'new'")
            if a.file and a.old:
                full = os.path.join(project_path, a.file)
                if os.path.exists(full):
                    with open(full, "r", encoding="utf-8") as f:
                        c = f.read()
                    n = c.count(a.old)
                    if n == 0:
                        errors.append(f"replace_block: блок не найден в {a.file}")
                    elif n > 1:
                        warnings.append(f"replace_block: блок встречается {n} раз — заменён первый")
        elif a.type == "replace_symbol":
            if not a.symbol:
                errors.append("replace_symbol: отсутствует 'symbol'")
            if not a.new_code or not a.new_code.strip():
                errors.append("replace_symbol: пустой 'new_code'")
            if a.symbol and a.file and not _find_symbol_code(os.path.join(project_path, a.file), a.symbol):
                errors.append(f"replace_symbol: символ '{a.symbol}' не найден")
        elif a.type in ("insert_after", "insert_before"):
            if not a.anchor:
                errors.append(f"{a.type}: отсутствует 'anchor'")
            elif not a.anchor.strip():
                errors.append(f"{a.type}: 'anchor' не может быть пустым")
            if a.content is None:
                errors.append(f"{a.type}: отсутствует 'content'")
            if a.file and a.anchor:
                full = os.path.join(project_path, a.file)
                if os.path.exists(full):
                    with open(full, "r", encoding="utf-8") as f:
                        c = f.read()
                    if a.anchor not in c:
                        errors.append(f"{a.type}: anchor не найден в файле {a.file}")
        elif a.type == "delete_block":
            if not a.old or not a.old.strip():
                errors.append("delete_block: пустой 'old'")
            elif a.file:
                full = os.path.join(project_path, a.file)
                if os.path.exists(full):
                    with open(full, "r", encoding="utf-8") as f:
                        c = f.read()
                    if a.old not in c:
                        errors.append(f"delete_block: блок не найден в {a.file}")
        elif a.type == "create_file":
            if not a.file:
                errors.append("create_file: отсутствует 'file'")
            elif not _safe_path(project_path, a.file):
                errors.append(f"create_file: путь '{a.file}' выходит за пределы проекта")
        elif a.type == "create_directory":
            if not a.path:
                errors.append("create_directory: отсутствует 'path'")
            elif not _safe_path(project_path, a.path):
                errors.append(f"create_directory: путь '{a.path}' выходит за пределы проекта")
        elif a.type == "delete_file":
            if not a.file:
                errors.append("delete_file: отсутствует 'file'")
        elif a.type == "add_import":
            if not a.module:
                errors.append("add_import: отсутствует 'module'")
        elif a.type not in ("rename_symbol",):
            errors.append(f"Неизвестный тип: {a.type}")
    return errors, warnings



def _replace_symbol_in_text(text, symbol, new_code):
    import ast
    try:
        tree = ast.parse(text)
    except Exception:
        return text

    parts = symbol.split('.')
    target_class = parts[0] if len(parts) > 1 else None
    target_name = parts[-1]
    node_to_replace = None

    for node in tree.body:
        if target_class is None:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == target_name:
                node_to_replace = node
                break
        else:
            if isinstance(node, ast.ClassDef) and node.name == target_class:
                if target_name == target_class:
                    node_to_replace = node
                    break
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name == target_name:
                        node_to_replace = sub
                        break
                if node_to_replace:
                    break

    if node_to_replace:
        lines = text.splitlines(keepends=True)
        start = node_to_replace.lineno - 1
        end = node_to_replace.end_lineno
        new_lines = new_code.splitlines(keepends=True)
        if lines[end-1].endswith('\n') and new_lines and not new_lines[-1].endswith('\n'):
            new_lines[-1] += '\n'
        if not new_lines:
            new_lines = []
        return "".join(lines[:start] + new_lines + lines[end:])
    return text

def simulate(actions, project_path):
    result = SimulationResult()
    file_acts = defaultdict(list)
    for a in actions:
        if a.type in ("create_file", "create_directory", "delete_file"):
            result.creations.append({
                "type": a.type,
                "file": a.file or a.path,
                "path": a.path or a.file,
                "content": a.content or "",
                "is_dir": a.is_dir or a.type == "create_directory",
            })
        elif a.file:
            file_acts[a.file].append(a)

    for file_path, acts in file_acts.items():
        full = _safe_path(project_path, file_path)
        if not full:
            result.errors.append(f"Небезопасный путь: {file_path}")
            continue
        if not os.path.exists(full):
            result.errors.append(f"Файл не существует: {file_path}")
            continue
        with open(full, "r", encoding="utf-8") as f:
            old = f.read()
        new = old
        rbs = [(old.find(a.old), a) for a in acts if a.type == "replace_block" and a.old]
        rbs = [(p, a) for p, a in rbs if p != -1]
        rbs.sort(reverse=True, key=lambda x: x[0])
        for _, a in rbs:
            new = new.replace(a.old, a.new or "", 1)
        # replace_block, которые не нашли old
        for a in acts:
            if a.type == "replace_block" and a.old and old.find(a.old) == -1:
                result.warnings.append(f"replace_block: блок не найден в {file_path}: {str(a.old)[:60]}")
        for a in acts:
            if a.type == "replace_symbol":
                new = _replace_symbol_in_text(new, a.symbol, a.new_code)
        for a in acts:
            if a.type == "add_import" and a.module:
                line = f"import {a.module}" + (f" as {a.alias}" if a.alias else "")
                if line not in new:
                    lines = new.splitlines()
                    idx = 0
                    for i, l in enumerate(lines):
                        if l.startswith("import ") or l.startswith("from "):
                            idx = i + 1
                    lines.insert(idx, line)
                    new = "\n".join(lines)
        for a in acts:
            if a.type == "insert_after":
                if a.anchor and a.anchor in new:
                    new = new.replace(a.anchor, a.anchor + "\n" + (a.content or ""), 1)
                else:
                    result.warnings.append(f"insert_after: anchor не найден в {file_path}: {str(a.anchor)[:60]}")
            elif a.type == "insert_before":
                if a.anchor and a.anchor in new:
                    new = new.replace(a.anchor, (a.content or "") + "\n" + a.anchor, 1)
                else:
                    result.warnings.append(f"insert_before: anchor не найден в {file_path}: {str(a.anchor)[:60]}")
            elif a.type == "delete_block":
                if a.old and a.old in new:
                    new = new.replace(a.old, "", 1)
                else:
                    result.warnings.append(f"delete_block: блок не найден в {file_path}: {str(a.old)[:60]}")
        if new != old:
            result.changes[file_path] = (old, new)
    return result


def apply_simulation(simulation, project_path):
    import shutil
    logger = get_logger("codegen")
    applied_files, created, errors, backups = [], [], [], []

    try:
        # === ФАЗА 1: Создание бэкапов для всех изменяемых и удаляемых файлов ===
        for file_path in simulation.changes.keys():
            full = _safe_path(project_path, file_path)
            if not full: raise ValueError(f"Небезопасный путь: {file_path}")
            if os.path.exists(full):
                bak = full + ".codegen.bak"
                shutil.copy2(full, bak)
                backups.append((full, bak))

        for item in simulation.creations:
            if item.get("type") == "delete_file":
                full = _safe_path(project_path, item.get("file") or item.get("path"))
                if not full: raise ValueError(f"Небезопасный путь: {item}")
                if os.path.exists(full):
                    bak = full + ".codegen.bak"
                    shutil.copy2(full, bak)
                    backups.append((full, bak))

        # === ФАЗА 2: Применение изменений ===
        for file_path, (old, new) in simulation.changes.items():
            full = _safe_path(project_path, file_path)
            with open(full, "w", encoding="utf-8") as f:
                f.write(new)
            applied_files.append(file_path)

        for item in simulation.creations:
            full = _safe_path(project_path, item.get("file") or item.get("path"))
            if item.get("type") == "delete_file":
                if os.path.exists(full):
                    os.remove(full)
                    created.append(full)
            elif item.get("is_dir"):
                os.makedirs(full, exist_ok=True)
                created.append(full)
            else:
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "w", encoding="utf-8") as f:
                    f.write(item.get("content", ""))
                created.append(full)

        # === УСПЕХ: Очистка бэкапов ===
        for _, bak in backups:
            if os.path.exists(bak):
                os.remove(bak)
        return True, applied_files, created, []

    except Exception as e:
        logger.exception("apply_simulation failed: %s", e)
        # === ОТКАТ: Восстановление всех бэкапов ===
        for full, bak in backups:
            if os.path.exists(bak):
                shutil.copy2(bak, full)
                os.remove(bak)
        # Удаление созданных файлов
        for p in created:
            try:
                if os.path.exists(p) and not any(p == b[0] for b in backups):
                    if os.path.isdir(p):
                        shutil.rmtree(p)
                    else:
                        os.remove(p)
            except Exception:
                pass
        return False, [], [], [str(e)]



