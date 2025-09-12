#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простой тест импорта
"""

import asyncio
from rich.console import Console

async def test_simple_import():
    """Простой тест импорта"""
    console = Console()
    
    try:
        console.print("[blue]🧪 Простой тест импорта[/blue]")
        
        # Тестируем импорт по одному
        console.print("[blue]Тестируем импорт config_manager...[/blue]")
        from config_manager import ConfigManager
        console.print("[green]✅ ConfigManager импортирован[/green]")
        
        console.print("[blue]Тестируем создание ConfigManager...[/blue]")
        config_manager = ConfigManager()
        console.print("[green]✅ ConfigManager создан[/green]")
        
        console.print("[blue]Тестируем импорт continuous_export...[/blue]")
        from continuous_export import ContinuousExporter
        console.print("[green]✅ ContinuousExporter импортирован[/green]")
        
        console.print("[blue]Тестируем создание ContinuousExporter...[/blue]")
        exporter = ContinuousExporter(console)
        console.print("[green]✅ ContinuousExporter создан[/green]")
        
        console.print("[green]✅ Все тесты прошли успешно[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Ошибка теста: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple_import())
