#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест фильтрации сообщений
"""

from content_filter import ContentFilter, FilterConfig

def test_filter():
    """Тестирование фильтрации различных сообщений"""
    filter_instance = ContentFilter(FilterConfig())
    
    # Тестовые сообщения
    test_messages = [
        # Обычные сообщения (должны пройти)
        "Привет! Как дела?",
        "Изучаю Python программирование",
        "Сегодня хорошая погода",
        "Новый курс по машинному обучению",
        "Обучение программированию с нуля",
        "Профессия веб-разработчика",
        
        # Реклама (должны быть отфильтрованы)
        "Реклама: скидка 50% на курсы",
        "Спонсорский пост от Skillbox",
        "Промокод SAVE20 для скидки",
        "На правах рекламы",
        
        # IT-школы без промо (должны пройти)
        "Skillbox выпустил новый курс",
        "Нетология проводит вебинар",
        "GeekBrains открыл новый поток",
        
        # IT-школы с промо (должны быть отфильтрованы)
        "Записаться на курс Skillbox",
        "Нетология: записаться на обучение",
        "GeekBrains: записаться на интенсив",
        "Митап от Skillbox",
        "Вебинар от Нетологии",
        "Семинар от GeekBrains",
        
        # Пустые сообщения
        "",
        "   ",
        None
    ]
    
    print("🧪 ТЕСТИРОВАНИЕ ФИЛЬТРАЦИИ СООБЩЕНИЙ")
    print("=" * 50)
    
    for i, message in enumerate(test_messages, 1):
        if message is None:
            message = ""
        
        should_filter, reason = filter_instance.should_filter_message(message)
        status = "❌ ОТФИЛЬТРОВАНО" if should_filter else "✅ ПРОЙДЕТ"
        
        print(f"{i:2d}. {status} - {reason}")
        print(f"    Текст: '{message}'")
        print()

if __name__ == "__main__":
    test_filter()
