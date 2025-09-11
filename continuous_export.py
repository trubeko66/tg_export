#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль постоянного экспорта каналов
"""

import asyncio
import time
import threading
import logging
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
        self.telegram_notifier = TelegramNotifier(console)
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
        self.channel_filtered_messages = {}  # Словарь для отслеживания отфильтрованных сообщений по каналам
        self.channel_useful_messages = {}  # Словарь для отслеживания полезных сообщений по каналам
        self.check_interval = 30  # Интервал проверки в секундах (по умолчанию 30)
        self.channels_state_file = Path("channels_state.json")  # Файл для сохранения состояния каналов
        
        # Настройка логгера для фильтрации
        self._setup_filter_logger()
        
        # Настройка обработчика сигналов для корректного завершения
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_filter_logger(self):
        """Настройка логгера для фильтрации сообщений"""
        # Создаем отдельный логгер для фильтрации
        self.filter_logger = logging.getLogger('ads_filter')
        self.filter_logger.setLevel(logging.DEBUG)
        
        # Удаляем существующие обработчики, если есть
        for handler in self.filter_logger.handlers[:]:
            self.filter_logger.removeHandler(handler)
        
        # Создаем обработчик для файла ads.log
        file_handler = logging.FileHandler('ads.log', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Расширенный формат лога с дополнительной информацией
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s] - %(funcName)s:%(lineno)d - %(message)s')
        file_handler.setFormatter(formatter)
        
        # Добавляем обработчик к логгеру
        self.filter_logger.addHandler(file_handler)
        
        # Предотвращаем дублирование сообщений
        self.filter_logger.propagate = False
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для корректного завершения"""
        self.console.print("\n[yellow]Получен сигнал завершения...[/yellow]")
        self.should_stop = True
        # Сохраняем состояние каналов при выходе
        self._save_channels_state()
    
    async def initialize(self):
        """Инициализация экспортера"""
        try:
            # Загружаем каналы сначала
            if self.config_manager.channels_file_exists():
                self.channels = self.config_manager.import_channels()
                self.console.print(f"[green]✅ Загружено {len(self.channels)} каналов[/green]")
                
                # Загружаем состояние каналов (last_message_id и т.д.)
                self._load_channels_state()
            else:
                self.console.print("[yellow]⚠️ Файл каналов не найден[/yellow]")
                return False
            
            # Показываем настройки фильтрации
            self.console.print(f"[blue]🔍 Настройки фильтрации:[/blue]")
            self.console.print(f"[blue]  - Фильтр рекламы: {'включен' if self.content_filter.config.filter_ads else 'отключен'}[/blue]")
            self.console.print(f"[blue]  - Фильтр IT-школ: {'включен' if self.content_filter.config.filter_schools else 'отключен'}[/blue]")
            
            # Логируем настройки фильтрации
            self.filter_logger.info(f"FILTER_SETTINGS: ads_filter={self.content_filter.config.filter_ads}, schools_filter={self.content_filter.config.filter_schools}")
            self.filter_logger.debug(f"Filter initialization completed. Channels loaded: {len(self.channels)}")
            
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
            # Показываем статус с обратным отсчетом
            # Время отображения зависит от интервала, но не более 10 секунд
            display_time = min(self.check_interval, 10)
            
            for remaining in range(display_time, 0, -1):
                layout = self._create_continuous_export_display(remaining)
                
                with Live(layout, refresh_per_second=1, console=self.console) as live:
                    await asyncio.sleep(1)
                
        except Exception as e:
            self.console.print(f"[red]Ошибка отображения статуса: {e}[/red]")
    
    def _create_continuous_export_display(self, countdown: int = 0) -> Layout:
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
        stats_content = self._create_continuous_stats(countdown)
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
    
    def _create_continuous_stats(self, countdown: int = 0) -> Text:
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
            self.filter_logger.debug(f"Starting channels check at {self._last_check_time}")
            
            # Показываем статусный экран во время проверки
            await self._show_checking_status()
            
            for i, channel in enumerate(self.channels):
                if self.should_stop:
                    break
                
                # Обновляем время последней проверки
                self.last_check_times[channel.id] = datetime.now()
                self.filter_logger.debug(f"Checking channel {i+1}/{len(self.channels)}: {channel.title}")
                
                # Проверяем канал на новые сообщения
                useful_messages, filtered_messages = await self._check_single_channel(channel)
                
                # Сохраняем количество сообщений для канала
                self.channel_new_messages[channel.id] = useful_messages + filtered_messages
                self.channel_useful_messages[channel.id] = useful_messages
                self.channel_filtered_messages[channel.id] = filtered_messages
                
                # Если есть новые полезные сообщения, экспортируем их в MD файл
                if useful_messages > 0 and self.telegram_connected and self.exporter:
                    self.console.print(f"[blue]🚀 Запускаем экспорт {useful_messages} сообщений для {channel.title}[/blue]")
                    await self._export_new_messages_to_md(channel, useful_messages)
                elif useful_messages > 0 and not self.telegram_connected:
                    self.console.print(f"[yellow]⚠️ Найдены новые сообщения в {channel.title}, но Telegram не подключен (демо-режим)[/yellow]")
                elif useful_messages == 0 and filtered_messages > 0:
                    mode = "демо-режим" if not self.telegram_connected else "реальный режим"
                    self.console.print(f"[dim]ℹ️ В {channel.title} найдены {filtered_messages} сообщений, но все отфильтрованы ({mode})[/dim]")
                    self.console.print(f"[dim]   💡 Проверьте детальную информацию выше для понимания причин фильтрации[/dim]")
                
                # Обновляем статистику
                self.export_stats['checked_channels'] += 1
                if useful_messages > 0 or filtered_messages > 0:
                    self.export_stats['new_messages'] += useful_messages + filtered_messages
                    self.export_stats['filtered_messages'] += filtered_messages
                
                # Небольшая пауза между каналами
                await asyncio.sleep(0.5)
            
            # Сохраняем состояние каналов после проверки
            self._save_channels_state()
            
            # Показываем финальный статусный экран с результатами
            await self._show_final_check_status()
            
            # Отправляем сводку в Telegram
            await self._send_check_summary()
            
            # Логируем завершение проверки
            total_useful = sum(self.channel_useful_messages.values())
            total_filtered = sum(self.channel_filtered_messages.values())
            self.filter_logger.debug(f"Channels check completed. Total useful: {total_useful}, total filtered: {total_filtered}")
                
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка проверки каналов: {e}[/red]")
            self.filter_logger.error(f"Error during channels check: {e}")
            self.export_stats['errors'] += 1
    
    async def _check_single_channel(self, channel: ChannelInfo) -> tuple:
        """Проверка одного канала на новые сообщения"""
        try:
            self.filter_logger.debug(f"Checking single channel: {channel.title}, last_message_id: {channel.last_message_id}")
            
            # Если Telegram не подключен, работаем в демо-режиме
            if not self.telegram_connected or not self.exporter or not self.exporter.client:
                self.filter_logger.debug(f"Working in demo mode for {channel.title}")
                await asyncio.sleep(0.1)  # Симуляция задержки
                
                # Симулируем обнаружение новых сообщений (каждый 5-й канал)
                if channel.id % 5 == 0:
                    # Обновляем информацию о канале
                    channel.last_message_id += 1
                    channel.last_check = datetime.now().isoformat()
                    channel.last_message_date = datetime.now().isoformat()
                    # Симулируем фильтрацию: 70% полезных, 30% отфильтрованных
                    total_messages = 1
                    useful_messages = int(total_messages * 0.7)
                    filtered_messages = total_messages - useful_messages
                    self.filter_logger.debug(f"Demo mode simulation for {channel.title}: useful={useful_messages}, filtered={filtered_messages}")
                    return (useful_messages, filtered_messages)
                return (0, 0)
            
            # Реальная проверка через Telegram API
            try:
                self.filter_logger.debug(f"Getting entity for channel {channel.title}")
                entity = await self.exporter.client.get_entity(channel.id)
                messages = await self.exporter.client.get_messages(entity, limit=1)
                
                if messages and len(messages) > 0:
                    last_message = messages[0]
                    self.console.print(f"[blue]🔍 Проверка {channel.title}: последнее сообщение ID={last_message.id}, известный ID={channel.last_message_id}[/blue]")
                    self.filter_logger.debug(f"Last message ID: {last_message.id}, known ID: {channel.last_message_id}")
                    
                    if last_message.id > channel.last_message_id:
                        new_messages_count = last_message.id - channel.last_message_id
                        self.console.print(f"[green]✅ Найдено {new_messages_count} новых сообщений в {channel.title}[/green]")
                        self.filter_logger.debug(f"Found {new_messages_count} new messages in {channel.title}")
                        
                        # Применяем фильтрацию к новым сообщениям
                        useful_messages = 0
                        filtered_messages = 0
                        
                        # Получаем новые сообщения для фильтрации
                        # min_id=channel.last_message_id означает "сообщения с ID больше last_message_id"
                        new_messages = await self.exporter.client.get_messages(
                            entity, 
                            min_id=channel.last_message_id,
                            limit=new_messages_count
                        )
                        
                        for message in new_messages:
                            # Получаем текст сообщения для фильтрации
                            message_text = getattr(message, 'text', '') or getattr(message, 'message', '') or ''
                            
                            # Получаем дату сообщения
                            message_date = self._format_message_date(message)
                            
                            message_id = str(getattr(message, 'id', 'unknown'))
                            self.filter_logger.debug(f"Processing message from {channel.title}, ID: {message_id}, date: {message_date}")
                            
                            # Тестируем фильтрацию для отладки
                            self._test_message_filtering(message_text, channel.title, message_date, message_id)
                            
                            should_filter, filter_reason = self.content_filter.should_filter_message(message_text)
                            
                            # Дополнительная отладка в основном цикле
                            self.filter_logger.debug(f"Main loop filter result: should_filter={should_filter}, reason='{filter_reason}'")
                            
                            if should_filter:
                                filtered_messages += 1
                                date_info = f" от {message_date}" if message_date else ""
                                
                                # Проверяем filter_reason в основном цикле
                                if not filter_reason or filter_reason.strip() == "":
                                    self.filter_logger.error(f"CRITICAL: Empty filter_reason in main loop! Channel: {channel.title}, Message ID: {message_id}")
                                    filter_reason = "ОШИБКА: Причина фильтрации не определена"
                                
                                self.console.print(f"[red]❌ ОТФИЛЬТРОВАНО: {channel.title}{date_info} - {filter_reason}[/red]")
                                
                                # Используем специальное логирование для отфильтрованных сообщений
                                self._log_filtered_message(channel.title, message_date, message_text, filter_reason, message_id)
                            else:
                                useful_messages += 1
                                date_info = f" от {message_date}" if message_date else ""
                                self.console.print(f"[green]✅ ПРИНЯТО: {channel.title}{date_info}[/green]")
                                
                                # Используем специальное логирование для прошедших сообщений
                                self._log_passed_message(channel.title, message_date, message_text, message_id)
                        
                        self.console.print(f"[cyan]📊 {channel.title}: полезных={useful_messages}, отфильтровано={filtered_messages}[/cyan]")
                        
                        # Логируем статистику по каналу
                        if useful_messages > 0 or filtered_messages > 0:
                            self.filter_logger.info(f"CHANNEL_STATS: {channel.title} - useful={useful_messages}, filtered={filtered_messages}")
                        
                        # Обновляем информацию о канале
                        channel.last_message_id = last_message.id
                        channel.last_check = datetime.now().isoformat()
                        channel.last_message_date = last_message.date.isoformat()
                        return (useful_messages, filtered_messages)
                    else:
                        self.console.print(f"[dim]ℹ️ {channel.title}: новых сообщений нет[/dim]")
                else:
                    self.console.print(f"[yellow]⚠️ {channel.title}: не удалось получить сообщения[/yellow]")
                
                return (0, 0)
                
            except Exception as e:
                # Если не удалось получить сообщения, симулируем проверку
                await asyncio.sleep(0.1)
                
                # Симулируем обнаружение новых сообщений (каждый 5-й канал)
                if channel.id % 5 == 0:
                    channel.last_message_id += 1
                    channel.last_check = datetime.now().isoformat()
                    # Симулируем фильтрацию: 70% полезных, 30% отфильтрованных
                    total_messages = 1
                    useful_messages = int(total_messages * 0.7)
                    filtered_messages = total_messages - useful_messages
                    return (useful_messages, filtered_messages)
                return (0, 0)
                
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка проверки канала {channel.title}: {e}[/red]")
            self.export_stats['errors'] += 1
            return (0, 0)
    
    def _format_message_date(self, message) -> str:
        """Форматирование даты сообщения"""
        if not hasattr(message, 'date') or not message.date:
            return ""
        
        try:
            from datetime import datetime
            if isinstance(message.date, datetime):
                return message.date.strftime("%Y-%m-%d %H:%M")
            else:
                return str(message.date)
        except Exception:
            return str(getattr(message, 'date', ''))
    
    def _log_filtered_message(self, channel_title: str, message_date: str, message_text: str, filter_reason: str, message_id: str = ""):
        """Специальное логирование отфильтрованных сообщений в ads.log"""
        # Обрезаем текст до 200 символов
        truncated_text = message_text[:200] + "..." if len(message_text) > 200 else message_text
        
        # Проверяем и обрабатываем filter_reason
        if not filter_reason or filter_reason.strip() == "":
            filter_reason = "Причина не указана"
            self.filter_logger.warning(f"Empty filter_reason for message from {channel_title}, ID: {message_id}")
        
        # Формируем структурированную запись
        log_entry = f"FILTERED_MESSAGE | Channel: {channel_title} | Date: {message_date} | ID: {message_id} | Reason: {filter_reason} | Text: {truncated_text}"
        
        # Логируем с уровнем INFO для отфильтрованных сообщений
        self.filter_logger.info(log_entry)
        
        # Дополнительно логируем с уровнем DEBUG для полной информации
        self.filter_logger.debug(f"Full filtered message details - Channel: {channel_title}, Date: {message_date}, ID: {message_id}, Reason: {filter_reason}, Full text: {message_text}")
        
        # Дополнительная отладка для диагностики
        self.filter_logger.debug(f"Filter reason debug - Original reason: '{filter_reason}', Length: {len(filter_reason)}, Type: {type(filter_reason)}")
    
    def _log_passed_message(self, channel_title: str, message_date: str, message_text: str, message_id: str = ""):
        """Логирование сообщений, прошедших фильтр"""
        # Обрезаем текст до 200 символов
        truncated_text = message_text[:200] + "..." if len(message_text) > 200 else message_text
        
        # Формируем структурированную запись
        log_entry = f"PASSED_MESSAGE | Channel: {channel_title} | Date: {message_date} | ID: {message_id} | Text: {truncated_text}"
        
        # Логируем с уровнем INFO
        self.filter_logger.info(log_entry)
    
    def _test_message_filtering(self, message_text: str, channel_title: str = "", message_date: str = "", message_id: str = "") -> None:
        """Тестирование фильтрации сообщения для отладки"""
        self.filter_logger.debug(f"Testing message filtering for channel: {channel_title}, date: {message_date}, ID: {message_id}")
        
        if not message_text or message_text.strip() == "":
            self.console.print(f"[yellow]⚠️ ПУСТОЕ СООБЩЕНИЕ в {channel_title}[/yellow]")
            self.filter_logger.warning(f"Empty message detected in channel: {channel_title}")
            return
            
        should_filter, filter_reason = self.content_filter.should_filter_message(message_text)
        date_info = f" от {message_date}" if message_date else ""
        
        # Детальная отладка результата фильтрации
        self.filter_logger.debug(f"Filter result: should_filter={should_filter}, reason='{filter_reason}'")
        self.filter_logger.debug(f"Filter reason details - Value: '{filter_reason}', Length: {len(filter_reason) if filter_reason else 0}, Type: {type(filter_reason)}")
        
        # Проверяем, что filter_reason не пустой
        if should_filter and (not filter_reason or filter_reason.strip() == ""):
            self.filter_logger.error(f"CRITICAL: Message should be filtered but filter_reason is empty! Channel: {channel_title}, Text: {message_text[:100]}")
            filter_reason = "ОШИБКА: Причина фильтрации не определена"
        
        if should_filter:
            self.console.print(f"[yellow]🔍 ФИЛЬТРАЦИЯ: {channel_title}{date_info} - {filter_reason}[/yellow]")
            self.console.print(f"[dim]📝 Текст: {message_text[:200]}...[/dim]")
            
            # Используем специальное логирование для отфильтрованных сообщений
            self._log_filtered_message(channel_title, message_date, message_text, filter_reason, message_id)
        else:
            self.console.print(f"[green]✅ ПРОЙДЕТ ФИЛЬТР: {channel_title}{date_info}[/green]")
            self.console.print(f"[dim]📝 Текст: {message_text[:200]}...[/dim]")
            
            # Используем специальное логирование для прошедших сообщений
            self._log_passed_message(channel_title, message_date, message_text, message_id)
    
    async def _export_new_messages_to_md(self, channel: ChannelInfo, useful_messages_count: int):
        """Экспорт новых сообщений в MD файл"""
        try:
            if not self.exporter or not self.exporter.client:
                return
            
            # Получаем канал
            entity = await self.exporter.client.get_entity(channel.id)
            
            # Получаем новые сообщения для экспорта
            # min_id=channel.last_message_id означает "сообщения с ID больше last_message_id"
            new_messages = []
            messages = await self.exporter.client.get_messages(
                entity, 
                min_id=channel.last_message_id - useful_messages_count,  # Получаем сообщения начиная с нужного ID
                limit=useful_messages_count * 2  # Берем больше, чтобы учесть отфильтрованные
            )
            
            # Фильтруем сообщения - берем только полезные (не отфильтрованные)
            self.filter_logger.debug(f"Starting export filtering for {channel.title}, need {useful_messages_count} useful messages")
            
            for message in messages:
                # Получаем текст сообщения для фильтрации
                message_text = getattr(message, 'text', '') or getattr(message, 'message', '') or ''
                
                # Получаем дату сообщения
                message_date = self._format_message_date(message)
                message_id = str(getattr(message, 'id', 'unknown'))
                
                self.filter_logger.debug(f"Export filtering message ID {message_id} from {channel.title}")
                
                should_filter, filter_reason = self.content_filter.should_filter_message(message_text)
                
                # Дополнительная отладка в функции экспорта
                self.filter_logger.debug(f"Export filter result: should_filter={should_filter}, reason='{filter_reason}'")
                
                if not should_filter:
                    new_messages.append(message)
                    self.filter_logger.debug(f"Message ID {message_id} added to export queue")
                    if len(new_messages) >= useful_messages_count:
                        self.filter_logger.debug(f"Reached target count {useful_messages_count} for export")
                        break  # Останавливаемся когда набрали нужное количество
                else:
                    date_info = f" от {message_date}" if message_date else ""
                    
                    # Проверяем filter_reason в функции экспорта
                    if not filter_reason or filter_reason.strip() == "":
                        self.filter_logger.error(f"CRITICAL: Empty filter_reason in export! Channel: {channel.title}, Message ID: {message_id}")
                        filter_reason = "ОШИБКА: Причина фильтрации не определена"
                    
                    self.console.print(f"[dim]🔍 Сообщение отфильтровано при экспорте{date_info}: {filter_reason}[/dim]")
                    
                    # Используем специальное логирование для отфильтрованных сообщений при экспорте
                    self._log_filtered_message(channel.title, message_date, message_text, f"EXPORT_FILTER: {filter_reason}", message_id)
            
            if not new_messages:
                self.console.print(f"[yellow]⚠️ Не найдено полезных сообщений для экспорта в {channel.title}[/yellow]")
                return
            
            # Создаем директорию для канала
            from pathlib import Path
            try:
                storage_cfg = self.config_manager.config.storage
                base_dir = getattr(storage_cfg, 'export_base_dir', 'exports') or 'exports'
            except Exception:
                base_dir = 'exports'
            
            base_path = Path(base_dir)
            base_path.mkdir(parents=True, exist_ok=True)
            sanitized_title = self.exporter._sanitize_channel_filename(channel.title)
            channel_dir = base_path / sanitized_title
            channel_dir.mkdir(exist_ok=True)
            
            # Путь к MD файлу
            md_file_path = channel_dir / f"{sanitized_title}.md"
            
            # Конвертируем сообщения в формат для экспорта
            from exporters import MarkdownExporter
            md_exporter = MarkdownExporter(str(channel_dir), sanitized_title)
            
            # Подготавливаем данные сообщений
            messages_data = []
            for message in new_messages:
                message_data = self.exporter._convert_message_to_dict(message, entity)
                if message_data:
                    messages_data.append(message_data)
            
            if messages_data:
                self.console.print(f"[blue]📝 Экспортируем {len(messages_data)} сообщений в {channel.title}[/blue]")
                
                # Экспортируем новые сообщения в режиме дописывания
                md_file = md_exporter.export_messages(messages_data, append_mode=True)
                
                if md_file and Path(md_file).exists():
                    self.console.print(f"[green]✅ Экспортировано {len(messages_data)} новых сообщений в {channel.title}[/green]")
                    self.export_stats['exported_messages'] += len(messages_data)
                else:
                    self.console.print(f"[yellow]⚠️ Не удалось экспортировать сообщения для {channel.title}[/yellow]")
            else:
                self.console.print(f"[yellow]⚠️ Нет данных для экспорта в {channel.title}[/yellow]")
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка экспорта новых сообщений для {channel.title}: {e}[/red]")
            self.export_stats['errors'] += 1
    
    async def _cleanup(self):
        """Очистка ресурсов при завершении"""
        try:
            if self.telegram_connected and self.exporter and hasattr(self.exporter, 'disconnect'):
                self.console.print("[blue]🔄 Отключение от Telegram...[/blue]")
                
                # Отключаем клиент
                await self.exporter.disconnect()
                
                # Ждем немного, чтобы все фоновые задачи завершились
                await asyncio.sleep(2)
                
                self.console.print("[green]✅ Telegram клиент отключен[/green]")
            
            # Останавливаем флаг работы
            self.should_stop = True
            
            self.console.print("[green]✅ Очистка ресурсов завершена[/green]")
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка очистки: {e}[/red]")
    
    async def _send_check_summary(self):
        """Отправка сводки по завершении проверки каналов"""
        try:
            # Не отправляем уведомления при выходе из программы
            if self.should_stop:
                return
            # Подготавливаем данные для сводки
            check_duration = (datetime.now() - self._last_check_time).total_seconds() if hasattr(self, '_last_check_time') else 0
            
            # Собираем каналы с новыми сообщениями
            channels_with_updates = []
            total_useful_messages = 0
            total_filtered_messages = 0
            channels_with_messages = 0
            
            for channel in self.channels:
                useful_messages = self.channel_useful_messages.get(channel.id, 0)
                filtered_messages = self.channel_filtered_messages.get(channel.id, 0)
                total_messages = useful_messages + filtered_messages
                
                # Добавляем канал в сводку только если есть полезные сообщения
                if useful_messages > 0:
                    channel_info = {
                        'channel': channel.title,
                        'new_messages': total_messages,
                        'useful_messages': useful_messages
                    }
                    
                    # Добавляем информацию об отфильтрованных сообщениях только если они есть
                    if filtered_messages > 0:
                        channel_info['filtered_messages'] = filtered_messages
                    
                    channels_with_updates.append(channel_info)
                    total_useful_messages += useful_messages
                    total_filtered_messages += filtered_messages
                    channels_with_messages += 1
            
            # Проверяем, есть ли новые сообщения для отправки уведомления
            total_new_messages = total_useful_messages + total_filtered_messages
            
            if total_new_messages == 0:
                self.console.print("[blue]ℹ️ Новых сообщений не обнаружено, уведомление не отправляется[/blue]")
                return
            
            # Формируем данные сводки
            check_results = {
                'total_channels': len(self.channels),
                'checked_channels': len(self.channels),
                'new_messages': total_new_messages,
                'useful_messages': total_useful_messages,
                'filtered_messages': total_filtered_messages,
                'channels_with_messages': channels_with_messages,
                'channels_with_updates': channels_with_updates,
                'check_duration': check_duration,
                'check_interval': self.check_interval
            }
            
            # Отправляем сводку только если есть новые сообщения
            await self.telegram_notifier.send_continuous_check_summary(check_results)
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка отправки сводки: {e}[/red]")
    
    def _save_channels_state(self):
        """Сохранение состояния каналов в файл"""
        try:
            if not self.channels:
                return
            
            state_data = {}
            for channel in self.channels:
                state_data[str(channel.id)] = {
                    'last_message_id': channel.last_message_id,
                    'last_check': channel.last_check,
                    'title': channel.title,
                    'username': getattr(channel, 'username', ''),
                    'description': getattr(channel, 'description', ''),
                    'subscribers_count': getattr(channel, 'subscribers_count', 0),
                    'total_messages': getattr(channel, 'total_messages', 0),
                    'media_size_mb': getattr(channel, 'media_size_mb', 0.0)
                }
            
            import json
            with open(self.channels_state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            
            self.console.print(f"[green]✅ Состояние {len(self.channels)} каналов сохранено[/green]")
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка сохранения состояния каналов: {e}[/red]")
    
    def _load_channels_state(self):
        """Загрузка состояния каналов из файла"""
        try:
            # Инициализируем last_message_id для всех каналов
            for channel in self.channels:
                if not hasattr(channel, 'last_message_id') or channel.last_message_id is None:
                    channel.last_message_id = 0
            
            if not self.channels_state_file.exists():
                self.console.print("[blue]ℹ️ Файл состояния каналов не найден, инициализируем с нуля[/blue]")
                return
            
            import json
            with open(self.channels_state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # Обновляем состояние каналов
            updated_count = 0
            for channel in self.channels:
                channel_id_str = str(channel.id)
                if channel_id_str in state_data:
                    state = state_data[channel_id_str]
                    channel.last_message_id = state.get('last_message_id', channel.last_message_id)
                    channel.last_check = state.get('last_check', channel.last_check)
                    updated_count += 1
                else:
                    # Если канал не в состоянии, инициализируем last_message_id как 0
                    # чтобы при первой проверке получить все сообщения
                    if not hasattr(channel, 'last_message_id') or channel.last_message_id is None:
                        channel.last_message_id = 0
            
            if updated_count > 0:
                self.console.print(f"[green]✅ Загружено состояние {updated_count} каналов[/green]")
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка загрузки состояния каналов: {e}[/red]")
    
    def _add_channel_to_state(self, channel: ChannelInfo):
        """Добавление нового канала в состояние"""
        try:
            # Загружаем текущее состояние
            state_data = {}
            if self.channels_state_file.exists():
                import json
                with open(self.channels_state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
            
            # Добавляем новый канал
            state_data[str(channel.id)] = {
                'last_message_id': channel.last_message_id,
                'last_check': channel.last_check,
                'title': channel.title,
                'username': getattr(channel, 'username', ''),
                'description': getattr(channel, 'description', ''),
                'subscribers_count': getattr(channel, 'subscribers_count', 0),
                'total_messages': getattr(channel, 'total_messages', 0),
                'media_size_mb': getattr(channel, 'media_size_mb', 0.0)
            }
            
            # Сохраняем обновленное состояние
            import json
            with open(self.channels_state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            
            self.console.print(f"[green]✅ Канал {channel.title} добавлен в состояние[/green]")
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка добавления канала в состояние: {e}[/red]")


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
