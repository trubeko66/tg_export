#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест для отладки фильтрации сообщений
"""

from content_filter import ContentFilter

def test_filter_debug():
    """Тестирование фильтрации с отладкой"""
    print("🔍 Тестирование фильтрации сообщений...")
    
    # Создаем фильтр контента
    content_filter = ContentFilter()
    
    # Тестовые сообщения, которые могут быть в IT каналах
    test_messages = [
        "Привет! Как дела?",
        "Реклама: купите наш продукт!",
        "Записаться на курс программирования",
        "Новости IT индустрии",
        "Набор в школу программирования",
        "Python для начинающих - бесплатный курс",
        "DevOps практики для Linux",
        "Анализ данных с помощью Python",
        "Курс машинного обучения",
        "Бесплатный вебинар по программированию",
        "Новости из мира IT",
        "Интересная статья о Linux",
        "Обзор новых технологий",
        "Советы по программированию",
        "Реклама курса программирования"
    ]
    
    print(f"\n📋 Тестируем {len(test_messages)} сообщений:")
    print("=" * 80)
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n{i:2d}. Сообщение: '{message}'")
        
        should_filter, filter_reason = content_filter.should_filter_message(message)
        
        if should_filter:
            print(f"    ❌ ОТФИЛЬТРОВАНО: {filter_reason}")
        else:
            print(f"    ✅ ПРИНЯТО")
    
    print("\n" + "=" * 80)
    print("✅ Тест завершен!")
    print("\n💡 Если сообщения фильтруются неправильно, проверьте:")
    print("   - Настройки фильтра в content_filter.py")
    print("   - Ключевые слова в ad_markers, school_keywords, event_keywords, promo_keywords")

if __name__ == "__main__":
    test_filter_debug()
