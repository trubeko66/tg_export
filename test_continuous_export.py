#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест постоянного экспорта без Telegram
"""

import asyncio
from rich.console import Console
from continuous_export import ContinuousExporter

async def test_continuous_export():
    """Тест постоянного экспорта в демо-режиме"""
    console = Console()
    
    try:
        console.print("[blue]🧪 Тестирование постоянного экспорта в демо-режиме[/blue]")
        
        # Создаем экспортер
        exporter = ContinuousExporter(console)
        
        # Устанавливаем короткий интервал для теста
        exporter.check_interval = 5  # 5 секунд вместо 30
        
        # Инициализируем
        console.print("[blue]🔄 Инициализация...[/blue]")
        success = await exporter.initialize()
        
        if success:
            console.print("[green]✅ Инициализация успешна[/green]")
            console.print("[blue]🚀 Запуск тестового экспорта на 30 секунд...[/blue]")
            
            # Запускаем экспорт на короткое время
            await exporter.start_continuous_export()
        else:
            console.print("[red]❌ Ошибка инициализации[/red]")
            
    except Exception as e:
        console.print(f"[red]❌ Ошибка теста: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_continuous_export())
