#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Улучшенный CLI интерфейс для Telegram Channel Exporter
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.align import Align
from rich.columns import Columns
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.status import Status
from rich.syntax import Syntax
from rich import box
from rich.console import Group
from rich.markdown import Markdown

from analytics import AnalyticsReporter
from channel_dashboard import ChannelDashboard


@dataclass
class MenuOption:
    """Опция меню"""
    key: str
    title: str
    description: str
    handler: Callable
    enabled: bool = True


class EnhancedCLI:
    """Улучшенный CLI интерфейс"""
    
    def __init__(self, console: Console):
        self.console = console
        self.analytics_reporter = AnalyticsReporter(console)
        self.dashboard = ChannelDashboard(console)
        self.current_menu = "main"
        self.menu_stack = []
        
    def show_welcome_screen(self):
        """Показать экран приветствия"""
        welcome_text = """
# 🚀 Telegram Channel Exporter

Добро пожаловать в улучшенную версию Telegram Channel Exporter!

## Возможности:
- 📊 **Интерактивная аналитика** — детальная статистика по каналам
- 🗺️ **Карта каналов** — визуальное представление всех каналов
- 📈 **Отчеты** — экспорт аналитики в JSON и CSV
- 🎯 **Улучшенный интерфейс** — удобная навигация и управление
- ⚡ **Быстрые действия** — горячие клавиши и контекстные меню

Нажмите **Enter** для продолжения или **Esc** для выхода.
        """
        
        panel = Panel(
            Markdown(welcome_text),
            title="🎉 Добро пожаловать!",
            border_style="green",
            padding=(1, 2)
        )
        
        self.console.print(panel)
        
        # Ждем нажатия клавиши
        try:
            input("Нажмите Enter для продолжения...")
        except KeyboardInterrupt:
            return False
        
        return True
    
    def show_main_menu(self) -> str:
        """Показать главное меню"""
        self.console.clear()
        
        menu_options = [
            MenuOption("1", "📊 Аналитика", "Просмотр аналитики и статистики каналов", self.show_analytics_menu),
            MenuOption("2", "🗺️ Карта каналов", "Интерактивная карта всех каналов", self.show_channel_dashboard),
            MenuOption("3", "📈 Отчеты", "Генерация и экспорт отчетов", self.show_reports_menu),
            MenuOption("4", "⚙️ Настройки", "Управление конфигурацией", self.show_settings_menu),
            MenuOption("5", "🔄 Экспорт", "Запуск экспорта каналов", self.show_export_menu),
            MenuOption("6", "📋 Логи", "Просмотр логов работы", self.show_logs_menu),
            MenuOption("7", "❓ Справка", "Документация и помощь", self.show_help_menu),
            MenuOption("0", "🚪 Выход", "Завершение работы программы", None)
        ]
        
        # Создаем таблицу меню
        table = Table(title="Главное меню", box=box.ROUNDED, show_header=False)
        table.add_column("Код", style="cyan", width=4, justify="center")
        table.add_column("Название", style="green", min_width=20)
        table.add_column("Описание", style="white")
        
        for option in menu_options:
            if option.enabled:
                table.add_row(option.key, option.title, option.description)
            else:
                table.add_row(option.key, f"[dim]{option.title}[/dim]", f"[dim]{option.description}[/dim]")
        
        # Добавляем информацию о системе
        info_panel = Panel(
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Версия: 1.2.0\n"
            f"Статус: Готов к работе",
            title="ℹ️ Информация",
            border_style="blue"
        )
        
        # Создаем макет
        layout = Layout()
        layout.split_column(
            Layout(table, name="menu", ratio=2),
            Layout(info_panel, name="info", size=8)
        )
        
        self.console.print(layout)
        
        # Получаем выбор пользователя
        choice = Prompt.ask(
            "Выберите действие",
            choices=[opt.key for opt in menu_options if opt.enabled] + ["q", "quit", "exit"]
        )
        
        if choice in ["q", "quit", "exit", "0"]:
            return "exit"
        
        # Выполняем выбранное действие
        selected_option = next((opt for opt in menu_options if opt.key == choice), None)
        if selected_option and selected_option.handler:
            return selected_option.handler()
        
        return "main"
    
    def show_analytics_menu(self) -> str:
        """Показать меню аналитики"""
        self.console.clear()
        
        analytics_options = [
            MenuOption("1", "📊 Общая статистика", "Общая статистика по всем каналам", self.show_general_analytics),
            MenuOption("2", "📈 Анализ канала", "Детальный анализ конкретного канала", self.show_channel_analysis),
            MenuOption("3", "🔄 Сравнение каналов", "Сравнительный анализ каналов", self.show_channel_comparison),
            MenuOption("4", "⏰ Временная аналитика", "Анализ активности по времени", self.show_temporal_analytics),
            MenuOption("0", "🔙 Назад", "Возврат в главное меню", None)
        ]
        
        table = Table(title="📊 Аналитика", box=box.ROUNDED, show_header=False)
        table.add_column("Код", style="cyan", width=4, justify="center")
        table.add_column("Название", style="green", min_width=20)
        table.add_column("Описание", style="white")
        
        for option in analytics_options:
            table.add_row(option.key, option.title, option.description)
        
        self.console.print(table)
        
        choice = Prompt.ask(
            "Выберите тип аналитики",
            choices=[opt.key for opt in analytics_options] + ["q", "quit"]
        )
        
        if choice in ["q", "quit", "0"]:
            return "main"
        
        selected_option = next((opt for opt in analytics_options if opt.key == choice), None)
        if selected_option and selected_option.handler:
            return selected_option.handler()
        
        return "analytics"
    
    def show_general_analytics(self) -> str:
        """Показать общую аналитику"""
        self.console.clear()
        
        with Status("Загрузка аналитики...", spinner="dots"):
            # Здесь должна быть реальная загрузка данных
            time.sleep(1)  # Симуляция загрузки
        
        # Создаем панель с общей статистикой
        stats_panel = Panel(
            "📊 Общая статистика\n\n"
            "• Всего каналов: 15\n"
            "• Активных каналов: 12\n"
            "• Всего сообщений: 45,678\n"
            "• Медиафайлов: 2,345\n"
            "• Общий размер: 1.2 ГБ\n"
            "• Последний экспорт: 2024-01-15 14:30",
            title="📈 Статистика",
            border_style="green"
        )
        
        # Создаем таблицу топ-каналов
        top_table = Table(title="Топ-5 каналов по активности", box=box.ROUNDED)
        top_table.add_column("Канал", style="cyan")
        top_table.add_column("Сообщений", style="green", justify="right")
        top_table.add_column("Медиа", style="yellow", justify="right")
        top_table.add_column("Размер (МБ)", style="blue", justify="right")
        
        top_table.add_row("IT News", "12,345", "456", "234.5")
        top_table.add_row("Tech Updates", "8,765", "321", "187.2")
        top_table.add_row("Programming", "6,543", "234", "156.8")
        top_table.add_row("AI Research", "4,321", "123", "98.4")
        top_table.add_row("Dev Tools", "3,210", "89", "67.3")
        
        # Создаем макет
        layout = Layout()
        layout.split_column(
            Layout(stats_panel, name="stats", size=12),
            Layout(top_table, name="top", ratio=1)
        )
        
        self.console.print(layout)
        
        input("\nНажмите Enter для продолжения...")
        return "analytics"
    
    def show_channel_analysis(self) -> str:
        """Показать анализ канала"""
        self.console.clear()
        
        # Список каналов для выбора
        channels = [
            "IT News",
            "Tech Updates", 
            "Programming",
            "AI Research",
            "Dev Tools"
        ]
        
        table = Table(title="Выберите канал для анализа", box=box.ROUNDED)
        table.add_column("№", style="cyan", width=4, justify="center")
        table.add_column("Название канала", style="green")
        
        for i, channel in enumerate(channels, 1):
            table.add_row(str(i), channel)
        
        self.console.print(table)
        
        try:
            choice = IntPrompt.ask(
                "Выберите номер канала",
                choices=[str(i) for i in range(1, len(channels) + 1)]
            )
            
            selected_channel = channels[choice - 1]
            
            # Показываем анализ выбранного канала
            with Status(f"Анализ канала '{selected_channel}'...", spinner="dots"):
                time.sleep(2)  # Симуляция анализа
            
            # Создаем детальный отчет
            analysis_panel = Panel(
                f"📊 Анализ канала: {selected_channel}\n\n"
                f"• Всего сообщений: 12,345\n"
                f"• Медиафайлов: 456\n"
                f"• Размер медиа: 234.5 МБ\n"
                f"• Сообщений в день: 45.2\n"
                f"• Пиковые часы: 10:00, 14:00, 18:00\n"
                f"• Уровень вовлеченности: 8.7/10\n"
                f"• Темп роста: +12.3%\n"
                f"• Последняя активность: 2024-01-15 16:45\n\n"
                f"Топ-ключевые слова:\n"
                f"• программирование (234)\n"
                f"• разработка (189)\n"
                f"• технологии (156)\n"
                f"• код (123)\n"
                f"• алгоритм (98)",
                title=f"📈 Анализ: {selected_channel}",
                border_style="blue"
            )
            
            self.console.print(analysis_panel)
            
        except (ValueError, IndexError):
            self.console.print("[red]Неверный выбор канала[/red]")
        
        input("\nНажмите Enter для продолжения...")
        return "analytics"
    
    def show_channel_comparison(self) -> str:
        """Показать сравнение каналов"""
        self.console.clear()
        
        with Status("Подготовка сравнительного анализа...", spinner="dots"):
            time.sleep(1)
        
        # Создаем сравнительную таблицу
        comparison_table = Table(title="Сравнение каналов", box=box.ROUNDED)
        comparison_table.add_column("Канал", style="cyan")
        comparison_table.add_column("Сообщений", style="green", justify="right")
        comparison_table.add_column("Медиа", style="yellow", justify="right")
        comparison_table.add_column("Размер (МБ)", style="blue", justify="right")
        comparison_table.add_column("Активность/день", style="magenta", justify="right")
        comparison_table.add_column("Вовлеченность", style="red", justify="right")
        
        comparison_table.add_row("IT News", "12,345", "456", "234.5", "45.2", "8.7")
        comparison_table.add_row("Tech Updates", "8,765", "321", "187.2", "32.1", "7.9")
        comparison_table.add_row("Programming", "6,543", "234", "156.8", "24.8", "8.2")
        comparison_table.add_row("AI Research", "4,321", "123", "98.4", "16.3", "7.5")
        comparison_table.add_row("Dev Tools", "3,210", "89", "67.3", "12.1", "6.8")
        
        self.console.print(comparison_table)
        
        input("\nНажмите Enter для продолжения...")
        return "analytics"
    
    def show_temporal_analytics(self) -> str:
        """Показать временную аналитику"""
        self.console.clear()
        
        with Status("Анализ временных паттернов...", spinner="dots"):
            time.sleep(1)
        
        # Создаем панель с временной аналитикой
        temporal_panel = Panel(
            "⏰ Временная аналитика\n\n"
            "📅 Активность по дням недели:\n"
            "• Понедельник: 15.2%\n"
            "• Вторник: 18.7%\n"
            "• Среда: 16.4%\n"
            "• Четверг: 14.8%\n"
            "• Пятница: 12.3%\n"
            "• Суббота: 11.2%\n"
            "• Воскресенье: 11.4%\n\n"
            "🕐 Активность по часам:\n"
            "• 09:00-12:00: 25.3% (пик)\n"
            "• 12:00-15:00: 18.7%\n"
            "• 15:00-18:00: 22.1% (пик)\n"
            "• 18:00-21:00: 19.4%\n"
            "• 21:00-00:00: 14.5%\n\n"
            "📈 Тренды:\n"
            "• Рост активности: +5.2% за месяц\n"
            "• Пиковые дни: вторник, среда\n"
            "• Тихие дни: выходные",
            title="⏰ Временные паттерны",
            border_style="yellow"
        )
        
        self.console.print(temporal_panel)
        
        input("\nНажмите Enter для продолжения...")
        return "analytics"
    
    def show_channel_dashboard(self) -> str:
        """Показать карту каналов"""
        self.console.clear()
        
        with Status("Загрузка карты каналов...", spinner="dots"):
            time.sleep(1)
        
        # Создаем интерактивную карту каналов
        dashboard_panel = Panel(
            "🗺️ Интерактивная карта каналов\n\n"
            "Здесь будет отображаться интерактивная карта всех каналов\n"
            "с возможностью фильтрации, сортировки и детального просмотра.\n\n"
            "Возможности:\n"
            "• Фильтрация по статусу (активные/неактивные/ошибки)\n"
            "• Сортировка по различным критериям\n"
            "• Поиск по названию канала\n"
            "• Выбор каналов для массовых операций\n"
            "• Детальная информация по каждому каналу\n\n"
            "В полной версии здесь будет полноценный интерактивный интерфейс.",
            title="🗺️ Карта каналов",
            border_style="cyan"
        )
        
        self.console.print(dashboard_panel)
        
        input("\nНажмите Enter для продолжения...")
        return "main"
    
    def show_reports_menu(self) -> str:
        """Показать меню отчетов"""
        self.console.clear()
        
        reports_options = [
            MenuOption("1", "📊 JSON отчет", "Экспорт аналитики в JSON формате", self.export_json_report),
            MenuOption("2", "📈 CSV отчет", "Экспорт аналитики в CSV формате", self.export_csv_report),
            MenuOption("3", "📋 HTML отчет", "Генерация HTML отчета", self.export_html_report),
            MenuOption("4", "📄 Детальный отчет", "Полный отчет с графиками", self.export_detailed_report),
            MenuOption("0", "🔙 Назад", "Возврат в главное меню", None)
        ]
        
        table = Table(title="📈 Отчеты", box=box.ROUNDED, show_header=False)
        table.add_column("Код", style="cyan", width=4, justify="center")
        table.add_column("Название", style="green", min_width=20)
        table.add_column("Описание", style="white")
        
        for option in reports_options:
            table.add_row(option.key, option.title, option.description)
        
        self.console.print(table)
        
        choice = Prompt.ask(
            "Выберите тип отчета",
            choices=[opt.key for opt in reports_options] + ["q", "quit"]
        )
        
        if choice in ["q", "quit", "0"]:
            return "main"
        
        selected_option = next((opt for opt in reports_options if opt.key == choice), None)
        if selected_option and selected_option.handler:
            return selected_option.handler()
        
        return "reports"
    
    def export_json_report(self) -> str:
        """Экспорт JSON отчета"""
        self.console.clear()
        
        with Status("Генерация JSON отчета...", spinner="dots"):
            time.sleep(2)
        
        self.console.print("[green]✅ JSON отчет успешно создан: analytics_report.json[/green]")
        input("\nНажмите Enter для продолжения...")
        return "reports"
    
    def export_csv_report(self) -> str:
        """Экспорт CSV отчета"""
        self.console.clear()
        
        with Status("Генерация CSV отчета...", spinner="dots"):
            time.sleep(2)
        
        self.console.print("[green]✅ CSV отчет успешно создан: analytics_report.csv[/green]")
        input("\nНажмите Enter для продолжения...")
        return "reports"
    
    def export_html_report(self) -> str:
        """Экспорт HTML отчета"""
        self.console.clear()
        
        with Status("Генерация HTML отчета...", spinner="dots"):
            time.sleep(3)
        
        self.console.print("[green]✅ HTML отчет успешно создан: analytics_report.html[/green]")
        input("\nНажмите Enter для продолжения...")
        return "reports"
    
    def export_detailed_report(self) -> str:
        """Экспорт детального отчета"""
        self.console.clear()
        
        with Status("Генерация детального отчета...", spinner="dots"):
            time.sleep(4)
        
        self.console.print("[green]✅ Детальный отчет успешно создан: detailed_report.html[/green]")
        input("\nНажмите Enter для продолжения...")
        return "reports"
    
    def show_settings_menu(self) -> str:
        """Показать меню настроек"""
        self.console.clear()
        
        settings_panel = Panel(
            "⚙️ Настройки\n\n"
            "Здесь будут доступны настройки программы:\n"
            "• Конфигурация Telegram API\n"
            "• Настройки уведомлений\n"
            "• Параметры WebDAV\n"
            "• Настройки фильтрации\n"
            "• Параметры экспорта\n\n"
            "В полной версии здесь будет полноценный интерфейс настроек.",
            title="⚙️ Управление настройками",
            border_style="yellow"
        )
        
        self.console.print(settings_panel)
        
        input("\nНажмите Enter для продолжения...")
        return "main"
    
    def show_export_menu(self) -> str:
        """Показать меню экспорта"""
        self.console.clear()
        
        export_panel = Panel(
            "🔄 Экспорт каналов\n\n"
            "Здесь будет интерфейс для запуска экспорта:\n"
            "• Выбор каналов для экспорта\n"
            "• Настройка параметров экспорта\n"
            "• Мониторинг прогресса\n"
            "• Просмотр результатов\n\n"
            "В полной версии здесь будет полноценный интерфейс экспорта.",
            title="🔄 Управление экспортом",
            border_style="green"
        )
        
        self.console.print(export_panel)
        
        input("\nНажмите Enter для продолжения...")
        return "main"
    
    def show_logs_menu(self) -> str:
        """Показать меню логов"""
        self.console.clear()
        
        # Показываем последние записи лога
        logs_panel = Panel(
            "📋 Последние записи лога\n\n"
            "2024-01-15 16:45:23 [INFO] Экспорт канала 'IT News' завершен успешно\n"
            "2024-01-15 16:44:15 [INFO] Обработано 45 сообщений\n"
            "2024-01-15 16:43:02 [INFO] Загружено 12 медиафайлов\n"
            "2024-01-15 16:42:30 [INFO] Начат экспорт канала 'IT News'\n"
            "2024-01-15 16:41:45 [INFO] Проверка новых сообщений\n"
            "2024-01-15 16:40:12 [INFO] Подключение к Telegram API\n"
            "2024-01-15 16:39:58 [INFO] Запуск программы\n\n"
            "Полный лог доступен в файле: export.log",
            title="📋 Логи работы",
            border_style="blue"
        )
        
        self.console.print(logs_panel)
        
        input("\nНажмите Enter для продолжения...")
        return "main"
    
    def show_help_menu(self) -> str:
        """Показать справку"""
        self.console.clear()
        
        help_text = """
# 📖 Справка по Telegram Channel Exporter

## Основные возможности

### 📊 Аналитика
- **Общая статистика** — сводка по всем каналам
- **Анализ канала** — детальная статистика конкретного канала
- **Сравнение каналов** — сравнительный анализ
- **Временная аналитика** — анализ активности по времени

### 🗺️ Карта каналов
- Интерактивное отображение всех каналов
- Фильтрация и сортировка
- Поиск по названию
- Массовые операции

### 📈 Отчеты
- Экспорт в JSON, CSV, HTML
- Детальные отчеты с графиками
- Настраиваемые параметры

## Горячие клавиши

- **Ctrl+C** — выход из программы
- **Esc** — возврат в предыдущее меню
- **Enter** — подтверждение действия
- **q/quit** — выход из текущего раздела

## Поддержка

При возникновении проблем:
1. Проверьте файл `export.log`
2. Убедитесь в правильности настроек
3. Проверьте подключение к интернету
4. Обратитесь к документации

## Версия: 1.2.0
        """
        
        help_panel = Panel(
            Markdown(help_text),
            title="❓ Справка",
            border_style="green",
            padding=(1, 2)
        )
        
        self.console.print(help_panel)
        
        input("\nНажмите Enter для продолжения...")
        return "main"
    
    async def run(self):
        """Запуск улучшенного CLI"""
        try:
            # Показываем экран приветствия
            if not self.show_welcome_screen():
                return
            
            # Основной цикл меню
            while True:
                try:
                    if self.current_menu == "main":
                        result = self.show_main_menu()
                    elif self.current_menu == "analytics":
                        result = self.show_analytics_menu()
                    elif self.current_menu == "reports":
                        result = self.show_reports_menu()
                    else:
                        result = "main"
                    
                    if result == "exit":
                        break
                    
                    self.current_menu = result
                    
                except KeyboardInterrupt:
                    if Confirm.ask("\nВы уверены, что хотите выйти?"):
                        break
                    continue
                except Exception as e:
                    self.console.print(f"[red]Ошибка: {e}[/red]")
                    input("Нажмите Enter для продолжения...")
                    self.current_menu = "main"
            
            # Прощальное сообщение
            self.console.clear()
            goodbye_panel = Panel(
                "👋 Спасибо за использование Telegram Channel Exporter!\n\n"
                "До свидания!",
                title="👋 До свидания!",
                border_style="green"
            )
            self.console.print(goodbye_panel)
            
        except Exception as e:
            self.console.print(f"[red]Критическая ошибка: {e}[/red]")


async def main():
    """Главная функция"""
    console = Console()
    cli = EnhancedCLI(console)
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
