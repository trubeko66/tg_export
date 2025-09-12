#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест ConfigManager
"""

import asyncio
from rich.console import Console

async def test_config_manager():
    """Тест ConfigManager"""
    console = Console()
    
    try:
        console.print("[blue]🧪 Тест ConfigManager[/blue]")
        
        # Тестируем импорт ConfigManager
        from config_manager import ConfigManager
        console.print("[green]✅ Импорт ConfigManager успешен[/green]")
        
        # Создаем ConfigManager
        config_manager = ConfigManager()
        console.print("[green]✅ Создание ConfigManager успешно[/green]")
        
        # Проверяем, есть ли файл каналов
        if config_manager.channels_file_exists():
            console.print("[green]✅ Файл каналов найден[/green]")
        else:
            console.print("[yellow]⚠️ Файл каналов не найден[/yellow]")
        
        console.print("[green]✅ Тест ConfigManager завершен успешно[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Ошибка теста ConfigManager: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_config_manager())
