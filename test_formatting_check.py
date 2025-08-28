#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test to check if excessive formatting symbols are preserved in Markdown export
"""

import re

def clean_text(text: str) -> str:
    """Упрощенная версия clean_text из BaseExporter"""
    if not text:
        return ""
    
    # Удаление анимированных эмодзи и специальных символов
    cleaned = re.sub(r'[\u200d\ufe0f]', '', text)  # Удаляем модификаторы эмодзи
    cleaned = re.sub(r'[\u2060-\u206f]', '', cleaned)  # Word joiner и другие
    
    # Удаляем или заменяем последовательности, которые могут вызвать ошибки KaTeX
    # Более консервативные паттерны - удаляем только действительно проблемные конструкции
    katex_problematic_patterns = [
        (r'\\-', '-'),              # \- заменяем на обычный дефис  
        (r'\\\+', '+'),            # \+ заменяем на обычный плюс
        (r'\\\*', '*'),            # \* заменяем на обычную звездочку
        # Удаляем только очевидные LaTeX команды в математическом контексте
        (r'\$\\[a-zA-Z]+\$', ''),  # Удаляем только $\command$ (математические команды в долларах)
        (r'\\begin\{[^}]+\}', ''), # Удаляем \begin{environment}
        (r'\\end\{[^}]+\}', ''),   # Удаляем \end{environment}
    ]
    
    for pattern, replacement in katex_problematic_patterns:
        cleaned = re.sub(pattern, replacement, cleaned)
    
    return cleaned.strip()

def safe_markdown_text_current(text: str) -> str:
    """Текущая версия _safe_markdown_text"""
    if not text:
        return ""
    
    # Сначала очищаем от проблемных символов
    cleaned = clean_text(text)
    
    # Находим и защищаем блоки кода (многострочные и однострочные)
    code_blocks = []
    code_counter = 0
    
    # Защищаем многострочные блоки кода (```)
    def protect_multiline_code(match):
        nonlocal code_counter
        code_blocks.append(match.group(0))
        placeholder = f"MDCODEBLOCK{code_counter}PLACEHOLDER"
        code_counter += 1
        return placeholder
    
    # Защищаем однострочные блоки кода (`code`)
    def protect_inline_code(match):
        nonlocal code_counter
        code_blocks.append(match.group(0))
        placeholder = f"MDCODEBLOCK{code_counter}PLACEHOLDER"
        code_counter += 1
        return placeholder
    
    # Сначала защищаем многострочные блоки кода
    cleaned = re.sub(r'```[\s\S]*?```', protect_multiline_code, cleaned)
    
    # Затем защищаем однострочные блоки кода
    cleaned = re.sub(r'`[^`\n]+`', protect_inline_code, cleaned)
    
    # Минимальное экранирование только проблемных символов KaTeX
    # НЕ экранируем Markdown символы разметки (*, _, [, ])
    # Экранируем решетку только в начале строки (для заголовков), но не в блоках кода
    # cleaned = re.sub(r'^#', '\\#', cleaned, flags=re.MULTILINE)  # Отключаем экранирование заголовков
    
    # Восстанавливаем защищенные блоки кода
    for i, code_block in enumerate(code_blocks):
        placeholder = f"MDCODEBLOCK{i}PLACEHOLDER"
        cleaned = cleaned.replace(placeholder, code_block)
    
    return cleaned

def test_excessive_formatting():
    """Тест на избыточное форматирование"""
    
    print("🧪 Тестирование избыточного форматирования в Markdown...")
    
    test_cases = [
        {
            "name": "Обычный текст с эмодзи",
            "input": "Привет! 👋 Как дела? 😊",
            "expected_preserved": ["👋", "😊"],
            "should_be_clean": True
        },
        {
            "name": "Telegram форматирование (жирный, курсив)",
            "input": "**Жирный текст** и *курсивный* текст",
            "expected_preserved": ["**", "*"],
            "should_be_clean": True
        },
        {
            "name": "Ссылки",
            "input": "Перейдите на [сайт](https://example.com) за подробностями",
            "expected_preserved": ["[", "]", "(", ")"],
            "should_be_clean": True
        },
        {
            "name": "KaTeX проблемные символы",
            "input": "Команда: find \\. \\-type f \\-mtime \\+30 \\-delete",
            "expected_cleaned": ["\\.", "\\-", "\\+"],
            "should_be_clean": True
        },
        {
            "name": "LaTeX команды",
            "input": "Формула: \\$E\\=mc\\^2\\$ и \\alpha \\beta \\gamma",
            "expected_cleaned": ["\\$", "\\=", "\\^", "\\alpha", "\\beta", "\\gamma"],
            "should_be_clean": True
        },
        {
            "name": "Сложные символы Unicode",
            "input": "Текст с\u200d\ufe0f анимацией\u2060и\u2061скрытыми\u206f символами",
            "expected_cleaned": ["\u200d", "\ufe0f", "\u2060", "\u2061", "\u206f"],
            "should_be_clean": True
        },
        {
            "name": "Код блоки",
            "input": "Команда `ls -la` и блок:\n```bash\necho 'hello'\n```",
            "expected_preserved": ["`", "```"],
            "should_be_clean": True
        },
        {
            "name": "Заголовки",
            "input": "# Заголовок 1\n## Заголовок 2\n### Заголовок 3",
            "expected_preserved": ["#"],
            "should_be_clean": True
        },
        {
            "name": "Избыточные символы HTML",
            "input": "&lt;div&gt;&amp;nbsp;&lt;/div&gt;",
            "expected_preserved": ["&lt;", "&gt;", "&amp;"],  # Эти не должны быть убраны
            "should_be_clean": True
        }
    ]
    
    issues_found = []
    
    for i, test_case in enumerate(test_cases):
        print(f"\n📝 Тест {i+1}: {test_case['name']}")
        
        original = test_case['input']
        result = safe_markdown_text_current(original)
        
        print(f"Исходный: {repr(original)}")
        print(f"Результат: {repr(result)}")
        
        # Проверяем, что ожидаемые символы сохранились
        if 'expected_preserved' in test_case:
            missing_symbols = []
            for symbol in test_case['expected_preserved']:
                if symbol not in result:
                    missing_symbols.append(symbol)
            
            if missing_symbols:
                print(f"⚠️  Пропущены символы: {missing_symbols}")
                issues_found.append(f"Тест {i+1}: пропущены символы {missing_symbols}")
        
        # Проверяем, что проблемные символы убраны
        if 'expected_cleaned' in test_case:
            remaining_symbols = []
            for symbol in test_case['expected_cleaned']:
                if symbol in result:
                    remaining_symbols.append(symbol)
            
            if remaining_symbols:
                print(f"✅ Убраны проблемные символы: {set(test_case['expected_cleaned']) - set(remaining_symbols)}")
                if remaining_symbols:
                    print(f"⚠️  Остались символы: {remaining_symbols}")
                    issues_found.append(f"Тест {i+1}: остались символы {remaining_symbols}")
        
        # Проверяем общую длину (не должно быть слишком агрессивной очистки)
        if len(result) < len(original) * 0.5:  # Если убрано более 50% - подозрительно
            print(f"⚠️  Возможно слишком агрессивная очистка: {len(original)} → {len(result)}")
            issues_found.append(f"Тест {i+1}: агрессивная очистка {len(original)} → {len(result)}")
        
        if not issues_found or len(issues_found) == 0:
            print("✅ Тест пройден")
    
    print(f"\n📊 Результаты тестирования:")
    if issues_found:
        print("⚠️  Найдены потенциальные проблемы:")
        for issue in issues_found:
            print(f"  • {issue}")
        return False
    else:
        print("✅ Все тесты пройдены успешно")
        print("✅ Избыточное форматирование не обнаружено")
        return True

if __name__ == "__main__":
    success = test_excessive_formatting()
    exit(0 if success else 1)