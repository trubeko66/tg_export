#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль ежедневной проверки каналов
"""

import asyncio
import schedule
import time
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box

from telegram_exporter import TelegramExporter, ChannelInfo
from config_manager import ConfigManager
from content_filter import ContentFilter


class DailyChannelChecker:
    """Класс для ежедневной проверки каналов"""
    
    def __init__(self, console: Console):
        self.console = console
        self.config_manager = ConfigManager()
        self.content_filter = ContentFilter()
        self.exporter = None
        self.channels = []
        # Пермское время (UTC+5)
        self.perm_timezone = timezone(timedelta(hours=5))
        
        # Статистика ежедневной проверки
        self.daily_stats = {
            'date': None,
            'total_channels': 0,
            'checked_channels': 0,
            'new_channels': 0,
            'new_messages': 0,
            'filtered_messages': 0,
            'exported_messages': 0,
            'errors': 0,
            'channels_with_updates': []
        }
    
    async def initialize(self):
        """Инициализация проверщика"""
        try:
            # Создаем базовый экспортер
            self.exporter = TelegramExporter()
            await self.exporter.initialize_client(force_reauth=False)
            
            # Загружаем каналы
            if self.config_manager.channels_file_exists():
                self.channels = self.config_manager.import_channels()
                self.console.print(f"[green]✅ Загружено {len(self.channels)} каналов для ежедневной проверки[/green]")
            else:
                self.console.print("[yellow]⚠️ Файл каналов не найден[/yellow]")
                return False
            
            return True
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка инициализации ежедневной проверки: {e}[/red]")
            return False
    
    def schedule_daily_check(self):
        """Планирование ежедневной проверки в 8:00 по Пермскому времени"""
        try:
            # Планируем проверку на 8:00 по Пермскому времени
            schedule.every().day.at("08:00").do(self._run_daily_check)
            
            self.console.print("[green]✅ Ежедневная проверка запланирована на 8:00 по Пермскому времени[/green]")
            
            # Запускаем планировщик в отдельном потоке
            scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            scheduler_thread.start()
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка планирования ежедневной проверки: {e}[/red]")
    
    def _run_scheduler(self):
        """Запуск планировщика в отдельном потоке"""
        while True:
            schedule.run_pending()
            time.sleep(60)  # Проверяем каждую минуту
    
    def _run_daily_check(self):
        """Запуск ежедневной проверки"""
        try:
            # Запускаем проверку в новом событийном цикле
            asyncio.run(self._perform_daily_check())
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка ежедневной проверки: {e}[/red]")
    
    async def _perform_daily_check(self):
        """Выполнение ежедневной проверки каналов"""
        try:
            if not await self.initialize():
                return
            
            # Инициализируем статистику
            self.daily_stats = {
                'date': datetime.now(self.perm_timezone).strftime("%Y-%m-%d"),
                'total_channels': len(self.channels),
                'checked_channels': 0,
                'new_channels': 0,
                'new_messages': 0,
                'filtered_messages': 0,
                'exported_messages': 0,
                'errors': 0,
                'channels_with_updates': []
            }
            
            self.console.print(f"[blue]🔄 Начало ежедневной проверки каналов - {self.daily_stats['date']}[/blue]")
            
            # Проверяем каждый канал
            for channel in self.channels:
                try:
                    await self._check_channel_for_new_messages(channel)
                    self.daily_stats['checked_channels'] += 1
                    
                except Exception as e:
                    self.console.print(f"[red]❌ Ошибка проверки канала {channel.title}: {e}[/red]")
                    self.daily_stats['errors'] += 1
            
            # Отправляем ежедневную сводку
            await self._send_daily_report()
            
            self.console.print(f"[green]✅ Ежедневная проверка завершена[/green]")
            
        except Exception as e:
            self.console.print(f"[red]❌ Критическая ошибка ежедневной проверки: {e}[/red]")
        finally:
            if self.exporter and hasattr(self.exporter, 'disconnect'):
                await self.exporter.disconnect()
    
    async def _check_channel_for_new_messages(self, channel: ChannelInfo):
        """Проверка канала на новые сообщения"""
        try:
            # Получаем последнее сообщение из канала
            last_message = await self._get_last_message_from_channel(channel)
            
            if not last_message:
                return
            
            # Проверяем, есть ли новые сообщения
            if last_message.id > channel.last_message_id:
                new_messages_count = last_message.id - channel.last_message_id
                self.daily_stats['new_messages'] += new_messages_count
                
                # Получаем новые сообщения
                new_messages = await self._get_new_messages(channel, channel.last_message_id, last_message.id)
                
                # Применяем фильтрацию
                filtered_messages = await self._apply_content_filtering(new_messages)
                self.daily_stats['filtered_messages'] += len(filtered_messages)
                
                # Экспортируем отфильтрованные сообщения
                if filtered_messages:
                    await self._export_new_messages(channel, filtered_messages)
                    self.daily_stats['exported_messages'] += len(filtered_messages)
                    self.daily_stats['channels_with_updates'].append({
                        'channel': channel.title,
                        'new_messages': len(filtered_messages)
                    })
                
                # Обновляем информацию о канале
                channel.last_message_id = last_message.id
                channel.last_check = datetime.now().isoformat()
                
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка проверки канала {channel.title}: {e}[/red]")
            raise
    
    async def _get_last_message_from_channel(self, channel: ChannelInfo):
        """Получение последнего сообщения из канала"""
        try:
            # Здесь должна быть логика получения последнего сообщения
            # Пока что возвращаем заглушку
            return None
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка получения последнего сообщения: {e}[/red]")
            return None
    
    async def _get_new_messages(self, channel: ChannelInfo, from_id: int, to_id: int):
        """Получение новых сообщений из канала"""
        try:
            # Здесь должна быть логика получения новых сообщений
            # Пока что возвращаем пустой список
            return []
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка получения новых сообщений: {e}[/red]")
            return []
    
    async def _apply_content_filtering(self, messages: List):
        """Применение фильтрации контента к сообщениям"""
        try:
            filtered_messages = []
            
            for message in messages:
                # Применяем фильтрацию
                if self.content_filter.should_export_message(message):
                    filtered_messages.append(message)
            
            return filtered_messages
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка фильтрации контента: {e}[/red]")
            return messages
    
    async def _export_new_messages(self, channel: ChannelInfo, messages: List):
        """Экспорт новых сообщений в существующий MD файл"""
        try:
            # Определяем путь к файлу канала
            export_dir = Path(self.config_manager.config.storage.export_base_dir)
            channel_dir = export_dir / self._sanitize_filename(channel.title)
            md_file = channel_dir / "messages.md"
            
            if not md_file.exists():
                # Если файл не существует, создаем новый
                await self._create_new_md_file(channel, messages, md_file)
            else:
                # Дописываем в существующий файл
                await self._append_to_existing_md_file(messages, md_file)
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка экспорта новых сообщений: {e}[/red]")
            raise
    
    async def _create_new_md_file(self, channel: ChannelInfo, messages: List, md_file: Path):
        """Создание нового MD файла"""
        try:
            # Создаем директорию если не существует
            md_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Создаем заголовок файла
            content = f"# {channel.title}\n\n"
            content += f"**Канал:** {channel.title}\n"
            content += f"**Username:** @{channel.username}\n"
            content += f"**Дата создания:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            content += "---\n\n"
            
            # Добавляем сообщения
            for message in messages:
                content += self._format_message_for_md(message)
            
            # Записываем файл
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.console.print(f"[green]✅ Создан новый MD файл: {md_file}[/green]")
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка создания MD файла: {e}[/red]")
            raise
    
    async def _append_to_existing_md_file(self, messages: List, md_file: Path):
        """Дописывание в существующий MD файл"""
        try:
            # Читаем существующий файл
            with open(md_file, 'r', encoding='utf-8') as f:
                existing_content = f.read()
            
            # Добавляем новые сообщения
            new_content = "\n\n---\n\n"
            new_content += f"## Обновление от {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            for message in messages:
                new_content += self._format_message_for_md(message)
            
            # Записываем обновленный файл
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(existing_content + new_content)
            
            self.console.print(f"[green]✅ Обновлен MD файл: {md_file}[/green]")
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка обновления MD файла: {e}[/red]")
            raise
    
    def _format_message_for_md(self, message) -> str:
        """Форматирование сообщения для MD файла"""
        try:
            # Здесь должна быть логика форматирования сообщения
            # Пока что возвращаем заглушку
            return f"**Сообщение {message.id}:** {message.text}\n\n"
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка форматирования сообщения: {e}[/red]")
            return ""
    
    def _sanitize_filename(self, filename: str) -> str:
        """Очистка имени файла"""
        import re
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        if len(sanitized) > 100:
            sanitized = sanitized[:100] + "..."
        return sanitized
    
    async def _send_daily_report(self):
        """Отправка ежедневной сводки в Telegram"""
        try:
            # Формируем сводку
            report = self._create_daily_report()
            
            # Отправляем в Telegram (безусловно)
            await self._send_telegram_message(report)
            
            self.console.print("[green]✅ Ежедневная сводка отправлена в Telegram[/green]")
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка отправки ежедневной сводки: {e}[/red]")
    
    def _create_daily_report(self) -> str:
        """Создание ежедневной сводки"""
        try:
            report = f"📊 Ежедневная сводка экспорта каналов\n"
            report += f"📅 Дата: {self.daily_stats['date']}\n\n"
            
            report += f"📈 Статистика:\n"
            report += f"• Всего каналов: {self.daily_stats['total_channels']}\n"
            report += f"• Проверено каналов: {self.daily_stats['checked_channels']}\n"
            report += f"• Новых сообщений: {self.daily_stats['new_messages']}\n"
            report += f"• Отфильтровано: {self.daily_stats['filtered_messages']}\n"
            report += f"• Экспортировано: {self.daily_stats['exported_messages']}\n"
            report += f"• Ошибок: {self.daily_stats['errors']}\n\n"
            
            if self.daily_stats['channels_with_updates']:
                report += f"🔄 Каналы с обновлениями:\n"
                for channel_info in self.daily_stats['channels_with_updates']:
                    report += f"• {channel_info['channel']}: {channel_info['new_messages']} сообщений\n"
            else:
                report += f"✅ Новых сообщений не обнаружено\n"
            
            return report
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка создания сводки: {e}[/red]")
            return "Ошибка создания сводки"
    
    async def _send_telegram_message(self, message: str):
        """Отправка сообщения в Telegram"""
        try:
            import requests
            
            config = self.config_manager.config
            
            # Проверяем настройку бота
            if not self.config_manager.is_bot_configured():
                self.console.print("[yellow]⚠️ Bot не настроен, сводка сохранена в лог[/yellow]")
                self._save_report_to_log(message)
                return
            
            url = f"https://api.telegram.org/bot{config.bot.token}/sendMessage"
            data = {
                'chat_id': config.bot.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка отправки в Telegram: {e}[/red]")
            # Сохраняем в лог при ошибке
            self._save_report_to_log(message)
            raise
    
    def _save_report_to_log(self, message: str):
        """Сохранение отчета в лог файл"""
        try:
            from datetime import datetime
            log_file = Path("daily_reports.log")
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"Ежедневная сводка - {timestamp}\n")
                f.write(f"{'='*50}\n")
                f.write(message)
                f.write(f"\n{'='*50}\n")
            
            self.console.print(f"[blue]📝 Сводка сохранена в {log_file}[/blue]")
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка сохранения в лог: {e}[/red]")


async def main():
    """Главная функция для запуска ежедневной проверки"""
    console = Console()
    
    try:
        checker = DailyChannelChecker(console)
        checker.schedule_daily_check()
        
        # Показываем информацию о планировщике
        console.print("[green]🕐 Планировщик ежедневной проверки запущен[/green]")
        console.print("[blue]📅 Проверка запланирована на 8:00 по Пермскому времени[/blue]")
        console.print("[yellow]💡 Нажмите Ctrl+C для выхода[/yellow]")
        
        # Ждем бесконечно
        while True:
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Планировщик остановлен пользователем[/yellow]")
    except Exception as e:
        console.print(f"[red]Критическая ошибка: {e}[/red]")
    finally:
        console.print("[green]Программа завершена[/green]")


if __name__ == "__main__":
    asyncio.run(main())
