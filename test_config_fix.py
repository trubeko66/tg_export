#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправления ошибки с api_id
"""

import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent))

from config_manager import ConfigManager
from rich.console import Console

def test_config_display():
    """Тестируем отображение конфигурации с различными типами api_id"""
    
    console = Console()
    console.print("[bold blue]Тестирование исправления ошибки с api_id[/bold blue]")
    
    try:
        # Создаем менеджер конфигурации
        config_manager = ConfigManager()
        
        # Тестируем с различными типами api_id и chat_id
        test_cases = [
            ("API ID - Число", "api_id", 1234567890),
            ("API ID - Строка", "api_id", "1234567890"),
            ("API ID - Длинная строка", "api_id", "12345678901234567890"),
            ("API ID - None", "api_id", None),
            ("API ID - Пустая строка", "api_id", ""),
            ("Chat ID - Число", "chat_id", 1234567890),
            ("Chat ID - Строка", "chat_id", "1234567890"),
            ("Chat ID - None", "chat_id", None),
        ]
        
        for test_name, field_name, test_value in test_cases:
            console.print(f"\n[cyan]Тест: {test_name} = {test_value}[/cyan]")
            
            # Устанавливаем тестовое значение
            if config_manager.config and hasattr(config_manager.config, 'telegram'):
                if field_name == "api_id":
                    config_manager.config.telegram.api_id = test_value
                elif field_name == "chat_id" and hasattr(config_manager.config, 'bot'):
                    config_manager.config.bot.chat_id = test_value
                
                # Пытаемся отобразить конфигурацию
                try:
                    config_manager.show_current_config()
                    console.print(f"[green]✅ Успешно: {test_name}[/green]")
                except Exception as e:
                    console.print(f"[red]❌ Ошибка: {test_name} - {e}[/red]")
            else:
                console.print(f"[yellow]⚠️ Конфигурация не инициализирована[/yellow]")
        
        console.print("\n[bold green]Тестирование завершено![/bold green]")
        
    except Exception as e:
        console.print(f"[red]Ошибка тестирования: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_config_display()
