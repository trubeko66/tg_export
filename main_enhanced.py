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
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

# Импортируем основные модули
from telegram_exporter import TelegramExporter, ChannelInfo
from config_manager import ConfigManager
from analytics import AnalyticsReporter
from channel_dashboard import ChannelDashboard
from html_reporter import HTMLReporter
from simple_cli import SimpleCLI
from settings_methods import SettingsMethods


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
    
    async def initialize(self):
        """Инициализация улучшенного экспортера"""
        try:
            # Инициализируем базовый экспортер
            await self.initialize_client()
            
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
            
            # Показываем статус системы
            status_panel = Panel(
                f"📊 Статус системы\n\n"
                f"• Каналов в списке: {len(self.channels)}\n"
                f"• Последний экспорт: {self.stats.last_export_time or 'Никогда'}\n"
                f"• Всего сообщений: {self.stats.total_messages:,}\n"
                f"• Ошибок экспорта: {self.stats.export_errors}\n"
                f"• Отфильтровано: {self.stats.filtered_messages:,}",
                title="ℹ️ Информация",
                border_style="blue"
            )
            
            # Показываем меню
            menu_panel = Panel(
                "🚀 Улучшенный Telegram Channel Exporter\n\n"
                "1. 📊 Аналитика и отчеты\n"
                "2. 🗺️ Интерактивная карта каналов\n"
                "3. 🔄 Экспорт каналов\n"
                "4. ⚙️ Настройки\n"
                "5. 📋 Логи\n"
                "6. 🎯 Улучшенный CLI интерфейс\n"
                "7. 📁 Импорт/Экспорт каналов\n"
                "0. 🚪 Выход",
                title="📋 Главное меню",
                border_style="green"
            )
            
            self.console.print(status_panel)
            self.console.print(menu_panel)
            
            choice = Prompt.ask(
                "Выберите действие",
                choices=["1", "2", "3", "4", "5", "6", "7", "0", "q", "quit"]
            )
            
            if choice in ["0", "q", "quit"]:
                if Confirm.ask("Вы уверены, что хотите выйти?"):
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
        
        # Получаем данные для аналитики
        channels_data = self._get_channels_data()
        
        if not channels_data:
            self.console.print("[yellow]Нет данных для анализа[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        # Генерируем отчет
        report = self.analytics_reporter.generate_export_report(self.channels, self.stats)
        self.console.print(report)
        
        input("\nНажмите Enter для продолжения...")
    
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
        
        if Confirm.ask(f"Экспортировать все {len(self.channels)} каналов?"):
            self.console.print("[green]Запуск экспорта всех каналов...[/green]")
            
            # Запускаем экспорт всех каналов
            for channel in self.channels:
                self.console.print(f"Экспорт канала: {channel.title}")
                await self.export_channel(channel)
            
            self.console.print("[green]✅ Экспорт завершен[/green]")
        
        input("\nНажмите Enter для продолжения...")
    
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
            self.console.print("[green]Запуск экспорта выбранных каналов...[/green]")
            
            # Запускаем экспорт выбранных каналов
            for channel in selected_channels:
                self.console.print(f"Экспорт канала: {channel.title}")
                await self.export_channel(channel)
            
            self.console.print("[green]✅ Экспорт завершен[/green]")
        
        input("\nНажмите Enter для продолжения...")
    
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
            self.console.print("[green]Запуск повторного экспорта...[/green]")
            
            # Запускаем повторный экспорт проблемных каналов
            for channel in problematic_channels:
                self.console.print(f"Повторный экспорт канала: {channel.title}")
                await self.export_channel(channel)
            
            self.console.print("[green]✅ Повторный экспорт завершен[/green]")
        
        input("\nНажмите Enter для продолжения...")
    
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
            success = self.config_manager.export_channels(self.channels, file_path)
            if success:
                self.console.print(f"[green]✅ Экспорт завершен: {file_path}[/green]")
            else:
                self.console.print("[red]❌ Ошибка экспорта[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
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
        
        # Импортируем каналы
        imported_channels = self.config_manager.import_channels(file_path)
        
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
        
        table = Table(title=f"📋 Список каналов ({len(self.channels)})")
        table.add_column("№", style="cyan", width=3)
        table.add_column("Название", style="green")
        table.add_column("Username", style="blue")
        table.add_column("ID", style="yellow")
        table.add_column("Сообщений", style="magenta")
        
        for i, channel in enumerate(self.channels, 1):
            messages = f"{channel.total_messages:,}" if channel.total_messages else "—"
            table.add_row(
                str(i),
                channel.title,
                channel.username or "—",
                str(channel.id) if channel.id else "—",
                messages
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


async def main():
    """Главная функция"""
    console = Console()
    
    try:
        # Создаем улучшенный экспортер
        exporter = EnhancedTelegramExporter()
        
        # Показываем приветствие
        welcome_panel = Panel(
            "🚀 Добро пожаловать в улучшенную версию Telegram Channel Exporter!\n\n"
            "Новые возможности:\n"
            "• 📊 Детальная аналитика и отчеты\n"
            "• 🗺️ Интерактивная карта каналов\n"
            "• 🎯 Улучшенный интерфейс\n"
            "• 📈 Экспорт аналитики в JSON/CSV/HTML\n\n"
            "Загрузка...",
            title="🎉 Улучшенная версия",
            border_style="green"
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
        console.print("[green]Программа завершена[/green]")


if __name__ == "__main__":
    asyncio.run(main())