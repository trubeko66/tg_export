#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль уведомлений в Telegram
"""

import asyncio
import requests
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from rich.console import Console

from config_manager import ConfigManager
from telegram_exporter import ChannelInfo


class TelegramNotifier:
    """Класс для отправки уведомлений в Telegram"""
    
    def __init__(self, console: Console):
        self.console = console
        self.config_manager = ConfigManager()
        self.notification_queue = []
    
    def is_configured(self) -> bool:
        """Проверка настройки бота"""
        return self.config_manager.is_bot_configured()
    
    async def send_new_channel_notification(self, channel: ChannelInfo):
        """Отправка уведомления о новом канале"""
        try:
            if not self.is_configured():
                self.console.print("[yellow]⚠️ Bot не настроен, уведомление не отправлено[/yellow]")
                return False
            
            message = self._create_new_channel_message(channel)
            success = await self._send_message(message)
            
            if success:
                self.console.print(f"[green]✅ Уведомление о новом канале отправлено: {channel.title}[/green]")
            else:
                self.console.print(f"[red]❌ Ошибка отправки уведомления о канале: {channel.title}[/red]")
            
            return success
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка отправки уведомления о новом канале: {e}[/red]")
            return False
    
    async def send_daily_report(self, report_data: dict):
        """Отправка ежедневной сводки"""
        try:
            if not self.is_configured():
                self.console.print("[yellow]⚠️ Bot не настроен, сводка сохранена в лог[/yellow]")
                # Сохраняем сводку в лог файл
                self._save_report_to_log(report_data)
                return False
            
            message = self._create_daily_report_message(report_data)
            success = await self._send_message(message)
            
            if success:
                self.console.print("[green]✅ Ежедневная сводка отправлена в Telegram[/green]")
            else:
                self.console.print("[red]❌ Ошибка отправки ежедневной сводки[/red]")
                # Сохраняем в лог при ошибке отправки
                self._save_report_to_log(report_data)
            
            return success
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка отправки ежедневной сводки: {e}[/red]")
            # Сохраняем в лог при исключении
            self._save_report_to_log(report_data)
            return False
    
    async def send_error_notification(self, error_message: str, channel_name: str = ""):
        """Отправка уведомления об ошибке"""
        try:
            if not self.is_configured():
                return False
            
            message = self._create_error_message(error_message, channel_name)
            success = await self._send_message(message)
            
            if success:
                self.console.print(f"[green]✅ Уведомление об ошибке отправлено[/green]")
            else:
                self.console.print(f"[red]❌ Ошибка отправки уведомления об ошибке[/red]")
            
            return success
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка отправки уведомления об ошибке: {e}[/red]")
            return False
    
    def _create_new_channel_message(self, channel: ChannelInfo) -> str:
        """Создание сообщения о новом канале"""
        try:
            message = f"🆕 <b>Новый канал добавлен в экспорт</b>\n\n"
            message += f"📺 <b>Название:</b> {channel.title}\n"
            
            if channel.username:
                message += f"🔗 <b>Username:</b> @{channel.username}\n"
            
            if channel.id:
                message += f"🆔 <b>ID:</b> {channel.id}\n"
            
            if channel.description:
                message += f"📝 <b>Описание:</b> {channel.description[:200]}...\n"
            
            if channel.subscribers_count:
                message += f"👥 <b>Подписчиков:</b> {channel.subscribers_count:,}\n"
            
            message += f"\n⏰ <b>Время добавления:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"🔄 <b>Статус:</b> Ожидает экспорта"
            
            return message
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка создания сообщения о новом канале: {e}[/red]")
            return f"Ошибка создания сообщения о канале {channel.title}"
    
    def _create_daily_report_message(self, report_data: dict) -> str:
        """Создание сообщения ежедневной сводки"""
        try:
            message = f"📊 <b>Ежедневная сводка экспорта каналов</b>\n"
            message += f"📅 <b>Дата:</b> {report_data.get('date', 'Неизвестно')}\n\n"
            
            # Статистика
            message += f"📈 <b>Статистика:</b>\n"
            message += f"• Всего каналов: {report_data.get('total_channels', 0)}\n"
            message += f"• Проверено каналов: {report_data.get('checked_channels', 0)}\n"
            message += f"• Новых сообщений: {report_data.get('new_messages', 0)}\n"
            message += f"• Отфильтровано: {report_data.get('filtered_messages', 0)}\n"
            message += f"• Экспортировано: {report_data.get('exported_messages', 0)}\n"
            message += f"• Ошибок: {report_data.get('errors', 0)}\n\n"
            
            # Каналы с обновлениями
            channels_with_updates = report_data.get('channels_with_updates', [])
            if channels_with_updates:
                message += f"🔄 <b>Каналы с обновлениями:</b>\n"
                for channel_info in channels_with_updates:
                    message += f"• {channel_info.get('channel', 'Неизвестно')}: {channel_info.get('new_messages', 0)} сообщений\n"
            else:
                message += f"✅ <b>Новых сообщений не обнаружено</b>\n"
            
            # Время отправки
            message += f"\n⏰ <b>Время отправки:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            return message
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка создания ежедневной сводки: {e}[/red]")
            return "Ошибка создания ежедневной сводки"
    
    def _create_error_message(self, error_message: str, channel_name: str = "") -> str:
        """Создание сообщения об ошибке"""
        try:
            message = f"❌ <b>Ошибка экспорта каналов</b>\n\n"
            
            if channel_name:
                message += f"📺 <b>Канал:</b> {channel_name}\n"
            
            message += f"🚨 <b>Ошибка:</b> {error_message}\n"
            message += f"⏰ <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"🔧 <b>Действие:</b> Проверьте логи и настройки"
            
            return message
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка создания сообщения об ошибке: {e}[/red]")
            return f"Ошибка: {error_message}"
    
    async def _send_message(self, message: str) -> bool:
        """Отправка сообщения в Telegram"""
        try:
            config = self.config_manager.config
            
            url = f"https://api.telegram.org/bot{config.bot.token}/sendMessage"
            data = {
                'chat_id': config.bot.chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                return True
            else:
                self.console.print(f"[red]❌ HTTP {response.status_code}: {response.text}[/red]")
                return False
                
        except requests.exceptions.Timeout:
            self.console.print("[red]❌ Таймаут отправки сообщения в Telegram[/red]")
            return False
        except requests.exceptions.ConnectionError:
            self.console.print("[red]❌ Ошибка подключения к Telegram API[/red]")
            return False
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка отправки сообщения: {e}[/red]")
            return False
    
    def _save_report_to_log(self, report_data: dict):
        """Сохранение отчета в лог файл"""
        try:
            from datetime import datetime
            log_file = Path("daily_reports.log")
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            report_text = self._create_daily_report_message(report_data)
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"Ежедневная сводка - {timestamp}\n")
                f.write(f"{'='*50}\n")
                f.write(report_text)
                f.write(f"\n{'='*50}\n")
            
            self.console.print(f"[blue]📝 Сводка сохранена в {log_file}[/blue]")
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка сохранения в лог: {e}[/red]")
    
    async def send_test_message(self) -> bool:
        """Отправка тестового сообщения"""
        try:
            if not self.is_configured():
                self.console.print("[yellow]⚠️ Bot не настроен[/yellow]")
                return False
            
            message = f"🧪 <b>Тестовое сообщение</b>\n\n"
            message += f"✅ <b>Статус:</b> Telegram уведомления работают\n"
            message += f"⏰ <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"🤖 <b>Bot:</b> Настроен и активен"
            
            success = await self._send_message(message)
            
            if success:
                self.console.print("[green]✅ Тестовое сообщение отправлено успешно[/green]")
            else:
                self.console.print("[red]❌ Ошибка отправки тестового сообщения[/red]")
            
            return success
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка отправки тестового сообщения: {e}[/red]")
            return False
    
    def add_to_queue(self, message_type: str, data: dict):
        """Добавление сообщения в очередь"""
        try:
            self.notification_queue.append({
                'type': message_type,
                'data': data,
                'timestamp': datetime.now()
            })
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка добавления в очередь: {e}[/red]")
    
    async def process_queue(self):
        """Обработка очереди уведомлений"""
        try:
            while self.notification_queue:
                notification = self.notification_queue.pop(0)
                
                if notification['type'] == 'new_channel':
                    await self.send_new_channel_notification(notification['data']['channel'])
                elif notification['type'] == 'daily_report':
                    await self.send_daily_report(notification['data'])
                elif notification['type'] == 'error':
                    await self.send_error_notification(
                        notification['data']['error'],
                        notification['data'].get('channel_name', '')
                    )
                
                # Небольшая пауза между отправками
                await asyncio.sleep(1)
                
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка обработки очереди: {e}[/red]")


# Глобальный экземпляр для использования в других модулях
_global_notifier = None

def get_notifier(console: Console = None) -> TelegramNotifier:
    """Получение глобального экземпляра уведомлений"""
    global _global_notifier
    if _global_notifier is None and console:
        _global_notifier = TelegramNotifier(console)
    return _global_notifier

def set_notifier(notifier: TelegramNotifier):
    """Установка глобального экземпляра уведомлений"""
    global _global_notifier
    _global_notifier = notifier
