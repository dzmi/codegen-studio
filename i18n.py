# -*- coding: utf-8 -*-
TRANSLATIONS = {
    "ru": {
        "menu_file": "Файл", "menu_export": "Экспорт", "menu_git": "Git", "menu_help": "Справка",
        "item_open_proj": "Открыть проект…", "item_refresh_tree": "Обновить дерево",
        "item_docs": "Документация…", "item_exit": "Выход",
        "item_export_proj": "Экспорт проекта…", "item_copy_struct": "Копировать структуру",
        "item_prompt_ai": "Промпт для ИИ…", "item_about": "О программе...",
        "tab_file": "Файл", "tab_json": "JSON", "tab_prompt": "Промпт", "tab_git": "Git", "tab_log": "Лог",
        "btn_project": "Проект", "btn_prompt": "Промпт", "btn_json": "Вставить JSON",
        "btn_apply": "Применить", "btn_export": "Экспорт", "btn_docs": "Docs", "btn_git": "Git",
        "settings_lang": "Язык интерфейса:", "restart_req": "Для применения языка перезапустите приложение.",
        "about_title": "О программе", "about_version": "Версия 1.1",
        "about_desc": "Офлайн-инструмент для безопасного применения JSON-инструкций к коду.\n\n• Работает без встроенного ИИ и без видеокарты.\n• Вы копируете промпт во внешнюю LLM (ChatGPT, Claude, LM Studio),\n  а затем вставляете полученный JSON в программу.\n• Приложение валидирует изменения, показывает diff и применяет их\n  с возможностью отката (атомарно, с созданием .bak).\n• Включает встроенный редактор кода и документации, Git-клиент\n  и экспорт проекта в JSON/ZIP.",
        "tip_open": "1. Открыть папку проекта", "tip_prompt": "2. Скопировать промпт для ИИ",
        "tip_json": "3. Вставить JSON-инструкции", "tip_apply": "4. Применить из буфера обмена",
        "tip_export": "5. Сохранить проект в JSON/ZIP", "tip_docs": "Открыть документацию",
        "tip_git": "Git commit", "tip_settings": "Настройки", "tip_close": "Закрыть приложение", "tip_mode": "Свернуть в полоску / Развернуть",

        "msg_info": "Инфо", "msg_error": "Ошибка", "msg_warn": "Внимание", "msg_yes": "Да", "msg_no": "Нет", "msg_cancel": "Отмена", "msg_close": "Закрыть", "msg_save": "💾 Сохранить",
        "msg_unsaved": "Не сохранено", "msg_unsaved_text": "Файл изменён. Сохранить?",

        "json_title": "JSON — вставить и применить", "json_how": "Как использовать",
        "json_step1": "1️⃣ Вставь JSON-инструкцию (уже вставлена из буфера, если есть)",
        "json_step2": "2️⃣ Нажми «✅ Применить» — откроется окно сравнения",
        "json_step3": "3️⃣ Проверь diff и подтверди изменения",
        "json_paste": "📋 Из буфера", "json_apply": "✅ ПРИМЕНИТЬ",

        "exp_title": "Экспорт проекта", "exp_proj": "Проект:", "exp_fmt": "Формат:",
        "exp_fmt_json": "JSON — один файл для передачи в LLM", "exp_fmt_zip": "ZIP — архив проекта (сохраняет структуру)",
        "exp_where": "Куда сохранять:", "exp_where_dumps": "В папку dumps/", "exp_where_manual": "Выбрать папку вручную…",
        "exp_not_incl": "Что НЕ попадёт:", "exp_not_incl_text": ".git, __pycache__, venv, node_modules, logs/, dumps/,\n.env, *.bak, *.pem, и всё, что указано в .gitignore",
        "exp_preview": "Предпросмотр (первые 12 файлов):", "exp_export": "💾 Экспортировать", "exp_open_dumps": "📂 Открыть dumps/",
        "exp_done": "Экспорт завершен", "exp_files": "Файлов:", "exp_saved_to": "Сохранено в:", "exp_open_q": "Открыть папку с файлом?",

        "pr_title": "Промпты для ИИ", "pr_1": "1. Выбери промпт:", "pr_2": "2. Что добавить к промпту:",
        "pr_only": "Только промпт", "pr_tree": "Промпт + дерево проекта", "pr_file": "Промпт + текущий файл", "pr_both": "Промпт + дерево + текущий файл",
        "pr_ctx": "Добавить блок 'Краткая выжимка для ИИ' из docs/PROJECT_CONTEXT.md",
        "pr_preview": "3. Превью (что попадёт в буфер):", "pr_copy": "КОПИРОВАТЬ В БУФЕР", "pr_chars": "Символов:",

        "docs_title": "Документация проекта — редактор", "docs_files": "Файлы docs/:", "docs_open_ext": "📄 Открыть внешне", "docs_update": "🔄 Обновить", "docs_open_dir": "📂 Открыть docs/",

        "diff_title": "Сравнение изменений", "diff_search": "🔍 Поиск:", "diff_files": "Файлы и изменения:", "diff_old": "Старый код:", "diff_new": "Новый код:", "diff_apply": "✅ Применить изменения",

        "err_copy_close": "📋 КОПИРОВАТЬ И ЗАКРЫТЬ",
        "edit_prompt_title": "Редактирование:", "edit_prompt_text": "Текст промпта (Markdown):", "edit_prompt_undo": "↩️ Undo", "edit_prompt_redo": "↪️ Redo", "edit_prompt_hl": "🎨 Подсветка"
    },
    "en": {
        "menu_file": "File", "menu_export": "Export", "menu_git": "Git", "menu_help": "Help",
        "item_open_proj": "Open Project…", "item_refresh_tree": "Refresh Tree",
        "item_docs": "Documentation…", "item_exit": "Exit",
        "item_export_proj": "Export Project…", "item_copy_struct": "Copy Structure",
        "item_prompt_ai": "Prompt for AI…", "item_about": "About...",
        "tab_file": "File", "tab_json": "JSON", "tab_prompt": "Prompt", "tab_git": "Git", "tab_log": "Log",
        "btn_project": "Project", "btn_prompt": "Prompt", "btn_json": "Insert JSON",
        "btn_apply": "Apply", "btn_export": "Export", "btn_docs": "Docs", "btn_git": "Git",
        "settings_lang": "Interface language:", "restart_req": "Please restart the application to apply the language.",
        "about_title": "About", "about_version": "Version 1.1",
        "about_desc": "Offline tool for safely applying JSON instructions to code.\n\n• Works without built-in AI or GPU.\n• You copy the prompt to an external LLM (ChatGPT, Claude, LM Studio),\n  and then paste the resulting JSON into the app.\n• The app validates changes, shows a diff, and applies them\n  atomically with rollback support (.bak files).\n• Includes a built-in code and documentation editor, Git client,\n  and project export to JSON/ZIP.",
        "tip_open": "1. Open project folder", "tip_prompt": "2. Copy prompt for AI",
        "tip_json": "3. Insert JSON instructions", "tip_apply": "4. Apply from clipboard",
        "tip_export": "5. Save project to JSON/ZIP", "tip_docs": "Open documentation",
        "tip_git": "Git commit", "tip_settings": "Settings", "tip_close": "Close application", "tip_mode": "Minimize to bar / Expand",

        "msg_info": "Info", "msg_error": "Error", "msg_warn": "Warning", "msg_yes": "Yes", "msg_no": "No", "msg_cancel": "Cancel", "msg_close": "Close", "msg_save": "💾 Save",
        "msg_unsaved": "Unsaved changes", "msg_unsaved_text": "File modified. Save?",

        "json_title": "JSON — Insert and Apply", "json_how": "How to use",
        "json_step1": "1️⃣ Paste JSON instructions (auto-pasted from clipboard if available)",
        "json_step2": "2️⃣ Click «✅ Apply» — the diff window will open",
        "json_step3": "3️⃣ Review the diff and confirm changes",
        "json_paste": "📋 From clipboard", "json_apply": "✅ APPLY",

        "exp_title": "Export Project", "exp_proj": "Project:", "exp_fmt": "Format:",
        "exp_fmt_json": "JSON — single file to send to LLM", "exp_fmt_zip": "ZIP — project archive (keeps structure)",
        "exp_where": "Save to:", "exp_where_dumps": "To dumps/ folder", "exp_where_manual": "Select folder manually…",
        "exp_not_incl": "What is excluded:", "exp_not_incl_text": ".git, __pycache__, venv, node_modules, logs/, dumps/,\n.env, *.bak, *.pem, and everything in .gitignore",
        "exp_preview": "Preview (first 12 files):", "exp_export": "💾 Export", "exp_open_dumps": "📂 Open dumps/",
        "exp_done": "Export complete", "exp_files": "Files:", "exp_saved_to": "Saved to:", "exp_open_q": "Open folder with file?",

        "pr_title": "Prompts for AI", "pr_1": "1. Select prompt:", "pr_2": "2. Add to prompt:",
        "pr_only": "Prompt only", "pr_tree": "Prompt + project tree", "pr_file": "Prompt + current file", "pr_both": "Prompt + tree + current file",
        "pr_ctx": "Add 'Short summary for AI' block from docs/PROJECT_CONTEXT.md",
        "pr_preview": "3. Preview (what will be copied):", "pr_copy": "COPY TO CLIPBOARD", "pr_chars": "Chars:",

        "docs_title": "Project Documentation — Editor", "docs_files": "Files in docs/:", "docs_open_ext": "📄 Open externally", "docs_update": "🔄 Update", "docs_open_dir": "📂 Open docs/",

        "diff_title": "Changes Diff", "diff_search": "🔍 Search:", "diff_files": "Files & changes:", "diff_old": "Old code:", "diff_new": "New code:", "diff_apply": "✅ Apply changes",

        "err_copy_close": "📋 COPY AND CLOSE",
        "edit_prompt_title": "Editing:", "edit_prompt_text": "Prompt text (Markdown):", "edit_prompt_undo": "↩️ Undo", "edit_prompt_redo": "↪️ Redo", "edit_prompt_hl": "🎨 Highlight"
    }
}
