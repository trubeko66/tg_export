#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автономная улучшенная версия Telegram Channel Exporter
"""

import asyncio
import sys
import time
import json
from pathlib import Path
from typing import List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box


@dataclass
class MockChannel:
    """Мок-канал для демонстрации"""
    title: str
    total_messages: int = 0
    last_check: Optional[str] = None
    export_errors: int = 0


@dataclass
class MockStats:
    """Мок-статистика для демонстрации"""
    total_messages: int = 0
    export_errors: int = 0
    filtered_messages: int = 0
    last_export_time: Optional[str] = None


class StandaloneEnhancedExporter:
    """Автономная улучшенная версия экспортера"""
    
    def __init__(self):
        self.console = Console()
        self.channels: List[MockChannel] = []
        self.stats = MockStats()
        self._load_demo_data()
    
    def _load_demo_data(self):
        """Загрузить демонстрационные данные"""
        # Создаем демонстрационные каналы
        demo_channels = [
            MockChannel("IT News", 5000, datetime.now().isoformat()),
            MockChannel("Tech Updates", 3000, datetime.now().isoformat()),
            MockChannel("Programming", 2000, datetime.now().isoformat()),
            MockChannel("AI Research", 1500, datetime.now().isoformat()),
            MockChannel("Dev Tools", 1000, datetime.now().isoformat()),
            MockChannel("Web Development", 800, datetime.now().isoformat()),
            MockChannel("Mobile Apps", 600, datetime.now().isoformat()),
            MockChannel("Data Science", 400, datetime.now().isoformat()),
        ]
        
        self.channels = demo_channels
        
        # Обновляем статистику
        self.stats.total_messages = sum(ch.total_messages for ch in self.channels)
        self.stats.export_errors = 2
        self.stats.filtered_messages = 567
        self.stats.last_export_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    async def initialize(self):
        """Инициализация"""
        try:
            self.console.print("[green]Инициализация автономной версии...[/green]")
            time.sleep(1)
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
                "🚀 Автономная улучшенная версия\n\n"
                "1. 📊 Аналитика и отчеты\n"
                "2. 🗺️ Интерактивная карта каналов\n"
                "3. 🔄 Экспорт каналов\n"
                "4. ⚙️ Настройки\n"
                "5. 📋 Логи\n"
                "6. 🎯 Простой CLI интерфейс\n"
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
                    await self.show_export_menu()
                elif choice == "4":
                    await self.show_settings_menu()
                elif choice == "5":
                    await self.show_logs_menu()
                elif choice == "6":
                    await self.show_simple_cli()
                    
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
        
        # Создаем панель с общей статистикой
        stats_panel = Panel(
            f"📊 Общая статистика\n\n"
            f"• Всего каналов: {len(self.channels)}\n"
            f"• Активных каналов: {len([ch for ch in self.channels if ch.last_check])}\n"
            f"• Всего сообщений: {self.stats.total_messages:,}\n"
            f"• Медиафайлов: 2,345\n"
            f"• Общий размер: 1.2 ГБ\n"
            f"• Последний экспорт: {self.stats.last_export_time}",
            title="📈 Статистика",
            border_style="green"
        )
        
        # Создаем таблицу топ-каналов
        top_table = Table(title="Топ-5 каналов по активности", box=box.ROUNDED)
        top_table.add_column("Канал", style="cyan")
        top_table.add_column("Сообщений", style="green", justify="right")
        top_table.add_column("Медиа", style="yellow", justify="right")
        top_table.add_column("Размер (МБ)", style="blue", justify="right")
        
        # Сортируем каналы по количеству сообщений
        sorted_channels = sorted(self.channels, key=lambda x: x.total_messages, reverse=True)
        
        for i, channel in enumerate(sorted_channels[:5]):
            media_count = channel.total_messages // 10  # Примерное количество медиа
            size_mb = channel.total_messages * 0.1  # Примерный размер
            top_table.add_row(
                channel.title,
                f"{channel.total_messages:,}",
                f"{media_count:,}",
                f"{size_mb:.1f}"
            )
        
        self.console.print(stats_panel)
        self.console.print(top_table)
        
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
            table.add_row(str(i), channel.title, f"{channel.total_messages:,}")
        
        self.console.print(table)
        
        try:
            choice = IntPrompt.ask(
                "Выберите номер канала",
                choices=[str(i) for i in range(1, len(self.channels) + 1)]
            )
            
            selected_channel = self.channels[choice - 1]
            
            with self.console.status(f"Анализ канала '{selected_channel.title}'..."):
                time.sleep(2)
            
            # Создаем детальный отчет
            analysis_panel = Panel(
                f"📊 Анализ канала: {selected_channel.title}\n\n"
                f"• Всего сообщений: {selected_channel.total_messages:,}\n"
                f"• Медиафайлов: {selected_channel.total_messages // 10:,}\n"
                f"• Размер медиа: {selected_channel.total_messages * 0.1:.1f} МБ\n"
                f"• Сообщений в день: {selected_channel.total_messages / 30:.1f}\n"
                f"• Пиковые часы: 10:00, 14:00, 18:00\n"
                f"• Уровень вовлеченности: 8.7/10\n"
                f"• Темп роста: +12.3%\n"
                f"• Последняя активность: {selected_channel.last_check or 'Неизвестно'}\n\n"
                f"Топ-ключевые слова:\n"
                f"• программирование (234)\n"
                f"• разработка (189)\n"
                f"• технологии (156)\n"
                f"• код (123)\n"
                f"• алгоритм (98)",
                title=f"📈 Анализ: {selected_channel.title}",
                border_style="blue"
            )
            
            self.console.print(analysis_panel)
            
        except (ValueError, IndexError):
            self.console.print("[red]Неверный выбор канала[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def show_channel_comparison(self):
        """Показать сравнение каналов"""
        self.console.clear()
        
        with self.console.status("Подготовка сравнения..."):
            time.sleep(1)
        
        # Создаем сравнительную таблицу
        comparison_table = Table(title="Сравнение каналов", box=box.ROUNDED)
        comparison_table.add_column("Канал", style="cyan")
        comparison_table.add_column("Сообщений", style="green", justify="right")
        comparison_table.add_column("Медиа", style="yellow", justify="right")
        comparison_table.add_column("Размер (МБ)", style="blue", justify="right")
        comparison_table.add_column("Активность/день", style="magenta", justify="right")
        comparison_table.add_column("Вовлеченность", style="red", justify="right")
        
        # Сортируем каналы по количеству сообщений
        sorted_channels = sorted(self.channels, key=lambda x: x.total_messages, reverse=True)
        
        for channel in sorted_channels:
            media_count = channel.total_messages // 10
            size_mb = channel.total_messages * 0.1
            activity_per_day = channel.total_messages / 30
            engagement = min(10, channel.total_messages / 500)
            
            comparison_table.add_row(
                channel.title,
                f"{channel.total_messages:,}",
                f"{media_count:,}",
                f"{size_mb:.1f}",
                f"{activity_per_day:.1f}",
                f"{engagement:.1f}"
            )
        
        self.console.print(comparison_table)
        
        input("\nНажмите Enter для продолжения...")
    
    async def export_json_report(self):
        """Экспорт JSON отчета"""
        self.console.clear()
        
        with self.console.status("Генерация JSON отчета..."):
            time.sleep(2)
        
        # Создаем JSON отчет
        report_data = {
            "export_timestamp": datetime.now().isoformat(),
            "channels": [
                {
                    "name": ch.title,
                    "total_messages": ch.total_messages,
                    "media_files": ch.total_messages // 10,
                    "size_mb": ch.total_messages * 0.1,
                    "last_check": ch.last_check,
                    "export_errors": ch.export_errors
                }
                for ch in self.channels
            ],
            "statistics": {
                "total_channels": len(self.channels),
                "total_messages": self.stats.total_messages,
                "export_errors": self.stats.export_errors,
                "filtered_messages": self.stats.filtered_messages
            }
        }
        
        # Сохраняем в файл
        output_file = Path("analytics_report.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        self.console.print(f"[green]✅ JSON отчет создан: {output_file}[/green]")
        input("\nНажмите Enter для продолжения...")
    
    async def export_csv_report(self):
        """Экспорт CSV отчета"""
        self.console.clear()
        
        with self.console.status("Генерация CSV отчета..."):
            time.sleep(2)
        
        # Создаем CSV отчет
        output_file = Path("analytics_report.csv")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("Channel,Total Messages,Media Files,Size MB,Last Check,Export Errors\n")
            for ch in self.channels:
                f.write(f"{ch.title},{ch.total_messages},{ch.total_messages // 10},{ch.total_messages * 0.1:.1f},{ch.last_check or 'Unknown'},{ch.export_errors}\n")
        
        self.console.print(f"[green]✅ CSV отчет создан: {output_file}[/green]")
        input("\nНажмите Enter для продолжения...")
    
    async def export_html_report(self):
        """Экспорт HTML отчета"""
        self.console.clear()
        
        with self.console.status("Генерация HTML отчета..."):
            time.sleep(3)
        
        # Создаем простой HTML отчет
        html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Аналитика Telegram каналов</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f0f0f0; padding: 20px; border-radius: 10px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: #e3f2fd; padding: 15px; border-radius: 8px; text-align: center; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Аналитика Telegram каналов</h1>
        <p>Отчет сгенерирован {datetime.now().strftime('%d.%m.%Y в %H:%M')}</p>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <h3>{len(self.channels)}</h3>
            <p>Всего каналов</p>
        </div>
        <div class="stat-card">
            <h3>{self.stats.total_messages:,}</h3>
            <p>Всего сообщений</p>
        </div>
        <div class="stat-card">
            <h3>{sum(ch.total_messages // 10 for ch in self.channels):,}</h3>
            <p>Медиафайлов</p>
        </div>
        <div class="stat-card">
            <h3>{sum(ch.total_messages * 0.1 for ch in self.channels):.1f} МБ</h3>
            <p>Общий размер</p>
        </div>
    </div>
    
    <table>
        <thead>
            <tr>
                <th>Канал</th>
                <th>Сообщений</th>
                <th>Медиа</th>
                <th>Размер (МБ)</th>
                <th>Последняя проверка</th>
                <th>Ошибки</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for ch in sorted(self.channels, key=lambda x: x.total_messages, reverse=True):
            html_content += f"""
            <tr>
                <td>{ch.title}</td>
                <td>{ch.total_messages:,}</td>
                <td>{ch.total_messages // 10:,}</td>
                <td>{ch.total_messages * 0.1:.1f}</td>
                <td>{ch.last_check or 'Неизвестно'}</td>
                <td>{ch.export_errors}</td>
            </tr>
"""
        
        html_content += """
        </tbody>
    </table>
</body>
</html>
"""
        
        # Сохраняем в файл
        output_file = Path("analytics_report.html")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.console.print(f"[green]✅ HTML отчет создан: {output_file}[/green]")
        input("\nНажмите Enter для продолжения...")
    
    async def show_dashboard(self):
        """Показать интерактивную карту каналов"""
        self.console.clear()
        
        with self.console.status("Загрузка карты каналов..."):
            time.sleep(1)
        
        # Создаем таблицу каналов
        channels_table = Table(title="🗺️ Карта каналов", box=box.ROUNDED)
        channels_table.add_column("Канал", style="cyan")
        channels_table.add_column("Статус", style="green", justify="center")
        channels_table.add_column("Сообщений", style="yellow", justify="right")
        channels_table.add_column("Размер (МБ)", style="blue", justify="right")
        channels_table.add_column("Последняя проверка", style="dim")
        
        for channel in sorted(self.channels, key=lambda x: x.total_messages, reverse=True):
            status = "🟢 Активен" if channel.last_check else "🔴 Неактивен"
            size_mb = channel.total_messages * 0.1
            last_check = channel.last_check[:10] if channel.last_check else "Никогда"
            
            channels_table.add_row(
                channel.title,
                status,
                f"{channel.total_messages:,}",
                f"{size_mb:.1f}",
                last_check
            )
        
        # Создаем панель статистики
        stats_panel = Panel(
            f"📊 Статистика карты\n\n"
            f"• Всего каналов: {len(self.channels)}\n"
            f"• Активных: {len([ch for ch in self.channels if ch.last_check])}\n"
            f"• Неактивных: {len([ch for ch in self.channels if not ch.last_check])}\n"
            f"• С ошибками: {len([ch for ch in self.channels if ch.export_errors > 0])}",
            title="📈 Статистика",
            border_style="blue"
        )
        
        self.console.print(channels_table)
        self.console.print(stats_panel)
        
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
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Экспорт каналов...", total=len(self.channels))
                
                for i, channel in enumerate(self.channels):
                    progress.update(task, description=f"Экспорт: {channel.title}")
                    time.sleep(1)  # Симуляция экспорта
                    progress.advance(task)
            
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
            status = "Активен" if channel.last_check else "Не проверен"
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
    
    async def export_problematic_channels(self):
        """Экспорт проблемных каналов"""
        self.console.clear()
        
        # Находим проблемные каналы
        problematic_channels = [ch for ch in self.channels if ch.export_errors > 0 or not ch.last_check]
        
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
        
        # Показываем информацию о настройках
        self.console.print("[yellow]Раздел настроек в разработке[/yellow]")
        self.console.print("Используйте обычную версию программы для настройки конфигурации.")
        
        input("Нажмите Enter для продолжения...")
    
    async def show_logs_menu(self):
        """Показать меню логов"""
        self.console.clear()
        
        # Создаем демонстрационные логи
        demo_logs = [
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [INFO] Запуск автономной версии",
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [INFO] Загружено {len(self.channels)} каналов",
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [INFO] Инициализация завершена",
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [INFO] Готов к работе",
        ]
        
        logs_text = "\n".join(demo_logs)
        
        logs_panel = Panel(
            logs_text,
            title="📋 Последние записи лога",
            border_style="blue"
        )
        
        self.console.print(logs_panel)
        
        input("\nНажмите Enter для продолжения...")
    
    async def show_simple_cli(self):
        """Показать простой CLI"""
        self.console.clear()
        
        self.console.print("[green]Запуск простого CLI интерфейса...[/green]")
        
        # Импортируем и запускаем простой CLI
        from simple_cli import SimpleCLI
        simple_cli = SimpleCLI(self.console)
        await simple_cli.run(self.channels, self.stats)


async def main():
    """Главная функция"""
    console = Console()
    
    try:
        # Создаем автономный экспортер
        exporter = StandaloneEnhancedExporter()
        
        # Показываем приветствие
        welcome_panel = Panel(
            "🚀 Добро пожаловать в автономную улучшенную версию!\n\n"
            "Эта версия работает с демонстрационными данными и включает:\n"
            "• 📊 Детальная аналитика и отчеты\n"
            "• 🗺️ Интерактивная карта каналов\n"
            "• 🎯 Улучшенный интерфейс\n"
            "• 📈 Экспорт аналитики в JSON/CSV/HTML\n\n"
            "Загрузка...",
            title="🎉 Автономная версия",
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
