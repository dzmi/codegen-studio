# История изменений

### 2026-11-03 — Codegen Studio v1

**Создан с нуля** (проект `AI_lite`, отдельно от `AI`).

#### Ядро
- `codegen_core.py`: `normalize_actions`, `validate`, `simulate`, `apply_simulation`.
- Типы действий: `replace_block`, `replace_symbol`, `insert_after/before`, `delete_block`, `add_import`, `create_file`, `create_directory`, `delete_file`.
- `apply_simulation` — транзакционная: `.bak` для каждого файла, откат при любой ошибке.
- `replace_symbol` через `ast.parse` — не требует дословного `old`.

#### GUI
- Компактное окно 1100×700, тулбар, дерево, notebook с 5 вкладками.
- Toolbar-режим 850×46 (без рамки, draggable, always-on-top по настройке).
- Имя проекта в полоске: `📂 AI_lite`.
- Diff-окно 1300×760: дерево изменений (`✏/➕/➖`), подсветка (🟡 replace, 🔴 delete, 🟢 insert), поиск как в Word, синхронный скролл.
- JSON-диалог 900×600 с пошаговой инструкцией и большой зелёной кнопкой.

#### Периферия
- `exporter.py`: JSON/ZIP с единым фильтром `.gitignore` (`DEFAULT_EXCLUDES` + `EXCLUDE_FILES` + пользовательский `.gitignore`).
- `git_py.py`: dulwich → subprocess git → offline, три backend.
- `logger.py`: `studio_app.log` (INFO+) + `studio_errors.log` (WARNING+), ротация 5 МБ × 5.
- `lite_highlighter.py`: pygments с fallback без подсветки.
- `settings_manager.py`: `~/.codegen_studio/settings.json` (mode, always_on_top, toolbar_pos, window_geometry).

#### Экспорт
- Быстрый дамп `⚡` → `dumps/<project>_dump_<timestamp>.json`.
- Диалоги экспорта JSON/ZIP с `initialdir=dumps/`.
- `_ensure_gitignore`: при открытии проекта дописывает `logs/`, `dumps/`, `*.pyc`, `__pycache__/`, `*.codegen.bak`.

#### Документация
- `docs/INDEX.md` — оглавление.
- `docs/USER_GUIDE.md`, `docs/WORKFLOW.md`, `docs/JSON_FORMAT.md`, `docs/DIFF_DIALOG.md`, `docs/SETTINGS.md`, `docs/TROUBLESHOOTING.md`, `docs/EXTENDING.md`.
- `docs/ARCHITECTURE.md` — 6 принципов, слои, модули.
- Корневой `README.md` обновлён.

#### Логирование ошибок
- Все неудачные замены пишутся в `logs/studio_errors.log`: JSON parse, validation, simulation, apply-failed, отмена пользователем.
- Успехи — в `logs/studio_app.log` (`apply-ok: <файл>`).

<!-- END OF DOC -->
