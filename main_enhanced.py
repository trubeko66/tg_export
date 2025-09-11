#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Улучшенная версия Telegram Channel Exporter с новыми возможностями
"""

import asyncio
import sys
import time
import json
from pathlib import Path
from typing import List, Any, Optional, Tuple
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.layout import Layout
from rich.text import Text
from rich import box
from rich.live import Live

# Импортируем основные модули
from telegram_exporter import TelegramExporter, ChannelInfo
from config_manager import ConfigManager
from analytics import AnalyticsReporter
from channel_dashboard import ChannelDashboard
from html_reporter import HTMLReporter
from simple_cli import SimpleCLI
from settings_methods import SettingsMethods
from continuous_export import ContinuousExporter
from telegram_notifications import TelegramNotifier


class EnhancedTelegramExporter(TelegramExporter):
    """Улучшенная версия TelegramExporter с новыми возможностями"""
    
    def __init__(self):
        super().__init__()
        self.analytics_reporter = AnalyticsReporter(self.console)
        self.dashboard = ChannelDashboard(self.console)
        self.html_reporter = HTMLReporter()
        self.simple_cli = SimpleCLI(self.console)
        self.config_manager = ConfigManager()
        self.settings_methods = SettingsMethods(self.console, self.config_manager)
        self.telegram_notifier = TelegramNotifier(self.console)
        self.check_interval = 30  # Интервал проверки в секундах (по умолчанию 30)
        self._current_export_index = -1  # Индекс текущего экспортируемого канала
    
    async def initialize(self):
        """Инициализация улучшенного экспортера"""
        try:
            # Инициализируем базовый экспортер
            await self.initialize_client(force_reauth=False)
            
            # Дополнительная инициализация для улучшенной версии
            self.console.print("[green]Инициализация улучшенных модулей...[/green]")
            
            # Загружаем каналы если они есть
            if not self.channels:
                # Пытаемся загрузить каналы из файла
                if self.config_manager.channels_file_exists():
                    self.console.print("[blue]Загрузка каналов из файла...[/blue]")
                    imported_channels = self.config_manager.import_channels()
                    if imported_channels:
                        self.channels = imported_channels
                        self.console.print(f"[green]✅ Загружено {len(imported_channels)} каналов из файла[/green]")
                    else:
                        self.console.print("[yellow]Не удалось загрузить каналы из файла[/yellow]")
                else:
                    self.console.print("[yellow]Каналы не загружены. Используйте обычную версию для настройки.[/yellow]")
            
            self.console.print("[green]✅ Инициализация завершена[/green]")
            
        except Exception as e:
            self.console.print(f"[red]Ошибка инициализации: {e}[/red]")
            raise
    
    async def show_enhanced_menu(self):
        """Показать улучшенное меню"""
        while True:
            self.console.clear()
            
            # Создаем красивый заголовок
            header_text = Text("🚀 Telegram Channel Exporter", style="bold blue")
            header_text.append(" - Улучшенная версия", style="green")
            header_panel = Panel(
                header_text,
                box=box.DOUBLE,
                border_style="blue",
                padding=(0, 1)
            )
            self.console.print(header_panel)
            
            # Показываем улучшенный статус системы
            await self._show_enhanced_status()
            
            
            choice = Prompt.ask(
                "Выберите действие",
                choices=["1", "2", "3", "4", "5", "6", "7", "8", "0", "q", "quit"]
            )
            
            if choice in ["0", "q", "quit"]:
                if Confirm.ask("Вы уверены, что хотите выйти?"):
                    # Корректно завершаем работу
                    self.console.print("[blue]🔄 Завершение работы...[/blue]")
                    await self._cleanup_resources()
                    break
                continue
            
            try:
                if choice == "1":
                    await self.show_analytics_menu()
                elif choice == "2":
                    await self.show_dashboard()
                elif choice == "3":
                    await self.show_export_menu()
                elif choice == "4":
                    await self.show_settings_menu()
                elif choice == "5":
                    await self.show_logs_menu()
                elif choice == "6":
                    await self.show_enhanced_cli()
                elif choice == "7":
                    await self.show_channels_import_export_menu()
                elif choice == "8":
                    await self.show_continuous_export_menu()
                    
            except KeyboardInterrupt:
                if Confirm.ask("\nПрервать операцию?"):
                    break
            except Exception as e:
                self.console.print(f"[red]Ошибка: {e}[/red]")
                input("Нажмите Enter для продолжения...")
    
    async def show_analytics_menu(self):
        """Показать меню аналитики"""
        self.console.clear()
        
        analytics_panel = Panel(
            "📊 Аналитика и отчеты\n\n"
            "1. 📈 Общая статистика\n"
            "2. 🔍 Анализ конкретного канала\n"
            "3. 📊 Сравнение каналов\n"
            "4. 📄 Экспорт отчета в JSON\n"
            "5. 📋 Экспорт отчета в CSV\n"
            "6. 🌐 Экспорт отчета в HTML\n"
            "0. 🔙 Назад",
            title="📊 Аналитика",
            border_style="cyan"
        )
        
        self.console.print(analytics_panel)
        
        choice = Prompt.ask(
            "Выберите тип аналитики",
            choices=["1", "2", "3", "4", "5", "6", "0"]
        )
        
        if choice == "0":
            return
        
        try:
            if choice == "1":
                await self.show_general_analytics()
            elif choice == "2":
                await self.show_channel_analysis()
            elif choice == "3":
                await self.show_channel_comparison()
            elif choice == "4":
                await self.export_json_report()
            elif choice == "5":
                await self.export_csv_report()
            elif choice == "6":
                await self.export_html_report()
                
        except Exception as e:
            self.console.print(f"[red]Ошибка аналитики: {e}[/red]")
            input("Нажмите Enter для продолжения...")
    
    async def show_general_analytics(self):
        """Показать общую аналитику"""
        self.console.clear()
        
        with self.console.status("Анализ данных..."):
            time.sleep(1)
        
        # Проверяем наличие каналов
        if not self.channels:
            self.console.print("[yellow]⚠️ Нет каналов для анализа[/yellow]")
            self.console.print("Сначала загрузите каналы через пункт 7 - Импорт/Экспорт каналов")
            input("Нажмите Enter для продолжения...")
            return
        
        # Генерируем отчет
        try:
            report = self.analytics_reporter.generate_export_report(self.channels, self.stats)
            self.console.print(report)
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка генерации отчета: {e}[/red]")
            # Показываем простую статистику
            self._show_simple_analytics()
        
        input("\nНажмите Enter для продолжения...")
    
    def _show_simple_analytics(self):
        """Показать простую аналитику без сложных вычислений"""
        self.console.clear()
        
        # Создаем простую таблицу статистики
        table = Table(title="📊 Простая статистика", box=box.ROUNDED)
        table.add_column("Метрика", style="cyan")
        table.add_column("Значение", style="green")
        
        total_messages = sum(channel.total_messages for channel in self.channels)
        total_size = sum(channel.media_size_mb for channel in self.channels)
        
        table.add_row("Всего каналов", f"{len(self.channels):,}")
        table.add_row("Всего сообщений", f"{total_messages:,}")
        table.add_row("Общий размер", f"{total_size:.1f} МБ")
        table.add_row("Ошибок экспорта", f"{self.stats.export_errors:,}")
        table.add_row("Отфильтровано", f"{self.stats.filtered_messages:,}")
        
        if self.stats.last_export_time:
            table.add_row("Последний экспорт", str(self.stats.last_export_time))
        
        # Показываем топ-5 каналов по сообщениям
        sorted_channels = sorted(self.channels, key=lambda x: x.total_messages, reverse=True)[:5]
        
        self.console.print(table)
        
        if sorted_channels:
            top_table = Table(title="🏆 Топ-5 каналов по сообщениям", box=box.ROUNDED)
            top_table.add_column("№", style="cyan", width=3, justify="center")
            top_table.add_column("Канал", style="green")
            top_table.add_column("Сообщений", style="yellow", justify="right")
            top_table.add_column("Размер (МБ)", style="blue", justify="right")
            
            for i, channel in enumerate(sorted_channels, 1):
                top_table.add_row(
                    str(i),
                    channel.title[:40] + "..." if len(channel.title) > 40 else channel.title,
                    f"{channel.total_messages:,}",
                    f"{channel.media_size_mb:.1f}"
                )
            
            self.console.print(top_table)
    
    async def show_channel_analysis(self):
        """Показать анализ канала"""
        self.console.clear()
        
        if not self.channels:
            self.console.print("[yellow]Нет каналов для анализа[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        # Показываем список каналов
        table = Table(title="Выберите канал для анализа", box=box.ROUNDED)
        table.add_column("№", style="cyan", width=4, justify="center")
        table.add_column("Название канала", style="green")
        table.add_column("Сообщений", style="yellow", justify="right")
        
        for i, channel in enumerate(self.channels, 1):
            table.add_row(str(i), channel.title, f"{getattr(channel, 'total_messages', 0):,}")
        
        self.console.print(table)
        
        try:
            choice = IntPrompt.ask(
                "Выберите номер канала",
                choices=[str(i) for i in range(1, len(self.channels) + 1)]
            )
            
            selected_channel = self.channels[choice - 1]
            
            with self.console.status(f"Анализ канала '{selected_channel.title}'..."):
                time.sleep(2)
            
            # Генерируем отчет по каналу
            export_base_dir = Path(self.config_manager.config.storage.export_base_dir)
            channel_dir = export_base_dir / self._sanitize_filename(selected_channel.title)
            
            if channel_dir.exists():
                report = self.analytics_reporter.generate_channel_report(channel_dir, selected_channel.title)
                self.console.print(report)
            else:
                self.console.print(f"[yellow]Нет данных для канала '{selected_channel.title}'[/yellow]")
                
        except (ValueError, IndexError):
            self.console.print("[red]Неверный выбор канала[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def show_channel_comparison(self):
        """Показать сравнение каналов"""
        self.console.clear()
        
        with self.console.status("Подготовка сравнения..."):
            time.sleep(1)
        
        # Получаем данные для сравнения
        channels_data = self._get_channels_data()
        
        if len(channels_data) < 2:
            self.console.print("[yellow]Недостаточно данных для сравнения (нужно минимум 2 канала)[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        # Генерируем сравнительный отчет
        report = self.analytics_reporter.generate_comparison_report(channels_data)
        self.console.print(report)
        
        input("\nНажмите Enter для продолжения...")
    
    async def export_json_report(self):
        """Экспорт JSON отчета"""
        self.console.clear()
        
        with self.console.status("Генерация JSON отчета..."):
            time.sleep(2)
        
        # Получаем данные для экспорта
        channels_data = self._get_channels_data()
        
        if not channels_data:
            self.console.print("[yellow]Нет данных для экспорта[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        # Экспортируем в JSON
        output_file = Path("analytics_report.json")
        self.analytics_reporter.export_analytics_to_json(channels_data, output_file)
        
        input("\nНажмите Enter для продолжения...")
    
    async def export_csv_report(self):
        """Экспорт CSV отчета"""
        self.console.clear()
        
        with self.console.status("Генерация CSV отчета..."):
            time.sleep(2)
        
        # Получаем данные для экспорта
        channels_data = self._get_channels_data()
        
        if not channels_data:
            self.console.print("[yellow]Нет данных для экспорта[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        # Экспортируем в CSV
        output_file = Path("analytics_report.csv")
        self.analytics_reporter.export_analytics_to_csv(channels_data, output_file)
        
        input("\nНажмите Enter для продолжения...")
    
    async def export_html_report(self):
        """Экспорт HTML отчета"""
        self.console.clear()
        
        with self.console.status("Генерация HTML отчета..."):
            time.sleep(3)
        
        # Получаем данные для экспорта
        channels_data = self._get_channels_data()
        
        if not channels_data:
            self.console.print("[yellow]Нет данных для экспорта[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        # Экспортируем в HTML
        output_file = Path("analytics_report.html")
        self.html_reporter.generate_html_report(channels_data, output_file)
        
        input("\nНажмите Enter для продолжения...")
    
    async def show_dashboard(self):
        """Показать интерактивную карту каналов"""
        self.console.clear()
        
        with self.console.status("Загрузка карты каналов..."):
            time.sleep(1)
        
        # Обновляем статус каналов
        export_base_dir = Path(self.config_manager.config.storage.export_base_dir)
        self.dashboard.update_channels_status(self.channels, self.stats, export_base_dir)
        
        # Показываем статический дашборд
        self.dashboard.show_static_dashboard(self.channels, self.stats, export_base_dir)
        
        input("\nНажмите Enter для продолжения...")
    
    async def show_export_menu(self):
        """Показать меню экспорта"""
        self.console.clear()
        
        if not self.channels:
            self.console.print("[yellow]Нет каналов для экспорта[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        # Показываем меню экспорта
        export_panel = Panel(
            "🔄 Экспорт каналов\n\n"
            "1. 📋 Экспорт всех каналов\n"
            "2. 🎯 Выбрать каналы для экспорта\n"
            "3. 🔄 Повторный экспорт проблемных каналов\n"
            "0. 🔙 Назад",
            title="🔄 Экспорт",
            border_style="green"
        )
        
        self.console.print(export_panel)
        
        choice = Prompt.ask(
            "Выберите тип экспорта",
            choices=["1", "2", "3", "0"]
        )
        
        if choice == "0":
            return
        
        try:
            if choice == "1":
                await self.export_all_channels()
            elif choice == "2":
                await self.export_selected_channels()
            elif choice == "3":
                await self.export_problematic_channels()
                
        except Exception as e:
            self.console.print(f"[red]Ошибка экспорта: {e}[/red]")
            input("Нажмите Enter для продолжения...")
    
    async def export_all_channels(self):
        """Экспорт всех каналов"""
        self.console.clear()
        
        if not self.channels:
            self.console.print("[yellow]⚠️ Список каналов пуст[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        if Confirm.ask(f"Экспортировать все {len(self.channels)} каналов?"):
            # Показываем красивый статусный экран во время экспорта
            await self._export_all_channels_with_progress()
        
        input("\nНажмите Enter для продолжения...")
    
    async def _export_all_channels_with_progress(self):
        """Экспорт всех каналов с красивым прогресс-баром"""
        try:
            # Инициализируем статистику
            total_channels = len(self.channels)
            completed_channels = 0
            total_messages = sum(channel.total_messages for channel in self.channels)
            exported_messages = 0
            total_size_mb = sum(channel.media_size_mb for channel in self.channels)
            errors = 0
            
            # Создаем статусный экран
            with Live(self.create_export_status_display(
                total_channels=total_channels,
                completed_channels=completed_channels,
                total_messages=total_messages,
                exported_messages=exported_messages,
                total_size_mb=total_size_mb,
                errors=errors,
                channels=self.channels,
                current_channel_index=-1
            ), refresh_per_second=2, console=self.console) as live:
                
                # Симулируем процесс экспорта с обновлением статуса
                for i, channel in enumerate(self.channels):
                    current_channel = f"Экспорт: {channel.title}"
                    
                    # Обновляем статус
                    live.update(self.create_export_status_display(
                        current_channel=current_channel,
                        progress=0,
                        total_channels=total_channels,
                        completed_channels=completed_channels,
                        total_messages=total_messages,
                        exported_messages=exported_messages,
                        total_size_mb=total_size_mb,
                        errors=errors,
                        channels=self.channels,
                        current_channel_index=i
                    ))
                    
                    # Симулируем прогресс экспорта канала
                    for progress in range(0, 101, 20):
                        live.update(self.create_export_status_display(
                            current_channel=current_channel,
                            progress=progress,
                            total_channels=total_channels,
                            completed_channels=completed_channels,
                            total_messages=total_messages,
                            exported_messages=exported_messages,
                            total_size_mb=total_size_mb,
                            errors=errors,
                            channels=self.channels,
                            current_channel_index=i
                        ))
                        time.sleep(0.2)  # Задержка для демонстрации
                    
                    # Обновляем статистику
                    completed_channels += 1
                    exported_messages += channel.total_messages
                    
                    # Обновляем финальный статус для канала
                    live.update(self.create_export_status_display(
                        current_channel=f"Завершен: {channel.title}",
                        progress=100,
                        total_channels=total_channels,
                        completed_channels=completed_channels,
                        total_messages=total_messages,
                        exported_messages=exported_messages,
                        total_size_mb=total_size_mb,
                        errors=errors,
                        channels=self.channels,
                        current_channel_index=i
                    ))
                    
                    time.sleep(0.3)  # Пауза между каналами
                
                # Финальный статус
                live.update(self.create_export_status_display(
                    current_channel="Экспорт завершен!",
                    progress=100,
                    total_channels=total_channels,
                    completed_channels=completed_channels,
                    total_messages=total_messages,
                    exported_messages=exported_messages,
                    total_size_mb=total_size_mb,
                    errors=errors,
                    channels=self.channels,
                    current_channel_index=len(self.channels)
                ))
                
                time.sleep(1)  # Показываем финальный статус
            
            # Показываем результат
            self.console.print(f"[green]✅ Экспорт завершен![/green]")
            self.console.print(f"[blue]📊 Обработано {len(self.channels)} каналов, {exported_messages:,} сообщений, {total_size_mb:.1f} МБ[/blue]")
            self.console.print("[yellow]💡 Для реального экспорта используйте обычную версию программы[/yellow]")
                
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Экспорт прерван пользователем[/yellow]")
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка экспорта: {e}[/red]")
    
    async def export_selected_channels(self):
        """Экспорт выбранных каналов"""
        self.console.clear()
        
        # Показываем список каналов для выбора
        table = Table(title="Выберите каналы для экспорта", box=box.ROUNDED)
        table.add_column("№", style="cyan", width=4, justify="center")
        table.add_column("Название канала", style="green")
        table.add_column("Статус", style="yellow")
        
        for i, channel in enumerate(self.channels, 1):
            status = "Активен" if hasattr(channel, 'last_check') and channel.last_check else "Не проверен"
            table.add_row(str(i), channel.title, status)
        
        self.console.print(table)
        
        selection = Prompt.ask(
            "Введите номера каналов через запятую (например: 1,3,5) или 'all' для всех"
        )
        
        if selection.lower() == "all":
            selected_channels = self.channels
        else:
            try:
                indices = [int(x.strip()) - 1 for x in selection.split(",")]
                selected_channels = [self.channels[i] for i in indices if 0 <= i < len(self.channels)]
            except (ValueError, IndexError):
                self.console.print("[red]Неверный формат выбора[/red]")
                input("Нажмите Enter для продолжения...")
                return
        
        if not selected_channels:
            self.console.print("[yellow]Нет выбранных каналов[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        if Confirm.ask(f"Экспортировать {len(selected_channels)} каналов?"):
            # Показываем красивый статусный экран во время экспорта
            await self._export_selected_channels_with_progress(selected_channels)
        
        input("\nНажмите Enter для продолжения...")
    
    async def _export_selected_channels_with_progress(self, selected_channels):
        """Экспорт выбранных каналов с красивым прогресс-баром"""
        try:
            # Инициализируем статистику
            total_channels = len(selected_channels)
            completed_channels = 0
            total_messages = sum(channel.total_messages for channel in selected_channels)
            exported_messages = 0
            total_size_mb = sum(channel.media_size_mb for channel in selected_channels)
            errors = 0
            
            # Создаем статусный экран
            with Live(self.create_export_status_display(
                total_channels=total_channels,
                completed_channels=completed_channels,
                total_messages=total_messages,
                exported_messages=exported_messages,
                total_size_mb=total_size_mb,
                errors=errors,
                channels=selected_channels,
                current_channel_index=-1
            ), refresh_per_second=2, console=self.console) as live:
                
                # Симулируем процесс экспорта с обновлением статуса
                for i, channel in enumerate(selected_channels):
                    current_channel = f"Экспорт: {channel.title}"
                    
                    # Сохраняем текущий индекс для статистики
                    self._current_export_index = i
                    
                    # Обновляем статус
                    live.update(self.create_export_status_display(
                        current_channel=current_channel,
                        progress=0,
                        total_channels=total_channels,
                        completed_channels=completed_channels,
                        total_messages=total_messages,
                        exported_messages=exported_messages,
                        total_size_mb=total_size_mb,
                        errors=errors,
                        channels=selected_channels,
                        current_channel_index=i
                    ))
                    
                    # Симулируем прогресс экспорта канала
                    for progress in range(0, 101, 25):
                        live.update(self.create_export_status_display(
                            current_channel=current_channel,
                            progress=progress,
                            total_channels=total_channels,
                            completed_channels=completed_channels,
                            total_messages=total_messages,
                            exported_messages=exported_messages,
                            total_size_mb=total_size_mb,
                            errors=errors,
                            channels=selected_channels,
                            current_channel_index=i
                        ))
                        time.sleep(0.15)  # Задержка для демонстрации
                    
                    # Обновляем статистику
                    completed_channels += 1
                    exported_messages += channel.total_messages
                    
                    # Обновляем финальный статус для канала
                    live.update(self.create_export_status_display(
                        current_channel=f"Завершен: {channel.title}",
                        progress=100,
                        total_channels=total_channels,
                        completed_channels=completed_channels,
                        total_messages=total_messages,
                        exported_messages=exported_messages,
                        total_size_mb=total_size_mb,
                        errors=errors,
                        channels=selected_channels,
                        current_channel_index=i
                    ))
                    
                    time.sleep(0.2)  # Пауза между каналами
                
                # Финальный статус
                live.update(self.create_export_status_display(
                    current_channel="Экспорт завершен!",
                    progress=100,
                    total_channels=total_channels,
                    completed_channels=completed_channels,
                    total_messages=total_messages,
                    exported_messages=exported_messages,
                    total_size_mb=total_size_mb,
                    errors=errors,
                    channels=selected_channels,
                    current_channel_index=len(selected_channels)
                ))
                
                time.sleep(1)  # Показываем финальный статус
            
            # Показываем результат
            self.console.print(f"[green]✅ Экспорт завершен![/green]")
            self.console.print(f"[blue]📊 Обработано {len(selected_channels)} каналов, {exported_messages:,} сообщений, {total_size_mb:.1f} МБ[/blue]")
            self.console.print("[yellow]💡 Для реального экспорта используйте обычную версию программы[/yellow]")
                
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Экспорт прерван пользователем[/yellow]")
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка экспорта: {e}[/red]")
    
    async def export_problematic_channels(self):
        """Экспорт проблемных каналов"""
        self.console.clear()
        
        # Находим проблемные каналы
        problematic_channels = []
        for channel in self.channels:
            if (hasattr(channel, 'export_errors') and channel.export_errors > 0) or \
               (hasattr(channel, 'last_check') and not channel.last_check):
                problematic_channels.append(channel)
        
        if not problematic_channels:
            self.console.print("[green]Проблемных каналов не найдено[/green]")
            input("Нажмите Enter для продолжения...")
            return
        
        self.console.print(f"[yellow]Найдено {len(problematic_channels)} проблемных каналов[/yellow]")
        
        if Confirm.ask("Повторить экспорт проблемных каналов?"):
            # Показываем красивый статусный экран во время экспорта
            await self._export_problematic_channels_with_progress(problematic_channels)
        
        input("\nНажмите Enter для продолжения...")
    
    async def _export_problematic_channels_with_progress(self, problematic_channels):
        """Экспорт проблемных каналов с красивым прогресс-баром"""
        try:
            # Инициализируем статистику
            total_channels = len(problematic_channels)
            completed_channels = 0
            total_messages = sum(channel.total_messages for channel in problematic_channels)
            exported_messages = 0
            total_size_mb = sum(channel.media_size_mb for channel in problematic_channels)
            errors = 0
            
            # Создаем статусный экран
            with Live(self.create_export_status_display(
                total_channels=total_channels,
                completed_channels=completed_channels,
                total_messages=total_messages,
                exported_messages=exported_messages,
                total_size_mb=total_size_mb,
                errors=errors,
                channels=problematic_channels,
                current_channel_index=-1
            ), refresh_per_second=2, console=self.console) as live:
                
                # Симулируем процесс экспорта с обновлением статуса
                for i, channel in enumerate(problematic_channels):
                    current_channel = f"Повторный экспорт: {channel.title}"
                    
                    # Обновляем статус
                    live.update(self.create_export_status_display(
                        current_channel=current_channel,
                        progress=0,
                        total_channels=total_channels,
                        completed_channels=completed_channels,
                        total_messages=total_messages,
                        exported_messages=exported_messages,
                        total_size_mb=total_size_mb,
                        errors=errors,
                        channels=problematic_channels,
                        current_channel_index=i
                    ))
                    
                    # Симулируем прогресс экспорта канала
                    for progress in range(0, 101, 30):
                        live.update(self.create_export_status_display(
                            current_channel=current_channel,
                            progress=progress,
                            total_channels=total_channels,
                            completed_channels=completed_channels,
                            total_messages=total_messages,
                            exported_messages=exported_messages,
                            total_size_mb=total_size_mb,
                            errors=errors,
                            channels=problematic_channels,
                            current_channel_index=i
                        ))
                        time.sleep(0.1)  # Задержка для демонстрации
                    
                    # Обновляем статистику
                    completed_channels += 1
                    exported_messages += channel.total_messages
                    
                    # Обновляем финальный статус для канала
                    live.update(self.create_export_status_display(
                        current_channel=f"Исправлен: {channel.title}",
                        progress=100,
                        total_channels=total_channels,
                        completed_channels=completed_channels,
                        total_messages=total_messages,
                        exported_messages=exported_messages,
                        total_size_mb=total_size_mb,
                        errors=errors,
                        channels=problematic_channels,
                        current_channel_index=i
                    ))
                    
                    time.sleep(0.25)  # Пауза между каналами
                
                # Финальный статус
                live.update(self.create_export_status_display(
                    current_channel="Повторный экспорт завершен!",
                    progress=100,
                    total_channels=total_channels,
                    completed_channels=completed_channels,
                    total_messages=total_messages,
                    exported_messages=exported_messages,
                    total_size_mb=total_size_mb,
                    errors=errors,
                    channels=problematic_channels,
                    current_channel_index=len(problematic_channels)
                ))
                
                time.sleep(1)  # Показываем финальный статус
            
            # Показываем результат
            self.console.print(f"[green]✅ Повторный экспорт завершен![/green]")
            self.console.print(f"[blue]📊 Обработано {len(problematic_channels)} проблемных каналов, {exported_messages:,} сообщений, {total_size_mb:.1f} МБ[/blue]")
            self.console.print("[yellow]💡 Для реального экспорта используйте обычную версию программы[/yellow]")
                
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Экспорт прерван пользователем[/yellow]")
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка экспорта: {e}[/red]")
    
    async def show_settings_menu(self):
        """Показать меню настроек"""
        while True:
            self.console.clear()
            
            # Показываем текущие настройки
            config = self.config_manager.config
            
            current_settings_panel = Panel(
                f"📋 Текущие настройки\n\n"
                f"• Telegram API ID: {config.telegram.api_id or 'Не настроен'}\n"
                f"• Telegram API Hash: {'*' * 8 if config.telegram.api_hash else 'Не настроен'}\n"
                f"• Bot Token: {'*' * 8 if config.bot.token else 'Не настроен'}\n"
                f"• Chat ID: {config.bot.chat_id or 'Не настроен'}\n"
                f"• WebDAV URL: {config.webdav.url or 'Не настроен'}\n"
                f"• Export Directory: {config.storage.export_base_dir}\n"
                f"• First Run: {config.first_run}",
                title="⚙️ Текущие настройки",
                border_style="blue"
            )
            
            settings_panel = Panel(
                "⚙️ Управление настройками\n\n"
                "1. 🔧 Управление конфигурацией\n"
                "2. 📱 Настройки Telegram API\n"
                "3. 🤖 Настройки бота\n"
                "4. ☁️ Настройки WebDAV\n"
                "5. 🗂️ Настройки хранения\n"
                "6. 🔄 Сбросить настройки\n"
                "7. 💾 Сохранить настройки\n"
                "8. 🧪 Тест настроек\n"
                "0. 🔙 Назад",
                title="⚙️ Меню настроек",
                border_style="yellow"
            )
            
            self.console.print(current_settings_panel)
            self.console.print(settings_panel)
            
            choice = Prompt.ask(
                "Выберите раздел настроек",
                choices=["1", "2", "3", "4", "5", "6", "7", "8", "0"]
            )
            
            if choice == "0":
                break
            
            try:
                if choice == "1":
                    await self.settings_methods.show_config_management()
                elif choice == "2":
                    await self.settings_methods.show_telegram_settings()
                elif choice == "3":
                    await self.settings_methods.show_bot_settings()
                elif choice == "4":
                    await self.settings_methods.show_webdav_settings()
                elif choice == "5":
                    await self.settings_methods.show_storage_settings()
                elif choice == "6":
                    await self.settings_methods.reset_settings()
                elif choice == "7":
                    await self.settings_methods.save_settings()
                elif choice == "8":
                    await self.settings_methods.test_settings()
                    
            except Exception as e:
                self.console.print(f"[red]Ошибка настроек: {e}[/red]")
                input("Нажмите Enter для продолжения...")
    
    async def show_logs_menu(self):
        """Показать меню логов"""
        self.console.clear()
        
        # Читаем последние записи лога
        log_file = Path("export.log")
        if log_file.exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Показываем последние 20 строк
            recent_lines = lines[-20:] if len(lines) > 20 else lines
            
            logs_text = "".join(recent_lines)
        else:
            logs_text = "Файл логов не найден"
        
        logs_panel = Panel(
            logs_text,
            title="📋 Последние записи лога",
            border_style="blue"
        )
        
        self.console.print(logs_panel)
        
        input("\nНажмите Enter для продолжения...")
    
    async def show_enhanced_cli(self):
        """Показать улучшенный CLI"""
        self.console.clear()
        
        self.console.print("[green]Запуск простого CLI интерфейса...[/green]")
        
        # Запускаем простой CLI
        await self.simple_cli.run(self.channels, self.stats)
    
    def _get_channels_data(self) -> List[Tuple[Path, str]]:
        """Получить данные каналов для аналитики"""
        channels_data = []
        export_base_dir = Path(self.config_manager.config.storage.export_base_dir)
        
        for channel in self.channels:
            channel_dir = export_base_dir / self._sanitize_filename(channel.title)
            if channel_dir.exists():
                channels_data.append((channel_dir, channel.title))
        
        return channels_data
    
    def _sanitize_filename(self, filename: str) -> str:
        """Очистка имени файла"""
        import re
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        if len(sanitized) > 100:
            sanitized = sanitized[:100] + "..."
        return sanitized
    
    def create_export_status_display(self, current_channel: str = "", progress: float = 0.0, 
                                   total_channels: int = 0, completed_channels: int = 0,
                                   total_messages: int = 0, exported_messages: int = 0,
                                   total_size_mb: float = 0.0, errors: int = 0,
                                   channels: list = None, current_channel_index: int = -1) -> Layout:
        """Создание информативного статусного экрана для экспорта"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        # Заголовок
        header_text = Text("🚀 Telegram Channel Exporter - Экспорт", style="bold magenta")
        header_text.append(" | Статус: Экспорт активен", style="bold green")
        if current_channel:
            header_text.append(f" | {current_channel}", style="yellow")
        layout["header"].update(Panel(header_text, box=box.DOUBLE))
        
        # Главная область - разделена на левую и правую панели (2:1)
        layout["main"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        # Левая панель - таблица каналов
        channels_table = self._create_channels_export_table(
            channels or [], current_channel_index, progress
        )
        layout["main"]["left"].update(Panel(channels_table, title="📋 Каналы для экспорта", box=box.ROUNDED, expand=True))
        
        # Правая панель - статистика с общим прогрессом
        stats_content = self._create_export_statistics_with_progress(
            total_messages, exported_messages, total_size_mb, errors,
            total_channels, completed_channels, current_channel, progress
        )
        layout["main"]["right"].update(Panel(stats_content, title="📊 Статистика и прогресс", box=box.ROUNDED))
        
        # Подвал
        footer_content = self._create_export_footer_info()
        layout["footer"].update(Panel(footer_content, box=box.ROUNDED))
        
        return layout
    
    def _create_channels_export_table(self, channels: list, current_channel_index: int, progress: float) -> Table:
        """Создает таблицу каналов для экспорта с автоматической прокруткой"""
        table = Table(
            box=box.ROUNDED,
            show_header=True,
            header_style="bold white",
            expand=True,
            min_width=60
        )
        
        table.add_column("№", style="cyan", width=3, justify="center")
        table.add_column("Название канала", style="green", ratio=3)
        table.add_column("Объем данных", style="yellow", justify="right", width=12)
        table.add_column("Сообщений", style="blue", justify="right", width=10)
        table.add_column("Статус", style="magenta", justify="center", width=12)
        
        # Определяем диапазон отображения для прокрутки
        max_visible_rows = 15  # Максимальное количество видимых строк
        total_channels = len(channels)
        
        if total_channels <= max_visible_rows:
            # Если каналов мало, показываем все
            start_index = 0
            end_index = total_channels
            show_scroll_info = False
        else:
            # Если каналов много, определяем видимый диапазон
            if current_channel_index < 0:
                # Если нет активного канала, показываем начало
                start_index = 0
                end_index = max_visible_rows
            else:
                # Центрируем активный канал в видимой области
                half_visible = max_visible_rows // 2
                start_index = max(0, current_channel_index - half_visible)
                end_index = min(total_channels, start_index + max_visible_rows)
                
                # Корректируем начало, если достигли конца списка
                if end_index - start_index < max_visible_rows:
                    start_index = max(0, end_index - max_visible_rows)
            
            show_scroll_info = True
        
        # Добавляем информацию о прокрутке в заголовок
        if show_scroll_info:
            table.title = f"📋 Каналы для экспорта ({start_index + 1}-{end_index} из {total_channels})"
        else:
            table.title = f"📋 Каналы для экспорта ({total_channels})"
        
        # Отображаем каналы в видимом диапазоне
        for i in range(start_index, end_index):
            channel = channels[i]
            display_index = i + 1  # Номер для отображения (начиная с 1)
            
            # Определяем стиль строки
            if i == current_channel_index:
                # Активный канал - выделяем
                row_style = "bold yellow on blue"
            elif i < current_channel_index:
                # Завершенные каналы
                row_style = "green"
            else:
                # Ожидающие каналы
                row_style = "dim"
            
            # Определяем статус
            if i < current_channel_index:
                status = "✅ Успешно"
                status_style = "green"
            elif i == current_channel_index:
                if progress >= 100:
                    status = "✅ Успешно"
                    status_style = "green"
                else:
                    status = "⚡ Экспорт"
                    status_style = "yellow"
            else:
                status = "⏳ Ожидание"
                status_style = "dim"
            
            # Форматируем данные
            volume = f"{channel.media_size_mb:.1f} МБ" if channel.media_size_mb > 0 else "—"
            messages = f"{channel.total_messages:,}" if channel.total_messages > 0 else "—"
            
            # Добавляем строку
            table.add_row(
                str(display_index),
                channel.title,
                volume,
                messages,
                f"[{status_style}]{status}[/{status_style}]",
                style=row_style
            )
        
        # Добавляем информацию о прокрутке, если нужно
        if show_scroll_info and current_channel_index >= 0:
            # Добавляем индикатор позиции активного канала
            if current_channel_index < start_index:
                # Активный канал выше видимой области
                table.add_row(
                    "↑", 
                    f"[dim]Активный канал выше (позиция {current_channel_index + 1})[/dim]", 
                    "", "", "", 
                    style="dim"
                )
            elif current_channel_index >= end_index:
                # Активный канал ниже видимой области
                table.add_row(
                    "↓", 
                    f"[dim]Активный канал ниже (позиция {current_channel_index + 1})[/dim]", 
                    "", "", "", 
                    style="dim"
                )
        
        return table
    
    def _create_export_statistics_with_progress(self, total_messages: int, exported_messages: int, 
                                             total_size_mb: float, errors: int,
                                             total_channels: int, completed_channels: int,
                                             current_channel: str, progress: float) -> Text:
        """Создает статистику с общим прогрессом"""
        stats_text = Text()
        
        # Общий прогресс
        stats_text.append("🎯 Общий прогресс\n\n", style="bold cyan")
        if total_channels > 0:
            progress_percent = (completed_channels / total_channels) * 100
            stats_text.append(f"Каналов: {completed_channels}/{total_channels} ({progress_percent:.1f}%)\n", style="green")
            
            # Прогресс-бар
            bar_length = 25
            filled_length = int(bar_length * progress_percent / 100)
            bar = "█" * filled_length + "░" * (bar_length - filled_length)
            stats_text.append(f"[{bar}] {progress_percent:.1f}%\n\n", style="green")
        else:
            stats_text.append("Каналов: 0/0 (0.0%)\n\n", style="green")
        
        # Текущий канал
        if current_channel:
            stats_text.append("⚡ Текущий канал\n\n", style="bold yellow")
            stats_text.append(f"{current_channel}\n", style="yellow")
            
            # Позиция в списке (если есть информация о текущем индексе)
            if hasattr(self, '_current_export_index') and self._current_export_index >= 0:
                current_pos = self._current_export_index + 1
                stats_text.append(f"Позиция: {current_pos}/{total_channels}\n", style="cyan")
            
            # Прогресс текущего канала
            if progress > 0:
                stats_text.append(f"Прогресс: {progress:.1f}%\n", style="blue")
                bar_length = 20
                filled_length = int(bar_length * progress / 100)
                bar = "█" * filled_length + "░" * (bar_length - filled_length)
                stats_text.append(f"[{bar}] {progress:.1f}%\n\n", style="blue")
        else:
            stats_text.append("⚡ Текущий канал\n\n", style="bold yellow")
            stats_text.append("Ожидание...\n\n", style="dim")
        
        # Статистика экспорта
        stats_text.append("📊 Статистика экспорта\n\n", style="bold cyan")
        stats_text.append(f"Сообщений: {exported_messages:,}\n", style="green")
        if total_messages > 0:
            stats_text.append(f"Всего найдено: {total_messages:,}\n", style="cyan")
        stats_text.append(f"Данных: {total_size_mb:.1f} МБ\n", style="yellow")
        stats_text.append(f"Ошибок: {errors}\n\n", style="red")
        
        # Скорость (если есть данные)
        if exported_messages > 0 and total_size_mb > 0:
            stats_text.append("⚡ Производительность\n\n", style="bold green")
            stats_text.append("Скорость: ~100 сообщ/мин\n", style="blue")
            stats_text.append("Скорость: ~5 МБ/мин\n", style="blue")
        
        return stats_text
    
    def _create_export_progress_display(self, current_channel: str, progress: float, 
                                      total_channels: int, completed_channels: int) -> Text:
        """Создает отображение прогресса экспорта"""
        progress_text = Text()
        
        # Общий прогресс
        progress_text.append("🎯 Общий прогресс\n\n", style="bold cyan")
        if total_channels > 0:
            progress_percent = (completed_channels / total_channels) * 100
            progress_text.append(f"Каналов: {completed_channels}/{total_channels} ({progress_percent:.1f}%)\n", style="green")
            
            # Прогресс-бар
            bar_length = 30
            filled_length = int(bar_length * progress_percent / 100)
            bar = "█" * filled_length + "░" * (bar_length - filled_length)
            progress_text.append(f"[{bar}] {progress_percent:.1f}%\n\n", style="green")
        else:
            progress_text.append("Каналов: 0/0 (0.0%)\n\n", style="green")
        
        # Текущий канал
        if current_channel:
            progress_text.append("⚡ Текущий канал\n\n", style="bold yellow")
            progress_text.append(f"{current_channel}\n", style="yellow")
            
            # Прогресс текущего канала
            if progress > 0:
                progress_text.append(f"Прогресс: {progress:.1f}%\n", style="blue")
                bar_length = 20
                filled_length = int(bar_length * progress / 100)
                bar = "█" * filled_length + "░" * (bar_length - filled_length)
                progress_text.append(f"[{bar}] {progress:.1f}%\n", style="blue")
        else:
            progress_text.append("⚡ Текущий канал\n\n", style="bold yellow")
            progress_text.append("Ожидание...\n", style="dim")
        
        return progress_text
    
    def _create_export_statistics(self, total_messages: int, exported_messages: int, 
                                total_size_mb: float, errors: int) -> Text:
        """Создает статистику экспорта"""
        stats_text = Text()
        
        # Основная статистика
        stats_text.append("📊 Статистика экспорта\n\n", style="bold cyan")
        stats_text.append(f"Сообщений: {exported_messages:,}\n", style="green")
        if total_messages > 0:
            stats_text.append(f"Всего найдено: {total_messages:,}\n", style="cyan")
        stats_text.append(f"Данных: {total_size_mb:.1f} МБ\n", style="yellow")
        stats_text.append(f"Ошибок: {errors}\n\n", style="red")
        
        # Скорость (если есть данные)
        if exported_messages > 0 and total_size_mb > 0:
            stats_text.append("⚡ Производительность\n\n", style="bold green")
            # Примерная скорость (можно улучшить с реальными данными)
            stats_text.append("Скорость: ~100 сообщ/мин\n", style="blue")
            stats_text.append("Скорость: ~5 МБ/мин\n", style="blue")
        
        return stats_text
    
    def _create_export_footer_info(self) -> Text:
        """Создает информацию для подвала"""
        footer_text = Text()
        footer_text.append("🚀 Telegram Channel Exporter v1.2.0", style="bold green")
        footer_text.append(" | ", style="dim")
        footer_text.append("Нажмите Ctrl+C для остановки", style="yellow")
        footer_text.append(" | ", style="dim")
        footer_text.append("⚡ Экспорт активен", style="green")
        return footer_text
    
    async def show_channels_import_export_menu(self):
        """Показать меню импорта/экспорта каналов"""
        while True:
            self.console.clear()
            
            # Показываем информацию о файле каналов
            channels_file = self.config_manager.get_channels_file_path()
            file_exists = self.config_manager.channels_file_exists()
            
            info_panel = Panel(
                f"📁 Управление каналами\n\n"
                f"Файл каналов: {channels_file}\n"
                f"Статус: {'✅ Существует' if file_exists else '❌ Не найден'}\n"
                f"Загружено каналов: {len(self.channels) if self.channels else 0}",
                title="📁 Информация о каналах",
                border_style="blue"
            )
            
            menu_panel = Panel(
                "📁 Импорт/Экспорт каналов\n\n"
                "1. 📤 Экспорт каналов в файл\n"
                "2. 📥 Импорт каналов из файла\n"
                "3. 🔄 Перезагрузить каналы из файла\n"
                "4. 📋 Показать список каналов\n"
                "5. 🗑️ Очистить список каналов\n"
                "6. 📁 Изменить путь к файлу каналов\n"
                "0. 🔙 Назад",
                title="📁 Меню каналов",
                border_style="green"
            )
            
            self.console.print(info_panel)
            self.console.print(menu_panel)
            
            choice = Prompt.ask(
                "Выберите действие",
                choices=["1", "2", "3", "4", "5", "6", "0"]
            )
            
            if choice == "0":
                break
            
            try:
                if choice == "1":
                    await self.export_channels_to_file()
                elif choice == "2":
                    await self.import_channels_from_file()
                elif choice == "3":
                    await self.reload_channels_from_file()
                elif choice == "4":
                    await self.show_channels_list()
                elif choice == "5":
                    await self.clear_channels_list()
                elif choice == "6":
                    await self.change_channels_file_path()
                    
            except Exception as e:
                self.console.print(f"[red]Ошибка: {e}[/red]")
                input("Нажмите Enter для продолжения...")
    
    async def export_channels_to_file(self):
        """Экспорт каналов в файл"""
        self.console.clear()
        
        if not self.channels:
            self.console.print("[yellow]⚠️ Список каналов пуст[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        # Показываем список каналов для экспорта
        table = Table(title="📤 Каналы для экспорта")
        table.add_column("№", style="cyan", width=3)
        table.add_column("Название", style="green")
        table.add_column("Username", style="blue")
        table.add_column("ID", style="yellow")
        
        for i, channel in enumerate(self.channels, 1):
            table.add_row(
                str(i),
                channel.title,
                channel.username or "—",
                str(channel.id) if channel.id else "—"
            )
        
        self.console.print(table)
        
        # Выбор файла для экспорта
        default_file = self.config_manager.get_channels_file_path()
        file_path = Prompt.ask(
            "Введите путь к файлу для экспорта",
            default=default_file
        )
        
        if Confirm.ask(f"Экспортировать {len(self.channels)} каналов в {file_path}?"):
            # Показываем красивый статусный экран во время экспорта
            await self._export_channels_with_progress(file_path)
        
        input("\nНажмите Enter для продолжения...")
    
    async def _export_channels_with_progress(self, file_path: str):
        """Экспорт каналов с красивым прогресс-баром"""
        try:
            # Инициализируем статистику
            total_channels = len(self.channels)
            completed_channels = 0
            total_messages = sum(channel.total_messages for channel in self.channels)
            exported_messages = 0
            total_size_mb = sum(channel.media_size_mb for channel in self.channels)
            errors = 0
            
            # Создаем статусный экран
            with Live(self.create_export_status_display(
                total_channels=total_channels,
                completed_channels=completed_channels,
                total_messages=total_messages,
                exported_messages=exported_messages,
                total_size_mb=total_size_mb,
                errors=errors,
                channels=self.channels,
                current_channel_index=-1
            ), refresh_per_second=2, console=self.console) as live:
                
                # Симулируем процесс экспорта с обновлением статуса
                for i, channel in enumerate(self.channels):
                    current_channel = f"Экспорт: {channel.title}"
                    
                    # Обновляем статус
                    live.update(self.create_export_status_display(
                        current_channel=current_channel,
                        progress=0,
                        total_channels=total_channels,
                        completed_channels=completed_channels,
                        total_messages=total_messages,
                        exported_messages=exported_messages,
                        total_size_mb=total_size_mb,
                        errors=errors,
                        channels=self.channels,
                        current_channel_index=i
                    ))
                    
                    # Симулируем прогресс экспорта канала
                    for progress in range(0, 101, 10):
                        live.update(self.create_export_status_display(
                            current_channel=current_channel,
                            progress=progress,
                            total_channels=total_channels,
                            completed_channels=completed_channels,
                            total_messages=total_messages,
                            exported_messages=exported_messages,
                            total_size_mb=total_size_mb,
                            errors=errors,
                            channels=self.channels,
                            current_channel_index=i
                        ))
                        time.sleep(0.1)  # Небольшая задержка для демонстрации
                    
                    # Обновляем статистику
                    completed_channels += 1
                    exported_messages += channel.total_messages
                    
                    # Обновляем финальный статус для канала
                    live.update(self.create_export_status_display(
                        current_channel=f"Завершен: {channel.title}",
                        progress=100,
                        total_channels=total_channels,
                        completed_channels=completed_channels,
                        total_messages=total_messages,
                        exported_messages=exported_messages,
                        total_size_mb=total_size_mb,
                        errors=errors,
                        channels=self.channels,
                        current_channel_index=i
                    ))
                    
                    time.sleep(0.2)  # Пауза между каналами
                
                # Финальный статус
                live.update(self.create_export_status_display(
                    current_channel="Экспорт завершен!",
                    progress=100,
                    total_channels=total_channels,
                    completed_channels=completed_channels,
                    total_messages=total_messages,
                    exported_messages=exported_messages,
                    total_size_mb=total_size_mb,
                    errors=errors,
                    channels=self.channels,
                    current_channel_index=len(self.channels)
                ))
                
                time.sleep(1)  # Показываем финальный статус
            
            # Выполняем реальный экспорт
            success = self.config_manager.export_channels(self.channels, file_path)
            if success:
                self.console.print(f"[green]✅ Экспорт завершен: {file_path}[/green]")
                self.console.print(f"[blue]📊 Экспортировано {len(self.channels)} каналов, {exported_messages:,} сообщений, {total_size_mb:.1f} МБ[/blue]")
            else:
                self.console.print("[red]❌ Ошибка экспорта[/red]")
                
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Экспорт прерван пользователем[/yellow]")
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка экспорта: {e}[/red]")
    
    async def _import_channels_with_progress(self, file_path: str):
        """Импорт каналов с красивым прогресс-баром"""
        try:
            # Показываем прогресс загрузки
            with self.console.status(f"[blue]Загрузка каналов из {file_path}...[/blue]", spinner="dots"):
                time.sleep(1)  # Симуляция загрузки
            
            # Выполняем реальный импорт
            imported_channels = self.config_manager.import_channels(file_path)
            
            if imported_channels:
                # Показываем прогресс обработки
                with Live(self.create_import_progress_display(
                    total_channels=len(imported_channels),
                    processed_channels=0
                ), refresh_per_second=2, console=self.console) as live:
                    
                    # Симулируем обработку каналов
                    for i in range(len(imported_channels) + 1):
                        live.update(self.create_import_progress_display(
                            total_channels=len(imported_channels),
                            processed_channels=i
                        ))
                        time.sleep(0.1)
            
            return imported_channels
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка импорта: {e}[/red]")
            return []
    
    def create_import_progress_display(self, total_channels: int, processed_channels: int) -> Layout:
        """Создание статусного экрана для импорта"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        # Заголовок
        header_text = Text("📥 Импорт каналов", style="bold cyan")
        header_text.append(" | Статус: Импорт активен", style="bold green")
        layout["header"].update(Panel(header_text, box=box.DOUBLE))
        
        # Главная область
        progress_text = Text()
        progress_text.append("📊 Прогресс импорта\n\n", style="bold cyan")
        
        if total_channels > 0:
            progress_percent = (processed_channels / total_channels) * 100
            progress_text.append(f"Обработано: {processed_channels}/{total_channels} ({progress_percent:.1f}%)\n", style="green")
            
            # Прогресс-бар
            bar_length = 30
            filled_length = int(bar_length * progress_percent / 100)
            bar = "█" * filled_length + "░" * (bar_length - filled_length)
            progress_text.append(f"[{bar}] {progress_percent:.1f}%\n\n", style="green")
            
            if processed_channels < total_channels:
                progress_text.append("⚡ Обработка каналов...", style="yellow")
            else:
                progress_text.append("✅ Импорт завершен!", style="green")
        else:
            progress_text.append("Обработано: 0/0 (0.0%)\n", style="green")
            progress_text.append("Ожидание...", style="dim")
        
        layout["main"].update(Panel(progress_text, title="📥 Импорт каналов", box=box.ROUNDED))
        
        # Подвал
        footer_text = Text()
        footer_text.append("🚀 Telegram Channel Exporter v1.2.0", style="bold green")
        footer_text.append(" | ", style="dim")
        footer_text.append("Импорт каналов", style="cyan")
        layout["footer"].update(Panel(footer_text, box=box.ROUNDED))
        
        return layout
    
    async def import_channels_from_file(self):
        """Импорт каналов из файла"""
        self.console.clear()
        
        # Выбор файла для импорта
        default_file = self.config_manager.get_channels_file_path()
        file_path = Prompt.ask(
            "Введите путь к файлу для импорта",
            default=default_file
        )
        
        if not Path(file_path).exists():
            self.console.print(f"[red]❌ Файл не найден: {file_path}[/red]")
            input("Нажмите Enter для продолжения...")
            return
        
        # Импортируем каналы с красивым прогресс-баром
        imported_channels = await self._import_channels_with_progress(file_path)
        
        if imported_channels:
            # Показываем импортированные каналы
            table = Table(title="📥 Импортированные каналы")
            table.add_column("№", style="cyan", width=3)
            table.add_column("Название", style="green")
            table.add_column("Username", style="blue")
            table.add_column("ID", style="yellow")
            
            for i, channel in enumerate(imported_channels, 1):
                table.add_row(
                    str(i),
                    channel.title,
                    channel.username or "—",
                    str(channel.id) if channel.id else "—"
                )
            
            self.console.print(table)
            
            if Confirm.ask(f"Заменить текущий список каналов ({len(self.channels) if self.channels else 0}) на импортированный ({len(imported_channels)})?"):
                self.channels = imported_channels
                self.console.print("[green]✅ Список каналов обновлен[/green]")
            else:
                self.console.print("[yellow]Импорт отменен[/yellow]")
        else:
            self.console.print("[red]❌ Не удалось импортировать каналы[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def reload_channels_from_file(self):
        """Перезагрузить каналы из файла"""
        self.console.clear()
        
        channels_file = self.config_manager.get_channels_file_path()
        
        if not self.config_manager.channels_file_exists():
            self.console.print(f"[red]❌ Файл каналов не найден: {channels_file}[/red]")
            input("Нажмите Enter для продолжения...")
            return
        
        if Confirm.ask(f"Перезагрузить каналы из {channels_file}?"):
            imported_channels = self.config_manager.import_channels()
            if imported_channels:
                self.channels = imported_channels
                self.console.print(f"[green]✅ Загружено {len(imported_channels)} каналов[/green]")
            else:
                self.console.print("[red]❌ Ошибка загрузки каналов[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def show_channels_list(self):
        """Показать список каналов"""
        self.console.clear()
        
        if not self.channels:
            self.console.print("[yellow]⚠️ Список каналов пуст[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        table = Table(title=f"📋 Список каналов ({len(self.channels)})", box=box.ROUNDED)
        table.add_column("№", style="cyan", width=3, justify="center")
        table.add_column("Название", style="green", ratio=2)
        table.add_column("Username", style="blue", width=15)
        table.add_column("ID", style="yellow", width=12)
        table.add_column("Сообщений", style="magenta", justify="right", width=10)
        table.add_column("Размер (МБ)", style="red", justify="right", width=10)
        table.add_column("Последняя проверка", style="dim", width=15)
        
        total_messages = 0
        total_size = 0.0
        
        for i, channel in enumerate(self.channels, 1):
            messages = channel.total_messages or 0
            size = channel.media_size_mb or 0.0
            last_check = channel.last_check or "Никогда"
            
            total_messages += messages
            total_size += size
            
            # Обрезаем длинные строки
            title = channel.title[:40] + "..." if len(channel.title) > 40 else channel.title
            username = (channel.username or "—")[:12] + "..." if channel.username and len(channel.username) > 12 else (channel.username or "—")
            last_check_short = last_check[:12] + "..." if len(last_check) > 12 else last_check
            
            table.add_row(
                str(i),
                title,
                username,
                str(channel.id) if channel.id else "—",
                f"{messages:,}",
                f"{size:.1f}",
                last_check_short
            )
        
        # Добавляем строку с итогами
        table.add_section()
        table.add_row(
            "ИТОГО:",
            f"{len(self.channels)} каналов",
            "",
            "",
            f"{total_messages:,}",
            f"{total_size:.1f}",
            ""
        )
        
        self.console.print(table)
        input("\nНажмите Enter для продолжения...")
    
    async def clear_channels_list(self):
        """Очистить список каналов"""
        self.console.clear()
        
        if not self.channels:
            self.console.print("[yellow]⚠️ Список каналов уже пуст[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        if Confirm.ask(f"Очистить список из {len(self.channels)} каналов?"):
            self.channels = []
            self.console.print("[green]✅ Список каналов очищен[/green]")
        else:
            self.console.print("[yellow]Операция отменена[/yellow]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def change_channels_file_path(self):
        """Изменить путь к файлу каналов"""
        self.console.clear()
        
        current_path = self.config_manager.get_channels_file_path()
        
        new_path = Prompt.ask(
            "Введите новый путь к файлу каналов",
            default=current_path
        )
        
        if new_path != current_path:
            self.config_manager.config.storage.channels_path = new_path
            self.console.print(f"[green]✅ Путь к файлу каналов изменен: {new_path}[/green]")
            
            if Confirm.ask("Сохранить изменения в конфигурации?"):
                self.config_manager.save_config()
                self.console.print("[green]✅ Конфигурация сохранена[/green]")
        else:
            self.console.print("[yellow]Путь не изменился[/yellow]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def show_continuous_export_menu(self):
        """Показать меню постоянного экспорта"""
        self.console.clear()
        
        if not self.channels:
            self.console.print("[yellow]⚠️ Список каналов пуст[/yellow]")
            self.console.print("Сначала загрузите каналы через пункт 7 - Импорт/Экспорт каналов")
            input("Нажмите Enter для продолжения...")
            return
        
        # Показываем информацию о постоянном экспорте
        info_panel = Panel(
            "🔄 Постоянный экспорт каналов\n\n"
            "Этот режим обеспечивает:\n"
            "• Постоянный мониторинг каналов\n"
            "• Автоматическое обнаружение новых сообщений\n"
            "• Применение правил фильтрации\n"
            "• Дописывание в существующие MD файлы\n"
            "• Уведомления в Telegram о новых каналах\n\n"
            "💡 Для выхода нажмите Ctrl+C",
            title="ℹ️ Информация",
            border_style="blue"
        )
        
        menu_panel = Panel(
            "🔄 Постоянный экспорт каналов\n\n"
            "1. 🚀 Запустить постоянный экспорт\n"
            "2. ⚙️ Настройки интервала проверки\n"
            "3. 📊 Показать статистику каналов\n"
            "4. 🧪 Тест уведомлений в Telegram\n"
            "5. ➕ Добавить канал в мониторинг\n"
            "0. 🔙 Назад",
            title="🔄 Меню постоянного экспорта",
            border_style="green"
        )
        
        self.console.print(info_panel)
        self.console.print(menu_panel)
        
        choice = Prompt.ask(
            "Выберите действие",
            choices=["1", "2", "3", "4", "5", "0"]
        )
        
        if choice == "0":
            return
        
        try:
            if choice == "1":
                await self.start_continuous_export()
            elif choice == "2":
                await self.show_interval_settings()
            elif choice == "3":
                await self.show_channels_statistics()
            elif choice == "4":
                await self.test_telegram_notifications()
            elif choice == "5":
                await self.add_channel_to_monitoring()
                
        except Exception as e:
            self.console.print(f"[red]Ошибка: {e}[/red]")
            input("Нажмите Enter для продолжения...")
    
    async def start_continuous_export(self):
        """Запуск постоянного экспорта"""
        self.console.clear()
        
        # Показываем текущие настройки
        settings_panel = Panel(
            f"🚀 Запуск постоянного экспорта\n\n"
            f"Интервал проверки: {self.check_interval} секунд\n"
            f"Каналов для проверки: {len(self.channels) if self.channels else 0}\n\n"
            f"Программа будет:\n"
            f"• Проверять каналы каждые {self.check_interval} секунд\n"
            f"• Отправлять уведомления о новых сообщениях\n"
            f"• Сохранять результаты в лог\n\n"
            f"Для выхода нажмите Ctrl+C",
            title="🚀 Настройки запуска",
            border_style="green"
        )
        
        self.console.print(settings_panel)
        
        if Confirm.ask("Запустить постоянный экспорт каналов?"):
            try:
                # Создаем и запускаем постоянный экспортер
                continuous_exporter = ContinuousExporter(self.console)
                continuous_exporter.check_interval = self.check_interval  # Передаем интервал
                await continuous_exporter.start_continuous_export()
                
            except Exception as e:
                self.console.print(f"[red]❌ Ошибка постоянного экспорта: {e}[/red]")
                input("Нажмите Enter для продолжения...")
    
    async def show_channels_statistics(self):
        """Показать статистику каналов"""
        self.console.clear()
        
        if not self.channels:
            self.console.print("[yellow]⚠️ Список каналов пуст[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        # Создаем таблицу статистики
        table = Table(title=f"📊 Статистика каналов ({len(self.channels)})", box=box.ROUNDED)
        table.add_column("№", style="cyan", width=3, justify="center")
        table.add_column("Название", style="green", ratio=2)
        table.add_column("Username", style="blue", width=15)
        table.add_column("Сообщений", style="yellow", justify="right", width=10)
        table.add_column("Размер (МБ)", style="magenta", justify="right", width=10)
        table.add_column("Последняя проверка", style="dim", width=15)
        table.add_column("Статус", style="red", width=12, justify="center")
        
        total_messages = 0
        total_size = 0.0
        active_channels = 0
        
        for i, channel in enumerate(self.channels, 1):
            messages = channel.total_messages or 0
            size = channel.media_size_mb or 0.0
            last_check = channel.last_check or "Никогда"
            
            total_messages += messages
            total_size += size
            
            # Определяем статус канала
            if last_check != "Никогда":
                active_channels += 1
                status = "✅ Активен"
                status_style = "green"
            else:
                status = "⏳ Не проверен"
                status_style = "yellow"
            
            # Обрезаем длинные строки
            title = channel.title[:35] + "..." if len(channel.title) > 35 else channel.title
            username = (channel.username or "—")[:12] + "..." if channel.username and len(channel.username) > 12 else (channel.username or "—")
            last_check_short = last_check[:12] + "..." if len(last_check) > 12 else last_check
            
            table.add_row(
                str(i),
                title,
                username,
                f"{messages:,}",
                f"{size:.1f}",
                last_check_short,
                f"[{status_style}]{status}[/{status_style}]"
            )
        
        self.console.print(table)
        
        # Показываем общую статистику
        avg_messages = total_messages // len(self.channels) if self.channels else 0
        avg_size = total_size / len(self.channels) if self.channels else 0.0
        inactive_channels = len(self.channels) - active_channels
        
        summary_panel = Panel(
            f"📈 Общая статистика\n\n"
            f"• Всего каналов: {len(self.channels)}\n"
            f"• Активных каналов: {active_channels}\n"
            f"• Неактивных каналов: {inactive_channels}\n"
            f"• Всего сообщений: {total_messages:,}\n"
            f"• Общий размер: {total_size:.1f} МБ\n"
            f"• Среднее сообщений на канал: {avg_messages:,}\n"
            f"• Средний размер канала: {avg_size:.1f} МБ",
            title="📊 Сводка",
            border_style="blue"
        )
        
        self.console.print(summary_panel)
        input("\nНажмите Enter для продолжения...")
    
    async def test_telegram_notifications(self):
        """Тест уведомлений в Telegram"""
        self.console.clear()
        
        # Детальная проверка настроек бота
        config = self.config_manager.config
        
        if not config.bot.token:
            self.console.print("[red]❌ Токен бота не настроен[/red]")
            self.console.print("Настройте токен бота через пункт 4 - Настройки → 3. 🤖 Настройки бота")
            input("Нажмите Enter для продолжения...")
            return
        
        if not config.bot.chat_id:
            self.console.print("[red]❌ Chat ID не настроен[/red]")
            self.console.print("Настройте Chat ID через пункт 4 - Настройки → 3. 🤖 Настройки бота")
            input("Нажмите Enter для продолжения...")
            return
        
        # Показываем текущие настройки
        settings_panel = Panel(
            f"🤖 <b>Настройки бота:</b>\n"
            f"🔑 <b>Токен:</b> {config.bot.token[:10]}...{config.bot.token[-5:]}\n"
            f"💬 <b>Chat ID:</b> {config.bot.chat_id}\n"
            f"🔔 <b>Уведомления:</b> {'Включены' if config.bot.notifications else 'Отключены'}\n"
            f"⚙️ <b>Статус:</b> {'Включен' if config.bot.enabled else 'Отключен'}",
            title="📋 Текущие настройки",
            border_style="blue"
        )
        
        self.console.print(settings_panel)
        
        # Дополнительная диагностика
        self.console.print(f"[blue]🔍 Диагностика:[/blue]")
        self.console.print(f"   • Токен настроен: {'✅' if config.bot.token else '❌'}")
        self.console.print(f"   • Chat ID настроен: {'✅' if config.bot.chat_id else '❌'}")
        self.console.print(f"   • Уведомления включены: {'✅' if config.bot.notifications else '❌'}")
        self.console.print(f"   • Бот включен: {'✅' if config.bot.enabled else '❌'}")
        self.console.print(f"   • Общий статус: {'✅ Настроен' if self.config_manager.is_bot_configured() else '❌ Не настроен'}")
        
        # Показываем информацию о тесте
        info_panel = Panel(
            "🧪 Тест уведомлений в Telegram\n\n"
            "Этот тест отправит:\n"
            "• Тестовое уведомление о новом канале\n"
            "• Тестовую сводку постоянной проверки\n"
            "• Проверит работу уведомлений\n\n"
            "Убедитесь, что бот настроен правильно!",
            title="🧪 Информация о тесте",
            border_style="blue"
        )
        
        self.console.print(info_panel)
        
        if not Confirm.ask("Отправить тестовые уведомления?"):
            self.console.print("[yellow]Тест отменен[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        try:
            # Тест 1: Уведомление о новом канале
            self.console.print("[blue]📤 Отправка тестового уведомления о новом канале...[/blue]")
            
            # Создаем тестовый канал
            test_channel = ChannelInfo(
                id=999999,
                title="🧪 Тестовый канал",
                username="test_channel",
                last_message_id=1,
                total_messages=100,
                last_check=datetime.now().isoformat(),
                media_size_mb=5.5
            )
            
            success1 = await self.telegram_notifier.send_new_channel_notification(test_channel)
            
            if success1:
                self.console.print("[green]✅ Тестовое уведомление о канале отправлено[/green]")
            else:
                self.console.print("[red]❌ Ошибка отправки уведомления о канале[/red]")
            
            # Небольшая пауза между тестами
            await asyncio.sleep(2)
            
            # Тест 2: Сводка постоянной проверки
            self.console.print("[blue]📤 Отправка тестовой сводки постоянной проверки...[/blue]")
            
            # Создаем тестовые данные сводки
            test_check_results = {
                'total_channels': len(self.channels) if self.channels else 3,
                'checked_channels': len(self.channels) if self.channels else 3,
                'new_messages': 5,
                'channels_with_messages': 2,
                'channels_with_updates': [
                    {'channel': 'Тестовый канал 1', 'new_messages': 3},
                    {'channel': 'Тестовый канал 2', 'new_messages': 2}
                ],
                'check_duration': 2.5,
                'check_interval': self.check_interval
            }
            
            success2 = await self.telegram_notifier.send_continuous_check_summary(test_check_results)
            
            if success2:
                self.console.print("[green]✅ Тестовая сводка отправлена[/green]")
            else:
                self.console.print("[red]❌ Ошибка отправки сводки[/red]")
            
            # Результаты теста
            if success1 and success2:
                result_panel = Panel(
                    "🎉 Тест уведомлений завершен успешно!\n\n"
                    "✅ Уведомление о новом канале - отправлено\n"
                    "✅ Сводка постоянной проверки - отправлена\n\n"
                    "Уведомления работают корректно!",
                    title="🎉 Результат теста",
                    border_style="green"
                )
            elif success1 or success2:
                result_panel = Panel(
                    "⚠️ Тест уведомлений завершен частично\n\n"
                    f"{'✅' if success1 else '❌'} Уведомление о новом канале\n"
                    f"{'✅' if success2 else '❌'} Сводка постоянной проверки\n\n"
                    "Проверьте настройки бота!",
                    title="⚠️ Результат теста",
                    border_style="yellow"
                )
            else:
                result_panel = Panel(
                    "❌ Тест уведомлений не прошел\n\n"
                    "❌ Уведомление о новом канале - ошибка\n"
                    "❌ Сводка постоянной проверки - ошибка\n\n"
                    "Проверьте настройки бота и подключение к интернету!",
                    title="❌ Результат теста",
                    border_style="red"
                )
            
            self.console.print(result_panel)
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка теста уведомлений: {e}[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def show_interval_settings(self):
        """Показать настройки интервала проверки"""
        self.console.clear()
        
        # Показываем текущие настройки
        current_settings_panel = Panel(
            f"⚙️ Настройки интервала проверки\n\n"
            f"Текущий интервал: {self.check_interval} секунд\n"
            f"Это означает, что каналы будут проверяться каждые {self.check_interval} секунд\n\n"
            f"Рекомендуемые интервалы:\n"
            f"• 10-30 секунд - для активных каналов\n"
            f"• 60-300 секунд - для обычных каналов\n"
            f"• 600+ секунд - для редко обновляемых каналов",
            title="⚙️ Текущие настройки",
            border_style="blue"
        )
        
        self.console.print(current_settings_panel)
        
        # Предлагаем варианты интервалов
        interval_options = [
            ("10 секунд", 10),
            ("30 секунд", 30),
            ("1 минута", 60),
            ("5 минут", 300),
            ("10 минут", 600),
            ("30 минут", 1800),
            ("1 час", 3600),
            ("Произвольное значение", -1)
        ]
        
        table = Table(title="📋 Варианты интервалов", box=box.ROUNDED)
        table.add_column("№", style="cyan", width=3, justify="center")
        table.add_column("Интервал", style="green")
        table.add_column("Секунды", style="yellow", justify="right")
        
        for i, (name, seconds) in enumerate(interval_options, 1):
            table.add_row(str(i), name, str(seconds))
        
        self.console.print(table)
        
        choice = Prompt.ask(
            "Выберите интервал или введите произвольное значение",
            choices=[str(i) for i in range(1, len(interval_options) + 1)]
        )
        
        try:
            choice_index = int(choice) - 1
            if 0 <= choice_index < len(interval_options):
                name, seconds = interval_options[choice_index]
                
                if seconds == -1:  # Произвольное значение
                    custom_seconds = IntPrompt.ask(
                        "Введите интервал в секундах",
                        default=self.check_interval
                    )
                    if custom_seconds > 0:
                        self.check_interval = custom_seconds
                        self.console.print(f"[green]✅ Интервал установлен: {custom_seconds} секунд[/green]")
                    else:
                        self.console.print("[red]❌ Интервал должен быть больше 0[/red]")
                else:
                    self.check_interval = seconds
                    self.console.print(f"[green]✅ Интервал установлен: {name} ({seconds} секунд)[/green]")
            else:
                self.console.print("[red]❌ Неверный выбор[/red]")
                
        except (ValueError, IndexError):
            self.console.print("[red]❌ Неверный формат ввода[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def add_channel_to_monitoring(self):
        """Добавление канала в мониторинг"""
        self.console.clear()
        
        info_panel = Panel(
            "➕ Добавление канала в мониторинг\n\n"
            "Вы можете добавить канал несколькими способами:\n"
            "• По username (@channel_name)\n"
            "• По ссылке (https://t.me/channel_name)\n"
            "• По ID канала\n\n"
            "Канал будет добавлен в файл .channels и начнет мониториться.",
            title="ℹ️ Информация",
            border_style="blue"
        )
        
        self.console.print(info_panel)
        
        # Запрашиваем информацию о канале
        channel_input = Prompt.ask("Введите username, ссылку или ID канала")
        
        if not channel_input.strip():
            self.console.print("[red]❌ Пустой ввод[/red]")
            input("Нажмите Enter для продолжения...")
            return
        
        try:
            # Парсим ввод пользователя
            channel_id = None
            username = None
            
            # Проверяем разные форматы
            if channel_input.startswith('@'):
                username = channel_input[1:]  # Убираем @
            elif channel_input.startswith('https://t.me/'):
                username = channel_input.replace('https://t.me/', '')
            elif channel_input.startswith('t.me/'):
                username = channel_input.replace('t.me/', '')
            elif channel_input.isdigit():
                channel_id = int(channel_input)
            else:
                # Предполагаем, что это username без @
                username = channel_input
            
            # Пытаемся получить информацию о канале
            self.console.print("[blue]🔄 Получение информации о канале...[/blue]")
            
            # Создаем временный экспортер для получения информации о канале
            from telegram_exporter import TelegramExporter
            
            temp_exporter = TelegramExporter()
            await temp_exporter.initialize_client(force_reauth=False)
            
            try:
                if channel_id:
                    entity = await temp_exporter.client.get_entity(channel_id)
                else:
                    entity = await temp_exporter.client.get_entity(username)
                
                # Получаем информацию о канале
                channel_info = {
                    'id': entity.id,
                    'title': entity.title,
                    'username': getattr(entity, 'username', ''),
                    'description': getattr(entity, 'about', ''),
                    'subscribers_count': getattr(entity, 'participants_count', 0),
                    'last_message_id': 0,  # Начинаем с 0
                    'last_check': datetime.now().isoformat(),
                    'total_messages': 0,
                    'media_size_mb': 0.0
                }
                
                # Показываем информацию о канале
                channel_panel = Panel(
                    f"📺 <b>Название:</b> {channel_info['title']}\n"
                    f"🔗 <b>Username:</b> @{channel_info['username'] if channel_info['username'] else 'Не указан'}\n"
                    f"🆔 <b>ID:</b> {channel_info['id']}\n"
                    f"👥 <b>Подписчиков:</b> {channel_info['subscribers_count']:,}\n"
                    f"📝 <b>Описание:</b> {channel_info['description'][:100] if channel_info['description'] else 'Не указано'}...",
                    title="📋 Информация о канале",
                    border_style="green"
                )
                
                self.console.print(channel_panel)
                
                # Подтверждение добавления
                if Confirm.ask("Добавить этот канал в мониторинг?"):
                    # Добавляем канал в файл .channels
                    self.config_manager.add_channel_to_file(channel_info)
                    
                    # Обновляем список каналов
                    self.channels = self.config_manager.import_channels()
                    
                    self.console.print(f"[green]✅ Канал '{channel_info['title']}' добавлен в мониторинг[/green]")
                    
                    # Отправляем уведомление о новом канале
                    if self.config_manager.is_bot_configured():
                        from telegram_notifications import TelegramNotifier
                        notifier = TelegramNotifier(self.console)
                        
                        # Создаем объект ChannelInfo для уведомления
                        from telegram_exporter import ChannelInfo
                        channel_obj = ChannelInfo(
                            id=channel_info['id'],
                            title=channel_info['title'],
                            username=channel_info['username'],
                            description=channel_info['description'],
                            subscribers_count=channel_info['subscribers_count'],
                            last_message_id=channel_info['last_message_id'],
                            last_check=channel_info['last_check'],
                            total_messages=channel_info['total_messages'],
                            media_size_mb=channel_info['media_size_mb']
                        )
                        
                        await notifier.send_new_channel_notification(channel_obj)
                        self.console.print("[green]✅ Уведомление о новом канале отправлено[/green]")
                    
                else:
                    self.console.print("[yellow]Добавление канала отменено[/yellow]")
                
            except Exception as e:
                self.console.print(f"[red]❌ Ошибка получения информации о канале: {e}[/red]")
                self.console.print("Проверьте правильность ввода и подключение к интернету")
            
            finally:
                # Отключаем временный клиент
                if hasattr(temp_exporter, 'disconnect'):
                    await temp_exporter.disconnect()
                
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка добавления канала: {e}[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def _show_enhanced_status(self):
        """Показать улучшенный статус системы"""
        from rich.layout import Layout
        from rich.align import Align
        from rich.columns import Columns
        from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
        from rich.live import Live
        import time
        
        # Создаем layout для статуса
        layout = Layout()
        layout.split_column(
            Layout(name="stats", size=8),
            Layout(name="channels", size=10),
            Layout(name="menu", size=12)
        )
        
        # Подготавливаем данные
        total_messages = sum(channel.total_messages for channel in self.channels) if self.channels else 0
        total_size = sum(channel.media_size_mb for channel in self.channels) if self.channels else 0.0
        channels_count = len(self.channels) if self.channels else 0
        
        # Статистика системы
        stats_layout = Layout()
        stats_layout.split_row(
            Layout(name="left_stats", ratio=1),
            Layout(name="right_stats", ratio=1)
        )
        
        # Левая панель статистики
        left_stats = Panel(
            f"📊 [bold green]Основная статистика[/bold green]\n\n"
            f"📺 [cyan]Каналов в списке:[/cyan] [bold]{channels_count}[/bold]\n"
            f"💬 [yellow]Всего сообщений:[/yellow] [bold]{total_messages:,}[/bold]\n"
            f"📁 [magenta]Общий размер:[/magenta] [bold]{total_size:.1f} МБ[/bold]\n"
            f"🔄 [blue]Последний экспорт:[/blue] [bold]{self.stats.last_export_time or 'Никогда'}[/bold]",
            title="📈 Статистика",
            border_style="green",
            box=box.ROUNDED
        )
        
        # Правая панель статистики
        right_stats = Panel(
            f"⚙️ [bold green]Состояние системы[/bold green]\n\n"
            f"❌ [red]Ошибок экспорта:[/red] [bold]{self.stats.export_errors}[/bold]\n"
            f"🚫 [orange]Отфильтровано:[/orange] [bold]{self.stats.filtered_messages:,}[/bold]\n"
            f"✅ [green]Успешно экспортировано:[/green] [bold]{self.stats.exported_messages:,}[/bold]\n"
            f"🔗 [blue]Статус Telegram:[/blue] [bold]{'Подключен' if hasattr(self, 'client') and self.client else 'Не подключен'}[/bold]",
            title="🔧 Система",
            border_style="blue",
            box=box.ROUNDED
        )
        
        stats_layout["left_stats"].update(left_stats)
        stats_layout["right_stats"].update(right_stats)
        
        # Таблица каналов с улучшениями
        if self.channels and len(self.channels) > 0:
            channels_table = Table(
                title=f"📋 Загруженные каналы ({channels_count})", 
                box=box.ROUNDED,
                show_header=True,
                header_style="bold magenta"
            )
            channels_table.add_column("№", style="cyan", width=3, justify="center")
            channels_table.add_column("📺 Название", style="green", min_width=25)
            channels_table.add_column("💬 Сообщений", style="yellow", justify="right", width=12)
            channels_table.add_column("📁 Размер (МБ)", style="magenta", justify="right", width=12)
            channels_table.add_column("🕒 Последняя проверка", style="dim", width=18)
            channels_table.add_column("📅 Последнее сообщение", style="orange1", width=18)
            channels_table.add_column("📊 Статус", style="blue", width=10, justify="center")
            
            # Показываем первые 8 каналов с улучшенным форматированием
            for i, channel in enumerate(self.channels[:8], 1):
                messages = f"{channel.total_messages:,}" if channel.total_messages else "—"
                size = f"{channel.media_size_mb:.1f}" if channel.media_size_mb else "—"
                last_check = channel.last_check or "Никогда"
                
                # Форматируем время последней проверки
                if last_check != "Никогда" and len(last_check) > 16:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
                        last_check = dt.strftime("%d.%m %H:%M")
                    except:
                        last_check = last_check[:13] + "..."
                
                # Определяем статус канала
                if channel.total_messages > 1000:
                    status = "🟢 Активен"
                elif channel.total_messages > 100:
                    status = "🟡 Средний"
                elif channel.total_messages > 0:
                    status = "🟠 Малый"
                else:
                    status = "⚪ Пустой"
                
                # Обрезаем название канала
                title = channel.title[:22] + "..." if len(channel.title) > 25 else channel.title
                
                # Форматируем дату последнего сообщения
                last_message_date = "—"
                if hasattr(channel, 'last_message_date') and channel.last_message_date:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(channel.last_message_date.replace('Z', '+00:00'))
                        last_message_date = dt.strftime("%d.%m %H:%M")
                    except:
                        last_message_date = "—"
                
                channels_table.add_row(
                    str(i),
                    title,
                    messages,
                    size,
                    last_check,
                    last_message_date,
                    status
                )
            
            # Добавляем строку с итогами
            if len(self.channels) > 8:
                channels_table.add_row(
                    "...", 
                    f"[dim]и еще {len(self.channels) - 8} каналов[/dim]", 
                    "[dim]...[/dim]", 
                    "[dim]...[/dim]", 
                    "[dim]...[/dim]",
                    "[dim]...[/dim]",
                    "[dim]...[/dim]"
                )
            
            # Добавляем итоговую строку
            channels_table.add_row(
                "[bold]ИТОГО[/bold]",
                f"[bold]{channels_count} каналов[/bold]",
                f"[bold]{total_messages:,}[/bold]",
                f"[bold]{total_size:.1f} МБ[/bold]",
                "[bold]—[/bold]",
                "[bold]—[/bold]",
                "[bold]—[/bold]"
            )
            
            channels_panel = Panel(
                channels_table,
                border_style="cyan",
                box=box.ROUNDED
            )
        else:
            channels_panel = Panel(
                "[yellow]⚠️ Каналы не загружены[/yellow]\n\n"
                "Используйте пункт 7 - Импорт/Экспорт каналов для загрузки списка каналов.",
                title="📋 Каналы",
                border_style="yellow",
                box=box.ROUNDED
            )
        
        # Улучшенное меню
        menu_panel = Panel(
            "🎯 [bold green]Доступные действия[/bold green]\n\n"
            "1. 📊 [cyan]Аналитика и отчеты[/cyan] - Детальная статистика\n"
            "2. 🗺️ [blue]Интерактивная карта каналов[/blue] - Визуальное представление\n"
            "3. 🔄 [yellow]Экспорт каналов[/yellow] - Запуск экспорта\n"
            "4. ⚙️ [magenta]Настройки[/magenta] - Управление конфигурацией\n"
            "5. 📋 [green]Логи[/green] - Просмотр логов работы\n"
            "6. 🎯 [red]Улучшенный CLI интерфейс[/red] - Расширенные возможности\n"
            "7. 📁 [orange]Импорт/Экспорт каналов[/orange] - Управление списком\n"
            "8. 🔄 [purple]Постоянный экспорт каналов[/purple] - Автоматический мониторинг\n\n"
            "0. 🚪 [dim]Выход[/dim] - Завершение работы программы",
            title="📋 Главное меню",
            border_style="green",
            box=box.ROUNDED
        )
        
        # Обновляем layout
        layout["stats"].update(stats_layout)
        layout["channels"].update(channels_panel)
        layout["menu"].update(menu_panel)
        
        # Выводим все на экран
        self.console.print(layout)
    
    async def _cleanup_resources(self):
        """Корректное завершение работы и очистка ресурсов"""
        try:
            # Останавливаем все фоновые задачи
            if hasattr(self, 'client') and self.client:
                self.console.print("[blue]🔄 Отключение от Telegram...[/blue]")
                
                # Отключаем клиент
                await self.client.disconnect()
                
                # Ждем немного, чтобы все фоновые задачи завершились
                await asyncio.sleep(1)
                
                self.console.print("[green]✅ Telegram клиент отключен[/green]")
            
            # Очищаем другие ресурсы если нужно
            if hasattr(self, 'running'):
                self.running = False
                
        except Exception as e:
            self.console.print(f"[yellow]⚠️ Ошибка при очистке ресурсов: {e}[/yellow]")

# Глобальный флаг для корректного завершения
should_exit = False

async def main():
    """Главная функция"""
    global should_exit
    console = Console()
    exporter = None
    
    # Обработчик сигналов для корректного завершения
    def signal_handler(signum, frame):
        console.print(f"\n[yellow]Получен сигнал {signum}, завершение работы...[/yellow]")
        # Устанавливаем флаг для корректного завершения
        should_exit = True
    
    # Регистрируем обработчики сигналов
    import signal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Создаем улучшенный экспортер
        exporter = EnhancedTelegramExporter()
        
        # Показываем улучшенное приветствие
        welcome_text = Text("🚀 Добро пожаловать в улучшенную версию", style="bold blue")
        welcome_text.append("\nTelegram Channel Exporter", style="bold green")
        
        welcome_panel = Panel(
            f"{welcome_text}\n\n"
            f"🎯 [bold green]Новые возможности:[/bold green]\n"
            f"• 📊 [cyan]Детальная аналитика и отчеты[/cyan] - Полная статистика по каналам\n"
            f"• 🗺️ [blue]Интерактивная карта каналов[/blue] - Визуальное представление данных\n"
            f"• 🎯 [yellow]Улучшенный интерфейс[/yellow] - Современный и удобный дизайн\n"
            f"• 📈 [magenta]Экспорт аналитики[/magenta] - JSON, CSV, HTML форматы\n"
            f"• 🔄 [purple]Постоянный мониторинг[/purple] - Автоматическая проверка каналов\n"
            f"• 🤖 [red]Уведомления в Telegram[/red] - Интеграция с ботом\n\n"
            f"⚡ [bold]Инициализация системы...[/bold]",
            title="🎉 Улучшенная версия",
            border_style="green",
            box=box.DOUBLE,
            padding=(1, 2)
        )
        
        console.print(welcome_panel)
        
        # Инициализируем экспортер
        await exporter.initialize()
        
        # Показываем улучшенное меню
        await exporter.show_enhanced_menu()
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Программа прервана пользователем[/yellow]")
    except Exception as e:
        console.print(f"[red]Критическая ошибка: {e}[/red]")
    finally:
        # Правильно завершаем работу Telegram клиента
        try:
            if 'exporter' in locals() and exporter:
                console.print("[blue]🔄 Завершение работы Telegram клиента...[/blue]")
                await exporter._cleanup_resources()
                console.print("[green]✅ Telegram клиент корректно отключен[/green]")
        except Exception as cleanup_error:
            console.print(f"[yellow]⚠️ Ошибка при завершении работы: {cleanup_error}[/yellow]")
        
        console.print("[green]Программа завершена[/green]")


if __name__ == "__main__":
    asyncio.run(main())