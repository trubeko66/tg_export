#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простой интерактивный CLI для Telegram Channel Exporter
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import List, Any, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box


class SimpleCLI:
    """Простой интерактивный CLI"""
    
    def __init__(self, console: Console):
        self.console = console
        
    def show_welcome(self):
        """Показать приветствие"""
        welcome_panel = Panel(
            "🚀 Простой интерактивный CLI\n\n"
            "Добро пожаловать в простой интерфейс для работы с каналами!\n"
            "Здесь вы можете быстро выполнить основные операции.",
            title="🎉 Добро пожаловать!",
            border_style="green"
        )
        self.console.print(welcome_panel)
    
    def show_main_menu(self) -> str:
        """Показать главное меню"""
        self.console.clear()
        
        menu_panel = Panel(
            "📋 Главное меню\n\n"
            "1. 📊 Просмотр каналов\n"
            "2. 🔄 Экспорт каналов\n"
            "3. 📈 Аналитика\n"
            "4. ⚙️ Настройки\n"
            "5. 📋 Логи\n"
            "0. 🚪 Выход",
            title="📋 Выберите действие",
            border_style="blue"
        )
        
        self.console.print(menu_panel)
        
        choice = Prompt.ask(
            "Выберите действие",
            choices=["1", "2", "3", "4", "5", "0", "q", "quit"]
        )
        
        return choice
    
    def show_channels(self, channels: List[Any]):
        """Показать список каналов"""
        self.console.clear()
        
        if not channels:
            self.console.print("[yellow]Нет каналов для отображения[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        table = Table(title="📋 Список каналов", box=box.ROUNDED)
        table.add_column("№", style="cyan", width=4, justify="center")
        table.add_column("Название канала", style="green")
        table.add_column("Сообщений", style="yellow", justify="right")
        table.add_column("Статус", style="blue")
        
        for i, channel in enumerate(channels, 1):
            status = "Активен" if hasattr(channel, 'last_check') and channel.last_check else "Не проверен"
            table.add_row(
                str(i),
                channel.title,
                f"{getattr(channel, 'total_messages', 0):,}",
                status
            )
        
        self.console.print(table)
        input("\nНажмите Enter для продолжения...")
    
    def show_export_menu(self, channels: List[Any]):
        """Показать меню экспорта"""
        self.console.clear()
        
        if not channels:
            self.console.print("[yellow]Нет каналов для экспорта[/yellow]")
            input("Нажмите Enter для продолжения...")
            return
        
        export_panel = Panel(
            "🔄 Экспорт каналов\n\n"
            "1. 📋 Экспорт всех каналов\n"
            "2. 🎯 Выбрать каналы для экспорта\n"
            "3. 🔄 Повторный экспорт проблемных каналов\n"
            "0. 🔙 Назад",
            title="🔄 Выберите тип экспорта",
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
                self._export_all_channels(channels)
            elif choice == "2":
                self._export_selected_channels(channels)
            elif choice == "3":
                self._export_problematic_channels(channels)
                
        except Exception as e:
            self.console.print(f"[red]Ошибка экспорта: {e}[/red]")
            input("Нажмите Enter для продолжения...")
    
    def _export_all_channels(self, channels: List[Any]):
        """Экспорт всех каналов"""
        if Confirm.ask(f"Экспортировать все {len(channels)} каналов?"):
            self.console.print("[green]Запуск экспорта всех каналов...[/green]")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Экспорт каналов...", total=len(channels))
                
                for i, channel in enumerate(channels):
                    progress.update(task, description=f"Экспорт: {channel.title}")
                    time.sleep(1)  # Симуляция экспорта
                    progress.advance(task)
            
            self.console.print("[green]✅ Экспорт завершен[/green]")
        
        input("\nНажмите Enter для продолжения...")
    
    def _export_selected_channels(self, channels: List[Any]):
        """Экспорт выбранных каналов"""
        # Показываем список каналов для выбора
        table = Table(title="Выберите каналы для экспорта", box=box.ROUNDED)
        table.add_column("№", style="cyan", width=4, justify="center")
        table.add_column("Название канала", style="green")
        table.add_column("Статус", style="yellow")
        
        for i, channel in enumerate(channels, 1):
            status = "Активен" if hasattr(channel, 'last_check') and channel.last_check else "Не проверен"
            table.add_row(str(i), channel.title, status)
        
        self.console.print(table)
        
        selection = Prompt.ask(
            "Введите номера каналов через запятую (например: 1,3,5) или 'all' для всех"
        )
        
        if selection.lower() == "all":
            selected_channels = channels
        else:
            try:
                indices = [int(x.strip()) - 1 for x in selection.split(",")]
                selected_channels = [channels[i] for i in indices if 0 <= i < len(channels)]
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
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Экспорт каналов...", total=len(selected_channels))
                
                for i, channel in enumerate(selected_channels):
                    progress.update(task, description=f"Экспорт: {channel.title}")
                    time.sleep(1)  # Симуляция экспорта
                    progress.advance(task)
            
            self.console.print("[green]✅ Экспорт завершен[/green]")
        
        input("\nНажмите Enter для продолжения...")
    
    def _export_problematic_channels(self, channels: List[Any]):
        """Экспорт проблемных каналов"""
        # Находим проблемные каналы
        problematic_channels = []
        for channel in channels:
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
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Повторный экспорт...", total=len(problematic_channels))
                
                for i, channel in enumerate(problematic_channels):
                    progress.update(task, description=f"Повторный экспорт: {channel.title}")
                    time.sleep(1)  # Симуляция экспорта
                    progress.advance(task)
            
            self.console.print("[green]✅ Повторный экспорт завершен[/green]")
        
        input("\nНажмите Enter для продолжения...")
    
    def show_analytics(self, channels: List[Any], stats: Any):
        """Показать аналитику"""
        self.console.clear()
        
        # Создаем панель с общей статистикой
        stats_panel = Panel(
            f"📊 Общая статистика\n\n"
            f"• Всего каналов: {len(channels)}\n"
            f"• Всего сообщений: {getattr(stats, 'total_messages', 0):,}\n"
            f"• Ошибок экспорта: {getattr(stats, 'export_errors', 0)}\n"
            f"• Отфильтровано: {getattr(stats, 'filtered_messages', 0):,}\n"
            f"• Последний экспорт: {getattr(stats, 'last_export_time', 'Никогда')}",
            title="📈 Статистика",
            border_style="green"
        )
        
        # Создаем таблицу топ-каналов
        if channels:
            top_table = Table(title="Топ-5 каналов по активности", box=box.ROUNDED)
            top_table.add_column("Канал", style="cyan")
            top_table.add_column("Сообщений", style="green", justify="right")
            top_table.add_column("Статус", style="yellow")
            
            # Сортируем каналы по количеству сообщений
            sorted_channels = sorted(channels, key=lambda x: getattr(x, 'total_messages', 0), reverse=True)
            
            for channel in sorted_channels[:5]:
                status = "Активен" if hasattr(channel, 'last_check') and channel.last_check else "Не проверен"
                top_table.add_row(
                    channel.title,
                    f"{getattr(channel, 'total_messages', 0):,}",
                    status
                )
            
            self.console.print(stats_panel)
            self.console.print(top_table)
        else:
            self.console.print(stats_panel)
        
        input("\nНажмите Enter для продолжения...")
    
    def show_settings(self):
        """Показать настройки"""
        self.console.clear()
        
        settings_panel = Panel(
            "⚙️ Настройки\n\n"
            "Для изменения настроек используйте обычную версию программы.\n"
            "Здесь отображается текущая конфигурация:\n\n"
            "• Telegram API: Настроен\n"
            "• Bot API: Настроен\n"
            "• WebDAV: Настроен\n"
            "• Хранилище: Настроено",
            title="⚙️ Текущие настройки",
            border_style="yellow"
        )
        
        self.console.print(settings_panel)
        input("\nНажмите Enter для продолжения...")
    
    def show_logs(self):
        """Показать логи"""
        self.console.clear()
        
        # Читаем последние записи лога
        log_file = Path("export.log")
        if log_file.exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Показываем последние 15 строк
            recent_lines = lines[-15:] if len(lines) > 15 else lines
            
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
    
    async def run(self, channels: List[Any], stats: Any):
        """Запуск простого CLI"""
        try:
            self.show_welcome()
            
            while True:
                choice = self.show_main_menu()
                
                if choice in ["0", "q", "quit"]:
                    if Confirm.ask("Вы уверены, что хотите выйти?"):
                        break
                    continue
                
                try:
                    if choice == "1":
                        self.show_channels(channels)
                    elif choice == "2":
                        self.show_export_menu(channels)
                    elif choice == "3":
                        self.show_analytics(channels, stats)
                    elif choice == "4":
                        self.show_settings()
                    elif choice == "5":
                        self.show_logs()
                        
                except KeyboardInterrupt:
                    if Confirm.ask("\nПрервать операцию?"):
                        break
                except Exception as e:
                    self.console.print(f"[red]Ошибка: {e}[/red]")
                    input("Нажмите Enter для продолжения...")
            
            # Прощальное сообщение
            self.console.clear()
            goodbye_panel = Panel(
                "👋 Спасибо за использование Simple CLI!\n\n"
                "До свидания!",
                title="👋 До свидания!",
                border_style="green"
            )
            self.console.print(goodbye_panel)
            
        except Exception as e:
            self.console.print(f"[red]Критическая ошибка: {e}[/red]")


async def main():
    """Главная функция для тестирования"""
    console = Console()
    cli = SimpleCLI(console)
    
    # Создаем тестовые данные
    class MockChannel:
        def __init__(self, title, messages=0):
            self.title = title
            self.total_messages = messages
            self.last_check = datetime.now().isoformat()
    
    class MockStats:
        def __init__(self):
            self.total_messages = 12345
            self.export_errors = 2
            self.filtered_messages = 567
            self.last_export_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    channels = [
        MockChannel("IT News", 5000),
        MockChannel("Tech Updates", 3000),
        MockChannel("Programming", 2000),
        MockChannel("AI Research", 1500),
        MockChannel("Dev Tools", 1000)
    ]
    
    stats = MockStats()
    
    await cli.run(channels, stats)


if __name__ == "__main__":
    asyncio.run(main())
