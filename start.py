#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт запуска Telegram Channel Exporter
"""

import sys
import subprocess
import importlib.util

def check_dependencies():
    """Проверка наличия зависимостей"""
    required_packages = [
        'telethon',
        'rich',
        'schedule',
        'requests',
        'markdown'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is None:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Отсутствуют следующие зависимости:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n🔧 Для установки выполните:")
        print("   pip install -r requirements.txt")
        return False
    
    return True

def main():
    """Главная функция запуска"""
    print("🚀 Telegram Channel Exporter")
    print("=" * 50)
    
    # Проверка зависимостей
    if not check_dependencies():
        sys.exit(1)
    
    print("✅ Все зависимости установлены")
    print("📡 Запуск программы...\n")
    
    try:
        # Импорт и запуск основной программы
        from telegram_exporter import main
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Программа завершена пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка запуска: {e}")
        print("📋 Проверьте файл export.log для получения подробной информации")
        sys.exit(1)

if __name__ == "__main__":
    main()