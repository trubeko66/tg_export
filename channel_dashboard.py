#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интерактивная карта каналов для Telegram Channel Exporter
"""

import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.align import Align
from rich.columns import Columns
from rich import box
from rich.prompt import Prompt, Confirm

from analytics import AnalyticsEngine, AnalyticsReporter


@dataclass
class ChannelStatus:
    """Статус канала"""
    name: str
    last_check: Optional[datetime]
    total_messages: int
    media_size_mb: float
    status: str  # "active", "inactive", "error", "never_checked"
    last_export: Optional[datetime]
    export_errors: int
    is_selected: bool = False


class ChannelDashboard:
    """Интерактивная карта каналов"""
    
    def __init__(self, console: Console):
        self.console = console
        self.analytics_engine = AnalyticsEngine(console)
        self.analytics_reporter = AnalyticsReporter(console)
        self.channels_status: Dict[str, ChannelStatus] = {}
        self.selected_channels: List[str] = []
        self.current_page = 0
        self.channels_per_page = 10
        self.sort_by = "name"  # "name", "messages", "size", "last_check"
        self.sort_reverse = False
        self.filter_status = "all"  # "all", "active", "inactive", "error"
        self.search_query = ""
        
    def update_channels_status(self, channels: List[Any], stats: Any, export_base_dir: Path):
        """Обновление статуса каналов"""
        self.channels_status.clear()
        
        for channel in channels:
            channel_dir = export_base_dir / self._sanitize_filename(channel.title)
            
            # Определяем статус
            status = "never_checked"
            if hasattr(channel, 'last_check') and channel.last_check:
                last_check = datetime.fromisoformat(channel.last_check) if isinstance(channel.last_check, str) else channel.last_check
                if last_check > datetime.now() - timedelta(days=1):
                    status = "active"
                elif last_check > datetime.now() - timedelta(days=7):
                    status = "inactive"
                else:
                    status = "error"
            
            # Получаем размер медиа
            media_size = 0.0
            if channel_dir.exists():
                media_size = self.analytics_engine._calculate_media_size(channel_dir)
            
            self.channels_status[channel.title] = ChannelStatus(
                name=channel.title,
                last_check=datetime.fromisoformat(channel.last_check) if hasattr(channel, 'last_check') and channel.last_check else None,
                total_messages=getattr(channel, 'total_messages', 0),
                media_size_mb=media_size,
                status=status,
                last_export=datetime.now() if hasattr(channel, 'last_export') else None,
                export_errors=getattr(channel, 'export_errors', 0),
                is_selected=channel.title in self.selected_channels
            )
    
    def _sanitize_filename(self, filename: str) -> str:
        """Очистка имени файла"""
        import re
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        if len(sanitized) > 100:
            sanitized = sanitized[:100] + "..."
        return sanitized
    
    def create_dashboard_layout(self) -> Layout:
        """Создание макета дашборда"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        
        layout["main"].split_row(
            Layout(name="channels", ratio=2),
            Layout(name="analytics", ratio=1)
        )
        
        return layout
    
    def render_header(self) -> Panel:
        """Рендер заголовка"""
        title = Text("📊 Интерактивная карта каналов", style="bold blue")
        subtitle = Text(f"Всего каналов: {len(self.channels_status)} | Выбрано: {len(self.selected_channels)}", style="dim")
        
        return Panel(
            Align.center(f"{title}\n{subtitle}"),
            border_style="blue"
        )
    
    def render_channels_table(self) -> Table:
        """Рендер таблицы каналов"""
        # Фильтруем и сортируем каналы
        filtered_channels = self._filter_and_sort_channels()
        
        # Пагинация
        start_idx = self.current_page * self.channels_per_page
        end_idx = start_idx + self.channels_per_page
        page_channels = filtered_channels[start_idx:end_idx]
        
        # Создаем таблицу
        table = Table(
            title=f"Каналы (стр. {self.current_page + 1}/{(len(filtered_channels) + self.channels_per_page - 1) // self.channels_per_page})",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        
        table.add_column("✓", width=2, justify="center")
        table.add_column("Канал", style="cyan", min_width=20)
        table.add_column("Статус", width=8, justify="center")
        table.add_column("Сообщений", justify="right", style="green")
        table.add_column("Размер (МБ)", justify="right", style="yellow")
        table.add_column("Последняя проверка", style="dim")
        
        for i, channel_name in enumerate(page_channels):
            if channel_name not in self.channels_status:
                continue
                
            channel = self.channels_status[channel_name]
            
            # Статус с цветом
            status_style = {
                "active": "green",
                "inactive": "yellow", 
                "error": "red",
                "never_checked": "dim"
            }.get(channel.status, "white")
            
            status_text = {
                "active": "🟢 Активен",
                "inactive": "🟡 Неактивен",
                "error": "🔴 Ошибка",
                "never_checked": "⚪ Не проверен"
            }.get(channel.status, "❓ Неизвестно")
            
            # Чекбокс
            checkbox = "☑" if channel.is_selected else "☐"
            
            # Последняя проверка
            last_check_str = "Никогда"
            if channel.last_check:
                if channel.last_check.date() == datetime.now().date():
                    last_check_str = channel.last_check.strftime("%H:%M")
                else:
                    last_check_str = channel.last_check.strftime("%d.%m.%Y")
            
            table.add_row(
                checkbox,
                channel.name,
                Text(status_text, style=status_style),
                f"{channel.total_messages:,}",
                f"{channel.media_size_mb:.1f}",
                last_check_str
            )
        
        return table
    
    def render_analytics_panel(self) -> Panel:
        """Рендер панели аналитики"""
        if not self.channels_status:
            return Panel("Нет данных", title="📈 Аналитика", border_style="blue")
        
        # Подсчитываем статистику
        total_channels = len(self.channels_status)
        active_channels = sum(1 for ch in self.channels_status.values() if ch.status == "active")
        total_messages = sum(ch.total_messages for ch in self.channels_status.values())
        total_size = sum(ch.media_size_mb for ch in self.channels_status.values())
        selected_count = len(self.selected_channels)
        
        # Создаем таблицу статистики
        stats_table = Table(show_header=False, box=box.SIMPLE)
        stats_table.add_column("Метрика", style="cyan")
        stats_table.add_column("Значение", style="green", justify="right")
        
        stats_table.add_row("Всего каналов", f"{total_channels}")
        stats_table.add_row("Активных", f"{active_channels}")
        stats_table.add_row("Выбрано", f"{selected_count}")
        stats_table.add_row("Всего сообщений", f"{total_messages:,}")
        stats_table.add_row("Общий размер", f"{total_size:.1f} МБ")
        
        # Топ-5 каналов по сообщениям
        top_channels = sorted(
            self.channels_status.values(),
            key=lambda x: x.total_messages,
            reverse=True
        )[:5]
        
        if top_channels:
            top_table = Table(title="Топ-5 каналов", show_header=False, box=box.SIMPLE)
            top_table.add_column("Канал", style="cyan")
            top_table.add_column("Сообщений", style="green", justify="right")
            
            for channel in top_channels:
                if channel.total_messages > 0:
                    top_table.add_row(channel.name, f"{channel.total_messages:,}")
        
            content = f"{stats_table}\n\n{top_table}"
        else:
            content = str(stats_table)
        
        return Panel(content, title="📈 Аналитика", border_style="blue")
    
    def render_footer(self) -> Panel:
        """Рендер подвала с командами"""
        commands = [
            "↑↓ - навигация",
            "Space - выбрать/снять",
            "A - выбрать все",
            "D - снять все",
            "S - сортировка",
            "F - фильтр",
            "Q - поиск",
            "R - обновить",
            "Enter - экспорт",
            "Esc - выход"
        ]
        
        return Panel(
            " | ".join(commands),
            border_style="dim"
        )
    
    def _filter_and_sort_channels(self) -> List[str]:
        """Фильтрация и сортировка каналов"""
        channels = list(self.channels_status.keys())
        
        # Фильтрация по статусу
        if self.filter_status != "all":
            channels = [
                name for name in channels
                if self.channels_status[name].status == self.filter_status
            ]
        
        # Поиск
        if self.search_query:
            query = self.search_query.lower()
            channels = [
                name for name in channels
                if query in name.lower()
            ]
        
        # Сортировка
        if self.sort_by == "name":
            channels.sort(reverse=self.sort_reverse)
        elif self.sort_by == "messages":
            channels.sort(
                key=lambda x: self.channels_status[x].total_messages,
                reverse=self.sort_reverse
            )
        elif self.sort_by == "size":
            channels.sort(
                key=lambda x: self.channels_status[x].media_size_mb,
                reverse=self.sort_reverse
            )
        elif self.sort_by == "last_check":
            channels.sort(
                key=lambda x: self.channels_status[x].last_check or datetime.min,
                reverse=self.sort_reverse
            )
        
        return channels
    
    def handle_key_input(self, key: str) -> bool:
        """Обработка нажатий клавиш"""
        if key == "escape":
            return False
        
        elif key == "up":
            # Навигация вверх (пока не реализована для отдельных строк)
            pass
        
        elif key == "down":
            # Навигация вниз (пока не реализована для отдельных строк)
            pass
        
        elif key == "space":
            # Переключение выбора текущего канала
            self._toggle_current_channel()
        
        elif key == "a":
            # Выбрать все видимые каналы
            self._select_all_visible()
        
        elif key == "d":
            # Снять выбор со всех
            self._deselect_all()
        
        elif key == "s":
            # Меню сортировки
            self._show_sort_menu()
        
        elif key == "f":
            # Меню фильтрации
            self._show_filter_menu()
        
        elif key == "q":
            # Поиск
            self._show_search()
        
        elif key == "r":
            # Обновление (перерисовка)
            pass
        
        elif key == "enter":
            # Экспорт выбранных каналов
            self._export_selected()
        
        elif key == "page_up":
            # Предыдущая страница
            if self.current_page > 0:
                self.current_page -= 1
        
        elif key == "page_down":
            # Следующая страница
            filtered_channels = self._filter_and_sort_channels()
            max_pages = (len(filtered_channels) + self.channels_per_page - 1) // self.channels_per_page
            if self.current_page < max_pages - 1:
                self.current_page += 1
        
        return True
    
    def _toggle_current_channel(self):
        """Переключение выбора текущего канала"""
        # Пока просто переключаем первый канал на странице
        filtered_channels = self._filter_and_sort_channels()
        start_idx = self.current_page * self.channels_per_page
        if start_idx < len(filtered_channels):
            channel_name = filtered_channels[start_idx]
            if channel_name in self.channels_status:
                channel = self.channels_status[channel_name]
                channel.is_selected = not channel.is_selected
                
                if channel.is_selected and channel_name not in self.selected_channels:
                    self.selected_channels.append(channel_name)
                elif not channel.is_selected and channel_name in self.selected_channels:
                    self.selected_channels.remove(channel_name)
    
    def _select_all_visible(self):
        """Выбрать все видимые каналы"""
        filtered_channels = self._filter_and_sort_channels()
        start_idx = self.current_page * self.channels_per_page
        end_idx = start_idx + self.channels_per_page
        
        for channel_name in filtered_channels[start_idx:end_idx]:
            if channel_name in self.channels_status:
                self.channels_status[channel_name].is_selected = True
                if channel_name not in self.selected_channels:
                    self.selected_channels.append(channel_name)
    
    def _deselect_all(self):
        """Снять выбор со всех каналов"""
        for channel in self.channels_status.values():
            channel.is_selected = False
        self.selected_channels.clear()
    
    def _show_sort_menu(self):
        """Показать меню сортировки"""
        self.console.clear()
        
        sort_options = [
            ("1", "name", "По названию"),
            ("2", "messages", "По количеству сообщений"),
            ("3", "size", "По размеру медиа"),
            ("4", "last_check", "По последней проверке")
        ]
        
        table = Table(title="Сортировка каналов", box=box.ROUNDED)
        table.add_column("Код", style="cyan")
        table.add_column("Поле", style="green")
        table.add_column("Описание", style="white")
        
        for code, field, description in sort_options:
            current = " ←" if self.sort_by == field else ""
            table.add_row(code, field, f"{description}{current}")
        
        self.console.print(table)
        
        choice = Prompt.ask("Выберите поле для сортировки", choices=["1", "2", "3", "4", "q"])
        
        if choice != "q":
            field_map = {"1": "name", "2": "messages", "3": "size", "4": "last_check"}
            new_sort = field_map[choice]
            
            if new_sort == self.sort_by:
                self.sort_reverse = not self.sort_reverse
            else:
                self.sort_by = new_sort
                self.sort_reverse = False
            
            self.current_page = 0  # Сброс на первую страницу
    
    def _show_filter_menu(self):
        """Показать меню фильтрации"""
        self.console.clear()
        
        filter_options = [
            ("1", "all", "Все каналы"),
            ("2", "active", "Только активные"),
            ("3", "inactive", "Только неактивные"),
            ("4", "error", "Только с ошибками")
        ]
        
        table = Table(title="Фильтрация каналов", box=box.ROUNDED)
        table.add_column("Код", style="cyan")
        table.add_column("Фильтр", style="green")
        table.add_column("Описание", style="white")
        
        for code, filter_type, description in filter_options:
            current = " ←" if self.filter_status == filter_type else ""
            table.add_row(code, filter_type, f"{description}{current}")
        
        self.console.print(table)
        
        choice = Prompt.ask("Выберите фильтр", choices=["1", "2", "3", "4", "q"])
        
        if choice != "q":
            filter_map = {"1": "all", "2": "active", "3": "inactive", "4": "error"}
            self.filter_status = filter_map[choice]
            self.current_page = 0  # Сброс на первую страницу
    
    def _show_search(self):
        """Показать поиск"""
        self.console.clear()
        
        current_query = self.search_query if self.search_query else ""
        new_query = Prompt.ask("Поиск по названию канала", default=current_query)
        
        self.search_query = new_query
        self.current_page = 0  # Сброс на первую страницу
    
    def _export_selected(self):
        """Экспорт выбранных каналов"""
        if not self.selected_channels:
            self.console.print("[yellow]Нет выбранных каналов для экспорта[/yellow]")
            return
        
        self.console.clear()
        self.console.print(f"[green]Экспорт {len(self.selected_channels)} каналов...[/green]")
        
        # Здесь можно добавить логику экспорта
        # Пока просто показываем список
        for channel_name in self.selected_channels:
            self.console.print(f"  • {channel_name}")
    
    async def run_interactive_dashboard(self, channels: List[Any], stats: Any, export_base_dir: Path):
        """Запуск интерактивного дашборда"""
        self.update_channels_status(channels, stats, export_base_dir)
        
        layout = self.create_dashboard_layout()
        
        with Live(layout, console=self.console, refresh_per_second=4) as live:
            while True:
                # Обновляем содержимое
                layout["header"].update(self.render_header())
                layout["channels"].update(self.render_channels_table())
                layout["analytics"].update(self.render_analytics_panel())
                layout["footer"].update(self.render_footer())
                
                # Ждем ввод пользователя
                try:
                    # В реальном приложении здесь был бы ввод с клавиатуры
                    # Пока используем простую симуляцию
                    await asyncio.sleep(0.1)
                    
                    # Для демонстрации - автоматический выход через 30 секунд
                    # В реальном приложении это будет обработка клавиш
                    
                except KeyboardInterrupt:
                    break
        
        self.console.print("[green]Дашборд закрыт[/green]")
    
    def show_static_dashboard(self, channels: List[Any], stats: Any, export_base_dir: Path):
        """Показать статический дашборд"""
        self.update_channels_status(channels, stats, export_base_dir)
        
        layout = self.create_dashboard_layout()
        layout["header"].update(self.render_header())
        layout["channels"].update(self.render_channels_table())
        layout["analytics"].update(self.render_analytics_panel())
        layout["footer"].update(self.render_footer())
        
        self.console.print(layout)
