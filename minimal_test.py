#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Минимальный тест
"""

import asyncio
from rich.console import Console

async def minimal_test():
    """Минимальный тест"""
    console = Console()
    
    try:
        console.print("[blue]🧪 Минимальный тест[/blue]")
        
        # Тестируем только импорт rich
        console.print("[green]✅ Rich импорт успешен[/green]")
        
        # Тестируем импорт asyncio
        console.print("[green]✅ Asyncio импорт успешен[/green]")
        
        # Тестируем импорт datetime
        from datetime import datetime
        console.print("[green]✅ Datetime импорт успешен[/green]")
        
        # Тестируем импорт pathlib
        from pathlib import Path
        console.print("[green]✅ Pathlib импорт успешен[/green]")
        
        console.print("[green]✅ Минимальный тест завершен успешно[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Ошибка теста: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(minimal_test())
