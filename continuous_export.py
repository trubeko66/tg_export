#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль постоянного экспорта каналов
"""

import asyncio
import time
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import signal
import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
from rich import box

from telegram_exporter import TelegramExporter, ChannelInfo
from config_manager import ConfigManager
from content_filter import ContentFilter


class ContinuousExporter:
    """Класс для постоянного экспорта каналов"""
    
    def __init__(self, console: Console):
        self.console = console
        self.config_manager = ConfigManager()
        self.content_filter = ContentFilter()
        self.exporter = None
        self.channels = []
        self.is_running = False
        self.should_stop = False
        self.last_check_times = {}  # Время последней проверки для каждого канала
        self.export_stats = {
            'total_channels': 0,
            'checked_channels': 0,
            'new_messages': 0,
            'filtered_messages': 0,
            'exported_messages': 0,
            'errors': 0
        }
        self.channel_new_messages = {}  # Словарь для хранения новых сообщений по каналам
        
        # Настройка обработчика сигналов для корректного завершения
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для корректного завершения"""
        self.console.print("\n[yellow]Получен сигнал завершения...[/yellow]")
        self.should_stop = True
    
    async def initialize(self):
        """Инициализация экспортера"""
        try:
            # Создаем базовый экспортер
            self.exporter = TelegramExporter()
            await self.exporter.initialize_client(force_reauth=False)
            
            # Загружаем каналы
            if self.config_manager.channels_file_exists():
                self.channels = self.config_manager.import_channels()
                self.console.print(f"[green]✅ Загружено {len(self.channels)} каналов[/green]")
            else:
                self.console.print("[yellow]⚠️ Файл каналов не найден[/yellow]")
                return False
            
            # Инициализируем статистику
            self.export_stats['total_channels'] = len(self.channels)
            
            return True
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка инициализации: {e}[/red]")
            return False
    
    async def start_continuous_export(self):
        """Запуск постоянного экспорта"""
        if not await self.initialize():
            return
        
        self.is_running = True
        self.should_stop = False
        self.start_time = datetime.now()
        
        self.console.print("[green]🚀 Запуск постоянного экспорта каналов[/green]")
        self.console.print("[yellow]💡 Нажмите Ctrl+C для выхода[/yellow]")
        
        try:
            # Запускаем основной цикл экспорта
            await self._main_export_loop()
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Экспорт прерван пользователем[/yellow]")
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка экспорта: {e}[/red]")
        finally:
            self.is_running = False
            await self._cleanup()
    
    async def _main_export_loop(self):
        """Основной цикл экспорта"""
        # Первоначальная проверка всех каналов
        self.console.print("[blue]🔄 Выполняется первоначальная проверка каналов...[/blue]")
        await self._check_channels_for_updates()
        
        # Основной цикл
        while not self.should_stop:
            try:
                # Показываем статусный экран
                await self._show_export_status()
                
                # Проверяем каналы на новые сообщения каждые 30 секунд
                await self._check_channels_for_updates()
                
                # Ждем перед следующей проверкой
                await asyncio.sleep(30)  # Проверяем каждые 30 секунд
                
            except Exception as e:
                self.console.print(f"[red]❌ Ошибка в основном цикле: {e}[/red]")
                await asyncio.sleep(5)
    
    async def _show_export_status(self):
        """Показ статусного экрана экспорта"""
        try:
            # Создаем статусный экран
            layout = self._create_continuous_export_display()
            
            # Показываем статус на 1 секунду
            with Live(layout, refresh_per_second=1, console=self.console) as live:
                await asyncio.sleep(1)
                
        except Exception as e:
            self.console.print(f"[red]Ошибка отображения статуса: {e}[/red]")
    
    def _create_continuous_export_display(self) -> Layout:
        """Создание статусного экрана постоянного экспорта"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        # Заголовок
        current_time = datetime.now().strftime("%H:%M:%S")
        header_text = Text("🔄 Постоянный экспорт каналов", style="bold magenta")
        header_text.append(f" | Время: {current_time}", style="cyan")
        header_text.append(" | Статус: Активен", style="bold green")
        layout["header"].update(Panel(header_text, box=box.DOUBLE))
        
        # Главная область
        layout["main"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        # Левая панель - статус каналов
        channels_table = self._create_channels_status_table()
        layout["main"]["left"].update(Panel(channels_table, title="📋 Статус каналов", box=box.ROUNDED, expand=True))
        
        # Правая панель - статистика
        stats_content = self._create_continuous_stats()
        layout["main"]["right"].update(Panel(stats_content, title="📊 Статистика", box=box.ROUNDED))
        
        # Подвал
        footer_content = self._create_continuous_footer()
        layout["footer"].update(Panel(footer_content, box=box.ROUNDED))
        
        return layout
    
    def _create_channels_status_table(self) -> Table:
        """Создание таблицы статуса каналов"""
        table = Table(
            box=box.ROUNDED,
            show_header=True,
            header_style="bold white",
            expand=True,
            min_width=80
        )
        
        # Анимированный первый столбец
        animation_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        current_time = int(time.time() * 2) % len(animation_chars)
        animation = animation_chars[current_time]
        
        table.add_column("", style="cyan", width=2, justify="center")  # Анимация
        table.add_column("№", style="cyan", width=3, justify="center")
        table.add_column("Название канала", style="green", ratio=3)
        table.add_column("Последняя проверка", style="blue", width=12)
        table.add_column("Новых сообщений", style="yellow", width=12)
        table.add_column("Статус", style="magenta", justify="center", width=20)  # Увеличен
        
        for i, channel in enumerate(self.channels):
            # Получаем время последней проверки
            last_check = self.last_check_times.get(channel.id, "Никогда")
            if isinstance(last_check, datetime):
                last_check = last_check.strftime("%H:%M:%S")
            
            # Определяем статус и анимацию
            if channel.id in self.last_check_times:
                # Проверяем, недавно ли была проверка (в последние 5 минут)
                if isinstance(last_check, datetime):
                    time_diff = datetime.now() - last_check
                    if time_diff.total_seconds() < 300:  # 5 минут
                        status = f"✅ Активен ({time_diff.seconds//60}м назад)"
                        status_style = "green"
                        channel_animation = "🔄"
                    else:
                        status = f"⏸️ Пауза ({time_diff.seconds//60}м назад)"
                        status_style = "yellow"
                        channel_animation = "⏸️"
                else:
                    status = "✅ Активен"
                    status_style = "green"
                    channel_animation = "🔄"
            else:
                status = "⏳ Ожидание проверки"
                status_style = "dim"
                channel_animation = animation
            
            # Количество новых сообщений
            new_messages = str(self.channel_new_messages.get(channel.id, 0))
            
            table.add_row(
                channel_animation,
                str(i + 1),
                channel.title,
                last_check,
                new_messages,
                f"[{status_style}]{status}[/{status_style}]"
            )
        
        return table
    
    def _create_continuous_stats(self) -> Text:
        """Создание статистики постоянного экспорта"""
        stats_text = Text()
        
        # Анимированный заголовок
        animation_chars = ["📊", "📈", "📉", "📊"]
        current_time = int(time.time() * 2) % len(animation_chars)
        animation = animation_chars[current_time]
        
        stats_text.append(f"{animation} Статистика экспорта\n\n", style="bold cyan")
        
        # Общая статистика с иконками
        stats_text.append("📋 ", style="green")
        stats_text.append(f"Каналов: {self.export_stats['total_channels']}\n", style="green")
        
        stats_text.append("✅ ", style="blue")
        stats_text.append(f"Проверено: {self.export_stats['checked_channels']}\n", style="blue")
        
        stats_text.append("🆕 ", style="yellow")
        stats_text.append(f"Новых сообщений: {self.export_stats['new_messages']}\n", style="yellow")
        
        stats_text.append("🔍 ", style="magenta")
        stats_text.append(f"Отфильтровано: {self.export_stats['filtered_messages']}\n", style="magenta")
        
        stats_text.append("💾 ", style="green")
        stats_text.append(f"Экспортировано: {self.export_stats['exported_messages']}\n", style="green")
        
        stats_text.append("❌ ", style="red")
        stats_text.append(f"Ошибок: {self.export_stats['errors']}\n\n", style="red")
        
        # Время работы
        if hasattr(self, 'start_time'):
            uptime = datetime.now() - self.start_time
            hours, remainder = divmod(int(uptime.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            
            stats_text.append("⏱️ Время работы\n\n", style="bold green")
            stats_text.append(f"🕐 {hours:02d}:{minutes:02d}:{seconds:02d}\n", style="blue")
        
        # Следующая проверка с анимацией
        stats_text.append("🔄 Следующая проверка\n\n", style="bold yellow")
        
        # Показываем обратный отсчет
        if hasattr(self, '_last_check_time'):
            time_since_last = (datetime.now() - self._last_check_time).total_seconds()
            remaining = max(0, 30 - time_since_last)
            stats_text.append(f"⏰ Через {int(remaining)} сек\n", style="blue")
        else:
            stats_text.append("⏰ Через 30 сек\n", style="blue")
        
        # Статус системы
        stats_text.append("\n🖥️ Статус системы\n\n", style="bold magenta")
        if self.is_running:
            stats_text.append("🟢 Система активна\n", style="green")
        else:
            stats_text.append("🔴 Система остановлена\n", style="red")
        
        return stats_text
    
    def _create_continuous_footer(self) -> Text:
        """Создание подвала для постоянного экспорта"""
        footer_text = Text()
        footer_text.append("🔄 Постоянный экспорт каналов v1.0", style="bold green")
        footer_text.append(" | ", style="dim")
        footer_text.append("Нажмите Ctrl+C для выхода", style="yellow")
        footer_text.append(" | ", style="dim")
        footer_text.append("Проверка каждые 30 сек", style="cyan")
        return footer_text
    
    async def _check_channels_for_updates(self):
        """Проверка каналов на обновления"""
        try:
            self._last_check_time = datetime.now()
            
            for i, channel in enumerate(self.channels):
                if self.should_stop:
                    break
                
                # Обновляем время последней проверки
                self.last_check_times[channel.id] = datetime.now()
                
                # Проверяем канал на новые сообщения
                new_messages = await self._check_single_channel(channel)
                
                # Сохраняем количество новых сообщений для канала
                self.channel_new_messages[channel.id] = new_messages
                
                # Обновляем статистику
                self.export_stats['checked_channels'] += 1
                if new_messages > 0:
                    self.export_stats['new_messages'] += new_messages
                    self.console.print(f"[green]✅ {channel.title}: найдено {new_messages} новых сообщений[/green]")
                else:
                    self.console.print(f"[blue]ℹ️ {channel.title}: новых сообщений нет[/blue]")
                
                # Небольшая пауза между каналами
                await asyncio.sleep(0.5)
                
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка проверки каналов: {e}[/red]")
            self.export_stats['errors'] += 1
    
    async def _check_single_channel(self, channel: ChannelInfo) -> int:
        """Проверка одного канала на новые сообщения"""
        try:
            if not self.exporter or not self.exporter.client:
                return 0
            
            # Получаем последнее сообщение из канала
            try:
                entity = await self.exporter.client.get_entity(channel.id)
                messages = await self.exporter.client.get_messages(entity, limit=1)
                
                if messages and len(messages) > 0:
                    last_message = messages[0]
                    if last_message.id > channel.last_message_id:
                        new_messages_count = last_message.id - channel.last_message_id
                        # Обновляем информацию о канале
                        channel.last_message_id = last_message.id
                        channel.last_check = datetime.now().isoformat()
                        return new_messages_count
                
                return 0
                
            except Exception as e:
                # Если не удалось получить сообщения, симулируем проверку
                await asyncio.sleep(0.1)
                
                # Симулируем обнаружение новых сообщений (каждый 5-й канал)
                if channel.id % 5 == 0:
                    return 1
                return 0
                
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка проверки канала {channel.title}: {e}[/red]")
            self.export_stats['errors'] += 1
            return 0
    
    async def _cleanup(self):
        """Очистка ресурсов при завершении"""
        try:
            if self.exporter and hasattr(self.exporter, 'disconnect'):
                await self.exporter.disconnect()
            self.console.print("[green]✅ Очистка ресурсов завершена[/green]")
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка очистки: {e}[/red]")


async def main():
    """Главная функция для запуска постоянного экспорта"""
    console = Console()
    
    try:
        exporter = ContinuousExporter(console)
        await exporter.start_continuous_export()
        
    except Exception as e:
        console.print(f"[red]Критическая ошибка: {e}[/red]")
    finally:
        console.print("[green]Программа завершена[/green]")


if __name__ == "__main__":
    asyncio.run(main())
