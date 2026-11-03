# Контекст проекта

## Краткая выжимка для ИИ
Codegen Studio — офлайн-инструмент на Python 3.10+ / Tkinter для применения JSON-инструкций к коду. Работает без встроенного ИИ: пользователь копирует промпт в ChatGPT/Claude/LM Studio, получает JSON, вставляет в Studio, проверяет diff и применяет.

**Стек:** Tkinter (stdlib), pygments (опц., подсветка), dulwich (опц., Git). Обязательных зависимостей — ноль.

**Архитектура:**
- `codegen_core.py` — ядро: `normalize_actions` → `validate` → `simulate` → `apply_simulation` (с `.bak` и атомарным откатом).
- `ui_main.py` — весь GUI, включая toolbar-режим и diff-окно.

**Ключевые правила:**
1. Любое изменение файла — только через `simulate` → пользователь подтверждает diff → `apply_simulation`.
2. `apply_simulation` атомарна: `.bak` восстанавливаются при любой ошибке.
3. `.gitignore` — единственный источник правды.
