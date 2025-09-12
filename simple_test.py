#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простой тест без Telegram
"""

import asyncio
from rich.console import Console

async def simple_test():
    """Простой тест"""
    console = Console()
    
    try:
        console.print("[blue]🧪 Простой тест[/blue]")
        
        # Тестируем импорт
        from continuous_export import ContinuousExporter
        console.print("[green]✅ Импорт успешен[/green]")
        
        # Создаем экспортер
        exporter = ContinuousExporter(console)
        console.print("[green]✅ Создание экспортера успешно[/green]")
        
        # Проверяем, есть ли файл каналов
        if exporter.config_manager.channels_file_exists():
            console.print("[green]✅ Файл каналов найден[/green]")
        else:
            console.print("[yellow]⚠️ Файл каналов не найден[/yellow]")
        
        console.print("[green]✅ Тест завершен успешно[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Ошибка теста: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(simple_test())
