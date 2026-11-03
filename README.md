# Codegen Studio

Мини-приложение для работы с JSON-инструкциями Codegen **без встроенного ИИ**.

## Что умеет

- Просмотр проекта с деревом файлов (фильтр по `.gitignore`)
- Подсветка синтаксиса через `pygments` (fallback — без неё)
- Вставка JSON из ChatGPT/Claude/LM Studio → валидация → симуляция → preview diff → применение с `.bak`
- Экспорт проекта в JSON/ZIP с фильтром `.gitignore` и папок-исключений
- Git через `dulwich` (чистый Python) или `subprocess git`, fallback — без git
- Готовые промпты: Codegen / Code review / Архитектура + «+ дерево проекта» / «+ текущий файл»
- Логи в `logs/studio_app.log` и `logs/studio_errors.log`

## Запуск

```
python main.py
```

## Установка зависимостей (опционально)

```
pip install pygments dulwich
```

- `pygments` — подсветка синтаксиса (без неё всё работает, но без цветов)
- `dulwich` — git на чистом Python (без неё fallback на системный git)

## Формат JSON-инструкций

```json
{
  "actions": [
    {"type": "replace_block", "file": "app.py", "old": "old code", "new": "new code"},
    {"type": "replace_symbol", "file": "app.py", "symbol": "Class.method", "new_code": "def method(self):\n    pass"}
  ]
}
```

Поддерживаются: `replace_block`, `replace_symbol`, `insert_after`, `insert_before`, `delete_block`, `add_import`, `create_file`, `create_directory`, `delete_file`.

## Что НЕ попадает в экспорт

`.git/`, `__pycache__/`, `venv/`, `node_modules/`, `logs/`, `dumps/`, `.env`, `*.bak`, всё из `.gitignore`.

<!-- END OF DOC -->
