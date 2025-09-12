#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправления логики ID сообщений
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent))

from telegram_exporter import TelegramExporter
from config_manager import ConfigManager
from rich.console import Console

async def test_message_id_logic():
    """Тестируем исправленную логику получения ID сообщений"""
    
    console = Console()
    console.print("[bold blue]Тестирование исправленной логики ID сообщений[/bold blue]")
    
    try:
        # Инициализируем экспортер
        config_manager = ConfigManager()
        exporter = TelegramExporter(config_manager)
        
        # Загружаем каналы
        if not config_manager.channels_file_exists():
            console.print("[red]Файл .channels не найден![/red]")
            return
            
        channels = config_manager.import_channels()
        console.print(f"[green]Загружено {len(channels)} каналов[/green]")
        
        # Ищем канал с ID 1329220738 (из примера пользователя)
        target_channel = None
        for channel in channels:
            if channel.id == 1329220738:
                target_channel = channel
                break
                
        if not target_channel:
            console.print("[yellow]Канал с ID 1329220738 не найден в списке[/yellow]")
            console.print("Доступные каналы:")
            for i, channel in enumerate(channels[:5]):  # Показываем первые 5
                console.print(f"  {i+1}. {channel.title} (ID: {channel.id})")
            return
            
        console.print(f"[blue]Тестируем канал: {target_channel.title} (ID: {target_channel.id})[/blue]")
        console.print(f"Текущий last_message_id: {target_channel.last_message_id}")
        
        # Подключаемся к Telegram
        await exporter.initialize_client()
        
        # Получаем entity канала
        entity = await exporter.client.get_entity(target_channel.id)
        
        # Тестируем старую логику (получение только последнего сообщения)
        console.print("\n[bold]Старая логика (limit=1):[/bold]")
        old_messages = await exporter.client.get_messages(entity, limit=1)
        if old_messages:
            old_last_id = old_messages[0].id
            console.print(f"  Последнее сообщение по времени: ID = {old_last_id}")
        
        # Тестируем новую логику (получение нескольких сообщений и поиск максимального ID)
        console.print("\n[bold]Новая логика (limit=10, max ID):[/bold]")
        new_messages = await exporter.client.get_messages(entity, limit=10)
        if new_messages:
            message_ids = [msg.id for msg in new_messages]
            max_id_message = max(new_messages, key=lambda msg: msg.id)
            console.print(f"  Полученные ID: {message_ids}")
            console.print(f"  Максимальный ID: {max_id_message.id}")
            console.print(f"  Разница: {max_id_message.id - old_last_id if old_messages else 'N/A'}")
        
        # Проверяем, есть ли новые сообщения
        if new_messages:
            max_id = max(msg.id for msg in new_messages)
            if max_id > target_channel.last_message_id:
                console.print(f"\n[green]✅ Найдены новые сообщения![/green]")
                console.print(f"  Новых сообщений: {max_id - target_channel.last_message_id}")
            else:
                console.print(f"\n[yellow]Новых сообщений не найдено[/yellow]")
        
        await exporter.client.disconnect()
        
    except Exception as e:
        console.print(f"[red]Ошибка: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_message_id_logic())
