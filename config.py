#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт управления конфигурацией Telegram Channel Exporter
"""

import sys
from config_manager import ConfigManager


def main():
    """Главная функция управления конфигурацией"""
    print("🔧 Управление конфигурацией Telegram Channel Exporter")
    print("=" * 60)
    
    try:
        config_manager = ConfigManager()
        
        # Запуск интерактивной настройки
        if config_manager.interactive_setup():
            print("\n✅ Конфигурация успешно настроена!")
            print("📋 Теперь вы можете запустить программу командой: python3 start.py")
        else:
            print("\n❌ Настройка конфигурации отменена")
            
    except KeyboardInterrupt:
        print("\n\n👋 Настройка конфигурации прервана пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка настройки конфигурации: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()