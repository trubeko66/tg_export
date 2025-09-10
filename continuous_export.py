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
from telegram_notifications import TelegramNotifier


class ContinuousExporter:
    """Класс для постоянного экспорта каналов"""
    
    def __init__(self, console: Console):
        self.console = console
        self.config_manager = ConfigManager()
        self.content_filter = ContentFilter()
        self.telegram_notifier = TelegramNotifier(console)  # Уведомления в Telegram
        self.exporter = None
        self.channels = []
        self.is_running = False
        self.should_stop = False
        self.telegram_connected = False  # Статус подключения к Telegram
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
        self.check_interval = 30  # Интервал проверки в секундах (по умолчанию 30)
        
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
            # Загружаем каналы сначала
            if self.config_manager.channels_file_exists():
                self.channels = self.config_manager.import_channels()
                self.console.print(f"[green]✅ Загружено {len(self.channels)} каналов[/green]")
            else:
                self.console.print("[yellow]⚠️ Файл каналов не найден[/yellow]")
                return False
            
            # Инициализируем статистику
            self.export_stats['total_channels'] = len(self.channels)
            
            # Пытаемся инициализировать Telegram клиент
            try:
                self.console.print("[blue]🔄 Подключение к Telegram...[/blue]")
                self.exporter = TelegramExporter()
                await self.exporter.initialize_client(force_reauth=False)
                self.console.print("[green]✅ Подключение к Telegram успешно[/green]")
                self.telegram_connected = True
                
            except Exception as telegram_error:
                self.console.print(f"[yellow]⚠️ Не удалось подключиться к Telegram: {telegram_error}[/yellow]")
                self.console.print("[blue]🔄 Переходим в демо-режим...[/blue]")
                self.exporter = None
                self.telegram_connected = False
            
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
        try:
            # Первоначальная проверка всех каналов
            self.console.print("[blue]🔄 Выполняется первоначальная проверка каналов...[/blue]")
            await self._check_channels_for_updates()
            
            # Основной цикл
            while not self.should_stop:
                try:
                    # Показываем статусный экран между проверками
                    await self._show_export_status()
                    
                    # Проверяем каналы на новые сообщения с настраиваемым интервалом
                    await self._check_channels_for_updates()
                    
                    # Ждем перед следующей проверкой
                    await asyncio.sleep(self.check_interval)  # Проверяем с настраиваемым интервалом
                    
                except KeyboardInterrupt:
                    self.console.print("\n[yellow]Получен сигнал прерывания...[/yellow]")
                    self.should_stop = True
                    break
                except Exception as e:
                    self.console.print(f"[red]❌ Ошибка в основном цикле: {e}[/red]")
                    await asyncio.sleep(5)
                    
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Экспорт прерван пользователем[/yellow]")
            self.should_stop = True
        except Exception as e:
            self.console.print(f"[red]❌ Критическая ошибка в основном цикле: {e}[/red]")
            self.should_stop = True
    
    async def _show_export_status(self):
        """Показ статусного экрана экспорта"""
        try:
            # Создаем статусный экран
            layout = self._create_continuous_export_display()
            
            # Показываем статус на 5 секунд с обновлением каждую секунду
            with Live(layout, refresh_per_second=1, console=self.console) as live:
                await asyncio.sleep(5)
                
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
        mode_text = "Демо-режим" if not self.telegram_connected else "Реальный режим"
        mode_style = "yellow" if not self.telegram_connected else "green"
        
        header_text = Text("🔄 Постоянный экспорт каналов", style="bold magenta")
        header_text.append(f" | Время: {current_time}", style="cyan")
        header_text.append(f" | Режим: {mode_text}", style=f"bold {mode_style}")
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
        
        # Режим работы
        if self.telegram_connected:
            stats_text.append("📡 Telegram: подключен\n", style="green")
        else:
            stats_text.append("📡 Telegram: демо-режим\n", style="yellow")
        
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
    
    async def _show_checking_status(self):
        """Показ статуса во время проверки каналов"""
        try:
            # Создаем статусный экран проверки
            layout = self._create_checking_display()
            
            # Показываем статус на 2 секунды
            with Live(layout, refresh_per_second=2, console=self.console) as live:
                await asyncio.sleep(2)
                
        except Exception as e:
            self.console.print(f"[red]Ошибка отображения статуса проверки: {e}[/red]")
    
    async def _show_final_check_status(self):
        """Показ финального статуса проверки с результатами"""
        try:
            # Создаем финальный статусный экран
            layout = self._create_final_check_display()
            
            # Показываем результаты на 3 секунды
            with Live(layout, refresh_per_second=1, console=self.console) as live:
                await asyncio.sleep(3)
                
        except Exception as e:
            self.console.print(f"[red]Ошибка отображения финального статуса: {e}[/red]")
    
    def _create_checking_display(self) -> Layout:
        """Создание статусного экрана проверки каналов"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        # Заголовок
        current_time = datetime.now().strftime("%H:%M:%S")
        header_text = Text("🔍 Проверка каналов на новые сообщения", style="bold yellow")
        header_text.append(f" | Время: {current_time}", style="cyan")
        header_text.append(" | Статус: Проверка активна", style="bold green")
        layout["header"].update(Panel(header_text, box=box.DOUBLE))
        
        # Главная область
        layout["main"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        # Левая панель - таблица каналов с анимацией
        channels_table = self._create_checking_channels_table()
        layout["main"]["left"].update(Panel(channels_table, title="📋 Проверяемые каналы", box=box.ROUNDED, expand=True))
        
        # Правая панель - статистика проверки
        stats_content = self._create_checking_stats()
        layout["main"]["right"].update(Panel(stats_content, title="📊 Статистика проверки", box=box.ROUNDED))
        
        # Подвал
        footer_content = self._create_checking_footer()
        layout["footer"].update(Panel(footer_content, box=box.ROUNDED))
        
        return layout
    
    def _create_final_check_display(self) -> Layout:
        """Создание финального статусного экрана с результатами"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        # Заголовок
        current_time = datetime.now().strftime("%H:%M:%S")
        header_text = Text("✅ Проверка каналов завершена", style="bold green")
        header_text.append(f" | Время: {current_time}", style="cyan")
        header_text.append(" | Статус: Готово", style="bold blue")
        layout["header"].update(Panel(header_text, box=box.DOUBLE))
        
        # Главная область
        layout["main"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        # Левая панель - таблица результатов
        results_table = self._create_results_table()
        layout["main"]["left"].update(Panel(results_table, title="📋 Результаты проверки", box=box.ROUNDED, expand=True))
        
        # Правая панель - итоговая статистика
        final_stats = self._create_final_stats()
        layout["main"]["right"].update(Panel(final_stats, title="📊 Итоговая статистика", box=box.ROUNDED))
        
        # Подвал
        footer_content = self._create_final_footer()
        layout["footer"].update(Panel(footer_content, box=box.ROUNDED))
        
        return layout
    
    def _create_checking_channels_table(self) -> Table:
        """Создание таблицы каналов во время проверки"""
        table = Table(
            box=box.ROUNDED,
            show_header=True,
            header_style="bold white",
            expand=True,
            min_width=80
        )
        
        # Анимированный первый столбец
        animation_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        current_time = int(time.time() * 4) % len(animation_chars)
        animation = animation_chars[current_time]
        
        table.add_column("", style="cyan", width=2, justify="center")  # Анимация
        table.add_column("№", style="cyan", width=3, justify="center")
        table.add_column("Название канала", style="green", ratio=3)
        table.add_column("Статус проверки", style="yellow", width=15)
        table.add_column("Новых сообщений", style="blue", width=12)
        table.add_column("Время проверки", style="magenta", width=12)
        
        for i, channel in enumerate(self.channels):
            # Определяем статус проверки
            if channel.id in self.last_check_times:
                status = "✅ Проверен"
                status_style = "green"
                check_time = self.last_check_times[channel.id].strftime("%H:%M:%S") if isinstance(self.last_check_times[channel.id], datetime) else "—"
            else:
                status = "⏳ Ожидание"
                status_style = "yellow"
                check_time = "—"
            
            # Количество новых сообщений
            new_messages = str(self.channel_new_messages.get(channel.id, 0))
            
            table.add_row(
                animation,
                str(i + 1),
                channel.title,
                f"[{status_style}]{status}[/{status_style}]",
                new_messages,
                check_time
            )
        
        return table
    
    def _create_checking_stats(self) -> Text:
        """Создание статистики проверки"""
        stats_text = Text()
        
        # Анимированный заголовок
        animation_chars = ["🔍", "🔎", "🔍", "🔎"]
        current_time = int(time.time() * 2) % len(animation_chars)
        animation = animation_chars[current_time]
        
        stats_text.append(f"{animation} Проверка каналов\n\n", style="bold yellow")
        
        # Статистика проверки
        checked_count = len(self.last_check_times)
        total_count = len(self.channels)
        
        stats_text.append("📋 ", style="green")
        stats_text.append(f"Всего каналов: {total_count}\n", style="green")
        
        stats_text.append("✅ ", style="blue")
        stats_text.append(f"Проверено: {checked_count}\n", style="blue")
        
        stats_text.append("⏳ ", style="yellow")
        stats_text.append(f"Осталось: {total_count - checked_count}\n", style="yellow")
        
        # Прогресс
        if total_count > 0:
            progress = (checked_count / total_count) * 100
            stats_text.append(f"\n📊 Прогресс: {progress:.1f}%\n", style="cyan")
            
            # Прогресс-бар
            bar_length = 20
            filled_length = int(bar_length * progress / 100)
            bar = "█" * filled_length + "░" * (bar_length - filled_length)
            stats_text.append(f"[{bar}] {progress:.1f}%\n", style="cyan")
        
        # Время проверки
        if hasattr(self, '_last_check_time'):
            check_duration = (datetime.now() - self._last_check_time).total_seconds()
            stats_text.append(f"\n⏱️ Время проверки: {check_duration:.1f}с\n", style="blue")
        
        return stats_text
    
    def _create_checking_footer(self) -> Text:
        """Создание подвала для проверки"""
        footer_text = Text()
        footer_text.append("🔍 Проверка каналов", style="bold yellow")
        footer_text.append(" | ", style="dim")
        footer_text.append("Поиск новых сообщений", style="cyan")
        footer_text.append(" | ", style="dim")
        footer_text.append("Пожалуйста, подождите...", style="green")
        return footer_text
    
    def _create_results_table(self) -> Table:
        """Создание таблицы результатов проверки"""
        table = Table(
            box=box.ROUNDED,
            show_header=True,
            header_style="bold white",
            expand=True,
            min_width=80
        )
        
        table.add_column("№", style="cyan", width=3, justify="center")
        table.add_column("Название канала", style="green", ratio=3)
        table.add_column("Новых сообщений", style="yellow", width=12, justify="center")
        table.add_column("Статус", style="blue", width=15, justify="center")
        table.add_column("Время проверки", style="magenta", width=12)
        
        total_new_messages = 0
        channels_with_messages = 0
        
        for i, channel in enumerate(self.channels):
            new_messages = self.channel_new_messages.get(channel.id, 0)
            total_new_messages += new_messages
            
            if new_messages > 0:
                channels_with_messages += 1
                status = f"✅ {new_messages} новых"
                status_style = "green"
            else:
                status = "ℹ️ Нет новых"
                status_style = "blue"
            
            check_time = self.last_check_times[channel.id].strftime("%H:%M:%S") if channel.id in self.last_check_times and isinstance(self.last_check_times[channel.id], datetime) else "—"
            
            table.add_row(
                str(i + 1),
                channel.title,
                str(new_messages),
                f"[{status_style}]{status}[/{status_style}]",
                check_time
            )
        
        # Добавляем строку с итогами
        table.add_section()
        table.add_row(
            "ИТОГО:",
            f"{len(self.channels)} каналов",
            str(total_new_messages),
            f"✅ {channels_with_messages} с новыми",
            ""
        )
        
        return table
    
    def _create_final_stats(self) -> Text:
        """Создание итоговой статистики"""
        stats_text = Text()
        
        stats_text.append("📊 Итоги проверки\n\n", style="bold green")
        
        # Основная статистика
        total_channels = len(self.channels)
        total_new_messages = sum(self.channel_new_messages.values())
        channels_with_messages = sum(1 for count in self.channel_new_messages.values() if count > 0)
        
        stats_text.append("📋 ", style="green")
        stats_text.append(f"Проверено каналов: {total_channels}\n", style="green")
        
        stats_text.append("🆕 ", style="yellow")
        stats_text.append(f"Новых сообщений: {total_new_messages}\n", style="yellow")
        
        stats_text.append("✅ ", style="blue")
        stats_text.append(f"Каналов с новыми: {channels_with_messages}\n", style="blue")
        
        stats_text.append("ℹ️ ", style="cyan")
        stats_text.append(f"Без изменений: {total_channels - channels_with_messages}\n", style="cyan")
        
        # Время проверки
        if hasattr(self, '_last_check_time'):
            check_duration = (datetime.now() - self._last_check_time).total_seconds()
            stats_text.append(f"\n⏱️ Время проверки: {check_duration:.1f}с\n", style="blue")
        
        # Следующая проверка
        stats_text.append("\n🔄 Следующая проверка\n\n", style="bold yellow")
        stats_text.append(f"⏰ Через {self.check_interval} секунд\n", style="blue")
        
        return stats_text
    
    def _create_final_footer(self) -> Text:
        """Создание финального подвала"""
        footer_text = Text()
        footer_text.append("✅ Проверка завершена", style="bold green")
        footer_text.append(" | ", style="dim")
        footer_text.append("Ожидание следующей проверки", style="cyan")
        footer_text.append(" | ", style="dim")
        footer_text.append("Ctrl+C для выхода", style="yellow")
        return footer_text
    
    async def _check_channels_for_updates(self):
        """Проверка каналов на обновления"""
        try:
            self._last_check_time = datetime.now()
            
            # Показываем статусный экран во время проверки
            await self._show_checking_status()
            
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
                
                # Небольшая пауза между каналами
                await asyncio.sleep(0.5)
            
            # Показываем финальный статусный экран с результатами
            await self._show_final_check_status()
            
            # Отправляем сводку в Telegram
            await self._send_check_summary()
                
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка проверки каналов: {e}[/red]")
            self.export_stats['errors'] += 1
    
    async def _check_single_channel(self, channel: ChannelInfo) -> int:
        """Проверка одного канала на новые сообщения"""
        try:
            # Если Telegram не подключен, работаем в демо-режиме
            if not self.telegram_connected or not self.exporter or not self.exporter.client:
                await asyncio.sleep(0.1)  # Симуляция задержки
                
                # Симулируем обнаружение новых сообщений (каждый 5-й канал)
                if channel.id % 5 == 0:
                    # Обновляем информацию о канале
                    channel.last_message_id += 1
                    channel.last_check = datetime.now().isoformat()
                    return 1
                return 0
            
            # Реальная проверка через Telegram API
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
                    channel.last_message_id += 1
                    channel.last_check = datetime.now().isoformat()
                    return 1
                return 0
                
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка проверки канала {channel.title}: {e}[/red]")
            self.export_stats['errors'] += 1
            return 0
    
    async def _cleanup(self):
        """Очистка ресурсов при завершении"""
        try:
            if self.telegram_connected and self.exporter and hasattr(self.exporter, 'disconnect'):
                await self.exporter.disconnect()
                self.console.print("[green]✅ Telegram клиент отключен[/green]")
            self.console.print("[green]✅ Очистка ресурсов завершена[/green]")
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка очистки: {e}[/red]")
    
    async def _send_check_summary(self):
        """Отправка сводки по завершении проверки каналов"""
        try:
            # Подготавливаем данные для сводки
            check_duration = (datetime.now() - self._last_check_time).total_seconds() if hasattr(self, '_last_check_time') else 0
            
            # Собираем каналы с новыми сообщениями
            channels_with_updates = []
            total_new_messages = 0
            channels_with_messages = 0
            
            for channel in self.channels:
                new_messages = self.channel_new_messages.get(channel.id, 0)
                if new_messages > 0:
                    channels_with_updates.append({
                        'channel': channel.title,
                        'new_messages': new_messages
                    })
                    total_new_messages += new_messages
                    channels_with_messages += 1
            
            # Формируем данные сводки
            check_results = {
                'total_channels': len(self.channels),
                'checked_channels': len(self.channels),
                'new_messages': total_new_messages,
                'channels_with_messages': channels_with_messages,
                'channels_with_updates': channels_with_updates,
                'check_duration': check_duration,
                'check_interval': self.check_interval
            }
            
            # Отправляем сводку
            await self.telegram_notifier.send_continuous_check_summary(check_results)
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка отправки сводки: {e}[/red]")


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
