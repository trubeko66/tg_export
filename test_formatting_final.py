#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Final test to verify that excessive formatting symbols are NOT being removed from Markdown export
"""

import re

def clean_text(text: str) -> str:
    """Updated conservative version of clean_text from BaseExporter"""
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

def test_final_formatting():
    """Финальный тест форматирования Markdown"""
    
    print("🧪 Финальный тест форматирования Markdown...")
    
    test_cases = [
        {
            "name": "Markdown форматирование (должно сохраняться)",
            "input": "**Жирный текст** и *курсивный* текст с [ссылкой](url)",
            "description": "Базовое Markdown форматирование должно полностью сохраняться",
            "expect_unchanged": True
        },
        {
            "name": "Заголовки (должны сохраняться)",
            "input": "# Заголовок 1\n## Заголовок 2\n### Заголовок 3",
            "description": "Заголовки должны сохраняться без экранирования",
            "expect_unchanged": True
        },
        {
            "name": "Код блоки (должны сохраняться)",
            "input": "Команда `ls -la` и блок:\n```bash\necho 'hello'\n```",
            "description": "Код блоки должны полностью сохраняться",
            "expect_unchanged": True
        },
        {
            "name": "Эмодзи (должны сохраняться)",
            "input": "Привет! 👋 Как дела? 😊 🚀",
            "description": "Эмодзи должны сохраняться (кроме служебных модификаторов)",
            "expect_unchanged": False,  # Модификаторы могут удаляться
            "expected_preserved": ["👋", "😊", "🚀"]
        },
        {
            "name": "Консервативная очистка проблемных символов",
            "input": "Команда: find \\. \\-type f \\-mtime \\+30 \\-delete",
            "description": "Должны убираться только самые проблемные символы (\\- и \\+)",
            "expect_unchanged": False,
            "must_contain": ["find", ".", "type", "f", "mtime", "30", "delete"],
            "should_not_contain": ["\\-", "\\+"]
        },
        {
            "name": "LaTeX команды (теперь сохраняются)",
            "input": "\\alpha \\beta \\gamma текст",
            "description": "LaTeX команды должны сохраняться (не удаляться агрессивно)",
            "expect_unchanged": True
        }
    ]
    
    all_passed = True
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📝 Тест {i}: {test_case['name']}")
        print(f"   {test_case['description']}")
        
        original = test_case['input']
        result = safe_markdown_text_current(original)
        
        print(f"   Исходный: {repr(original)}")
        print(f"   Результат: {repr(result)}")
        
        test_passed = True
        
        # Проверка на полное сохранение
        if test_case.get('expect_unchanged', False):
            if result != original:
                print(f"   ❌ ОШИБКА: Текст изменился, хотя должен был остаться неизменным")
                test_passed = False
            else:
                print(f"   ✅ Текст правильно сохранен без изменений")
        
        # Проверка на сохранение конкретных элементов
        if 'expected_preserved' in test_case:
            missing = []
            for symbol in test_case['expected_preserved']:
                if symbol not in result:
                    missing.append(symbol)
            
            if missing:
                print(f"   ❌ ОШИБКА: Пропущены символы: {missing}")
                test_passed = False
            else:
                print(f"   ✅ Все ожидаемые символы сохранены")
        
        # Проверка обязательного содержимого
        if 'must_contain' in test_case:
            missing_content = []
            for content in test_case['must_contain']:
                if content not in result:
                    missing_content.append(content)
            
            if missing_content:
                print(f"   ❌ ОШИБКА: Отсутствует обязательное содержимое: {missing_content}")
                test_passed = False
        
        # Проверка нежелательного содержимого
        if 'should_not_contain' in test_case:
            unwanted_content = []
            for content in test_case['should_not_contain']:
                if content in result:
                    unwanted_content.append(content)
            
            if unwanted_content:
                print(f"   ❌ ОШИБКА: Найдено нежелательное содержимое: {unwanted_content}")
                test_passed = False
        
        if test_passed:
            print(f"   ✅ Тест пройден")
        else:
            all_passed = False
    
    print(f"\n📊 Результаты финального тестирования:")
    if all_passed:
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("✅ Избыточное форматирование ИСПРАВЛЕНО")
        print("✅ Markdown будет корректно отображаться в редакторах")
        return True
    else:
        print("❌ Некоторые тесты не пройдены")
        print("⚠️  Требуются дополнительные исправления")
        return False

if __name__ == "__main__":
    success = test_final_formatting()
    exit(0 if success else 1)