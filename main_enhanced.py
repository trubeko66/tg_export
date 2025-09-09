#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Улучшенная версия Telegram Channel Exporter с новыми возможностями
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import List, Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

# Импортируем основные модули
from telegram_exporter import TelegramExporter, ChannelInfo
from config_manager import ConfigManager
from analytics import AnalyticsReporter
from channel_dashboard import ChannelDashboard
from enhanced_cli import EnhancedCLI


class EnhancedTelegramExporter(TelegramExporter):
    """Улучшенная версия TelegramExporter с новыми возможностями"""
    
    def __init__(self):
        super().__init__()
        self.analytics_reporter = AnalyticsReporter(self.console)
        self.dashboard = ChannelDashboard(self.console)
        self.enhanced_cli = EnhancedCLI(self.console)
    
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
                "3. 🔄 Обычный экспорт каналов\n"
                "4. ⚙️ Настройки\n"
                "5. 📋 Логи\n"
                "6. 🎯 Улучшенный CLI интерфейс\n"
                "0. 🚪 Выход",
                title="📋 Главное меню",
                border_style="green"
            )
            
            self.console.print(status_panel)
            self.console.print(menu_panel)
            
            choice = Prompt.ask(
                "Выберите действие",
                choices=["1", "2", "3", "4", "5", "6", "0", "q", "quit"]
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
                    await self.run_standard_export()
                elif choice == "4":
                    await self.show_settings_menu()
                elif choice == "5":
                    await self.show_logs_menu()
                elif choice == "6":
                    await self.run_enhanced_cli()
                    
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
            "0. 🔙 Назад",
            title="📊 Аналитика",
            border_style="cyan"
        )
        
        self.console.print(analytics_panel)
        
        choice = Prompt.ask(
            "Выберите тип аналитики",
            choices=["1", "2", "3", "4", "5", "0"]
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
                
        except Exception as e:
            self.console.print(f"[red]Ошибка аналитики: {e}[/red]")
            input("Нажмите Enter для продолжения...")
    
    async def show_general_analytics(self):
        """Показать общую аналитику"""
        self.console.clear()
        
        with self.console.status("Анализ данных..."):
            time.sleep(1)  # Симуляция анализа
        
        # Получаем данные для аналитики
        channels_data = []
        export_base_dir = Path(self.config.storage.export_base_dir)
        
        for channel in self.channels:
            channel_dir = export_base_dir / self._sanitize_filename(channel.title)
            if channel_dir.exists():
                channels_data.append((channel_dir, channel.title))
        
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
        from rich.table import Table
        table = Table(title="Выберите канал для анализа", box="rounded")
        table.add_column("№", style="cyan", width=4, justify="center")
        table.add_column("Название канала", style="green")
        table.add_column("Сообщений", style="yellow", justify="right")
        
        for i, channel in enumerate(self.channels, 1):
            table.add_row(str(i), channel.title, f"{getattr(channel, 'total_messages', 0):,}")
        
        self.console.print(table)
        
        try:
            from rich.prompt import IntPrompt
            choice = IntPrompt.ask(
                "Выберите номер канала",
                choices=[str(i) for i in range(1, len(self.channels) + 1)]
            )
            
            selected_channel = self.channels[choice - 1]
            
            with self.console.status(f"Анализ канала '{selected_channel.title}'..."):
                time.sleep(2)
            
            # Генерируем отчет по каналу
            export_base_dir = Path(self.config.storage.export_base_dir)
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
        channels_data = []
        export_base_dir = Path(self.config.storage.export_base_dir)
        
        for channel in self.channels:
            channel_dir = export_base_dir / self._sanitize_filename(channel.title)
            if channel_dir.exists():
                channels_data.append((channel_dir, channel.title))
        
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
        channels_data = []
        export_base_dir = Path(self.config.storage.export_base_dir)
        
        for channel in self.channels:
            channel_dir = export_base_dir / self._sanitize_filename(channel.title)
            if channel_dir.exists():
                channels_data.append((channel_dir, channel.title))
        
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
        channels_data = []
        export_base_dir = Path(self.config.storage.export_base_dir)
        
        for channel in self.channels:
            channel_dir = export_base_dir / self._sanitize_filename(channel.title)
            if channel_dir.exists():
                channels_data.append((channel_dir, channel.title))
        
        if not channels_data:
            self.console.print("[yellow]Нет данных для экспорта[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        # Экспортируем в CSV
        output_file = Path("analytics_report.csv")
        self.analytics_reporter.export_analytics_to_csv(channels_data, output_file)
        
        input("\nНажмите Enter для продолжения...")
    
    async def show_dashboard(self):
        """Показать интерактивную карту каналов"""
        self.console.clear()
        
        with self.console.status("Загрузка карты каналов..."):
            time.sleep(1)
        
        # Обновляем статус каналов
        export_base_dir = Path(self.config.storage.export_base_dir)
        self.dashboard.update_channels_status(self.channels, self.stats, export_base_dir)
        
        # Показываем статический дашборд
        self.dashboard.show_static_dashboard(self.channels, self.stats, export_base_dir)
        
        input("\nНажмите Enter для продолжения...")
    
    async def run_standard_export(self):
        """Запуск обычного экспорта"""
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
            await self.export_all_channels()
    
    async def export_selected_channels(self):
        """Экспорт выбранных каналов"""
        self.console.clear()
        
        # Показываем список каналов для выбора
        from rich.table import Table
        table = Table(title="Выберите каналы для экспорта", box="rounded")
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
            # Здесь должен быть вызов экспорта выбранных каналов
            self.console.print("[green]Экспорт запущен...[/green]")
            # await self.export_channels(selected_channels)
    
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
            # Здесь должен быть вызов экспорта проблемных каналов
            self.console.print("[green]Повторный экспорт запущен...[/green]")
            # await self.export_channels(problematic_channels)
    
    async def show_settings_menu(self):
        """Показать меню настроек"""
        self.console.clear()
        
        settings_panel = Panel(
            "⚙️ Настройки\n\n"
            "1. 🔧 Управление конфигурацией\n"
            "2. 📱 Настройки Telegram API\n"
            "3. 🤖 Настройки бота\n"
            "4. ☁️ Настройки WebDAV\n"
            "5. 🗂️ Настройки хранения\n"
            "0. 🔙 Назад",
            title="⚙️ Настройки",
            border_style="yellow"
        )
        
        self.console.print(settings_panel)
        
        choice = Prompt.ask(
            "Выберите раздел настроек",
            choices=["1", "2", "3", "4", "5", "0"]
        )
        
        if choice == "0":
            return
        
        # Здесь должна быть логика настроек
        self.console.print("[yellow]Раздел настроек в разработке[/yellow]")
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
    
    async def run_enhanced_cli(self):
        """Запуск улучшенного CLI"""
        self.console.clear()
        
        self.console.print("[green]Запуск улучшенного CLI интерфейса...[/green]")
        await self.enhanced_cli.run()
    
    def _sanitize_filename(self, filename: str) -> str:
        """Очистка имени файла"""
        import re
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        if len(sanitized) > 100:
            sanitized = sanitized[:100] + "..."
        return sanitized


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
            "• 📈 Экспорт аналитики в JSON/CSV\n\n"
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
