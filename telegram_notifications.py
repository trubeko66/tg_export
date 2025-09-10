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
    
    async def send_continuous_check_summary(self, check_results: dict):
        """Отправка сводки по завершении постоянной проверки"""
        try:
            if not self.is_configured():
                self.console.print("[yellow]⚠️ Bot не настроен, сводка сохранена в лог[/yellow]")
                # Сохраняем сводку в лог файл
                self._save_continuous_check_to_log(check_results)
                return False
            
            message = self._create_continuous_check_message(check_results)
            success = await self._send_message(message)
            
            if success:
                self.console.print("[green]✅ Сводка постоянной проверки отправлена в Telegram[/green]")
            else:
                self.console.print("[red]❌ Ошибка отправки сводки постоянной проверки[/red]")
                # Сохраняем в лог при ошибке отправки
                self._save_continuous_check_to_log(check_results)
            
            return success
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка отправки сводки постоянной проверки: {e}[/red]")
            # Сохраняем в лог при исключении
            self._save_continuous_check_to_log(check_results)
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
            message = f"🆕 Новый канал добавлен в экспорт\n\n"
            message += f"📺 Название: {channel.title}\n"
            
            if hasattr(channel, 'username') and channel.username:
                message += f"🔗 Username: @{channel.username}\n"
            
            if hasattr(channel, 'id') and channel.id:
                message += f"🆔 ID: {channel.id}\n"
            
            if hasattr(channel, 'description') and channel.description:
                message += f"📝 Описание: {channel.description[:200]}...\n"
            
            if hasattr(channel, 'subscribers_count') and channel.subscribers_count:
                message += f"👥 Подписчиков: {channel.subscribers_count:,}\n"
            
            if hasattr(channel, 'total_messages') and channel.total_messages:
                message += f"💬 Сообщений: {channel.total_messages:,}\n"
            
            if hasattr(channel, 'media_size_mb') and channel.media_size_mb:
                message += f"📁 Размер медиа: {channel.media_size_mb:.1f} МБ\n"
            
            message += f"\n⏰ Время добавления: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"🔄 Статус: Ожидает экспорта"
            
            return message
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка создания сообщения о новом канале: {e}[/red]")
            return f"Ошибка создания сообщения о канале {channel.title}"
    
    def _create_daily_report_message(self, report_data: dict) -> str:
        """Создание сообщения ежедневной сводки"""
        try:
            message = f"📊 Ежедневная сводка экспорта каналов\n"
            message += f"📅 Дата: {report_data.get('date', 'Неизвестно')}\n\n"
            
            # Статистика
            message += f"📈 Статистика:\n"
            message += f"• Всего каналов: {report_data.get('total_channels', 0)}\n"
            message += f"• Проверено каналов: {report_data.get('checked_channels', 0)}\n"
            message += f"• Новых сообщений: {report_data.get('new_messages', 0)}\n"
            message += f"• Отфильтровано: {report_data.get('filtered_messages', 0)}\n"
            message += f"• Экспортировано: {report_data.get('exported_messages', 0)}\n"
            message += f"• Ошибок: {report_data.get('errors', 0)}\n\n"
            
            # Каналы с обновлениями
            channels_with_updates = report_data.get('channels_with_updates', [])
            if channels_with_updates:
                message += f"🔄 Каналы с обновлениями:\n"
                for channel_info in channels_with_updates:
                    message += f"• {channel_info.get('channel', 'Неизвестно')}: {channel_info.get('new_messages', 0)} сообщений\n"
            else:
                message += f"✅ Новых сообщений не обнаружено\n"
            
            # Время отправки
            message += f"\n⏰ Время отправки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            return message
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка создания ежедневной сводки: {e}[/red]")
            return "Ошибка создания ежедневной сводки"
    
    def _create_error_message(self, error_message: str, channel_name: str = "") -> str:
        """Создание сообщения об ошибке"""
        try:
            message = f"❌ Ошибка экспорта каналов\n\n"
            
            if channel_name:
                message += f"📺 Канал: {channel_name}\n"
            
            message += f"🚨 Ошибка: {error_message}\n"
            message += f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"🔧 Действие: Проверьте логи и настройки"
            
            return message
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка создания сообщения об ошибке: {e}[/red]")
            return f"Ошибка: {error_message}"
    
    async def _send_message(self, message: str) -> bool:
        """Отправка сообщения в Telegram"""
        try:
            config = self.config_manager.config
            
            # Проверяем настройки
            if not config.bot.token:
                self.console.print("[red]❌ Токен бота не настроен[/red]")
                return False
            
            if not config.bot.chat_id:
                self.console.print("[red]❌ Chat ID не настроен[/red]")
                return False
            
            # Очищаем сообщение от потенциально проблемных символов
            clean_message = self._clean_message_for_telegram(message)
            
            url = f"https://api.telegram.org/bot{config.bot.token}/sendMessage"
            data = {
                'chat_id': config.bot.chat_id,
                'text': clean_message,
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                return True
            else:
                # Детальная обработка ошибок
                error_info = self._parse_telegram_error(response)
                self.console.print(f"[red]❌ HTTP {response.status_code}: {error_info}[/red]")
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
    
    def _clean_message_for_telegram(self, message: str) -> str:
        """Очистка сообщения для отправки в Telegram"""
        try:
            # Ограничиваем длину сообщения (Telegram лимит 4096 символов)
            if len(message) > 4000:
                clean_message = message[:4000] + "\n\n... (сообщение обрезано)"
            else:
                clean_message = message
            
            return clean_message
            
        except Exception as e:
            self.console.print(f"[yellow]⚠️ Ошибка очистки сообщения: {e}[/yellow]")
            return message[:4000] if len(message) > 4000 else message
    
    def _parse_telegram_error(self, response) -> str:
        """Парсинг ошибки от Telegram API"""
        try:
            import json
            error_data = response.json()
            
            if 'description' in error_data:
                error_desc = error_data['description']
                
                # Специальная обработка для частых ошибок
                if 'chat not found' in error_desc.lower():
                    return "Чат не найден. Проверьте Chat ID и убедитесь, что бот добавлен в чат."
                elif 'bot was blocked' in error_desc.lower():
                    return "Бот заблокирован пользователем. Разблокируйте бота в чате."
                elif 'invalid token' in error_desc.lower():
                    return "Неверный токен бота. Проверьте токен в настройках."
                elif 'chat_id is empty' in error_desc.lower():
                    return "Chat ID не указан. Настройте Chat ID в настройках бота."
                elif 'message is too long' in error_desc.lower():
                    return "Сообщение слишком длинное. Попробуйте сократить текст."
                elif 'parse_mode' in error_desc.lower():
                    return "Ошибка форматирования HTML. Проверьте теги в сообщении."
                else:
                    return error_desc
            else:
                return f"Неизвестная ошибка: {response.text}"
                
        except Exception as e:
            return f"Ошибка парсинга ответа: {response.text}"
    
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
    
    def _create_continuous_check_message(self, check_results: dict) -> str:
        """Создание сообщения сводки постоянной проверки"""
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            message = f"🔄 Сводка постоянной проверки каналов\n"
            message += f"⏰ Время: {current_time}\n\n"
            
            # Статистика проверки
            total_channels = check_results.get('total_channels', 0)
            checked_channels = check_results.get('checked_channels', 0)
            new_messages = check_results.get('new_messages', 0)
            channels_with_messages = check_results.get('channels_with_messages', 0)
            
            message += f"📊 Статистика проверки:\n"
            message += f"• Всего каналов: {total_channels}\n"
            message += f"• Проверено: {checked_channels}\n"
            message += f"• Новых сообщений: {new_messages}\n"
            message += f"• Каналов с обновлениями: {channels_with_messages}\n\n"
            
            # Каналы с новыми сообщениями
            channels_with_updates = check_results.get('channels_with_updates', [])
            if channels_with_updates:
                message += f"🆕 Каналы с новыми сообщениями:\n"
                for channel_info in channels_with_updates:
                    channel_name = channel_info.get('channel', 'Неизвестно')
                    new_count = channel_info.get('new_messages', 0)
                    message += f"• {channel_name}: {new_count} сообщений\n"
            else:
                message += f"✅ Новых сообщений не обнаружено\n"
            
            # Время проверки
            check_duration = check_results.get('check_duration', 0)
            if check_duration > 0:
                message += f"\n⏱️ Время проверки: {check_duration:.1f}с\n"
            
            # Следующая проверка
            check_interval = check_results.get('check_interval', 30)
            message += f"🔄 Следующая проверка: через {check_interval} секунд"
            
            return message
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка создания сообщения сводки: {e}[/red]")
            return f"Ошибка создания сводки постоянной проверки"
    
    def _save_continuous_check_to_log(self, check_results: dict):
        """Сохранение сводки постоянной проверки в лог"""
        try:
            log_file = Path("continuous_check_reports.log")
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n=== Сводка постоянной проверки - {current_time} ===\n")
                
                # Статистика
                f.write(f"Всего каналов: {check_results.get('total_channels', 0)}\n")
                f.write(f"Проверено: {check_results.get('checked_channels', 0)}\n")
                f.write(f"Новых сообщений: {check_results.get('new_messages', 0)}\n")
                f.write(f"Каналов с обновлениями: {check_results.get('channels_with_messages', 0)}\n")
                
                # Каналы с обновлениями
                channels_with_updates = check_results.get('channels_with_updates', [])
                if channels_with_updates:
                    f.write("Каналы с новыми сообщениями:\n")
                    for channel_info in channels_with_updates:
                        channel_name = channel_info.get('channel', 'Неизвестно')
                        new_count = channel_info.get('new_messages', 0)
                        f.write(f"  - {channel_name}: {new_count} сообщений\n")
                else:
                    f.write("Новых сообщений не обнаружено\n")
                
                # Время проверки
                check_duration = check_results.get('check_duration', 0)
                if check_duration > 0:
                    f.write(f"Время проверки: {check_duration:.1f}с\n")
                
                f.write("=" * 50 + "\n")
            
            self.console.print(f"[blue]📝 Сводка сохранена в лог: {log_file}[/blue]")
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка сохранения сводки в лог: {e}[/red]")


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
