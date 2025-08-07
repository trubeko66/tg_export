#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Channel Exporter
Программа для мониторинга и экспорта Telegram каналов
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from pathlib import Path
import re
import schedule
import time
from dataclasses import dataclass, asdict
import html
import markdown

from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat, User, MessageMediaPhoto, MessageMediaDocument, Message
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, TaskID
from rich import box
import requests

from exporters import (
    MessageData, JSONExporter, HTMLExporter, MarkdownExporter, MediaDownloader
)


@dataclass
class ChannelInfo:
    """Информация о канале"""
    id: int
    title: str
    username: Optional[str]
    last_message_id: int = 0
    total_messages: int = 0
    last_check: Optional[str] = None


@dataclass
class ExportStats:
    """Статистика экспорта"""
    total_channels: int = 0
    total_messages: int = 0
    total_size_mb: float = 0.0
    last_export_time: Optional[str] = None
    export_errors: int = 0


class TelegramExporter:
    def __init__(self):
        self.console = Console()
        self.client: Optional[TelegramClient] = None
        self.channels: List[ChannelInfo] = []
        self.channels_file = Path('.channels')
        self.stats = ExportStats()
        self.bot_token: Optional[str] = None
        self.chat_id: Optional[str] = None
        self.running = True
        
        # Настройка логирования
        self.setup_logging()
        
    def setup_logging(self):
        """Настройка системы логирования"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('export.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    async def initialize_client(self):
        """Инициализация Telegram клиента"""
        try:
            api_id = Prompt.ask("Введите API ID", password=False)
            api_hash = Prompt.ask("Введите API Hash", password=True)
            phone = Prompt.ask("Введите номер телефона")
            
            self.client = TelegramClient('session_name', api_id, api_hash)
            await self.client.start(phone)
            
            if await self.client.is_user_authorized():
                self.console.print("[green]✓ Успешная авторизация в Telegram[/green]")
                self.logger.info("Successful Telegram authorization")
                return True
            else:
                self.console.print("[red]✗ Ошибка авторизации[/red]")
                return False
                
        except Exception as e:
            self.console.print(f"[red]Ошибка инициализации клиента: {e}[/red]")
            self.logger.error(f"Client initialization error: {e}")
            return False
    
    def setup_bot_notifications(self):
        """Настройка уведомлений через бота"""
        if Confirm.ask("Настроить уведомления через Telegram бота?"):
            self.bot_token = Prompt.ask("Введите токен бота")
            self.chat_id = Prompt.ask("Введите Chat ID для уведомлений")
            
            # Проверка работы бота
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
                response = requests.get(url)
                if response.status_code == 200:
                    self.console.print("[green]✓ Бот настроен успешно[/green]")
                else:
                    self.console.print("[yellow]⚠ Не удалось проверить бота[/yellow]")
            except Exception as e:
                self.console.print(f"[yellow]⚠ Ошибка проверки бота: {e}[/yellow]")
    
    async def send_notification(self, message: str):
        """Отправка уведомления через бота"""
        if not self.bot_token or not self.chat_id:
            return
            
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            requests.post(url, data=data)
        except Exception as e:
            self.logger.error(f"Notification error: {e}")
    
    def load_channels(self) -> bool:
        """Загрузка списка каналов из файла"""
        if self.channels_file.exists():
            try:
                with open(self.channels_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.channels = [ChannelInfo(**item) for item in data]
                return True
            except Exception as e:
                self.logger.error(f"Error loading channels: {e}")
        return False
    
    def save_channels(self):
        """Сохранение списка каналов в файл"""
        try:
            with open(self.channels_file, 'w', encoding='utf-8') as f:
                json.dump([asdict(channel) for channel in self.channels], f, 
                         ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving channels: {e}")
    
    async def select_channels(self):
        """Выбор каналов для мониторинга"""
        self.console.print("\n[bold blue]Получение списка каналов...[/bold blue]")
        
        try:
            dialogs = []
            async for dialog in self.client.iter_dialogs():
                if hasattr(dialog.entity, 'broadcast') and dialog.entity.broadcast:
                    dialogs.append(dialog)
            
            if not dialogs:
                self.console.print("[yellow]Каналы не найдены[/yellow]")
                return
            
            # Создание таблицы для выбора
            table = Table(title="Доступные каналы", box=box.ROUNDED)
            table.add_column("№", style="cyan", width=4)
            table.add_column("Название", style="green")
            table.add_column("Username", style="blue")
            table.add_column("Участников", style="yellow", justify="right")
            
            for i, dialog in enumerate(dialogs, 1):
                username = f"@{dialog.entity.username}" if dialog.entity.username else "—"
                participants = getattr(dialog.entity, 'participants_count', 0)
                table.add_row(str(i), dialog.title, username, str(participants))
            
            self.console.print(table)
            
            # Выбор каналов
            selection = Prompt.ask(
                "\nВведите номера каналов через запятую (или 'all' для всех)"
            )
            
            if selection.lower() == 'all':
                selected_indices = list(range(len(dialogs)))
            else:
                selected_indices = [int(x.strip()) - 1 for x in selection.split(',') 
                                 if x.strip().isdigit()]
            
            # Добавление выбранных каналов
            for i in selected_indices:
                if 0 <= i < len(dialogs):
                    dialog = dialogs[i]
                    channel_info = ChannelInfo(
                        id=dialog.entity.id,
                        title=dialog.title,
                        username=dialog.entity.username
                    )
                    self.channels.append(channel_info)
            
            self.save_channels()
            self.console.print(f"[green]✓ Выбрано {len(self.channels)} каналов[/green]")
            
        except Exception as e:
            self.console.print(f"[red]Ошибка выбора каналов: {e}[/red]")
            self.logger.error(f"Channel selection error: {e}")
    
    def create_status_display(self) -> Layout:
        """Создание статусного экрана"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )
        
        # Заголовок
        header_text = Text("Telegram Channel Exporter", style="bold magenta")
        header_text.append(" | Статус: Работает", style="bold green")
        layout["header"].update(Panel(header_text, box=box.DOUBLE))
        
        # Информация о каналах
        channels_table = Table(title="Выбранные каналы", box=box.ROUNDED)
        channels_table.add_column("Канал", style="green")
        channels_table.add_column("Последняя проверка", style="blue")
        channels_table.add_column("Сообщений", style="yellow", justify="right")
        
        for channel in self.channels:
            last_check = channel.last_check or "Никогда"
            channels_table.add_row(
                channel.title[:30] + "..." if len(channel.title) > 30 else channel.title,
                last_check,
                str(channel.total_messages)
            )
        
        layout["left"].update(Panel(channels_table))
        
        # Статистика
        stats_text = Text()
        stats_text.append(f"Всего каналов: {self.stats.total_channels}\n", style="cyan")
        stats_text.append(f"Всего сообщений: {self.stats.total_messages}\n", style="green")
        stats_text.append(f"Объем данных: {self.stats.total_size_mb:.2f} МБ\n", style="yellow")
        stats_text.append(f"Ошибки: {self.stats.export_errors}\n", style="red")
        stats_text.append(f"Последний экспорт: {self.stats.last_export_time or 'Никогда'}\n", style="blue")
        
        layout["right"].update(Panel(stats_text, title="Статистика"))
        
        # Подвал с инструкциями
        footer_text = Text("Нажмите Ctrl+C для завершения работы", style="bold red")
        layout["footer"].update(Panel(footer_text))
        
        return layout
    
    async def run_scheduler(self):
        """Запуск планировщика задач"""
        def schedule_export():
            """Функция для планировщика"""
            if self.running:
                asyncio.create_task(self.export_all_channels())
        
        schedule.every().day.at("00:00").do(schedule_export)
        
        # Также добавляем возможность запуска экспорта при первом старте
        # если каналы не проверялись больше суток
        if self.channels:
            need_initial_export = False
            for channel in self.channels:
                if not channel.last_check:
                    need_initial_export = True
                    break
                try:
                    last_check = datetime.strptime(channel.last_check, "%Y-%m-%d %H:%M:%S")
                    if (datetime.now() - last_check).days >= 1:
                        need_initial_export = True
                        break
                except:
                    need_initial_export = True
                    break
            
            if need_initial_export:
                self.logger.info("Starting initial export for channels that haven't been checked recently")
                asyncio.create_task(self.export_all_channels())
        
        while self.running:
            schedule.run_pending()
            await asyncio.sleep(60)  # Проверка каждую минуту
    
    async def export_all_channels(self):
        """Экспорт всех каналов"""
        self.logger.info("Starting scheduled export of all channels")
        
        for channel in self.channels:
            try:
                await self.export_channel(channel)
            except Exception as e:
                self.logger.error(f"Export error for channel {channel.title}: {e}")
                self.stats.export_errors += 1
        
        self.stats.last_export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    async def export_channel(self, channel: ChannelInfo):
        """Экспорт конкретного канала"""
        try:
            self.logger.info(f"Starting export for channel: {channel.title}")
            
            # Создание директории для канала
            channel_dir = Path(channel.title.replace('/', '_').replace('\\', '_'))
            channel_dir.mkdir(exist_ok=True)
            
            # Получение канала
            entity = await self.client.get_entity(channel.id)
            
            # Инициализация экспортеров
            json_exporter = JSONExporter(channel.title, channel_dir)
            html_exporter = HTMLExporter(channel.title, channel_dir)
            md_exporter = MarkdownExporter(channel.title, channel_dir)
            media_downloader = MediaDownloader(channel_dir)
            
            # Получение сообщений
            messages_data = []
            total_size = 0.0
            new_messages_count = 0
            
            # Получаем сообщения начиная с последнего обработанного
            min_id = channel.last_message_id
            
            try:
                async for message in self.client.iter_messages(entity, min_id=min_id):
                    try:
                        # Загрузка медиафайлов
                        media_path = None
                        media_type = None
                        
                        if message.media:
                            media_path = await media_downloader.download_media(self.client, message)
                            if media_path:
                                file_size = media_downloader.get_file_size_mb(channel_dir / media_path)
                                total_size += file_size
                                
                            # Определение типа медиа
                            if isinstance(message.media, MessageMediaPhoto):
                                media_type = "Фото"
                            elif isinstance(message.media, MessageMediaDocument):
                                media_type = "Документ"
                            else:
                                media_type = "Другое медиа"
                        
                        # Создание объекта данных сообщения
                        msg_data = MessageData(
                            id=message.id,
                            date=message.date,
                            text=message.text or "",
                            author=None,  # Каналы обычно не показывают авторов
                            media_type=media_type,
                            media_path=media_path,
                            views=getattr(message, 'views', 0) or 0,
                            forwards=getattr(message, 'forwards', 0) or 0,
                            replies=getattr(message, 'replies', {}).get('replies', 0) if hasattr(message, 'replies') and message.replies else 0,
                            edited=message.edit_date
                        )
                        
                        messages_data.append(msg_data)
                        new_messages_count += 1
                        
                        # Обновляем последний ID сообщения
                        if message.id > channel.last_message_id:
                            channel.last_message_id = message.id
                            
                    except Exception as e:
                        self.logger.error(f"Error processing message {message.id}: {e}")
                        self.stats.export_errors += 1
            
            except FloodWaitError as e:
                self.logger.warning(f"FloodWait error for channel {channel.title}: waiting {e.seconds} seconds")
                await asyncio.sleep(e.seconds)
                # Повторная попытка после ожидания
                await self.export_channel(channel)
                return
            except Exception as e:
                self.logger.error(f"Error iterating messages for channel {channel.title}: {e}")
                self.stats.export_errors += 1
            
            if messages_data:
                # Сортировка сообщений по дате (старые сначала)
                messages_data.sort(key=lambda x: x.date or datetime.min)
                
                # Экспорт в различные форматы
                json_file = json_exporter.export_messages(messages_data)
                html_file = html_exporter.export_messages(messages_data)
                md_file = md_exporter.export_messages(messages_data)
                
                # Обновление статистики канала
                channel.total_messages += len(messages_data)
                channel.last_check = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Обновление общей статистики
                self.stats.total_messages += len(messages_data)
                self.stats.total_size_mb += total_size
                
                # Отправка уведомления
                if new_messages_count > 0:
                    notification = self._create_notification(channel, new_messages_count, True)
                    await self.send_notification(notification)
                
                self.logger.info(f"Successfully exported {len(messages_data)} messages from {channel.title}")
                
            else:
                self.logger.info(f"No new messages found in {channel.title}")
                channel.last_check = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Сохранение обновленной информации о каналах
            self.save_channels()
            
        except Exception as e:
            self.logger.error(f"Export error for channel {channel.title}: {e}")
            self.stats.export_errors += 1
            
            # Отправка уведомления об ошибке
            notification = self._create_notification(channel, 0, False, str(e))
            await self.send_notification(notification)
    
    def _create_notification(self, channel: ChannelInfo, messages_count: int, success: bool, error: str = None) -> str:
        """Создание текста уведомления"""
        if success and messages_count > 0:
            return f"""
📢 <b>Новые сообщения в канале</b>

🔗 <b>Канал:</b> {channel.title}
📊 <b>Новых сообщений:</b> {messages_count}
📅 <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
✅ <b>Статус:</b> Успешно экспортировано

📁 Файлы сохранены в папку: {channel.title}
            """.strip()
        elif success and messages_count == 0:
            return f"""
📢 <b>Проверка канала завершена</b>

🔗 <b>Канал:</b> {channel.title}
📊 <b>Новых сообщений:</b> не найдено
📅 <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
✅ <b>Статус:</b> Проверка выполнена
            """.strip()
        else:
            return f"""
📢 <b>Ошибка экспорта канала</b>

🔗 <b>Канал:</b> {channel.title}
📅 <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
❌ <b>Статус:</b> Ошибка
🔍 <b>Причина:</b> {error or 'Неизвестная ошибка'}
            """.strip()
    
    async def main_loop(self):
        """Основной цикл программы"""
        try:
            with Live(self.create_status_display(), refresh_per_second=1) as live:
                # Запуск планировщика в фоне
                scheduler_task = asyncio.create_task(self.run_scheduler())
                
                # Основной цикл
                while self.running:
                    live.update(self.create_status_display())
                    await asyncio.sleep(1)
                    
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Получен сигнал завершения...[/yellow]")
            self.running = False
            
        finally:
            if self.client:
                await self.client.disconnect()
    
    async def run(self):
        """Главный метод запуска программы"""
        self.console.print(Panel.fit(
            "[bold blue]Telegram Channel Exporter[/bold blue]\n"
            "Программа для мониторинга и экспорта каналов Telegram",
            box=box.DOUBLE
        ))
        
        # Инициализация клиента
        if not await self.initialize_client():
            return
        
        # Настройка уведомлений
        self.setup_bot_notifications()
        
        # Загрузка или выбор каналов
        if self.channels_file.exists() and Confirm.ask("Использовать сохраненный список каналов?"):
            self.load_channels()
        else:
            await self.select_channels()
        
        if not self.channels:
            self.console.print("[red]Каналы не выбраны. Завершение работы.[/red]")
            return
        
        # Обновление статистики
        self.stats.total_channels = len(self.channels)
        
        # Запуск основного цикла
        await self.main_loop()


async def main():
    """Точка входа в программу"""
    exporter = TelegramExporter()
    await exporter.run()


if __name__ == "__main__":
    asyncio.run(main())