#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест навигации по каналам (без зависимостей)
"""

import os

def clear_screen():
    """Очистка экрана"""
    os.system('clear' if os.name == 'posix' else 'cls')

def display_test_navigation():
    """Демонстрация исправленной навигации"""
    
    # Имитация каналов
    channels = [f"Тестовый канал {i+1}" for i in range(25)]
    page_size = 10
    current_page = 0
    total_pages = (len(channels) - 1) // page_size + 1
    
    while True:
        clear_screen()
        
        # Отображение текущей страницы
        print(f"📡 Доступные каналы (страница {current_page + 1} из {total_pages})")
        print("=" * 60)
        
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(channels))
        
        for i in range(start_idx, end_idx):
            print(f"{i + 1:3}. {channels[i]}")
        
        print("=" * 60)
        
        # Навигация (исправленная версия)
        nav_parts = []
        if current_page > 0:
            nav_parts.append("[p] - предыдущая страница")
        if current_page < total_pages - 1:
            nav_parts.append("[n] - следующая страница")
        nav_parts.append("[s] - выбрать каналы")
        nav_parts.append("[q] - выход")
        
        nav_text = "  |  ".join(nav_parts)
        print(f"\n{nav_text}")
        print(f"\nНавигация: Страница {current_page + 1} из {total_pages}")
        
        # Получение команды
        command = input("\nВведите команду (p/n/s/q): ").lower().strip()
        
        if command == 'p':
            if current_page > 0:
                current_page -= 1
            else:
                print("⚠ Вы уже на первой странице")
                input("Нажмите Enter для продолжения...")
        elif command == 'n':
            if current_page < total_pages - 1:
                current_page += 1
            else:
                print("⚠ Вы уже на последней странице")
                input("Нажмите Enter для продолжения...")
        elif command == 's':
            print("✓ Переход к выбору каналов...")
            break
        elif command == 'q':
            print("👋 Выход из программы")
            return
        else:
            print("❌ Неверная команда!")
            print("Доступные команды:")
            print("  p - предыдущая страница")
            print("  n - следующая страница") 
            print("  s - выбрать каналы")
            print("  q - выход")
            input("\nНажмите Enter для продолжения...")

if __name__ == "__main__":
    print("🧪 Тест навигации по каналам")
    print("Этот скрипт демонстрирует исправленную навигацию")
    print("=" * 50)
    input("Нажмите Enter для начала теста...")
    
    display_test_navigation()
    
    print("\n✅ Тест завершен. Навигация работает корректно!")