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
        
        # Тестируем с различными типами api_id
        test_cases = [
            ("Число", 1234567890),
            ("Строка", "1234567890"),
            ("Длинная строка", "12345678901234567890"),
            ("None", None),
            ("Пустая строка", ""),
        ]
        
        for test_name, api_id_value in test_cases:
            console.print(f"\n[cyan]Тест: {test_name} = {api_id_value}[/cyan]")
            
            # Устанавливаем тестовое значение
            if config_manager.config and hasattr(config_manager.config, 'telegram'):
                config_manager.config.telegram.api_id = api_id_value
                
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
