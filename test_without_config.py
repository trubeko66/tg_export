#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест без ConfigManager
"""

import asyncio
from rich.console import Console

async def test_without_config():
    """Тест без ConfigManager"""
    console = Console()
    
    try:
        console.print("[blue]🧪 Тест без ConfigManager[/blue]")
        
        # Тестируем импорт только основных модулей
        from content_filter import ContentFilter
        console.print("[green]✅ Импорт ContentFilter успешен[/green]")
        
        from telegram_notifications import TelegramNotifier
        console.print("[green]✅ Импорт TelegramNotifier успешен[/green]")
        
        from message_detector import MessageDetector
        console.print("[green]✅ Импорт MessageDetector успешен[/green]")
        
        # Создаем объекты
        content_filter = ContentFilter()
        console.print("[green]✅ Создание ContentFilter успешно[/green]")
        
        telegram_notifier = TelegramNotifier(console)
        console.print("[green]✅ Создание TelegramNotifier успешно[/green]")
        
        message_detector = MessageDetector()
        console.print("[green]✅ Создание MessageDetector успешно[/green]")
        
        console.print("[green]✅ Тест завершен успешно[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Ошибка теста: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_without_config())
