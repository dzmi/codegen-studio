# Формат JSON-инструкций

## Общая структура
```json
{
  "actions": [
    {"type": "имя_действия", "file": "путь/к/файлу.py", ...}
  ]
}
```

## Типы действий

### 1. replace_symbol (Рекомендуется)
Заменяет функцию, класс или метод целиком по его имени (через AST). Не требует копирования старого кода.
```json
{"type": "replace_symbol", "file": "app.py", "symbol": "MyClass.my_method", "new_code": "def my_method(self):\n    return 42"}
```

### 2. replace_block
Заменяет точный кусок текста. Поле `old` должно быть дословной копией.
```json
{"type": "replace_block", "file": "config.py", "old": "DEBUG = True", "new": "DEBUG = False"}
```

### 3. insert_before / insert_after
Вставляет код до или после уникального якоря (anchor).
```json
{"type": "insert_before", "file": "utils.py", "anchor": "def existing_func():", "content": "def new_func():\n    pass\n"}
```

### 4. create_file / create_directory
Создает новые файлы или папки.
```json
{"type": "create_file", "file": "tests/test_app.py", "content": "def test_1():\n    assert True"}
{"type": "create_directory", "path": "tests/data"}
```

### 5. delete_file / delete_block
Удаляет файл или кусок кода.
```json
{"type": "delete_file", "file": "old_script.py"}
{"type": "delete_block", "file": "app.py", "old": "print('debug')"}
```

### 6. add_import
Добавляет импорт в начало файла.
```json
{"type": "add_import", "file": "main.py", "module": "os"}
```
