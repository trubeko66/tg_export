#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль аналитики и отчетов для Telegram Channel Exporter
"""

import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
import re
import statistics

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import box


@dataclass
class ChannelAnalytics:
    """Аналитика по каналу"""
    channel_name: str
    total_messages: int
    total_media_files: int
    total_size_mb: float
    avg_messages_per_day: float
    peak_hours: List[int]
    top_keywords: List[Tuple[str, int]]
    engagement_rate: float
    last_activity: Optional[datetime]
    growth_rate: float
    media_types: Dict[str, int]


@dataclass
class ExportAnalytics:
    """Аналитика экспорта"""
    total_channels: int
    total_messages: int
    total_media_files: int
    total_size_mb: float
    export_success_rate: float
    avg_export_time: float
    most_active_channels: List[Tuple[str, int]]
    export_errors: int
    filtered_messages: int
    last_export: Optional[datetime]


class AnalyticsEngine:
    """Движок аналитики"""
    
    def __init__(self, console: Console):
        self.console = console
        self.analytics_cache = {}
        self.cache_ttl = 300  # 5 минут
        
    def analyze_channel(self, channel_dir: Path, channel_name: str) -> ChannelAnalytics:
        """Анализ одного канала"""
        try:
            # Проверяем кеш
            cache_key = f"channel_{channel_name}_{channel_dir.stat().st_mtime}"
            if cache_key in self.analytics_cache:
                cached_data, timestamp = self.analytics_cache[cache_key]
                if datetime.now().timestamp() - timestamp < self.cache_ttl:
                    return cached_data
            
            # Анализируем JSON файл
            json_file = channel_dir / f"{channel_name}.json"
            if not json_file.exists():
                return self._empty_analytics(channel_name)
            
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            messages = data.get('messages', [])
            if not messages:
                return self._empty_analytics(channel_name)
            
            # Подсчитываем статистику
            total_messages = len(messages)
            total_media_files = sum(1 for msg in messages if msg.get('media_type'))
            total_size_mb = self._calculate_media_size(channel_dir)
            
            # Анализируем временные паттерны
            dates = [datetime.fromisoformat(msg['date']) for msg in messages if msg.get('date')]
            avg_messages_per_day = self._calculate_avg_messages_per_day(dates)
            peak_hours = self._find_peak_hours(dates)
            
            # Анализируем контент
            all_text = ' '.join(msg.get('text', '') for msg in messages if msg.get('text'))
            top_keywords = self._extract_top_keywords(all_text)
            
            # Анализируем медиа
            media_types = self._analyze_media_types(messages)
            
            # Рассчитываем метрики
            engagement_rate = self._calculate_engagement_rate(messages)
            growth_rate = self._calculate_growth_rate(dates)
            last_activity = max(dates) if dates else None
            
            analytics = ChannelAnalytics(
                channel_name=channel_name,
                total_messages=total_messages,
                total_media_files=total_media_files,
                total_size_mb=total_size_mb,
                avg_messages_per_day=avg_messages_per_day,
                peak_hours=peak_hours,
                top_keywords=top_keywords,
                engagement_rate=engagement_rate,
                last_activity=last_activity,
                growth_rate=growth_rate,
                media_types=media_types
            )
            
            # Кешируем результат
            self.analytics_cache[cache_key] = (analytics, datetime.now().timestamp())
            
            return analytics
            
        except Exception as e:
            self.console.print(f"[red]Ошибка анализа канала {channel_name}: {e}[/red]")
            return self._empty_analytics(channel_name)
    
    def analyze_export_stats(self, channels: List[Any], stats: Any) -> ExportAnalytics:
        """Анализ статистики экспорта"""
        try:
            # Анализируем каналы
            channel_activity = []
            total_messages = 0
            total_media = 0
            total_size = 0.0
            
            for channel in channels:
                if hasattr(channel, 'total_messages') and channel.total_messages > 0:
                    channel_activity.append((channel.title, channel.total_messages))
                    total_messages += channel.total_messages
                    total_media += getattr(channel, 'media_count', 0)
                    total_size += getattr(channel, 'media_size_mb', 0.0)
            
            # Сортируем по активности
            most_active_channels = sorted(channel_activity, key=lambda x: x[1], reverse=True)[:10]
            
            # Рассчитываем метрики
            export_success_rate = 100.0 - (stats.export_errors / max(1, len(channels)) * 100)
            avg_export_time = getattr(stats, 'avg_export_time', 0.0)
            
            return ExportAnalytics(
                total_channels=len(channels),
                total_messages=total_messages,
                total_media_files=total_media,
                total_size_mb=total_size,
                export_success_rate=export_success_rate,
                avg_export_time=avg_export_time,
                most_active_channels=most_active_channels,
                export_errors=stats.export_errors,
                filtered_messages=stats.filtered_messages,
                last_export=datetime.now() if stats.last_export_time else None
            )
            
        except Exception as e:
            self.console.print(f"[red]Ошибка анализа статистики экспорта: {e}[/red]")
            return self._empty_export_analytics()
    
    def _empty_analytics(self, channel_name: str) -> ChannelAnalytics:
        """Пустая аналитика для канала"""
        return ChannelAnalytics(
            channel_name=channel_name,
            total_messages=0,
            total_media_files=0,
            total_size_mb=0.0,
            avg_messages_per_day=0.0,
            peak_hours=[],
            top_keywords=[],
            engagement_rate=0.0,
            last_activity=None,
            growth_rate=0.0,
            media_types={}
        )
    
    def _empty_export_analytics(self) -> ExportAnalytics:
        """Пустая аналитика экспорта"""
        return ExportAnalytics(
            total_channels=0,
            total_messages=0,
            total_media_files=0,
            total_size_mb=0.0,
            export_success_rate=0.0,
            avg_export_time=0.0,
            most_active_channels=[],
            export_errors=0,
            filtered_messages=0,
            last_export=None
        )
    
    def _calculate_media_size(self, channel_dir: Path) -> float:
        """Подсчет размера медиафайлов"""
        try:
            media_dir = channel_dir / "media"
            if not media_dir.exists():
                return 0.0
            
            total_size = 0
            for file_path in media_dir.iterdir():
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            
            return total_size / (1024 * 1024)  # В МБ
        except Exception:
            return 0.0
    
    def _calculate_avg_messages_per_day(self, dates: List[datetime]) -> float:
        """Подсчет среднего количества сообщений в день"""
        if not dates:
            return 0.0
        
        dates.sort()
        if len(dates) < 2:
            return len(dates)
        
        time_span = (dates[-1] - dates[0]).days
        if time_span == 0:
            return len(dates)
        
        return len(dates) / time_span
    
    def _find_peak_hours(self, dates: List[datetime]) -> List[int]:
        """Поиск пиковых часов активности"""
        if not dates:
            return []
        
        hour_counts = Counter(date.hour for date in dates)
        # Возвращаем топ-3 часа
        return [hour for hour, _ in hour_counts.most_common(3)]
    
    def _extract_top_keywords(self, text: str) -> List[Tuple[str, int]]:
        """Извлечение топ-ключевых слов"""
        if not text:
            return []
        
        # Очищаем текст и извлекаем слова
        clean_text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = [word for word in clean_text.split() if len(word) > 3]
        
        # Исключаем стоп-слова
        stop_words = {
            'это', 'что', 'как', 'для', 'или', 'но', 'если', 'когда', 'где', 'почему',
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'man', 'men', 'put', 'say', 'she', 'too', 'use'
        }
        
        filtered_words = [word for word in words if word not in stop_words]
        word_counts = Counter(filtered_words)
        
        # Возвращаем топ-10 слов
        return word_counts.most_common(10)
    
    def _analyze_media_types(self, messages: List[Dict]) -> Dict[str, int]:
        """Анализ типов медиафайлов"""
        media_types = Counter()
        for msg in messages:
            media_type = msg.get('media_type')
            if media_type:
                media_types[media_type] += 1
        
        return dict(media_types)
    
    def _calculate_engagement_rate(self, messages: List[Dict]) -> float:
        """Подсчет уровня вовлеченности"""
        if not messages:
            return 0.0
        
        total_engagement = 0
        for msg in messages:
            views = msg.get('views', 0)
            forwards = msg.get('forwards', 0)
            replies = msg.get('replies', 0)
            total_engagement += views + forwards * 2 + replies * 3
        
        return total_engagement / len(messages)
    
    def _calculate_growth_rate(self, dates: List[datetime]) -> float:
        """Подсчет темпа роста"""
        if len(dates) < 2:
            return 0.0
        
        dates.sort()
        # Разбиваем на периоды по месяцам
        monthly_counts = defaultdict(int)
        for date in dates:
            month_key = f"{date.year}-{date.month:02d}"
            monthly_counts[month_key] += 1
        
        if len(monthly_counts) < 2:
            return 0.0
        
        # Рассчитываем средний рост
        counts = list(monthly_counts.values())
        growth_rates = []
        for i in range(1, len(counts)):
            if counts[i-1] > 0:
                growth_rate = (counts[i] - counts[i-1]) / counts[i-1] * 100
                growth_rates.append(growth_rate)
        
        return statistics.mean(growth_rates) if growth_rates else 0.0


class AnalyticsReporter:
    """Генератор отчетов"""
    
    def __init__(self, console: Console):
        self.console = console
        self.analytics_engine = AnalyticsEngine(console)
    
    def generate_channel_report(self, channel_dir: Path, channel_name: str) -> Panel:
        """Генерация отчета по каналу"""
        analytics = self.analytics_engine.analyze_channel(channel_dir, channel_name)
        
        # Создаем таблицу с аналитикой
        table = Table(title=f"Аналитика канала: {channel_name}", box=box.ROUNDED)
        table.add_column("Метрика", style="cyan")
        table.add_column("Значение", style="green")
        
        table.add_row("Всего сообщений", f"{analytics.total_messages:,}")
        table.add_row("Медиафайлов", f"{analytics.total_media_files:,}")
        table.add_row("Размер медиа", f"{analytics.total_size_mb:.1f} МБ")
        table.add_row("Сообщений в день", f"{analytics.avg_messages_per_day:.1f}")
        table.add_row("Уровень вовлеченности", f"{analytics.engagement_rate:.1f}")
        table.add_row("Темп роста", f"{analytics.growth_rate:.1f}%")
        
        if analytics.peak_hours:
            peak_hours_str = ", ".join(map(str, analytics.peak_hours))
            table.add_row("Пиковые часы", f"{peak_hours_str}:00")
        
        if analytics.last_activity:
            table.add_row("Последняя активность", analytics.last_activity.strftime("%Y-%m-%d %H:%M"))
        
        # Добавляем топ-ключевые слова
        if analytics.top_keywords:
            keywords_text = ", ".join([f"{word} ({count})" for word, count in analytics.top_keywords[:5]])
            table.add_row("Топ-слова", keywords_text)
        
        # Добавляем типы медиа
        if analytics.media_types:
            media_text = ", ".join([f"{type_name} ({count})" for type_name, count in analytics.media_types.items()])
            table.add_row("Типы медиа", media_text)
        
        return Panel(table, title="📊 Аналитика канала", border_style="blue")
    
    def generate_export_report(self, channels: List[Any], stats: Any) -> Panel:
        """Генерация отчета по экспорту"""
        analytics = self.analytics_engine.analyze_export_stats(channels, stats)
        
        # Создаем таблицу с общей статистикой
        table = Table(title="Общая статистика экспорта", box=box.ROUNDED)
        table.add_column("Метрика", style="cyan")
        table.add_column("Значение", style="green")
        
        table.add_row("Всего каналов", f"{analytics.total_channels:,}")
        table.add_row("Всего сообщений", f"{analytics.total_messages:,}")
        table.add_row("Медиафайлов", f"{analytics.total_media_files:,}")
        table.add_row("Общий размер", f"{analytics.total_size_mb:.1f} МБ")
        table.add_row("Успешность экспорта", f"{analytics.export_success_rate:.1f}%")
        table.add_row("Ошибки экспорта", f"{analytics.export_errors:,}")
        table.add_row("Отфильтровано", f"{analytics.filtered_messages:,}")
        
        if analytics.last_export:
            table.add_row("Последний экспорт", analytics.last_export.strftime("%Y-%m-%d %H:%M"))
        
        # Создаем таблицу с самыми активными каналами
        if analytics.most_active_channels:
            active_table = Table(title="Самые активные каналы", box=box.ROUNDED)
            active_table.add_column("Канал", style="cyan")
            active_table.add_column("Сообщений", style="green", justify="right")
            
            for channel_name, message_count in analytics.most_active_channels:
                active_table.add_row(channel_name, f"{message_count:,}")
        
            # Создаем Layout для правильного отображения таблиц
            layout = Layout()
            layout.split_column(
                Layout(table, name="main_stats"),
                Layout(active_table, name="active_channels")
            )
            
            return Panel(
                layout,
                title="📈 Отчет по экспорту",
                border_style="green"
            )
        
        return Panel(table, title="📈 Отчет по экспорту", border_style="green")
    
    def generate_comparison_report(self, channels_data: List[Tuple[Path, str]]) -> Panel:
        """Генерация сравнительного отчета"""
        if not channels_data:
            return Panel("Нет данных для сравнения", title="📊 Сравнительный отчет")
        
        # Анализируем все каналы
        all_analytics = []
        for channel_dir, channel_name in channels_data:
            analytics = self.analytics_engine.analyze_channel(channel_dir, channel_name)
            all_analytics.append(analytics)
        
        # Создаем сравнительную таблицу
        table = Table(title="Сравнение каналов", box=box.ROUNDED)
        table.add_column("Канал", style="cyan")
        table.add_column("Сообщений", style="green", justify="right")
        table.add_column("Медиа", style="yellow", justify="right")
        table.add_column("Размер (МБ)", style="blue", justify="right")
        table.add_column("Активность/день", style="magenta", justify="right")
        table.add_column("Вовлеченность", style="red", justify="right")
        
        # Сортируем по количеству сообщений
        all_analytics.sort(key=lambda x: x.total_messages, reverse=True)
        
        for analytics in all_analytics:
            table.add_row(
                analytics.channel_name,
                f"{analytics.total_messages:,}",
                f"{analytics.total_media_files:,}",
                f"{analytics.total_size_mb:.1f}",
                f"{analytics.avg_messages_per_day:.1f}",
                f"{analytics.engagement_rate:.1f}"
            )
        
        return Panel(table, title="📊 Сравнительный отчет", border_style="yellow")
    
    def export_analytics_to_json(self, channels_data: List[Tuple[Path, str]], output_file: Path):
        """Экспорт аналитики в JSON"""
        try:
            analytics_data = {
                "export_timestamp": datetime.now().isoformat(),
                "channels": []
            }
            
            for channel_dir, channel_name in channels_data:
                analytics = self.analytics_engine.analyze_channel(channel_dir, channel_name)
                analytics_data["channels"].append(asdict(analytics))
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(analytics_data, f, ensure_ascii=False, indent=2, default=str)
            
            self.console.print(f"[green]Аналитика экспортирована в {output_file}[/green]")
            
        except Exception as e:
            self.console.print(f"[red]Ошибка экспорта аналитики: {e}[/red]")
    
    def export_analytics_to_csv(self, channels_data: List[Tuple[Path, str]], output_file: Path):
        """Экспорт аналитики в CSV"""
        try:
            import csv
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Заголовки
                writer.writerow([
                    'Channel', 'Total Messages', 'Media Files', 'Size MB',
                    'Messages per Day', 'Engagement Rate', 'Growth Rate %',
                    'Peak Hours', 'Top Keywords', 'Media Types', 'Last Activity'
                ])
                
                # Данные
                for channel_dir, channel_name in channels_data:
                    analytics = self.analytics_engine.analyze_channel(channel_dir, channel_name)
                    
                    peak_hours = ", ".join(map(str, analytics.peak_hours)) if analytics.peak_hours else ""
                    top_keywords = ", ".join([f"{word}({count})" for word, count in analytics.top_keywords[:5]])
                    media_types = ", ".join([f"{type_name}({count})" for type_name, count in analytics.media_types.items()])
                    last_activity = analytics.last_activity.strftime("%Y-%m-%d %H:%M") if analytics.last_activity else ""
                    
                    writer.writerow([
                        analytics.channel_name,
                        analytics.total_messages,
                        analytics.total_media_files,
                        f"{analytics.total_size_mb:.1f}",
                        f"{analytics.avg_messages_per_day:.1f}",
                        f"{analytics.engagement_rate:.1f}",
                        f"{analytics.growth_rate:.1f}",
                        peak_hours,
                        top_keywords,
                        media_types,
                        last_activity
                    ])
            
            self.console.print(f"[green]Аналитика экспортирована в {output_file}[/green]")
            
        except Exception as e:
            self.console.print(f"[red]Ошибка экспорта аналитики в CSV: {e}[/red]")
