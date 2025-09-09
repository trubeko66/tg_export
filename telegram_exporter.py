#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Channel Exporter
Программа для мониторинга и экспорта Telegram каналов
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from pathlib import Path
import re
import schedule
import time
from dataclasses import dataclass, asdict
import html
import markdown
import posixpath
import zipfile
from enum import Enum
import sys
import threading
import queue

from content_filter import ContentFilter, FilterConfig
from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat, User, MessageMediaPhoto, MessageMediaDocument, Message
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, TaskID
from rich import box
import requests

from exporters import (
    MessageData, JSONExporter, HTMLExporter, MarkdownExporter, MediaDownloader, BaseExporter
)
from config_manager import ConfigManager


class ExportType(Enum):
    """Типы экспорта"""
    BOTH = "both"  # Сообщения и файлы
    MESSAGES_ONLY = "messages_only"  # Только сообщения
    FILES_ONLY = "files_only"  # Только файлы


@dataclass
class ChannelInfo:
    """Информация о канале"""
    id: int
    title: str
    username: Optional[str]
    last_message_id: int = 0
    total_messages: int = 0
    last_check: Optional[str] = None
    media_size_mb: float = 0.0  # Кэшированный размер медиафайлов в МБ
    export_type: ExportType = ExportType.BOTH  # Тип экспорта


@dataclass
class ExportStats:
    """Статистика экспорта"""
    total_channels: int = 0
    total_messages: int = 0
    total_size_mb: float = 0.0
    export_errors: int = 0
    filtered_messages: int = 0
    last_export_time: Optional[str] = None
    current_export_info: Optional[str] = None  # Информация о текущем экспорте
    total_messages_in_channel: int = 0  # Общее количество сообщений в текущем канале
    download_speed_files_per_sec: float = 0.0  # Текущая скорость в файлах/сек
    download_speed_mb_per_sec: float = 0.0     # Текущая скорость в МБ/сек
    remaining_files_to_download: int = 0       # Осталось файлов к скачиванию
    discovered_messages: int = 0               # Общее количество обнаруженных сообщений
    exported_messages: int = 0                 # Количество уже экспортированных сообщений
    md_verification_status: Optional[str] = None  # Статус проверки MD файлов
    md_verification_channel: Optional[str] = None  # Текущий канал проверки MD
    md_reexport_count: int = 0                 # Количество повторных экспортов MD
    md_verification_progress: Optional[str] = None  # Прогресс проверки MD файлов


class TelegramExporter:
    # Константы для обработки больших каналов
    BATCH_SIZE = 1000  # Размер батча для обработки сообщений
    MAX_MESSAGES_PER_EXPORT = 50000  # Максимум сообщений за один экспорт
    PROGRESS_UPDATE_INTERVAL = 100  # Интервал обновления прогресса
    
    def __init__(self):
        self.console = Console()
        self.client: Optional[TelegramClient] = None
        self.channels: List[ChannelInfo] = []
        self.stats = ExportStats()
        self.running = True
        
        # Параметры прокрутки для главного экрана
        self.channels_scroll_offset = 0
        self.channels_display_limit = 10  # Количество каналов на экране
        
        # Очередь для обработки клавиш
        self.key_queue = queue.Queue()
        self.key_thread = None
        self.key_thread_running = False
        
        # Инициализация менеджера конфигурации
        self.config_manager = ConfigManager()
        # Путь списка каналов из конфигурации
        try:
            storage_cfg = self.config_manager.config.storage  # type: ignore[attr-defined]
            channels_path = getattr(storage_cfg, 'channels_path', '.channels') if storage_cfg else '.channels'
        except Exception:
            channels_path = '.channels'
        self.channels_file = Path(channels_path)

        # Инициализация фильтра контента
        self.content_filter = ContentFilter()
        
        # Настройка логирования
        self.setup_logging()
        
    def _sanitize_channel_filename(self, channel_title: str) -> str:
        """Sanitize channel title for use as filename using the same logic as exporters"""
        # Use the same sanitization logic as BaseExporter
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', channel_title)
        # Ограничение длины
        if len(sanitized) > 100:
            sanitized = sanitized[:100] + "..."
        return sanitized
    
    # ===== Вспомогательные методы пути хранения =====
    def _get_channels_file_path(self) -> Path:
        try:
            storage_cfg = self.config_manager.config.storage  # type: ignore[attr-defined]
            channels_path = getattr(storage_cfg, 'channels_path', None)
            return Path(channels_path) if channels_path else Path('.channels')
        except Exception:
            return Path('.channels')

    # ===== WebDAV синхронизация =====
    def _webdav_enabled(self) -> bool:
        try:
            return bool(self.config_manager.config.webdav.enabled)  # type: ignore[attr-defined]
        except Exception:
            return False

    def _webdav_build_url(self, base_url: str, path: str) -> str:
        if not base_url.endswith('/'):
            base_url += '/'
        return base_url + path.lstrip('/')

    def _webdav_make_dirs(self, base_url: str, auth: tuple, remote_path: str) -> None:
        try:
            import requests
            dir_path = posixpath.dirname(remote_path) or '/'
            if dir_path in ('', '/', None):
                return
            segments = [seg for seg in dir_path.strip('/').split('/') if seg]
            current = ''
            for seg in segments:
                current = current + '/' + seg
                url = self._webdav_build_url(base_url, current)
                resp = requests.request('MKCOL', url, auth=auth)
                if resp.status_code not in (201, 405):
                    self.logger.warning(f"MKCOL {url} returned {resp.status_code}")
        except Exception as e:
            self.logger.warning(f"WebDAV make dirs error: {e}")

    def _webdav_download(self) -> bool:
        if not self._webdav_enabled():
            return False
        try:
            import requests
            webdav = self.config_manager.config.webdav  # type: ignore[attr-defined]
            base_url = webdav.url or ''
            remote_path = webdav.remote_path or '/channels/.channels'
            auth = (webdav.username or '', webdav.password or '')
            url = self._webdav_build_url(base_url, remote_path)
            resp = requests.get(url, auth=auth, timeout=30)
            if resp.status_code == 200:
                local_path = self._get_channels_file_path()
                local_path.parent.mkdir(parents=True, exist_ok=True)
                with open(local_path, 'wb') as f:
                    f.write(resp.content)
                self.logger.info(f"WebDAV download succeeded: {url} -> {local_path}")
                return True
            else:
                self.logger.warning(f"WebDAV download skipped ({resp.status_code}): {url}")
                return False
        except Exception as e:
            self.logger.error(f"WebDAV download error: {e}")
            return False

    def _webdav_upload(self) -> bool:
        if not self._webdav_enabled():
            return False
        try:
            import requests
            webdav = self.config_manager.config.webdav  # type: ignore[attr-defined]
            base_url = webdav.url or ''
            remote_path = webdav.remote_path or '/channels/.channels'
            auth = (webdav.username or '', webdav.password or '')
            url = self._webdav_build_url(base_url, remote_path)
            self._webdav_make_dirs(base_url, auth, remote_path)
            local_path = self._get_channels_file_path()
            if not local_path.exists():
                return False
            with open(local_path, 'rb') as f:
                data = f.read()
            resp = requests.put(url, data=data, auth=auth, timeout=30)
            if resp.status_code in (200, 201, 204):
                self.logger.info(f"WebDAV upload succeeded: {local_path} -> {url}")
                return True
            else:
                self.logger.error(f"WebDAV upload failed ({resp.status_code}): {url}")
                return False
        except Exception as e:
            self.logger.error(f"WebDAV upload error: {e}")
            return False

    async def _webdav_download_and_notify(self):
        try:
            webdav = self.config_manager.config.webdav  # type: ignore[attr-defined]
            if self._webdav_download() and getattr(webdav, 'notify_on_sync', True):
                await self.send_notification("✅ Синхронизация WebDAV: загрузка списка каналов выполнена успешно")
        except Exception:
            pass

    async def _webdav_upload_and_notify(self):
        try:
            webdav = self.config_manager.config.webdav  # type: ignore[attr-defined]
            if self._webdav_upload() and getattr(webdav, 'notify_on_sync', True):
                await self.send_notification("✅ Синхронизация WebDAV: выгрузка списка каналов выполнена успешно")
        except Exception:
            pass

    def _zip_channel_folder(self, channel_dir: Path) -> Optional[Path]:
        try:
            if not channel_dir.exists() or not channel_dir.is_dir():
                return None
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            zip_path = channel_dir.parent / f"{channel_dir.name}_{ts}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(channel_dir):
                    for file in files:
                        full_path = Path(root) / file
                        arcname = str(full_path.relative_to(channel_dir.parent))
                        zf.write(full_path, arcname)
            return zip_path
        except Exception as e:
            self.logger.error(f"ZIP archive error for {channel_dir}: {e}")
            return None

    def _webdav_upload_archive(self, archive_path: Path) -> bool:
        if not self._webdav_enabled():
            return False
        try:
            import requests
            webdav = self.config_manager.config.webdav  # type: ignore[attr-defined]
            base_url = webdav.url or ''
            remote_dir = webdav.archives_remote_dir or '/channels/archives'
            auth = (webdav.username or '', webdav.password or '')
            # ensure remote dir
            self._webdav_make_dirs(base_url, auth, posixpath.join(remote_dir, 'dummy'))
            remote_name = archive_path.name
            url = self._webdav_build_url(base_url, posixpath.join(remote_dir, remote_name))
            with open(archive_path, 'rb') as f:
                data = f.read()
            resp = requests.put(url, data=data, auth=auth, timeout=60)
            if resp.status_code in (200, 201, 204):
                self.logger.info(f"Archive uploaded to WebDAV: {url}")
                return True
            else:
                self.logger.error(f"Archive upload failed ({resp.status_code}): {url}")
                return False
        except Exception as e:
            self.logger.error(f"WebDAV archive upload error: {e}")
            return False
        
    # ===== Работа с файлами каналов =====
    def load_channels_from_file(self, file_path: Path) -> bool:
        """Загрузка списка каналов из произвольного JSON-файла"""
        if not file_path.exists():
            self.logger.error(f"Файл не найден: {file_path}")
            self.console.print(f"[red]Файл не найден: {file_path}[/red]")
            return False
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                
            if not content:
                self.logger.error(f"Файл пуст: {file_path}")
                self.console.print(f"[red]Файл пуст: {file_path}[/red]")
                return False
                
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                self.logger.error(f"Ошибка формата JSON в файле {file_path}: {e}")
                self.console.print(f"[red]Ошибка формата JSON в файле {file_path}:[/red]")
                self.console.print(f"[red]Строка {e.lineno}, позиция {e.colno}: {e.msg}[/red]")
                
                # Показываем проблемный фрагмент
                try:
                    lines = content.split('\n')
                    if e.lineno <= len(lines):
                        problem_line = lines[e.lineno - 1]
                        self.console.print(f"[yellow]Проблемная строка: {problem_line}[/yellow]")
                        if e.colno > 0 and e.colno <= len(problem_line):
                            pointer = ' ' * (e.colno - 1) + '^'
                            self.console.print(f"[yellow]{pointer}[/yellow]")
                except Exception:
                    pass
                    
                return False
                
            if not isinstance(data, list):
                self.logger.error(f"Неверный формат данных в файле {file_path}: ожидался список, получен {type(data)}")
                self.console.print(f"[red]Неверный формат файла: ожидался список каналов, получен {type(data).__name__}[/red]")
                return False
                
            # Конвертируем данные в ChannelInfo с проверкой полей
            valid_channels = []
            errors = []
            
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    errors.append(f"Элемент {i + 1}: не является объектом (получен {type(item).__name__})")
                    continue
                    
                # Проверяем обязательные поля
                required_fields = ['id', 'title']
                missing_fields = [field for field in required_fields if field not in item or item[field] is None]
                if missing_fields:
                    errors.append(f"Элемент {i + 1} ('{item.get('title', 'без названия')}'): отсутствуют поля {missing_fields}")
                    continue
                    
                try:
                    # Приводим export_type к правильному типу если нужно
                    if 'export_type' in item:
                        export_type_value = item['export_type']
                        if isinstance(export_type_value, str):
                            try:
                                item['export_type'] = ExportType(export_type_value)
                            except ValueError:
                                item['export_type'] = ExportType.BOTH
                                errors.append(f"Элемент {i + 1}: неизвестный тип экспорта '{export_type_value}', используется BOTH")
                    else:
                        item['export_type'] = ExportType.BOTH
                        
                    channel = ChannelInfo(**item)
                    valid_channels.append(channel)
                    
                except Exception as e:
                    errors.append(f"Элемент {i + 1}: ошибка создания объекта канала - {e}")
                    continue
                    
            # Показываем результаты
            if errors:
                self.console.print(f"[yellow]Найдены проблемы при загрузке:[/yellow]")
                for error in errors:
                    self.console.print(f"[yellow]  • {error}[/yellow]")
                    
            if not valid_channels:
                self.console.print(f"[red]Не удалось загрузить ни одного валидного канала из файла[/red]")
                return False
                
            self.channels = valid_channels
            success_msg = f"Успешно загружено {len(valid_channels)} каналов"
            if len(valid_channels) != len(data):
                success_msg += f" из {len(data)} (пропущено {len(data) - len(valid_channels)})"
                
            self.console.print(f"[green]{success_msg}[/green]")
            self.logger.info(f"Loaded {len(valid_channels)} channels from {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Общая ошибка загрузки из файла {file_path}: {e}")
            self.console.print(f"[red]Ошибка загрузки из файла {file_path}: {e}[/red]")
            return False

    def save_channels_to_file(self, file_path: Path) -> bool:
        """Сохранение списка каналов в произвольный JSON-файл для редактирования"""
        try:
            # Преобразуем каналы в словарь с правильной сериализацией enum
            channels_data = []
            for channel in self.channels:
                channel_dict = asdict(channel)
                # Преобразуем ExportType в строку
                if 'export_type' in channel_dict and isinstance(channel_dict['export_type'], ExportType):
                    channel_dict['export_type'] = channel_dict['export_type'].value
                channels_data.append(channel_dict)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(channels_data, f, ensure_ascii=False, indent=2)
                
            self.console.print(f"[green]✓ Список каналов сохранен в {file_path}[/green]")
            return True
        except Exception as e:
            self.logger.error(f"Error saving channels to {file_path}: {e}")
            self.console.print(f"[red]Ошибка сохранения в файл {file_path}: {e}[/red]")
            return False

    def setup_logging(self):
        """Настройка системы логирования"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('export.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    async def initialize_client(self, force_reauth: bool = False):
        """Инициализация Telegram клиента"""
        try:
            # Получение конфигурации из менеджера
            telegram_config = self.config_manager.get_telegram_config()
            
            # Проверяем наличие и корректность API credentials
            if not telegram_config or not telegram_config.api_id or not telegram_config.api_hash:
                self.console.print("[red]Ошибка: не настроены API credentials для Telegram[/red]")
                return False
                
            # Конвертируем api_id в int если нужно
            api_id = int(telegram_config.api_id) if isinstance(telegram_config.api_id, str) else telegram_config.api_id
            if not isinstance(api_id, int):
                self.console.print("[red]Ошибка: API ID должен быть числом[/red]")
                return False
                
            api_hash = str(telegram_config.api_hash)
            phone = str(telegram_config.phone) if telegram_config.phone else None
            
            if not phone:
                self.console.print("[red]Ошибка: не указан номер телефона[/red]")
                return False
                
            # Создаем уникальное имя сессии на основе API ID для изоляции
            session_name = f'session_{api_id}'
            
            # Если требуется принудительная повторная авторизация, удаляем старую сессию
            if force_reauth:
                await self._clear_session(session_name)
                self.console.print("[yellow]⚠️ Старая сессия очищена, требуется повторная авторизация[/yellow]")
            
            # Проверяем, не заблокирован ли файл сессии
            actual_session_name = await self._check_and_unlock_session(session_name)
            if actual_session_name:
                session_name = actual_session_name
            
            self.client = TelegramClient(session_name, api_id, api_hash)
            
            # Запускаем клиент с принудительной авторизацией если требуется
            try:
                if force_reauth:
                    await self.client.start(phone=phone, force_sms=True)
                else:
                    await self.client.start(phone=phone, force_sms=False)
            except Exception as start_error:
                if "database is locked" in str(start_error):
                    self.console.print("[yellow]⚠️ База данных заблокирована, пытаемся разблокировать...[/yellow]")
                    # Пытаемся разблокировать и перезапустить
                    await asyncio.sleep(3)
                    try:
                        if force_reauth:
                            await self.client.start(phone=phone, force_sms=True)
                        else:
                            await self.client.start(phone=phone, force_sms=False)
                    except Exception as retry_error:
                        self.console.print(f"[red]❌ Не удалось разблокировать базу данных: {retry_error}[/red]")
                        return False
                else:
                    raise
            
            if await self.client.is_user_authorized():
                self.console.print("[green]✓ Успешная авторизация в Telegram[/green]")
                self.logger.info("Successful Telegram authorization")
                return True
            else:
                self.console.print("[red]✗ Ошибка авторизации[/red]")
                return False
                
        except Exception as e:
            self.console.print(f"[red]Ошибка инициализации клиента: {e}[/red]")
            self.logger.error(f"Client initialization error: {e}")
            return False
    
    async def _clear_session(self, session_name: str):
        """Очистка файла сессии"""
        try:
            session_file = Path(f"{session_name}.session")
            if session_file.exists():
                session_file.unlink()
                self.console.print(f"[blue]🗑️ Удален файл сессии: {session_file}[/blue]")
        except Exception as e:
            self.console.print(f"[yellow]⚠️ Не удалось удалить сессию: {e}[/yellow]")
    
    async def _check_and_unlock_session(self, session_name: str):
        """Проверка и разблокировка файла сессии"""
        try:
            session_file = Path(f"{session_name}.session")
            if not session_file.exists():
                return
            
            # Проверяем, не заблокирован ли файл
            try:
                # Пытаемся открыть файл для записи
                with open(session_file, 'r+b') as f:
                    pass
                self.console.print(f"[green]✅ Файл сессии доступен: {session_file}[/green]")
            except (PermissionError, OSError) as e:
                if "database is locked" in str(e) or "Permission denied" in str(e):
                    self.console.print(f"[yellow]⚠️ Файл сессии заблокирован: {session_file}[/yellow]")
                    self.console.print("[blue]🔄 Попытка разблокировки...[/blue]")
                    
                    # Ждем немного и пытаемся снова
                    await asyncio.sleep(2)
                    
                    try:
                        # Пытаемся удалить заблокированный файл
                        session_file.unlink()
                        self.console.print(f"[green]✅ Заблокированный файл сессии удален: {session_file}[/green]")
                    except Exception as delete_error:
                        self.console.print(f"[red]❌ Не удалось удалить заблокированный файл: {delete_error}[/red]")
                        # Создаем новый файл с уникальным именем
                        import time
                        timestamp = int(time.time())
                        new_session_name = f"{session_name}_{timestamp}"
                        self.console.print(f"[blue]🔄 Используем новое имя сессии: {new_session_name}[/blue]")
                        return new_session_name
                else:
                    raise
                    
        except Exception as e:
            self.console.print(f"[yellow]⚠️ Ошибка проверки сессии: {e}[/yellow]")
            return session_name
    
    def setup_bot_notifications(self):
        """Настройка уведомлений через бота (теперь через конфигурацию)"""
        # Этот метод больше не нужен, так как настройка происходит через ConfigManager
        pass
    
    async def send_notification(self, message: str):
        """Отправка уведомления через бота"""
        bot_config = self.config_manager.get_bot_config()
        
        if not bot_config.enabled or not bot_config.bot_token or not bot_config.chat_id:
            return
            
        try:
            url = f"https://api.telegram.org/bot{bot_config.bot_token}/sendMessage"
            data = {
                'chat_id': bot_config.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            requests.post(url, data=data)
        except Exception as e:
            self.logger.error(f"Notification error: {e}")
    
    def load_channels(self) -> bool:
        """Загрузка списка каналов из файла"""
        self.channels_file = self._get_channels_file_path()
        if not self.channels_file.exists():
            self.logger.info(f"Файл каналов не найден: {self.channels_file}")
            return False
            
        try:
            with open(self.channels_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                
            if not content:
                self.logger.warning(f"Файл каналов пуст: {self.channels_file}")
                self.console.print(f"[yellow]Файл каналов пуст: {self.channels_file}[/yellow]")
                return False
                
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                self.logger.error(f"Ошибка формата JSON в файле {self.channels_file}: {e}")
                self.console.print(f"[red]Ошибка формата JSON в файле каналов:[/red]")
                self.console.print(f"[red]Строка {e.lineno}, позиция {e.colno}: {e.msg}[/red]")
                
                # Предлагаем пользователю исправить файл
                if Confirm.ask("Создать новый пустой файл каналов?", default=True):
                    try:
                        with open(self.channels_file, 'w', encoding='utf-8') as f:
                            json.dump([], f, ensure_ascii=False, indent=2)
                        self.console.print(f"[green]Создан новый пустой файл: {self.channels_file}[/green]")
                        self.channels = []
                        return True
                    except Exception as write_error:
                        self.logger.error(f"Ошибка создания нового файла: {write_error}")
                        self.console.print(f"[red]Ошибка создания файла: {write_error}[/red]")
                return False
                
            if not isinstance(data, list):
                self.logger.error(f"Неверный формат данных в файле каналов: ожидался список, получен {type(data)}")
                self.console.print(f"[red]Неверный формат файла каналов: ожидался список каналов[/red]")
                return False
                
            # Конвертируем данные в ChannelInfo с проверкой полей
            valid_channels = []
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    self.logger.warning(f"Пропуск элемента {i}: не является объектом")
                    continue
                    
                # Проверяем обязательные поля
                required_fields = ['id', 'title']
                missing_fields = [field for field in required_fields if field not in item]
                if missing_fields:
                    self.logger.warning(f"Пропуск канала {i}: отсутствуют поля {missing_fields}")
                    continue
                    
                try:
                    # Приводим export_type к правильному типу если нужно
                    if 'export_type' in item:
                        export_type_value = item['export_type']
                        if isinstance(export_type_value, str):
                            # Пытаемся найти соответствующий enum
                            try:
                                item['export_type'] = ExportType(export_type_value)
                            except ValueError:
                                # Если не найден, используем значение по умолчанию
                                item['export_type'] = ExportType.BOTH
                                self.logger.warning(f"Неизвестный тип экспорта '{export_type_value}' для канала {item.get('title', 'unknown')}, используется BOTH")
                    else:
                        item['export_type'] = ExportType.BOTH
                        
                    channel = ChannelInfo(**item)
                    valid_channels.append(channel)
                except Exception as e:
                    self.logger.warning(f"Ошибка создания ChannelInfo для элемента {i}: {e}")
                    continue
                    
            self.channels = valid_channels
            
            if len(valid_channels) != len(data):
                invalid_count = len(data) - len(valid_channels)
                self.console.print(f"[yellow]Пропущено {invalid_count} некорректных записей из файла каналов[/yellow]")
                
                # Сохраняем исправленную версию
                if valid_channels:
                    self.save_channels()
                    self.console.print(f"[green]Файл каналов исправлен и сохранен[/green]")
                    
            self.console.print(f"[green]Успешно загружено {len(valid_channels)} каналов[/green]")
            self.logger.info(f"Loaded {len(valid_channels)} channels from {self.channels_file}")
            return len(valid_channels) > 0
            
        except Exception as e:
            self.logger.error(f"Общая ошибка загрузки каналов: {e}")
            self.console.print(f"[red]Ошибка загрузки файла каналов: {e}[/red]")
            return False
    
    def save_channels(self):
        """Сохранение списка каналов в файл"""
        try:
            self.channels_file = self._get_channels_file_path()
            
            # Преобразуем каналы в словарь с правильной сериализацией enum
            channels_data = []
            for channel in self.channels:
                channel_dict = asdict(channel)
                # Преобразуем ExportType в строку
                if 'export_type' in channel_dict and isinstance(channel_dict['export_type'], ExportType):
                    channel_dict['export_type'] = channel_dict['export_type'].value
                channels_data.append(channel_dict)
            
            with open(self.channels_file, 'w', encoding='utf-8') as f:
                json.dump(channels_data, f, ensure_ascii=False, indent=2)
                
            # WebDAV upload
            if self._webdav_enabled():
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._webdav_upload_and_notify())
                except RuntimeError:
                    self._webdav_upload()
        except Exception as e:
            self.logger.error(f"Error saving channels: {e}")
    
    def display_channels_page(self, dialogs: list, page: int, selected_ids: Optional[set] = None, page_size: int = 10) -> Table:
        """Отображение страницы каналов"""
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, len(dialogs))
        
        table = Table(title=f"Доступные каналы (страница {page + 1} из {(len(dialogs) - 1) // page_size + 1})", box=box.ROUNDED)
        table.add_column("✔", style="magenta", width=2)
        table.add_column("№", style="cyan", width=4)
        table.add_column("Название", style="green", max_width=40)
        table.add_column("Username", style="blue", max_width=20)
        table.add_column("Участников", style="yellow", justify="right")
        
        for i in range(start_idx, end_idx):
            dialog = dialogs[i]
            username = f"@{dialog.entity.username}" if dialog.entity.username else "—"
            participants = getattr(dialog.entity, 'participants_count', 0)
            # Обрезаем длинные названия
            title = dialog.title[:37] + "..." if len(dialog.title) > 40 else dialog.title
            is_selected = "✓" if (selected_ids and getattr(dialog.entity, 'id', None) in selected_ids) else ""
            table.add_row(is_selected, str(i + 1), title, username, str(participants))
        
        return table

    async def select_channels(self):
        """Выбор каналов для мониторинга с постраничным отображением и удобными командами"""
        self.console.print("\n[bold blue]Получение списка каналов...[/bold blue]")
        
        try:
            # Получаем список каналов-бродкастов
            all_dialogs = []
            async for dialog in self.client.iter_dialogs():
                if hasattr(dialog.entity, 'broadcast') and dialog.entity.broadcast:
                    all_dialogs.append(dialog)
            
            if not all_dialogs:
                self.console.print("[yellow]Каналы не найдены[/yellow]")
                return
            
            # Текущее отображаемое множество и выбранные каналы (по id)
            dialogs = list(all_dialogs)
            selected_ids: set = set()
            
            page_size = 10
            current_page = 0
            
            def total_pages_for(lst: list) -> int:
                return (len(lst) - 1) // page_size + 1 if lst else 1
            
            while True:
                total_pages = total_pages_for(dialogs)
                if current_page >= total_pages:
                    current_page = max(0, total_pages - 1)
                
                # Очистка экрана и отображение текущей страницы
                self.console.clear()
                table = self.display_channels_page(dialogs, current_page, selected_ids, page_size)
                self.console.print(table)
                
                # Инструкции
                self.console.print(
                    "\n[bold yellow]Команды:[/bold yellow] p/n — страница | sa/sd — выделить/снять страницу | "
                    "1,3-5 — переключить номера | f — поиск | x — очистить | s — продолжить | q — выход"
                )
                self.console.print(f"[dim]Страница {current_page + 1} из {total_pages} | Выбрано: {len(selected_ids)}[/dim]")
                
                # Получение команды
                command = Prompt.ask("\nВведите команду").strip().lower()
                
                if command == 'p':
                    if current_page > 0:
                        current_page -= 1
                    else:
                        self.console.print("[yellow]⚠ Вы уже на первой странице[/yellow]")
                        input("Нажмите Enter для продолжения...")
                elif command == 'n':
                    if current_page < total_pages - 1:
                        current_page += 1
                    else:
                        self.console.print("[yellow]⚠ Вы уже на последней странице[/yellow]")
                        input("Нажмите Enter для продолжения...")
                elif command == 'sa':
                    # Select All on page
                    start_idx = current_page * page_size
                    end_idx = min(start_idx + page_size, len(dialogs))
                    for i in range(start_idx, end_idx):
                        selected_ids.add(getattr(dialogs[i].entity, 'id', None))
                elif command == 'sd':
                    # Select None (deselect) on page
                    start_idx = current_page * page_size
                    end_idx = min(start_idx + page_size, len(dialogs))
                    for i in range(start_idx, end_idx):
                        selected_ids.discard(getattr(dialogs[i].entity, 'id', None))
                elif command == 'x':
                    selected_ids.clear()
                elif command == 'f':
                    query = Prompt.ask("Поиск по названию/username (пусто — показать все)", default="")
                    q = query.strip().lower()
                    if not q:
                        dialogs = list(all_dialogs)
                    else:
                        filtered_dialogs = []
                        for d in all_dialogs:
                            title_match = q in (d.title or '').lower()
                            uname = getattr(d.entity, 'username', None)
                            uname_match = (uname and q in uname.lower())
                            if title_match or uname_match:
                                filtered_dialogs.append(d)
                        dialogs = filtered_dialogs
                    current_page = 0
                elif command == 's':
                    break
                elif command == 'q':
                    return
                else:
                    # попытка разобрать как список номеров/диапазонов
                    tokens = [t.strip() for t in command.split(',') if t.strip()]
                    if not tokens:
                        self.console.print("[red]❌ Неверная команда[/red]")
                        input("Нажмите Enter для продолжения...")
                        continue
                    ok = True
                    for token in tokens:
                        if '-' in token:
                            parts = token.split('-')
                            if len(parts) != 2:
                                ok = False
                                break
                            try:
                                a = int(parts[0])
                                b = int(parts[1])
                            except ValueError:
                                ok = False
                                break
                            if a > b:
                                a, b = b, a
                            for num in range(a, b + 1):
                                if 1 <= num <= len(dialogs):
                                    dlg = dialogs[num - 1]
                                    dlg_id = getattr(dlg.entity, 'id', None)
                                    if dlg_id in selected_ids:
                                        selected_ids.discard(dlg_id)
                                    else:
                                        selected_ids.add(dlg_id)
                        else:
                            try:
                                num = int(token)
                            except ValueError:
                                ok = False
                                break
                            if 1 <= num <= len(dialogs):
                                dlg = dialogs[num - 1]
                                dlg_id = getattr(dlg.entity, 'id', None)
                                if dlg_id in selected_ids:
                                    selected_ids.discard(dlg_id)
                                else:
                                    selected_ids.add(dlg_id)
                            else:
                                ok = False
                                break
                    if not ok:
                        self.console.print("[red]❌ Неверный формат. Используйте числа и диапазоны, например: 1,3-6[/red]")
                        input("Нажмите Enter для продолжения...")
                        continue
            
            # Финализация выбора
            if not selected_ids:
                self.console.print("[yellow]Вы ничего не выбрали[/yellow]")
                return
            
            # Преобразуем выбранные id в объекты ChannelInfo (по оригинальному списку)
            selected_map = {getattr(d.entity, 'id', None): d for d in all_dialogs}
            for dlg_id in selected_ids:
                d = selected_map.get(dlg_id)
                if d is None:
                    continue
                self.channels.append(ChannelInfo(
                    id=getattr(d.entity, 'id', 0),
                    title=d.title,
                    username=getattr(d.entity, 'username', None)
                ))
            
            self.save_channels()
            self.console.print(f"[green]✓ Выбрано {len(self.channels)} каналов[/green]")
        
        except Exception as e:
            self.console.print(f"[red]Ошибка выбора каналов: {e}[/red]")
            self.logger.error(f"Channel selection error: {e}")
    
    def create_status_display(self) -> Layout:
        """Создание информативного статусного экрана с двумя панелями"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        # Заголовок
        header_text = Text("Telegram Channel Exporter", style="bold magenta")
        header_text.append(" | Статус: Работает", style="bold green")
        if self.stats.current_export_info:
            header_text.append(f" | {self.stats.current_export_info}", style="yellow")
        layout["header"].update(Panel(header_text, box=box.DOUBLE))
        
        # Главная область - разделена на левую и правую панели (2:1)
        layout["main"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        # Левая панель - оптимизированная таблица каналов с полным растягиванием
        channels_table = self._create_detailed_channels_table()
        layout["main"]["left"].update(Panel(channels_table, title="Мониторинг каналов", box=box.ROUNDED, expand=True))
        
        # Правая панель - детальная статистика
        stats_content = self._create_detailed_statistics()
        layout["main"]["right"].update(Panel(stats_content, title="Статистика", box=box.ROUNDED))
        
        # Добавляем информацию о подвале
        footer_content = self._create_footer_info()
        layout["footer"].update(Panel(footer_content, box=box.ROUNDED))
        
        return layout

    def _create_detailed_channels_table(self) -> Table:
        """Создает оптимизированную таблицу каналов для левой панели"""
        channels_table = Table(
            box=box.ROUNDED, 
            show_header=True, 
            header_style="bold white", 
            expand=True,
            min_width=60,  # Минимальная ширина
            collapse_padding=True  # Уменьшаем отступы для экономии места
        )
        channels_table.add_column("Канал", style="green", no_wrap=False, ratio=3)
        channels_table.add_column("Проверка", style="blue", no_wrap=True, ratio=2)
        channels_table.add_column("Сообщений", style="yellow", justify="right", no_wrap=True, ratio=1)
        channels_table.add_column("Статус", style="white", no_wrap=True, ratio=2)
        
        if not self.channels:
            channels_table.add_row(
                "[Каналы не выбраны]",
                "", "", ""
            )
            return channels_table
        
        # Определяем текущий экспортируемый канал
        current_export_channel_title = None
        if self.stats.current_export_info:
            # Извлекаем название канала из строки вида "Экспорт: Название канала"
            parts = self.stats.current_export_info.split(": ", 1)
            if len(parts) > 1:
                # Очищаем от дополнительной информации
                channel_part = parts[1].split(" | ")[0]  # Берем только название канала
                current_export_channel_title = channel_part.strip()
        
        # Находим индекс текущего канала
        current_channel_index = -1
        if current_export_channel_title:
            for i, channel in enumerate(self.channels):
                if channel.title == current_export_channel_title:
                    current_channel_index = i
                    break
        
        # Определяем диапазон отображения для автоматической прокрутки
        max_visible_channels = 25  # Увеличиваем для лучшего использования вертикального пространства
        start_index = 0
        
        if current_channel_index >= 0:
            # Центрируем текущий канал в списке
            half_window = max_visible_channels // 2
            start_index = max(0, current_channel_index - half_window)
            
            # Корректируем, чтобы не выходить за границы
            if start_index + max_visible_channels > len(self.channels):
                start_index = max(0, len(self.channels) - max_visible_channels)
        
        end_index = min(start_index + max_visible_channels, len(self.channels))
        display_channels = self.channels[start_index:end_index]
        
        for i, channel in enumerate(display_channels):
            actual_index = start_index + i
            last_check = channel.last_check or "Никогда"
            
            # Определяем статус канала
            status = "Ожидание"
            # Более компактное имя для лучшего использования пространства
            channel_name = channel.title
            if len(channel_name) > 35:  # Увеличиваем допустимую длину
                channel_name = channel_name[:32] + "..."
            
            # Подсвечиваем текущий экспортируемый канал
            if actual_index == current_channel_index:
                status = "[green]⚡ Экспорт[/green]"
                channel_name = f"[bold green]▶ {channel_name}[/bold green]"
            elif channel.last_check:
                status = "[blue]✓ Готов[/blue]"
            else:
                status = "[dim]⏳ Ожид.[/dim]"
            
            # Компактное форматирование даты
            if last_check != "Никогда":
                try:
                    dt = datetime.strptime(last_check, "%Y-%m-%d %H:%M:%S")
                    last_check = dt.strftime("%d.%m %H:%M")
                except:
                    last_check = last_check[:10] if len(last_check) > 10 else last_check
            else:
                last_check = "Никогда"
            
            # Форматирование количества сообщений (полное число без сокращений)
            msg_count = channel.total_messages
            msg_str = str(msg_count)
            
            channels_table.add_row(
                channel_name,
                last_check,
                msg_str,
                status
            )
        
        # Информация о позиции в списке
        if len(self.channels) > max_visible_channels:
            total_channels = len(self.channels)
            showing_range = f"{start_index + 1}-{end_index}"
            info_text = f"[dim]Показано {showing_range} из {total_channels} каналов[/dim]"
            
            if current_channel_index >= 0:
                info_text += f" | [green]Текущий: #{current_channel_index + 1}[/green]"
            
            channels_table.add_row(
                info_text,
                "", "", ""
            )
        
        return channels_table

    def _create_detailed_statistics(self) -> Text:
        """Создает детальную статистику для правой панели"""
        stats_text = Text()
        
        # Основная статистика
        stats_text.append("📊 Общая статистика\n\n", style="bold cyan")
        stats_text.append(f"Каналов: {self.stats.total_channels}\n", style="green")
        
        # Отображаем обнаруженные и экспортированные сообщения
        if self.stats.discovered_messages > 0:
            stats_text.append(f"Обнаружено сообщений: {self.stats.discovered_messages}\n", style="cyan")
            stats_text.append(f"Экспортировано: {self.stats.exported_messages}\n", style="yellow")
        else:
            stats_text.append(f"Сообщений: {self.stats.total_messages}\n", style="yellow")
        
        stats_text.append(f"Данных: {self.stats.total_size_mb:.1f} МБ\n", style="cyan")
        stats_text.append(f"Ошибок: {self.stats.export_errors}\n\n", style="red")
        
        # Статистика фильтрации
        if self.stats.filtered_messages > 0:
            stats_text.append("🔍 Фильтрация\n\n", style="bold magenta")
            stats_text.append(f"Отфильтровано: {self.stats.filtered_messages}\n\n", style="magenta")
        
        # Текущий экспорт
        if self.stats.current_export_info:
            stats_text.append("⚡ Текущий экспорт\n\n", style="bold green")
            
            # Извлекаем название канала без дополнительной информации
            export_info = self.stats.current_export_info
            if " | " in export_info:
                channel_name = export_info.split(" | ")[0]
            else:
                channel_name = export_info
            
            stats_text.append(f"{channel_name}\n", style="green")
            
            # Прогресс экспорта
            if self.stats.total_messages_in_channel > 0:
                stats_text.append(f"Сообщений в канале: {self.stats.total_messages_in_channel}\n", style="blue")
            
            # Скорость загрузки
            if self.stats.download_speed_files_per_sec > 0:
                stats_text.append(f"Скорость: {self.stats.download_speed_files_per_sec:.1f} ф/с\n", style="blue")
            
            if self.stats.download_speed_mb_per_sec > 0:
                stats_text.append(f"Скорость: {self.stats.download_speed_mb_per_sec:.1f} МБ/с\n", style="blue")
            
            # Осталось файлов - отображаем только если больше 0
            if self.stats.remaining_files_to_download > 0:
                stats_text.append(f"Осталось: {self.stats.remaining_files_to_download}\n", style="yellow")
            
            stats_text.append("\n")  # Добавляем пустую строку после блока
        
        # MD файл проверка и ре-экспорт
        if (self.stats.md_verification_status or 
            self.stats.md_verification_channel or 
            self.stats.md_verification_progress or 
            self.stats.md_reexport_count > 0):
            
            stats_text.append("📁 MD проверка\n\n", style="bold magenta")
            
            # Статус проверки
            if self.stats.md_verification_status:
                if "Ошибка" in self.stats.md_verification_status:
                    stats_text.append(f"Статус: {self.stats.md_verification_status}\n", style="red")
                elif "успешно" in self.stats.md_verification_status:
                    stats_text.append(f"Статус: {self.stats.md_verification_status}\n", style="green")
                else:
                    stats_text.append(f"Статус: {self.stats.md_verification_status}\n", style="yellow")
            
            # Текущий канал проверки
            if self.stats.md_verification_channel:
                stats_text.append(f"Канал: {self.stats.md_verification_channel}\n", style="cyan")
            
            # Прогресс проверки
            if self.stats.md_verification_progress:
                stats_text.append(f"Прогресс: {self.stats.md_verification_progress}\n", style="blue")
            
            # Количество повторных экспортов
            if self.stats.md_reexport_count > 0:
                stats_text.append(f"Повторные экспорты: {self.stats.md_reexport_count}\n", style="orange1")
            
            stats_text.append("\n")  # Добавляем пустую строку после блока
        
        # Последний экспорт
        if self.stats.last_export_time:
            stats_text.append("\n📅 Последний экспорт\n\n", style="bold blue")
            stats_text.append(f"{self.stats.last_export_time}\n", style="blue")
        
        return stats_text

    def _create_footer_info(self) -> Text:
        """Создает информацию для подвала"""
        footer_text = Text()
        
        # Информация о программе
        footer_text.append("🚀 Telegram Channel Exporter v1.2.0", style="bold green")
        footer_text.append(" | ", style="dim")
        footer_text.append("Нажмите Ctrl+C для выхода", style="yellow")
        
        # Информация о статусе
        if self.stats.current_export_info:
            footer_text.append(" | ", style="dim")
            footer_text.append("⚡ Экспорт активен", style="green")
        
        if self.stats.md_verification_status:
            footer_text.append(" | ", style="dim")
            footer_text.append("📁 Проверка MD", style="blue")
        
        return footer_text

    def _update_discovered_exported_stats(self):
        """Обновляет статистику обнаруженных и экспортированных сообщений"""
        try:
            discovered = 0
            exported = 0
            
            for channel in self.channels:
                # Обнаруженные сообщения = total_messages из метаданных канала
                discovered += channel.total_messages
                
                # Подсчитываем экспортированные сообщения из файлов экспорта
                try:
                    storage_cfg = self.config_manager.config.storage
                    base_dir = getattr(storage_cfg, 'export_base_dir', 'exports') or 'exports'
                except Exception:
                    base_dir = 'exports'
                
                base_path = Path(base_dir)
                sanitized_title = self._sanitize_channel_filename(channel.title)
                channel_dir = base_path / sanitized_title
                json_file = channel_dir / f"{sanitized_title}.json"
                
                if json_file.exists():
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            export_data = json.load(f)
                        
                        if isinstance(export_data, list):
                            exported += len(export_data)
                        elif isinstance(export_data, dict) and 'messages' in export_data:
                            exported += len(export_data['messages'])
                    except Exception as e:
                        self.logger.debug(f"Error reading export file for {channel.title}: {e}")
            
            # Обновляем статистику
            self.stats.discovered_messages = discovered
            self.stats.exported_messages = exported
            
        except Exception as e:
            self.logger.error(f"Error updating discovered/exported stats: {e}")
            # При ошибке сбрасываем статистику
            self.stats.discovered_messages = 0
            self.stats.exported_messages = 0
    
    def _verify_md_file_count(self, channel: ChannelInfo) -> tuple[bool, int, str]:
        """Проверяет количество сообщений в MD файле канала
        
        Args:
            channel: Информация о канале для проверки
            
        Returns:
            tuple[bool, int, str]: (Совпадает ли количество, фактическое количество сообщений в MD файле, тип несоответствия)
            Тип несоответствия: "missing" - файл отсутствует, "imbalance" - дисбаланс (>2 раза), "normal" - нормальное несоответствие
        """
        try:
            # Получаем путь к MD файлу
            try:
                storage_cfg = self.config_manager.config.storage
                base_dir = getattr(storage_cfg, 'export_base_dir', 'exports') or 'exports'
            except Exception:
                base_dir = 'exports'
            
            base_path = Path(base_dir)
            sanitized_title = self._sanitize_channel_filename(channel.title)
            channel_dir = base_path / sanitized_title
            md_file = channel_dir / f"{sanitized_title}.md"
            
            # Проверяем существование MD файла
            if not md_file.exists():
                self.logger.warning(f"MD файл не найден для канала {channel.title}")
                return False, 0, "missing"
            
            # Читаем MD файл и подсчитываем количество сообщений
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Используем регулярное выражение для поиска заголовков сообщений
                # Паттерн для поиска строк вида "## Сообщение #123" или "## Message #123"
                message_pattern = r'^## (?:Сообщение|Message) #\d+'
                messages_found = re.findall(message_pattern, content, re.MULTILINE)
                actual_count = len(messages_found)
                
                # Сравниваем с ожидаемым количеством
                expected_count = channel.total_messages
                
                # Проверяем дисбаланс - если в файле сообщений в 2 раза меньше чем в канале
                if expected_count > 0 and actual_count > 0 and expected_count / actual_count >= 2:
                    self.logger.warning(f"MD файл для {channel.title}: найдено {actual_count} сообщений, ожидалось {expected_count} - ДИСБАЛАНС")
                    return False, actual_count, "imbalance"
                
                # Нормальное несоответствие - файл есть, но количество сообщений не совпадает
                matches = (actual_count >= expected_count)  # Используем >= чтобы учесть возможные обновления
                
                if matches:
                    self.logger.info(f"MD файл для {channel.title}: найдено {actual_count} сообщений, ожидалось {expected_count} - ОК")
                else:
                    self.logger.warning(f"MD файл для {channel.title}: найдено {actual_count} сообщений, ожидалось {expected_count} - НЕСООТВЕТСТВИЕ")
                
                return matches, actual_count, "normal"
                
            except Exception as e:
                self.logger.error(f"Ошибка чтения MD файла для {channel.title}: {e}")
                return False, 0, "normal"
                
        except Exception as e:
            self.logger.error(f"Ошибка проверки MD файла для {channel.title}: {e}")
            return False, 0, "normal"

    async def _post_loading_menu(self):
        """Меню дополнительных действий после загрузки каналов"""
        self.console.print(Panel(
            "Каналы загружены и готовы к работе. Доступны дополнительные действия:\n"
            "- [i]config[/i] — настроить типы экспорта каналов\n"
            "- [i]start[/i] — запустить мониторинг (по умолчанию)",
            title="Дополнительные действия", box=box.ROUNDED
        ))
        
        action = Prompt.ask("Выберите действие", choices=["config", "start"], default="start")
        
        if action == "config":
            self.configure_export_types()
        # Для "start" продолжаем выполнение
    
    async def run_scheduler(self):
        """Запуск планировщика задач"""
        # Планируем ежедневную проверку в 6:00 по Московскому времени (MSK = UTC+3)
        # Schedule for 3:00 UTC which is 6:00 MSK
        schedule.every().day.at("03:00").do(lambda: asyncio.create_task(self._daily_check_new_messages()))
        
        while self.running:
            schedule.run_pending()
            await asyncio.sleep(60)  # Проверка каждую минуту
    
    def scroll_channels_up(self):
        """Прокрутка списка каналов вверх"""
        if self.channels_scroll_offset > 0:
            self.channels_scroll_offset = max(0, self.channels_scroll_offset - self.channels_display_limit)
    
    def scroll_channels_down(self):
        """Прокрутка списка каналов вниз"""
        max_offset = max(0, len(self.channels) - self.channels_display_limit)
        if self.channels_scroll_offset < max_offset:
            self.channels_scroll_offset = min(max_offset, self.channels_scroll_offset + self.channels_display_limit)
    
    def configure_export_types(self):
        """Настройка типов экспорта для каналов с дополнительными возможностями"""
        if not self.channels:
            self.console.print("[bright_red]Нет выбранных каналов[/bright_red]")
            input("Нажмите Enter для продолжения...")
            return
        
        self.console.clear()
        self.console.print(Panel(
            "Настройка экспорта",
            style="bold magenta"
        ))
        
        # Отображаем список каналов с текущими настройками
        table = Table(box=box.ROUNDED)
        table.add_column("№", style="cyan", width=4)
        table.add_column("Канал", style="green")
        table.add_column("Тип экспорта", style="yellow")
        
        export_type_names = {
            ExportType.BOTH: "Сообщения и файлы",
            ExportType.MESSAGES_ONLY: "Только сообщения",
            ExportType.FILES_ONLY: "Только файлы"
        }
        
        for i, channel in enumerate(self.channels, 1):
            table.add_row(
                str(i),
                channel.title[:40] + "..." if len(channel.title) > 40 else channel.title,
                export_type_names[channel.export_type]
            )
        
        self.console.print(table)
        
        self.console.print("\n[bright_blue]Команды:[/bright_blue]")
        self.console.print("1 - Изменить тип экспорта конкретного канала")
        self.console.print("2 - Установить одинаковый тип для всех каналов")
        self.console.print("3 - [новое] Переэкспортировать все каналы в Markdown")
        self.console.print("4 - [новое] Переэкспортировать конкретный канал в Markdown")
        self.console.print("q - Вернуться к главному экрану")
        
        choice = Prompt.ask("Выберите действие").strip().lower()
        
        if choice == "1":
            self._configure_single_channel_export_type()
        elif choice == "2":
            self._configure_all_channels_export_type()
        elif choice == "3":
            asyncio.create_task(self._reexport_all_channels_to_markdown())
        elif choice == "4":
            self._reexport_single_channel_to_markdown()
        elif choice == "q":
            return
        else:
            self.console.print("[bright_red]Неверная команда[/bright_red]")
            input("Нажмите Enter для продолжения...")
    
    def _configure_single_channel_export_type(self):
        """Настройка типа экспорта для одного канала"""
        try:
            channel_num = int(Prompt.ask("Введите номер канала")) - 1
            if 0 <= channel_num < len(self.channels):
                new_type = self._choose_export_type()
                if new_type:
                    self.channels[channel_num].export_type = new_type
                    self.save_channels()
                    self.console.print(f"[bright_green]Тип экспорта для канала '{self.channels[channel_num].title}' обновлен[/bright_green]")
            else:
                self.console.print("[bright_red]Неверный номер канала[/bright_red]")
        except ValueError:
            self.console.print("[bright_red]Неверный формат номера[/bright_red]")
        
        input("Нажмите Enter для продолжения...")
    
    def _configure_all_channels_export_type(self):
        """Настройка одинакового типа экспорта для всех каналов"""
        new_type = self._choose_export_type()
        if new_type:
            for channel in self.channels:
                channel.export_type = new_type
            self.save_channels()
            self.console.print("[bright_green]Тип экспорта обновлен для всех каналов[/bright_green]")
        
        input("Нажмите Enter для продолжения...")
    
    def _choose_export_type(self) -> Optional[ExportType]:
        """Выбор типа экспорта"""
        self.console.print("\nВыберите тип экспорта:")
        self.console.print("1 - Сообщения и файлы (по умолчанию)")
        self.console.print("2 - Только сообщения (без загрузки файлов)")
        self.console.print("3 - Только файлы (без текста сообщений)")
        
        choice = Prompt.ask("Ваш выбор").strip()
        
        if choice == "1":
            return ExportType.BOTH
        elif choice == "2":
            return ExportType.MESSAGES_ONLY
        elif choice == "3":
            return ExportType.FILES_ONLY
        else:
            self.console.print("[bright_red]Неверный выбор[/bright_red]")
            return None
    
    async def _reexport_all_channels_to_markdown(self):
        """Переэкспорт всех каналов в Markdown формат"""
        if not Confirm.ask("Переэкспортировать все каналы в Markdown с перезаписью файлов?", default=False):
            return
            
        self.console.print("[green]Запуск переэкспорта всех каналов...[/green]")
        
        success_count = 0
        error_count = 0
        
        for i, channel in enumerate(self.channels, 1):
            try:
                self.console.print(f"[blue]Переэкспорт {i}/{len(self.channels)}: {channel.title}[/blue]")
                await self._reexport_channel_to_markdown(channel)
                success_count += 1
                self.console.print(f"[green]✓ Завершен: {channel.title}[/green]")
            except Exception as e:
                error_count += 1
                self.logger.error(f"Error reexporting {channel.title} to Markdown: {e}")
                self.console.print(f"[red]✗ Ошибка: {channel.title} - {e}[/red]")
        
        self.console.print(f"\n[bold green]Переэкспорт завершен![/bold green]")
        self.console.print(f"Успешно: {success_count}, Ошибок: {error_count}")
        
        # Отправляем уведомление
        notification = f"📝 Переэкспорт в Markdown завершен\n✓ Успешно: {success_count}\n✗ Ошибок: {error_count}"
        await self.send_notification(notification)
        
        input("Нажмите Enter для продолжения...")
    
    def _reexport_single_channel_to_markdown(self):
        """Переэкспорт конкретного канала в Markdown формат"""
        try:
            channel_num = int(Prompt.ask("Введите номер канала")) - 1
            if 0 <= channel_num < len(self.channels):
                channel = self.channels[channel_num]
                if Confirm.ask(f"Переэкспортировать '{channel.title}' в Markdown с перезаписью файла?", default=False):
                    self.console.print(f"[green]Запуск переэкспорта: {channel.title}[/green]")
                    asyncio.create_task(self._reexport_channel_to_markdown(channel))
                    self.console.print(f"[green]✓ Переэкспорт запущен: {channel.title}[/green]")
            else:
                self.console.print("[bright_red]Неверный номер канала[/bright_red]")
        except ValueError:
            self.console.print("[bright_red]Неверный формат номера[/bright_red]")
        
        input("Нажмите Enter для продолжения...")
    
    async def _reexport_channel_to_markdown(self, channel: ChannelInfo):
        """Переэкспорт конкретного канала в Markdown"""
        try:
            # Получаем путь к директории канала
            try:
                storage_cfg = self.config_manager.config.storage
                base_dir = getattr(storage_cfg, 'export_base_dir', 'exports') or 'exports'
            except Exception:
                base_dir = 'exports'
            
            base_path = Path(base_dir)
            sanitized_title = self._sanitize_channel_filename(channel.title)
            channel_dir = base_path / sanitized_title
            
            # Получаем все сообщения из Telegram API заново
            self.console.print(f"[blue]Получение сообщений из Telegram для {channel.title}...[/blue]")
            
            try:
                # Получаем Telegram entity
                entity = await self.client.get_entity(channel.id)
                
                # Получаем все сообщения канала
                messages = []
                message_count = 0
                
                async for message in self.client.iter_messages(entity, limit=None):
                    # Фильтруем контент
                    if self.content_filter.should_filter_message(message.text or ""):
                        continue
                        
                    # Обрабатываем медиафайлы
                    media_type = None
                    media_path = None
                    
                    if message.media:
                        if isinstance(message.media, MessageMediaPhoto):
                            media_type = "photo"
                        elif isinstance(message.media, MessageMediaDocument):
                            if message.document:
                                if message.document.mime_type and message.document.mime_type.startswith('image/'):
                                    media_type = "photo"
                                elif message.document.mime_type and message.document.mime_type.startswith('video/'):
                                    media_type = "video"
                                else:
                                    media_type = "document"
                    
                    # Создаем MessageData
                    msg_data = MessageData(
                        id=message.id,
                        date=message.date,
                        text=message.text or "",
                        author=getattr(message.sender, 'username', None) if message.sender else None,
                        media_type=media_type,
                        media_path=media_path,
                        views=getattr(message, 'views', 0) or 0,
                        forwards=getattr(message, 'forwards', 0) or 0,
                        replies=getattr(message, 'replies', {}).get('replies', 0) if hasattr(message, 'replies') and message.replies else 0,
                        edited=message.edit_date
                    )
                    messages.append(msg_data)
                    message_count += 1
                    
                    # Показываем прогресс каждые 100 сообщений
                    if message_count % 100 == 0:
                        self.console.print(f"[green]Обработано {message_count} сообщений...[/green]")
                
                self.console.print(f"[green]Получено {len(messages)} сообщений для реэкспорта[/green]")
                
                if not messages:
                    raise ValueError(f"Не найдено сообщений для реэкспорта канала {channel.title}")
                
                # Сортируем сообщения по ID (старые сначала)
                messages.sort(key=lambda x: x.id)
                
                # Создаем Markdown экспортер и перезаписываем файл
                md_exporter = MarkdownExporter(channel.title, channel_dir)
                md_file = md_exporter.export_messages(messages, append_mode=False)  # append_mode=False для перезаписи
                
                if md_file and Path(md_file).exists():
                    self.logger.info(f"Successfully reexported {channel.title} to Markdown: {md_file}")
                    self.console.print(f"[green]✓ Переэкспорт в Markdown завершен: {md_file}[/green]")
                else:
                    raise RuntimeError(f"Не удалось создать Markdown файл для {channel.title}")
                    
            except Exception as e:
                self.logger.error(f"Error getting messages from Telegram for {channel.title}: {e}")
                raise
            
        except Exception as e:
            self.logger.error(f"Error reexporting {channel.title} to Markdown: {e}")
            raise
    
    async def _handle_reexport_channels(self):
        """Обработка переэкспорта сообщений каналов с перезаписью"""
        if not self.channels:
            self.console.print("[yellow]Каналы не выбраны. Необходимо сначала выбрать каналы для экспорта.[/yellow]")
            return
        
        self.console.clear()
        self.console.print(Panel(
            "Переэкспорт сообщений каналов",
            style="bold magenta"
        ))
        
        # Отображаем список каналов
        table = Table(box=box.ROUNDED)
        table.add_column("№", style="cyan", width=4)
        table.add_column("Канал", style="green")
        table.add_column("Сообщений", style="yellow", justify="right")
        
        for i, channel in enumerate(self.channels, 1):
            table.add_row(
                str(i),
                channel.title[:50] + "..." if len(channel.title) > 50 else channel.title,
                str(channel.total_messages)
            )
        
        self.console.print(table)
        
        self.console.print("\n[bright_blue]Варианты переэкспорта:[/bright_blue]")
        self.console.print("1 - Переэкспортировать все каналы в все форматы")
        self.console.print("2 - Переэкспортировать конкретный канал в все форматы")
        self.console.print("3 - Переэкспортировать все каналы только в Markdown")
        self.console.print("4 - Переэкспортировать конкретный канал только в Markdown")
        self.console.print("q - Вернуться к главному меню")
        
        choice = Prompt.ask("Выберите действие").strip().lower()
        
        if choice == "1":
            await self._reexport_all_channels_all_formats()
        elif choice == "2":
            await self._reexport_single_channel_all_formats()
        elif choice == "3":
            await self._reexport_all_channels_to_markdown()
        elif choice == "4":
            await self._reexport_single_channel_to_markdown_from_menu()
        elif choice == "q":
            return
        else:
            self.console.print("[bright_red]Неверная команда[/bright_red]")
            input("Нажмите Enter для продолжения...")
    
    async def _reexport_all_channels_all_formats(self):
        """Переэкспорт всех каналов во все форматы"""
        if not Confirm.ask("Переэкспортировать все каналы в JSON, HTML и Markdown с перезаписью файлов?", default=False):
            return
            
        self.console.print("[green]Запуск полного переэкспорта всех каналов...[/green]")
        
        success_count = 0
        error_count = 0
        
        for i, channel in enumerate(self.channels, 1):
            try:
                self.console.print(f"[blue]Переэкспорт {i}/{len(self.channels)}: {channel.title}[/blue]")
                await self._reexport_channel_to_all_formats(channel)
                success_count += 1
                self.console.print(f"[green]✓ Завершен: {channel.title}[/green]")
            except Exception as e:
                error_count += 1
                self.logger.error(f"Error reexporting {channel.title} to all formats: {e}")
                self.console.print(f"[red]✗ Ошибка: {channel.title} - {e}[/red]")
        
        self.console.print(f"\n[bold green]Полный переэкспорт завершен![/bold green]")
        self.console.print(f"Успешно: {success_count}, Ошибок: {error_count}")
        
        # Отправляем уведомление
        notification = f"📋 Полный переэкспорт в все форматы завершен\n✓ Успешно: {success_count}\n✗ Ошибок: {error_count}"
        await self.send_notification(notification)
        
        input("Нажмите Enter для продолжения...")
    
    async def _reexport_single_channel_all_formats(self):
        """Переэкспорт конкретного канала во все форматы"""
        try:
            channel_num = int(Prompt.ask("Введите номер канала")) - 1
            if 0 <= channel_num < len(self.channels):
                channel = self.channels[channel_num]
                if Confirm.ask(f"Переэкспортировать '{channel.title}' в JSON, HTML и Markdown с перезаписью файлов?", default=False):
                    self.console.print(f"[green]Запуск полного переэкспорта: {channel.title}[/green]")
                    await self._reexport_channel_to_all_formats(channel)
                    self.console.print(f"[green]✓ Полный переэкспорт завершен: {channel.title}[/green]")
            else:
                self.console.print("[bright_red]Неверный номер канала[/bright_red]")
        except ValueError:
            self.console.print("[bright_red]Неверный формат номера[/bright_red]")
        
        input("Нажмите Enter для продолжения...")
    
    async def _reexport_single_channel_to_markdown_from_menu(self):
        """Переэкспорт конкретного канала в Markdown формат из меню"""
        try:
            channel_num = int(Prompt.ask("Введите номер канала")) - 1
            if 0 <= channel_num < len(self.channels):
                channel = self.channels[channel_num]
                if Confirm.ask(f"Переэкспортировать '{channel.title}' в Markdown с перезаписью файла?", default=False):
                    self.console.print(f"[green]Запуск переэкспорта: {channel.title}[/green]")
                    await self._reexport_channel_to_markdown(channel)
                    self.console.print(f"[green]✓ Переэкспорт завершен: {channel.title}[/green]")
            else:
                self.console.print("[bright_red]Неверный номер канала[/bright_red]")
        except ValueError:
            self.console.print("[bright_red]Неверный формат номера[/bright_red]")
        
        input("Нажмите Enter для продолжения...")
    
    async def _reexport_channel_to_all_formats(self, channel: ChannelInfo):
        """Переэкспорт конкретного канала во все форматы"""
        try:
            # Получаем путь к директории канала
            try:
                storage_cfg = self.config_manager.config.storage
                base_dir = getattr(storage_cfg, 'export_base_dir', 'exports') or 'exports'
            except Exception:
                base_dir = 'exports'
            
            base_path = Path(base_dir)
            sanitized_title = self._sanitize_channel_filename(channel.title)
            channel_dir = base_path / sanitized_title
            
            # Получаем все сообщения из Telegram API заново
            self.console.print(f"[blue]Получение сообщений из Telegram для {channel.title}...[/blue]")
            
            try:
                # Получаем Telegram entity
                entity = await self.client.get_entity(channel.id)
                
                # Получаем все сообщения канала
                messages = []
                message_count = 0
                
                async for message in self.client.iter_messages(entity, limit=None):
                    # Фильтруем контент
                    if self.content_filter.should_filter_message(message.text or ""):
                        continue
                        
                    # Обрабатываем медиафайлы
                    media_type = None
                    media_path = None
                    
                    if message.media:
                        if isinstance(message.media, MessageMediaPhoto):
                            media_type = "photo"
                        elif isinstance(message.media, MessageMediaDocument):
                            if message.document:
                                if message.document.mime_type and message.document.mime_type.startswith('image/'):
                                    media_type = "photo"
                                elif message.document.mime_type and message.document.mime_type.startswith('video/'):
                                    media_type = "video"
                                else:
                                    media_type = "document"
                    
                    # Создаем MessageData
                    msg_data = MessageData(
                        id=message.id,
                        date=message.date,
                        text=message.text or "",
                        author=getattr(message.sender, 'username', None) if message.sender else None,
                        media_type=media_type,
                        media_path=media_path,
                        views=getattr(message, 'views', 0) or 0,
                        forwards=getattr(message, 'forwards', 0) or 0,
                        replies=getattr(message, 'replies', {}).get('replies', 0) if hasattr(message, 'replies') and message.replies else 0,
                        edited=message.edit_date
                    )
                    messages.append(msg_data)
                    message_count += 1
                    
                    # Показываем прогресс каждые 100 сообщений
                    if message_count % 100 == 0:
                        self.console.print(f"[green]Обработано {message_count} сообщений...[/green]")
                
                self.console.print(f"[green]Получено {len(messages)} сообщений для реэкспорта[/green]")
                
                if not messages:
                    raise ValueError(f"Не найдено сообщений для реэкспорта канала {channel.title}")
                
                # Сортируем сообщения по ID (старые сначала)
                messages.sort(key=lambda x: x.id)
                
                # Экспортируем в JSON (перезаписываем)
                json_exporter = JSONExporter(channel.title, channel_dir)
                json_file = json_exporter.export_messages(messages, append_mode=False)
                
                # Экспортируем в HTML (перезаписываем)
                html_exporter = HTMLExporter(channel.title, channel_dir)
                html_file = html_exporter.export_messages(messages, append_mode=False)
                
                # Экспортируем в Markdown (перезаписываем)
                md_exporter = MarkdownExporter(channel.title, channel_dir)
                md_file = md_exporter.export_messages(messages, append_mode=False)
                
                # Проверяем успешность экспорта
                files_created = []
                if json_file and Path(json_file).exists():
                    files_created.append("JSON")
                if html_file and Path(html_file).exists():
                    files_created.append("HTML")
                if md_file and Path(md_file).exists():
                    files_created.append("Markdown")
                
                if files_created:
                    self.logger.info(f"Successfully reexported {channel.title} to formats: {', '.join(files_created)}")
                    self.console.print(f"[green]✓ Переэкспорт завершен: {', '.join(files_created)}[/green]")
                else:
                    raise RuntimeError(f"Не удалось создать файлы экспорта для {channel.title}")
                    
            except Exception as e:
                self.logger.error(f"Error getting messages from Telegram for {channel.title}: {e}")
                raise
            
        except Exception as e:
            self.logger.error(f"Error reexporting {channel.title} to all formats: {e}")
            raise



    async def _daily_check_new_messages(self):
        """Ежедневная проверка новых сообщений в 6:00 по Московскому времени"""
        try:
            self.logger.info("Запуск ежедневной проверки новых сообщений")
            
            # Отправляем уведомление о начале проверки
            await self.send_notification("🕒 Запуск ежедневной проверки новых сообщений...")
            
            # Словарь для хранения информации о новых сообщениях по каналам
            new_messages_summary = {}
            total_new_messages = 0
            
            # Проверяем каждый канал на наличие новых сообщений
            for channel in self.channels:
                try:
                    new_count = await self._check_and_append_new_messages(channel)
                    if new_count > 0:
                        new_messages_summary[channel.title] = new_count
                        total_new_messages += new_count
                        self.logger.info(f"Найдено {new_count} новых сообщений в канале {channel.title}")
                except Exception as e:
                    self.logger.error(f"Ошибка проверки канала {channel.title}: {e}")
                    continue
            
            # Отправляем сводное уведомление
            if total_new_messages > 0:
                summary_text = self._create_daily_summary_notification(new_messages_summary, total_new_messages)
                await self.send_notification(summary_text)
                self.logger.info(f"Ежедневная проверка завершена. Найдено {total_new_messages} новых сообщений.")
            else:
                await self.send_notification("✅ Ежедневная проверка завершена. Новых сообщений не найдено.")
                self.logger.info("Ежедневная проверка завершена. Новых сообщений не найдено.")
                
        except Exception as e:
            self.logger.error(f"Ошибка ежедневной проверки: {e}")
            await self.send_notification(f"❌ Ошибка ежедневной проверки: {str(e)}")

    async def _check_and_append_new_messages(self, channel: ChannelInfo) -> int:
        """Проверка и добавление новых сообщений в существующий MD файл"""
        try:
            self.logger.info(f"Проверка новых сообщений для канала: {channel.title}")
            
            # Получаем путь к директории канала
            try:
                storage_cfg = self.config_manager.config.storage
                base_dir = getattr(storage_cfg, 'export_base_dir', 'exports') or 'exports'
            except Exception:
                base_dir = 'exports'
            
            base_path = Path(base_dir)
            sanitized_title = self._sanitize_channel_filename(channel.title)
            channel_dir = base_path / sanitized_title
            
            # Создаем директорию если не существует
            channel_dir.mkdir(exist_ok=True)
            
            # Получаем канал
            entity = await self.client.get_entity(channel.id)
            
            # Получаем новые сообщения (начиная с последнего обработанного ID)
            new_messages = []
            min_id = channel.last_message_id
            
            self.logger.info(f"Поиск сообщений в канале {channel.title} после ID {min_id}")
            
            # Получаем только новые сообщения
            async for message in self.client.iter_messages(entity, min_id=min_id):
                try:
                    # Фильтрация рекламных и промо-сообщений
                    should_filter, filter_reason = self.content_filter.should_filter_message(message.text or "")
                    if should_filter:
                        self.logger.info(f"Сообщение {message.id} отфильтровано: {filter_reason}")
                        continue

                    # Обрабатываем медиафайлы
                    media_type = None
                    if message.media:
                        if isinstance(message.media, MessageMediaPhoto):
                            media_type = "photo"
                        elif isinstance(message.media, MessageMediaDocument):
                            if message.document:
                                if message.document.mime_type and message.document.mime_type.startswith('image/'):
                                    media_type = "photo"
                                elif message.document.mime_type and message.document.mime_type.startswith('video/'):
                                    media_type = "video"
                                else:
                                    media_type = "document"
                    
                    # Создание объекта данных сообщения
                    replies_count = 0
                    if hasattr(message, 'replies') and message.replies:
                        if hasattr(message.replies, 'replies'):
                            replies_count = message.replies.replies
                        elif hasattr(message.replies, 'replies_pts'):
                            replies_count = getattr(message.replies, 'replies_pts', 0)
                    
                    msg_data = MessageData(
                        id=message.id,
                        date=message.date,
                        text=message.text or "",
                        author=None,
                        media_type=media_type,
                        media_path=None,  # Путь будет установлен при загрузке медиа
                        views=getattr(message, 'views', 0) or 0,
                        forwards=getattr(message, 'forwards', 0) or 0,
                        replies=replies_count,
                        edited=message.edit_date
                    )
                    
                    new_messages.append(msg_data)
                    
                    # Обновляем последний ID сообщения
                    if message.id > channel.last_message_id:
                        channel.last_message_id = message.id
                        
                except Exception as e:
                    self.logger.error(f"Ошибка обработки сообщения {message.id}: {e}")
                    continue
            
            # Если есть новые сообщения, добавляем их в существующий MD файл
            if new_messages:
                self.logger.info(f"Найдено {len(new_messages)} новых сообщений для канала {channel.title}")
                
                # Сортируем сообщения по ID (старые сначала)
                new_messages.sort(key=lambda x: x.id)
                
                # Создаем Markdown экспортер и добавляем новые сообщения в существующий файл
                md_exporter = MarkdownExporter(channel.title, channel_dir)
                md_file = md_exporter.export_messages(new_messages, append_mode=True)
                
                if md_file and Path(md_file).exists():
                    self.logger.info(f"Успешно добавлено {len(new_messages)} сообщений в MD файл для канала {channel.title}")
                    
                    # Обновляем статистику канала
                    channel.total_messages += len(new_messages)
                    channel.last_check = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Сохраняем обновленную информацию о каналах
                    self.save_channels()
                    
                    return len(new_messages)
                else:
                    self.logger.error(f"Не удалось добавить сообщения в MD файл для канала {channel.title}")
                    return 0
            else:
                self.logger.info(f"Нет новых сообщений для канала {channel.title}")
                # Обновляем время последней проверки
                channel.last_check = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.save_channels()
                return 0
                
        except Exception as e:
            self.logger.error(f"Ошибка проверки и добавления сообщений для канала {channel.title}: {e}")
            return 0

    def _create_daily_summary_notification(self, new_messages_summary: Dict[str, int], total_new_messages: int) -> str:
        """Создание текста сводного уведомления о новых сообщениях"""
        if not new_messages_summary:
            return "✅ Ежедневная проверка завершена. Новых сообщений не найдено."
        
        # Формируем список каналов с новыми сообщениями
        channels_list = []
        for channel_title, count in new_messages_summary.items():
            channels_list.append(f"🔗 {channel_title}: {count} новых сообщений")
        
        channels_text = "\n".join(channels_list)
        
        return f"""
📢 <b>Ежедневная проверка новых сообщений завершена</b>

📊 <b>Всего новых сообщений:</b> {total_new_messages}
📅 <b>Время проверки:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{channels_text}

📁 Новые сообщения добавлены в соответствующие MD файлы
        """.strip()
    
    async def export_channel(self, channel: ChannelInfo):
        """Экспорт конкретного канала"""
        try:
            self.logger.info(f"Starting export for channel: {channel.title}")
            
            # Обнуляем счетчик повторных экспортов MD перед новым экспортом
            if not hasattr(channel, '_force_full_reexport') or not channel._force_full_reexport:
                # Сбрасываем счетчик только для новых экспортов (не для ре-экспортов)
                self.stats.md_reexport_count = 0
            
            # Обновляем информацию о текущем экспорте
            self.stats.current_export_info = f"Экспорт: {channel.title}"
            
            # Создание директории для канала (учет базового каталога из настроек)
            try:
                storage_cfg = self.config_manager.config.storage  # type: ignore[attr-defined]
                base_dir = getattr(storage_cfg, 'export_base_dir', 'exports') or 'exports'
            except Exception:
                base_dir = 'exports'
            base_path = Path(base_dir)
            base_path.mkdir(parents=True, exist_ok=True)
            sanitized_title = self._sanitize_channel_filename(channel.title)
            channel_dir = base_path / sanitized_title
            channel_dir.mkdir(exist_ok=True)
            
            # Получение канала
            entity = await self.client.get_entity(channel.id)
            
            # Проверяем наличие MD файла для принятия решения о режиме экспорта
            md_file_path = channel_dir / f"{sanitized_title}.md"
            md_file_missing = not md_file_path.exists()
            
            if md_file_missing:
                self.logger.info(f"MD файл отсутствует для канала {channel.title}, запуск полного ре-экспорта с пересчетом сообщений")
                # Игнорируем кэшированные параметры и принудительно пересчитываем
                channel.last_message_id = 0
                channel.total_messages = 0
                # Отмечаем для принудительного полного экспорта
                channel._force_full_reexport = True
                # Обновляем статистику
                self.stats.md_verification_status = "Обнаружен отсутствующий MD файл"
                self.stats.md_verification_channel = channel.title
                self.stats.md_verification_progress = "Подготовка к полному ре-экспорту"
            
            # Получаем информацию о канале эффективно без полного подсчета сообщений
            total_messages_in_channel = 0
            try:
                # При принудительном полном ре-экспорте или отсутствии MD файла получаем реальное количество сообщений
                if md_file_missing or (hasattr(channel, '_force_full_reexport') and channel._force_full_reexport):
                    if md_file_missing:
                        self.logger.info(f"Отсутствует MD файл: подсчитываем реальное количество сообщений в {channel.title}")
                        self.stats.md_verification_progress = f"Подсчет сообщений в {channel.title}"
                    else:
                        self.logger.info(f"Принудительный полный ре-экспорт: подсчитываем реальное количество сообщений в {channel.title}")
                    
                    # Получаем первое и последнее сообщения
                    first_msg = await self.client.get_messages(entity, limit=1, reverse=True)
                    last_msg = await self.client.get_messages(entity, limit=1)
                    if first_msg and last_msg and len(first_msg) > 0 and len(last_msg) > 0:
                        # Получаем точное количество сообщений через подсчет
                        message_count = 0
                        messages_to_export = []  # Сохраняем сообщения для последующей обработки
                        async for message in self.client.iter_messages(entity):
                            message_count += 1
                            messages_to_export.append(message)
                            if message_count % 1000 == 0:
                                if md_file_missing:
                                    self.stats.md_verification_progress = f"Подсчитано {message_count} сообщений в {channel.title}..."
                                self.logger.info(f"Подсчитано {message_count} сообщений в {channel.title}...")
                        total_messages_in_channel = message_count
                        self.logger.info(f"Реальное количество сообщений в {channel.title}: {total_messages_in_channel}")
                        # Обновляем кэшированное значение - только при отсутствии MD файла или принудительном реэкспорте
                        if md_file_missing or (hasattr(channel, '_force_full_reexport') and channel._force_full_reexport):
                            channel.total_messages = total_messages_in_channel
                        
                        if md_file_missing:
                            self.stats.md_verification_progress = f"Обнаружено {total_messages_in_channel} сообщений, начало экспорта"
                    else:
                        self.logger.warning(f"Channel {channel.title}: Не удалось получить сообщения для подсчета")
                        total_messages_in_channel = 0
                else:
                    # Обычный режим - пытаемся получить примерную оценку количества сообщений
                    first_msg = await self.client.get_messages(entity, limit=1)
                    last_msg = await self.client.get_messages(entity, limit=1, reverse=True)
                    if first_msg and last_msg:
                        # Оценка количества сообщений по диапазону ID (не идеально, но быстро)
                        total_messages_in_channel = max(1, last_msg[0].id - first_msg[0].id + 1)
                        self.logger.info(f"Channel {channel.title}: Estimated {total_messages_in_channel} messages (ID range: {first_msg[0].id}-{last_msg[0].id})")
                        self.logger.info(f"Channel {channel.title}: Current last_message_id: {channel.last_message_id}")
                    else:
                        self.logger.warning(f"Channel {channel.title}: Could not get message range")
            except Exception as e:
                self.logger.warning(f"Could not get channel info for {channel.title}: {e}")
                total_messages_in_channel = 0
            
            self.stats.total_messages_in_channel = total_messages_in_channel
            
            # Инициализация экспортеров
            json_exporter = JSONExporter(channel.title, channel_dir)
            html_exporter = HTMLExporter(channel.title, channel_dir)
            md_exporter = MarkdownExporter(channel.title, channel_dir)
            
            # Получаем настройки для загрузки медиа из конфигурации
            try:
                storage_cfg = self.config_manager.config.storage  # type: ignore[attr-defined]
                media_threads = getattr(storage_cfg, 'media_download_threads', 4) or 4
                adaptive_download = getattr(storage_cfg, 'adaptive_download', True)
                min_delay = getattr(storage_cfg, 'min_download_delay', 0.1)
                max_delay = getattr(storage_cfg, 'max_download_delay', 3.0)
            except Exception:
                media_threads = 4
                adaptive_download = True
                min_delay = 0.1
                max_delay = 3.0
            
            media_downloader = MediaDownloader(channel_dir, max_workers=media_threads)
            # Колбэк прогресса для обновления статистики в реальном времени
            def _on_progress(progress: Dict[str, float]):
                try:
                    self.stats.download_speed_files_per_sec = float(progress.get('files_per_sec', 0.0))
                    self.stats.download_speed_mb_per_sec = float(progress.get('mb_per_sec', 0.0))
                    self.stats.remaining_files_to_download = int(progress.get('remaining', 0))
                    # Убираем строку, которая дописывала информацию - 
                    # это уже обрабатывается в _create_detailed_statistics с правильным форматированием
                except Exception:
                    pass
            media_downloader.progress_callback = _on_progress
            
            # Применяем дополнительные настройки если включена адаптивная загрузка
            if adaptive_download:
                media_downloader.min_delay = min_delay
                media_downloader.max_delay = max_delay

            # Получение сообщений
            messages_data = []
            total_size = 0.0
            new_messages_count = 0
            
            # Инициализируем счетчик отфильтрованных сообщений для текущей сессии экспорта
            session_filtered_count = 0
            
            # Получаем сообщения начиная с последнего обработанного
            min_id = channel.last_message_id
            messages_to_process = None  # Для хранения сообщений при полном реэкспорте
            
            # Если last_message_id = 0, значит это первая проверка канала - экспортируем все сообщения
            if min_id == 0:
                self.logger.info(f"First time export for channel {channel.title} - will export all {total_messages_in_channel} messages")
                # При полном реэкспорте используем уже собранные сообщения
                if 'messages_to_export' in locals():
                    messages_to_process = messages_to_export
                    min_id = None  # Помечаем что используем предварительно собранные сообщения
                else:
                    min_id = None  # None означает "с самого начала"
            else:
                self.logger.info(f"Exporting new messages for channel {channel.title} starting from message ID {min_id}")
            
            try:
                # Используем правильный параметр для получения сообщений
                if min_id is None:
                    # При полном реэкспорте используем уже собранные сообщения
                    if messages_to_process is not None:
                        self.logger.info(f"Processing {len(messages_to_process)} pre-collected messages for full re-export")
                        for message in messages_to_process:
                            try:
                                # Обновляем прогресс экспорта
                                self.stats.current_export_info = f"Экспорт: {channel.title} | Обработано {len(messages_data)} из {total_messages_in_channel}"
                                
                                # Фильтрация рекламных и промо-сообщений
                                should_filter, filter_reason = self.content_filter.should_filter_message(message.text or "")
                                if should_filter:
                                    self.logger.info(f"Message {message.id} filtered: {filter_reason}")
                                    session_filtered_count += 1
                                    continue

                                # Загрузка медиафайлов
                                media_path = None
                                media_type = None
                                
                                if message.media:
                                    # Добавляем в очередь загрузки вместо немедленной загрузки
                                    media_path = media_downloader.add_to_download_queue(self.client, message)
                                    
                                    # Определение типа медиа
                                    if isinstance(message.media, MessageMediaPhoto):
                                        media_type = "Фото"
                                    elif isinstance(message.media, MessageMediaDocument):
                                        media_type = "Документ"
                                    else:
                                        media_type = "Другое медиа"
                                
                                # Создание объекта данных сообщения
                                # Безопасное получение количества ответов
                                replies_count = 0
                                if hasattr(message, 'replies') and message.replies:
                                    if hasattr(message.replies, 'replies'):
                                        replies_count = message.replies.replies
                                    elif hasattr(message.replies, 'replies_pts'):
                                        replies_count = getattr(message.replies, 'replies_pts', 0)
                                
                                msg_data = MessageData(
                                    id=message.id,
                                    date=message.date,
                                    text=message.text or "",
                                    author=None,  # Каналы обычно не показывают авторов
                                    media_type=media_type,
                                    media_path=media_path,
                                    views=getattr(message, 'views', 0) or 0,
                                    forwards=getattr(message, 'forwards', 0) or 0,
                                    replies=replies_count,
                                    edited=message.edit_date
                                )
                                
                                messages_data.append(msg_data)
                                new_messages_count += 1
                                
                                # Обновляем последний ID сообщения
                                if message.id > channel.last_message_id:
                                    channel.last_message_id = message.id
                                    
                            except Exception as e:
                                self.logger.error(f"Error processing message {message.id}: {e}")
                                self.stats.export_errors += 1
                else:
                    # Получаем только новые сообщения
                    async for message in self.client.iter_messages(entity, min_id=min_id):
                        try:
                            # Обновляем прогресс экспорта
                            self.stats.current_export_info = f"Экспорт: {channel.title} | Обработано {len(messages_data)} из {total_messages_in_channel}"
                            
                            # Фильтрация рекламных и промо-сообщений
                            should_filter, filter_reason = self.content_filter.should_filter_message(message.text or "")
                            if should_filter:
                                self.logger.info(f"Message {message.id} filtered: {filter_reason}")
                                session_filtered_count += 1
                                continue

                            # Загрузка медиафайлов
                            media_path = None
                            media_type = None
                            
                            if message.media:
                                # Добавляем в очередь загрузки вместо немедленной загрузки
                                media_path = media_downloader.add_to_download_queue(self.client, message)
                                
                                # Определение типа медиа
                                if isinstance(message.media, MessageMediaPhoto):
                                    media_type = "Фото"
                                elif isinstance(message.media, MessageMediaDocument):
                                    media_type = "Документ"
                                else:
                                    media_type = "Другое медиа"
                            
                            # Создание объекта данных сообщения
                            # Безопасное получение количества ответов
                            replies_count = 0
                            if hasattr(message, 'replies') and message.replies:
                                if hasattr(message.replies, 'replies'):
                                    replies_count = message.replies.replies
                                elif hasattr(message.replies, 'replies_pts'):
                                    replies_count = getattr(message.replies, 'replies_pts', 0)
                            
                            msg_data = MessageData(
                                id=message.id,
                                date=message.date,
                                text=message.text or "",
                                author=None,  # Каналы обычно не показывают авторов
                                media_type=media_type,
                                media_path=media_path,
                                views=getattr(message, 'views', 0) or 0,
                                forwards=getattr(message, 'forwards', 0) or 0,
                                replies=replies_count,
                                edited=message.edit_date
                            )
                            
                            messages_data.append(msg_data)
                            new_messages_count += 1
                            
                            # Обновляем последний ID сообщения
                            if message.id > channel.last_message_id:
                                channel.last_message_id = message.id
                                
                        except Exception as e:
                            self.logger.error(f"Error processing message {message.id}: {e}")
                            self.stats.export_errors += 1
            
            except FloodWaitError as e:
                # Используем итеративный подход вместо рекурсии
                retry_count = getattr(self, '_floodwait_retry_count', 0)
                max_retries = 3
                
                if retry_count >= max_retries:
                    self.logger.error(f"Максимум попыток ({max_retries}) превышен для канала {channel.title}")
                    self.stats.export_errors += 1
                    return
                    
                wait_time = min(e.seconds, 300)  # Максимум 5 минут ожидания
                self.logger.warning(f"FloodWait {wait_time}s для {channel.title}, попытка {retry_count + 1}/{max_retries}")
                await asyncio.sleep(wait_time)
                
                # Увеличиваем счетчик попыток
                self._floodwait_retry_count = retry_count + 1
                
                # Повторная попытка (итеративно)
                # Устанавливаем флаг, чтобы предотвратить отправку уведомлений во время рекурсивного вызова
                original_in_md_verification = getattr(self, '_in_md_verification', False)
                self._in_md_verification = True
                
                try:
                    await self.export_channel(channel)
                finally:
                    # Восстанавливаем оригинальное значение флага
                    self._in_md_verification = original_in_md_verification
                
                return
            except Exception as e:
                self.logger.error(f"Error iterating messages for channel {channel.title}: {e}")
                self.stats.export_errors += 1
            
            # Логируем результаты обработки
            self.logger.info(f"Channel {channel.title}: processed {len(messages_data)} messages, total in channel: {total_messages_in_channel}")
            
            if messages_data:
                # Сортировка сообщений по дате (старые сначала)
                messages_data.sort(key=lambda x: x.date or datetime.min)
                
                # Проверяем режим экспорта - если файлы не существуют, создаем их с нуля
                export_mode = "incremental"  # По умолчанию инкрементальный режим
                
                json_file_path = json_exporter.output_dir / f"{json_exporter.sanitize_filename(json_exporter.channel_name)}.json"
                html_file_path = html_exporter.output_dir / f"{html_exporter.sanitize_filename(html_exporter.channel_name)}.html" 
                md_file_path = md_exporter.output_dir / f"{md_exporter.sanitize_filename(md_exporter.channel_name)}.md"
                
                # Проверяем, есть ли флаг принудительного полного ре-экспорта
                if hasattr(channel, '_force_full_reexport') and channel._force_full_reexport:
                    export_mode = "initial"
                    self.logger.info(f"Forced full re-export mode for {channel.title} - recreating all files from scratch")
                elif not json_file_path.exists() or not html_file_path.exists() or not md_file_path.exists():
                    export_mode = "initial"
                    self.logger.info(f"Initial export mode for {channel.title} - creating files from scratch")
                
                # Параллельная загрузка всех медиафайлов
                if media_downloader.get_queue_size() > 0:
                    queue_size = media_downloader.get_queue_size()
                    self.logger.info(f"Starting intelligent download of {queue_size} media files")
                    self.stats.current_export_info = f"Интеллектуальная загрузка: {channel.title} | {queue_size} файлов"
                    
                    try:
                        downloaded_files = await media_downloader.download_queue_parallel()
                        # После завершения загрузки сбрасываем скорость и оставшиеся
                        self.stats.download_speed_files_per_sec = 0.0
                        self.stats.download_speed_mb_per_sec = 0.0
                        self.stats.remaining_files_to_download = 0
                        
                        # Получаем статистику загрузки
                        stats = media_downloader.get_download_stats()
                        
                        self.logger.info(f"Download completed: {len(downloaded_files)} files successful")
                        self.logger.info(f"Download stats: {stats['success_rate']:.1f}% success rate, "
                                       f"{stats['flood_waits']} flood waits, "
                                       f"{stats['average_speed']:.1f} files/sec")
                        
                        # Обновляем пути к медиафайлам в данных сообщений
                        for msg_data in messages_data:
                            if msg_data.media_path and msg_data.media_path.startswith("media/"):
                                # Проверяем, был ли файл успешно загружен
                                actual_path = media_downloader.get_downloaded_file(msg_data.id)
                                if actual_path:
                                    # Проверяем, что файл действительно существует и имеет размер больше 0
                                    full_path = channel_dir / actual_path
                                    if full_path.exists() and full_path.stat().st_size > 0:
                                        msg_data.media_path = actual_path
                                        # Подсчитываем размер файла
                                        file_size = media_downloader.get_file_size_mb(actual_path)
                                        total_size += file_size
                                        self.logger.info(f"Media file {actual_path} loaded successfully, size: {file_size:.2f} MB")
                                    else:
                                        # Файл существует, но имеет размер 0 - считаем его неудачной загрузкой
                                        self.logger.warning(f"Media file {actual_path} has size 0, removing reference")
                                        msg_data.media_path = None
                                        msg_data.media_type = None
                                else:
                                    # Файл не был загружен, убираем ссылку
                                    self.logger.warning(f"Media file for message {msg_data.id} was not downloaded")
                                    msg_data.media_path = None
                                    msg_data.media_type = None
                        
                    except Exception as e:
                        self.logger.error(f"Error during parallel media download: {e}")
                        # Продолжаем без медиафайлов
                        for msg_data in messages_data:
                            msg_data.media_path = None
                            msg_data.media_type = None
                
                # Экспорт в различные форматы
                append_mode = (export_mode == "incremental")
                mode_description = "incremental mode" if append_mode else "initial mode"
                self.logger.info(f"Exporting {len(messages_data)} messages in {mode_description}")
                
                json_file = json_exporter.export_messages(messages_data, append_mode=append_mode)
                html_file = html_exporter.export_messages(messages_data, append_mode=append_mode)
                
                # Для Markdown файла используем append_mode всегда когда файл существует
                # Это обеспечивает инкрементальное добавление сообщений
                md_append_mode = append_mode or (md_file_path.exists() and not (hasattr(channel, '_force_full_reexport') and channel._force_full_reexport))
                md_file = md_exporter.export_messages(messages_data, append_mode=md_append_mode)
                
                # Проверка создания файлов экспорта
                export_files_created = []
                if json_file and Path(json_file).exists():
                    export_files_created.append("JSON")
                if html_file and Path(html_file).exists():
                    export_files_created.append("HTML")
                if md_file and Path(md_file).exists():
                    export_files_created.append("Markdown")
                
                if not export_files_created:
                    self.logger.error(f"Export files were not created for channel {channel.title}")
                    self.stats.export_errors += 1
                    # Отправляем уведомление об ошибке
                    notification = self._create_notification(channel, 0, False, "Файлы экспорта не были созданы")
                    await self.send_notification(notification)
                    return
                
                self.logger.info(f"Export files created for {channel.title}: {', '.join(export_files_created)}")
                
                # Обновление статистики канала - только при инкрементальном экспорте
                # При полном ре-экспорте total_messages уже установлен правильно выше
                if not (hasattr(channel, '_force_full_reexport') and channel._force_full_reexport):
                    channel.total_messages += len(messages_data)
                channel.last_check = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Обновление общей статистики
                # Обновление общей статистики
                self.stats.total_messages += len(messages_data)
                self.stats.total_size_mb += total_size
                # Добавляем отфильтрованные сообщения из текущей сессии к общей статистике
                self.stats.filtered_messages += session_filtered_count
                
                # Отправка уведомления
                if new_messages_count > 0:
                    notification = self._create_notification(channel, new_messages_count, True)
                    await self.send_notification(notification)
                    # Загрузка архива канала (опционально) после успешного экспорта
                    try:
                        webdav = self.config_manager.config.webdav  # type: ignore[attr-defined]
                        if getattr(webdav, 'enabled', False) and getattr(webdav, 'upload_archives', False):
                            archive = self._zip_channel_folder(channel_dir)
                            if archive and self._webdav_upload_archive(archive):
                                if getattr(webdav, 'notify_on_sync', True):
                                    await self.send_notification(f"✅ Загружен архив канала на WebDAV: {archive.name}")
                    except Exception as e:
                        self.logger.error(f"Archive upload flow error: {e}")
                
                self.logger.info(f"Successfully exported {len(messages_data)} messages from {channel.title}")
                
                # После-экспортная проверка MD файла и автоматический ре-экспорт
                # Только если это не рекурсивный вызов (не MD verification)
                if not getattr(self, '_in_md_verification', False):
                    if md_file and Path(md_file).exists():
                        self.logger.info(f"Проверка MD файла после экспорта для {channel.title}")
                        self.stats.md_verification_status = "Проверка MD файла"
                        self.stats.md_verification_channel = channel.title
                        self.stats.md_verification_progress = "Проверка количества сообщений в MD файле"
                        
                        # Используем нашу функцию проверки
                        md_matches, actual_md_count, discrepancy_type = self._verify_md_file_count(channel)
                        
                        # Реэкспорт нужен только в двух случаях:
                        # 1. Отсутствует MD файл
                        # 2. Есть дисбаланс (>2 раза разница)
                        if not md_matches and (discrepancy_type == "missing" or discrepancy_type == "imbalance"):
                            reason = "отсутствует MD файл" if discrepancy_type == "missing" else "дисбаланс сообщений (>2 раза)"
                            self.logger.warning(f"MD файл для {channel.title} требует реэкспорта: {reason}")
                            self.stats.md_reexport_count += 1
                            self.stats.md_verification_progress = f"Требуется ре-экспорт: {reason}, попытка #{self.stats.md_reexport_count}"
                            
                            # Сохраняем причину для уведомления
                            reexport_reason = reason
                            
                            # Проверяем максимальное количество попыток ре-экспорта
                            max_reexport_attempts = 3
                            if self.stats.md_reexport_count <= max_reexport_attempts:
                                try:
                                    # Устанавливаем флаг, чтобы предотвратить отправку уведомлений во время рекурсивного вызова
                                    self._in_md_verification = True
                                    
                                    # Принудительно пересчитываем сообщения в канале заново
                                    self.logger.info(f"Повторный подсчет сообщений в {channel.title} для ре-экспорта")
                                    message_count = 0
                                    async for message in self.client.iter_messages(entity):
                                        message_count += 1
                                        if message_count % 1000 == 0:
                                            self.stats.md_verification_progress = f"Переподсчет: {message_count} сообщений..."
                                    
                                    # Обновляем общее количество сообщений - только если оно действительно изменилось
                                    self.logger.info(f"Обновленное количество сообщений в {channel.title}: {message_count}")
                                    # Сохраняем старое значение для сравнения
                                    
                                    # Принудительно сбрасываем last_message_id чтобы загрузить все сообщения
                                    original_last_id = channel.last_message_id
                                    channel.last_message_id = 0
                                    
                                    # Отмечаем, что это принудительный полный ре-экспорт
                                    channel._force_full_reexport = True
                                    
                                    try:
                                        await self.export_channel(channel)
                                        self.logger.info(f"Успешно выполнен повторный экспорт для {channel.title}")
                                        
                                        # Отправляем уведомление о реэкспорте с причиной
                                        notification = self._create_reexport_notification(channel, reexport_reason)
                                        await self.send_notification(notification)
                                    except Exception as e:
                                        self.logger.error(f"Ошибка повторного экспорта для {channel.title}: {e}")
                                    finally:
                                        # Восстанавливаем оригинальное значение
                                        channel.last_message_id = original_last_id
                                        # Убираем флаг принудительного ре-экспорта
                                        if hasattr(channel, '_force_full_reexport'):
                                            delattr(channel, '_force_full_reexport')
                                        # Сбрасываем флаг MD верификации
                                        self._in_md_verification = False
                                except Exception as e:
                                    self.logger.error(f"Ошибка в процессе повторного экспорта {channel.title}: {e}")
                                    # Сбрасываем флаг MD верификации в случае ошибки
                                    self._in_md_verification = False
                            else:
                                self.logger.error(f"Превышено максимальное количество попыток ре-экспорта для {channel.title}")
                                # Сбрасываем флаг MD верификации
                                self._in_md_verification = False
                        else:
                            # MD файл совпадает или обычное несоответствие (дополняем, не перезаписываем)
                            self._in_md_verification = False
                            
                            # Если есть обычное несоответствие, но не дисбаланс и файл есть, 
                            # то при следующем экспорте новые сообщения будут добавлены
                            if not md_matches and discrepancy_type == "normal":
                                self.logger.info(f"MD файл для {channel.title} будет дополнен при следующем экспорте новых сообщений")
                    else:
                        # Нет MD файла, сбрасываем флаг
                        self._in_md_verification = False
                else:
                    # Мы в рекурсивном вызове, сбрасываем флаг
                    self._in_md_verification = False
            else:
                self.logger.info(f"No new messages found in {channel.title}")
                channel.last_check = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Проверяем, существуют ли файлы экспорта, если нет - создаем пустые
                export_files_to_check = [
                    (json_exporter, "JSON"),
                    (html_exporter, "HTML"), 
                    (md_exporter, "Markdown")
                ]
                
                missing_files = []
                for exporter, format_name in export_files_to_check:
                    expected_file = None
                    if format_name == "JSON":
                        expected_file = exporter.output_dir / f"{exporter.sanitize_filename(exporter.channel_name)}.json"
                    elif format_name == "HTML":
                        expected_file = exporter.output_dir / f"{exporter.sanitize_filename(exporter.channel_name)}.html"
                    elif format_name == "Markdown":
                        expected_file = exporter.output_dir / f"{exporter.sanitize_filename(exporter.channel_name)}.md"
                    
                    if expected_file and not expected_file.exists():
                        missing_files.append((exporter, format_name))
                
                # Создаем отсутствующие файлы с пустым содержимым
                if missing_files:
                    self.logger.info(f"Creating missing export files for {channel.title}: {[f[1] for f in missing_files]}")
                    
                    for exporter, format_name in missing_files:
                        try:
                            # Создаем файл с пустым списком сообщений
                            empty_file = exporter.export_messages([], append_mode=False)
                            if empty_file and Path(empty_file).exists():
                                self.logger.info(f"Created empty {format_name} file: {empty_file}")
                            else:
                                self.logger.error(f"Failed to create empty {format_name} file")
                        except Exception as e:
                            self.logger.error(f"Error creating empty {format_name} file: {e}")
                
                # Если экспорт прошел без сообщений, но в канале есть сообщения - повторная проверка
                if total_messages_in_channel > 0:
                    self.logger.info(f"Re-checking channel {channel.title} - found {total_messages_in_channel} total messages")
                    self.stats.current_export_info = f"Повторная проверка: {channel.title} | Всего сообщений: {total_messages_in_channel}"
                    
                    # Если это первая проверка и сообщений нет, но в канале они есть - принудительно экспортируем все
                    if channel.last_message_id == 0 and total_messages_in_channel > 0:
                        self.logger.warning(f"Channel {channel.title} has {total_messages_in_channel} messages but export returned 0. This might indicate an access issue.")
                        # Можно добавить дополнительную диагностику здесь
            
            # Сбрасываем счетчик FloodWait попыток после успешного завершения
            self._floodwait_retry_count = 0
            
            # Обновляем статистику обнаруженных/экспортированных сообщений
            self._update_discovered_exported_stats()
            
            # Очищаем статус проверки MD файлов после успешного экспорта
            if md_file_missing or self.stats.md_verification_status:
                self.stats.md_verification_status = None
                self.stats.md_verification_channel = None
                self.stats.md_verification_progress = None
                # Сбрасываем счетчик повторных экспортов после успешного завершения
                self.stats.md_reexport_count = 0
                self.logger.info(f"Экспорт для {channel.title} успешно завершен, MD проверка очищена")
            
            # Убираем флаг принудительного ре-экспорта
            if hasattr(channel, '_force_full_reexport'):
                delattr(channel, '_force_full_reexport')
            
            # Сохранение обновленной информации о каналах (включая last_message_id и total_messages)
            self.save_channels()
            
        except Exception as e:
            self.logger.error(f"Export error for channel {channel.title}: {e}")
            self.stats.export_errors += 1
            
            # Отправка уведомления об ошибке
            notification = self._create_notification(channel, 0, False, str(e))
            await self.send_notification(notification)
        finally:
            # Очищаем информацию о текущем экспорте
            self.stats.current_export_info = None
            self.stats.total_messages_in_channel = 0
    
    def reset_channel_export_state(self, channel_title: str) -> bool:
        """Сброс состояния экспорта канала для принудительного переэкспорта всех сообщений"""
        for channel in self.channels:
            if channel.title == channel_title:
                old_id = channel.last_message_id
                channel.last_message_id = 0
                channel.total_messages = 0
                channel.last_check = None
                # Отмечаем, что при следующем экспорте нужно полностью переэкспортировать
                channel._force_full_reexport = True
                self.logger.info(f"Reset export state for channel {channel_title}: last_message_id {old_id} -> 0")
                self.save_channels()
                return True
        return False
    
    def list_channels_with_issues(self) -> List[str]:
        """Возвращает список каналов, которые могут иметь проблемы с экспортом"""
        problematic_channels = []
        for channel in self.channels:
            if channel.total_messages == 0 and channel.last_check:
                problematic_channels.append(channel.title)
        return problematic_channels
    
    async def verify_and_complete_export(self, channel: ChannelInfo) -> bool:
        """Проверяет целостность экспорта канала и докачивает недостающие сообщения"""
        try:
            self.logger.info(f"Проверка целостности экспорта для канала: {channel.title}")
            
            # Получаем путь к директории канала
            try:
                storage_cfg = self.config_manager.config.storage
                base_dir = getattr(storage_cfg, 'export_base_dir', 'exports') or 'exports'
            except Exception:
                base_dir = 'exports'
            
            base_path = Path(base_dir)
            sanitized_title = self._sanitize_channel_filename(channel.title)
            channel_dir = base_path / sanitized_title
            
            # Проверяем существование JSON файла экспорта
            json_file = channel_dir / f"{sanitized_title}.json"
            if not json_file.exists():
                self.logger.info(f"JSON файл не найден для {channel.title}, требуется полный экспорт")
                return False
            
            # Читаем существующий экспорт
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    export_data = json.load(f)
                
                if not isinstance(export_data, list):
                    self.logger.warning(f"Неверный формат JSON файла для {channel.title}")
                    return False
                
                # Извлекаем ID сообщений из экспорта
                exported_ids = set()
                for msg in export_data:
                    if isinstance(msg, dict) and 'id' in msg:
                        exported_ids.add(msg['id'])
                
                self.logger.info(f"Найдено {len(exported_ids)} сообщений в существующем экспорте")
                
            except Exception as e:
                self.logger.error(f"Ошибка чтения JSON файла для {channel.title}: {e}")
                return False
            
            # Получаем актуальный диапазон сообщений в канале
            try:
                entity = await self.client.get_entity(channel.id)
                
                # Получаем первое и последнее сообщения для определения диапазона
                first_msg = await self.client.get_messages(entity, limit=1, reverse=True)
                last_msg = await self.client.get_messages(entity, limit=1)
                
                if not first_msg or not last_msg:
                    self.logger.warning(f"Не удалось получить сообщения из канала {channel.title}")
                    return True  # Считаем что все в порядке если канал пустой
                
                first_id = first_msg[0].id
                last_id = last_msg[0].id
                
                self.logger.info(f"Диапазон сообщений в канале {channel.title}: {first_id}-{last_id}")
                
                # Определяем недостающие сообщения
                missing_ids = []
                
                # 1. Новые сообщения после последнего экспортированного
                max_exported_id = max(exported_ids) if exported_ids else 0
                if last_id > max_exported_id:
                    # Получаем новые сообщения
                    async for message in self.client.iter_messages(entity, min_id=max_exported_id, limit=None):
                        if message.id not in exported_ids:
                            missing_ids.append(message.id)
                
                # 2. Пропуски в середине диапазона
                # Проверяем наличие значительных пропусков (более 10 подряд отсутствующих ID)
                if exported_ids:
                    min_exported_id = min(exported_ids)
                    
                    # Создаем список всех ID в диапазоне от min до max экспортированных
                    expected_range = set(range(min_exported_id, max_exported_id + 1))
                    gaps_in_range = expected_range - exported_ids
                    
                    # Фильтруем значительные пропуски (где отсутствует более 5 сообщений подряд)
                    significant_gaps = []
                    if gaps_in_range:
                        sorted_gaps = sorted(gaps_in_range)
                        current_gap = [sorted_gaps[0]]
                        
                        for i in range(1, len(sorted_gaps)):
                            if sorted_gaps[i] == sorted_gaps[i-1] + 1:
                                current_gap.append(sorted_gaps[i])
                            else:
                                if len(current_gap) >= 5:  # Значительный пропуск
                                    significant_gaps.extend(current_gap)
                                current_gap = [sorted_gaps[i]]
                        
                        # Не забываем последний пропуск
                        if len(current_gap) >= 5:
                            significant_gaps.extend(current_gap)
                    
                    # Проверяем, существуют ли эти сообщения в канале
                    for gap_id in significant_gaps:
                        try:
                            msg = await self.client.get_messages(entity, ids=gap_id)
                            if msg and msg[0] and gap_id not in exported_ids:
                                missing_ids.append(gap_id)
                        except Exception:
                            # Сообщение не существует, игнорируем
                            pass
                
                missing_ids = sorted(set(missing_ids))
                
                if not missing_ids:
                    self.logger.info(f"Экспорт канала {channel.title} полный, недостающих сообщений не найдено")
                    return True
                
                self.logger.info(f"Найдено {len(missing_ids)} недостающих сообщений в канале {channel.title}")
                
                # Получаем недостающие сообщения
                missing_messages = []
                
                # Используем батчевое получение для эффективности
                batch_size = 100
                for i in range(0, len(missing_ids), batch_size):
                    batch_ids = missing_ids[i:i + batch_size]
                    try:
                        messages = await self.client.get_messages(entity, ids=batch_ids)
                        for message in messages:
                            if message and message.id:
                                # Обрабатываем сообщение также как в основном экспорте
                                msg_data = await self._process_single_message(message, channel, None)
                                if msg_data:
                                    missing_messages.append(msg_data)
                    
                    except Exception as e:
                        self.logger.error(f"Ошибка получения батча сообщений {batch_ids}: {e}")
                        # Пробуем получить по одному
                        for msg_id in batch_ids:
                            try:
                                msg = await self.client.get_messages(entity, ids=msg_id)
                                if msg and msg[0] and msg[0].id:
                                    msg_data = await self._process_single_message(msg[0], channel, None)
                                    if msg_data:
                                        missing_messages.append(msg_data)
                            except Exception:
                                continue
                
                if not missing_messages:
                    self.logger.info(f"Недостающие сообщения не удалось получить для {channel.title}")
                    return True
                
                self.logger.info(f"Получено {len(missing_messages)} недостающих сообщений для {channel.title}")
                
                # Добавляем недостающие сообщения к существующему экспорту
                # Объединяем с существующими данными
                combined_messages = list(export_data)
                
                for msg_data in missing_messages:
                    # Преобразуем MessageData в словарь для добавления в JSON
                    msg_dict = {
                        'id': msg_data.id,
                        'date': msg_data.date.isoformat() if msg_data.date else None,
                        'text': msg_data.text,
                        'author': msg_data.author,
                        'media_type': msg_data.media_type,
                        'media_path': msg_data.media_path,
                        'views': msg_data.views,
                        'forwards': msg_data.forwards,
                        'replies': msg_data.replies,
                        'edited': msg_data.edited.isoformat() if msg_data.edited else None
                    }
                    combined_messages.append(msg_dict)
                
                # Сортируем все сообщения по ID
                combined_messages.sort(key=lambda x: x.get('id', 0))
                
                # Убираем дубликаты по ID
                seen_ids = set()
                unique_messages = []
                for msg in combined_messages:
                    msg_id = msg.get('id')
                    if msg_id and msg_id not in seen_ids:
                        seen_ids.add(msg_id)
                        unique_messages.append(msg)
                
                # Сохраняем обновленный экспорт
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(unique_messages, f, ensure_ascii=False, indent=2)
                
                self.logger.info(f"Целостность экспорта восстановлена для {channel.title}: добавлено {len(missing_messages)} сообщений")
                
                # Обновляем также HTML и Markdown файлы
                try:
                    # Преобразуем обратно в MessageData для экспортеров
                    updated_messages = []
                    for msg_dict in unique_messages:
                        msg_data = MessageData(
                            id=msg_dict.get('id', 0),
                            date=datetime.fromisoformat(msg_dict['date']) if msg_dict.get('date') else None,
                            text=msg_dict.get('text', ''),
                            author=msg_dict.get('author'),
                            media_type=msg_dict.get('media_type'),
                            media_path=msg_dict.get('media_path'),
                            views=msg_dict.get('views', 0),
                            forwards=msg_dict.get('forwards', 0),
                            replies=msg_dict.get('replies', 0),
                            edited=datetime.fromisoformat(msg_dict['edited']) if msg_dict.get('edited') else None
                        )
                        updated_messages.append(msg_data)
                    
                    # Обновляем HTML и Markdown файлы
                    html_exporter = HTMLExporter(channel.title, channel_dir)
                    md_exporter = MarkdownExporter(channel.title, channel_dir)
                    
                    html_exporter.export_messages(updated_messages, append_mode=False)  # Перезаписываем полностью
                    md_exporter.export_messages(updated_messages, append_mode=False)  # Перезаписываем полностью
                    
                    self.logger.info(f"Обновлены HTML и Markdown файлы для {channel.title}")
                    
                except Exception as e:
                    self.logger.error(f"Ошибка обновления HTML/Markdown файлов для {channel.title}: {e}")
                
                # Обновляем статистику канала
                channel.last_message_id = max(last_id, channel.last_message_id)
                channel.total_messages = len(unique_messages)
                
                return True
                
            except Exception as e:
                self.logger.error(f"Ошибка проверки целостности для {channel.title}: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Общая ошибка проверки целостности для {channel.title}: {e}")
            return False
    
    def _create_notification(self, channel: ChannelInfo, messages_count: int, success: bool, error: str = None) -> str:
        """Создание текста уведомления о новых сообщениях"""
        if success and messages_count > 0:
            return f"""
📢 <b>Новые сообщения в канале</b>

🔗 <b>Канал:</b> {channel.title}
📊 <b>Новых сообщений:</b> {messages_count}
📅 <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
✅ <b>Статус:</b> Успешно экспортировано

📁 Файлы сохранены в папку: {channel.title}
            """.strip()
        elif success and messages_count == 0:
            return f"""
📢 <b>Проверка канала завершена</b>

🔗 <b>Канал:</b> {channel.title}
📊 <b>Новых сообщений:</b> не найдено
📅 <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
✅ <b>Статус:</b> Проверка выполнена
            """.strip()
        else:
            return f"""
📢 <b>Ошибка экспорта канала</b>

🔗 <b>Канал:</b> {channel.title}
📅 <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
❌ <b>Статус:</b> Ошибка
🔍 <b>Причина:</b> {error or 'Неизвестная ошибка'}
            """.strip()
    
    def _create_reexport_notification(self, channel: ChannelInfo, reason: str) -> str:
        """Создание текста уведомления о реэкспорте"""
        return f"""
🔄 <b>Выполнен реэкспорт канала</b>

🔗 <b>Канал:</b> {channel.title}
❓ <b>Причина:</b> {reason}
📅 <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
✅ <b>Статус:</b> Реэкспорт завершен

📁 Файлы сохранены в папку: {channel.title}
        """.strip()
    
    async def main_loop(self):
        """Упрощенный основной цикл программы без управления клавишами"""
        try:
            # Проверяем, нужен ли начальный экспорт
            if self.channels:
                need_initial_export = False
                for channel in self.channels:
                    if not channel.last_check:
                        need_initial_export = True
                        break
                    try:
                        last_check = datetime.strptime(channel.last_check, "%Y-%m-%d %H:%M:%S")
                        if (datetime.now() - last_check).days >= 1:
                            need_initial_export = True
                            break
                    except:
                        need_initial_export = True
                        break
                
                if need_initial_export:
                    self.logger.info("Starting initial export for channels that haven't been checked recently")
                    asyncio.create_task(self.export_all_channels())
                
                # Проверяем наличие MD файлов для всех каналов
                self._check_missing_md_files()
            
            with Live(self.create_status_display(), refresh_per_second=2) as live:
                # Запуск планировщика в фоне
                scheduler_task = asyncio.create_task(self.run_scheduler())
                
                # Основной цикл
                while self.running:
                    # Обновляем интерфейс
                    live.update(self.create_status_display())
                    await asyncio.sleep(0.5)
                    
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Получен сигнал завершения (Ctrl+C)...[/yellow]")
            self.running = False
            
        finally:
            if self.client:
                await self.client.disconnect()
    
    def _check_missing_md_files(self):
        """Проверяет наличие MD файлов и запускает экспорт при их отсутствии"""
        try:
            # Получаем базовый каталог экспорта
            try:
                storage_cfg = self.config_manager.config.storage  # type: ignore[attr-defined]
                base_dir = getattr(storage_cfg, 'export_base_dir', 'exports') or 'exports'
            except Exception:
                base_dir = 'exports'
            
            base_path = Path(base_dir)
            channels_needing_export = []
            
            for channel in self.channels:
                sanitized_title = self._sanitize_channel_filename(channel.title)
                channel_dir = base_path / sanitized_title
                md_file = channel_dir / f"{sanitized_title}.md"
                
                if not md_file.exists():
                    self.logger.info(f"MD файл отсутствует для канала: {channel.title}")
                    channels_needing_export.append(channel)
            
            if channels_needing_export:
                self.logger.info(f"Найдено {len(channels_needing_export)} каналов без MD файлов, запуск экспорта")
                
                # Запускаем экспорт для каналов без MD файлов синхронно
                # Чтобы обеспечить обработку всех каналов
                try:
                    loop = asyncio.get_running_loop()
                    # Запускаем в фоновом режиме, но логируем начало
                    task = loop.create_task(self._export_missing_md_channels(channels_needing_export))
                    self.logger.info("Задача экспорта каналов без MD файлов запущена")
                except RuntimeError:
                    # Если нет текущего event loop, создаем новый
                    self.logger.warning("Нет активного event loop, экспорт MD файлов будет отложен")
                
        except Exception as e:
            self.logger.error(f"Ошибка проверки MD файлов: {e}")
    
    async def _export_missing_md_channels(self, channels: List[ChannelInfo]):
        """Экспорт каналов без MD файлов"""
        try:
            self.logger.info(f"Начало экспорта {len(channels)} каналов без MD файлов")
            
            # Устанавливаем флаг, чтобы предотвратить отправку уведомлений во время этого процесса
            original_in_md_verification = getattr(self, '_in_md_verification', False)
            self._in_md_verification = True
            
            try:
                for i, channel in enumerate(channels):
                    self.logger.info(f"Запуск экспорта для канала без MD файла: {channel.title} ({i+1}/{len(channels)})")
                    
                    # Обновляем информацию о текущем экспорте для авто-прокрутки
                    self.stats.current_export_info = f"Полный ре-экспорт {i+1}/{len(channels)}: {channel.title}"
                    
                    # Сбрасываем last_message_id чтобы загрузить все сообщения
                    original_last_id = channel.last_message_id
                    channel.last_message_id = 0
                    
                    # Отмечаем, что это принудительный полный ре-экспорт
                    channel._force_full_reexport = True
                    
                    try:
                        await self.export_channel(channel)
                        self.logger.info(f"Успешно экспортирован канал: {channel.title}")
                        
                        # Отправляем уведомление о реэкспорте из-за отсутствия MD файла
                        notification = self._create_reexport_notification(channel, "отсутствует MD файл")
                        await self.send_notification(notification)
                    except Exception as e:
                        self.logger.error(f"Ошибка экспорта канала {channel.title}: {e}")
                        # Восстанавливаем оригинальное значение при ошибке
                        channel.last_message_id = original_last_id
                    finally:
                        # Убираем флаг принудительного ре-экспорта
                        if hasattr(channel, '_force_full_reexport'):
                            delattr(channel, '_force_full_reexport')
                        # Очищаем информацию о текущем экспорте между каналами
                        self.stats.current_export_info = None
                        # Небольшая пауза для обновления UI
                        await asyncio.sleep(0.5)
                
                self.logger.info(f"Завершен экспорт {len(channels)} каналов без MD файлов")
                # Обновляем статистику обнаруженных/экспортированных сообщений
                self._update_discovered_exported_stats()
                # Окончательно очищаем информацию о экспорте
                self.stats.current_export_info = None
            finally:
                # Восстанавливаем оригинальное значение флага
                self._in_md_verification = original_in_md_verification
        except Exception as e:
            self.logger.error(f"Ошибка экспорта каналов без MD файлов: {e}")
        finally:
            # Гарантируем очистку состояния
            self.stats.current_export_info = None
    
    async def export_all_channels(self):
        """Экспорт всех каналов"""
        self.logger.info("Starting scheduled export of all channels")
        
        for i, channel in enumerate(self.channels):
            try:
                # Обновляем информацию о текущем экспорте для авто-прокрутки
                self.stats.current_export_info = f"Экспорт {i+1}/{len(self.channels)}: {channel.title}"
                await self.export_channel(channel)
            except Exception as e:
                self.logger.error(f"Export error for channel {channel.title}: {e}")
                self.stats.export_errors += 1
            finally:
                # Очищаем информацию о текущем экспорте между каналами
                self.stats.current_export_info = None
                # Небольшая пауза для обновления UI
                await asyncio.sleep(0.5)
        
        self.stats.last_export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Обновляем статистику обнаруженных/экспортированных сообщений
        self._update_discovered_exported_stats()
        # Окончательно очищаем информацию о экспорте
        self.stats.current_export_info = None

    async def run(self):
        """Главный метод запуска программы"""
        self.console.print(Panel.fit(
            "[bold blue]Telegram Channel Exporter[/bold blue]\n"
            "Программа для мониторинга и экспорта каналов Telegram",
            box=box.DOUBLE
        ))
        
        # Проверка и настройка конфигурации
        if not self.config_manager.ensure_configured():
            return
        
        # Возможность изменения конфигурации
        if Confirm.ask("Изменить настройки конфигурации?", default=False):
            if not self.config_manager.interactive_setup():
                return
        
        # Предложить импорт/экспорт списка каналов в произвольный JSON
        try:
            self.console.print(Panel(
                "Вы можете импортировать/экспортировать список каналов для ручного редактирования в JSON.\n"
                "Доступные действия:\n"
                "- [i]import[/i] — загрузить из JSON-файла\n"
                "- [i]export[/i] — сохранить текущий список в JSON\n"
                "- [i]reset[/i] — сбросить состояние экспорта для проблемных каналов\n"
                "- [i]skip[/i] — пропустить",
                title="Импорт/Экспорт каналов", box=box.ROUNDED
            ))
            io_action = Prompt.ask("Действие", choices=["import", "export", "reset", "skip"], default="skip")
            if io_action == "import":
                # Перед импортом попробуем подтянуть актуальный файл с WebDAV
                if self._webdav_enabled():
                    await self._webdav_download_and_notify()
                path_str = Prompt.ask("Путь к JSON-файлу для импорта", default="channels.json")
                file_path = Path(path_str)
                if not file_path.exists():
                    self.console.print(f"[red]Файл {file_path} не найден[/red]")
                else:
                    if self.load_channels_from_file(file_path):
                        self.console.print(f"[green]✓ Импортировано каналов: {len(self.channels)}[/green]")
            elif io_action == "export":
                # Если каналов пока нет — дадим возможность выбрать, чтобы было что сохранять
                if not self.channels and Confirm.ask("Список каналов пуст. Выбрать каналы перед экспортом?", default=True):
                    # Инициализация клиента перед выбором
                    if not await self.initialize_client():
                        return
                    await self.select_channels()
                path_str = Prompt.ask("Путь для сохранения JSON", default="channels.json")
                self.save_channels_to_file(Path(path_str))
                # После сохранения — выгрузка на WebDAV, если включен и совпадает основной путь
                if self._webdav_enabled():
                    await self._webdav_upload_and_notify()
            elif io_action == "reset":
                # Показываем проблемные каналы и предлагаем сбросить их состояние
                problematic_channels = self.list_channels_with_issues()
                if problematic_channels:
                    self.console.print(f"[yellow]Найдены каналы с возможными проблемами экспорта:[/yellow]")
                    for i, title in enumerate(problematic_channels, 1):
                        self.console.print(f"  {i}. {title}")
                    
                    if Confirm.ask("Сбросить состояние экспорта для этих каналов?", default=False):
                        for title in problematic_channels:
                            if self.reset_channel_export_state(title):
                                self.console.print(f"[green]✓ Сброшено состояние для канала: {title}[/green]")
                        self.console.print("[green]✓ Состояние экспорта сброшено. При следующем запуске каналы будут экспортированы заново.[/green]")
                else:
                    self.console.print("[green]Проблемных каналов не найдено[/green]")
        except Exception as e:
            self.logger.error(f"IO setup error: {e}")

        # Инициализация клиента
        if not await self.initialize_client():
            return
        
        # Загрузка или выбор каналов
        if not self.channels:
            if self.channels_file.exists() and Confirm.ask("Использовать сохраненный список каналов?"):
                self.load_channels()
            else:
                await self.select_channels()
        
        if not self.channels:
            self.console.print("[red]Каналы не выбраны. Завершение работы.[/red]")
            return
        
        # Обновление статистики
        self.stats.total_channels = len(self.channels)
        
        # Обновляем статистику обнаруженных и экспортированных сообщений
        self._update_discovered_exported_stats()
        
        # Проверка целостности экспорта при запуске
        self.console.print("[yellow]Проверка целостности экспортов...[/yellow]")
        integrity_issues = 0
        integrity_fixed = 0
        
        for channel in self.channels:
            try:
                self.console.print(f"Проверка канала: {channel.title}")
                result = await self.verify_and_complete_export(channel)
                if result:
                    integrity_fixed += 1
                else:
                    integrity_issues += 1
            except Exception as e:
                self.logger.error(f"Ошибка проверки целостности для {channel.title}: {e}")
                integrity_issues += 1
        
        # Сохраняем обновленную информацию о каналах после проверки целостности
        self.save_channels()
        
        # Обновляем статистику обнаруженных/экспортированных сообщений
        self._update_discovered_exported_stats()
        
        if integrity_fixed > 0:
            self.console.print(f"[green]✓ Целостность восстановлена для {integrity_fixed} каналов[/green]")
            # Отправляем уведомление о восстановлении
            notification = f"📋 Проверка целостности завершена\n✅ Восстановлено: {integrity_fixed} каналов\n❌ Проблемы: {integrity_issues} каналов"
            await self.send_notification(notification)
        
        if integrity_issues > 0:
            self.console.print(f"[yellow]⚠ Проблемы с целостностью у {integrity_issues} каналов (см. лог)[/yellow]")
        
        if integrity_issues == 0 and integrity_fixed == 0:
            self.console.print("[green]✓ Все экспорты актуальны[/green]")
        
        # Меню дополнительных действий после загрузки каналов
        await self._post_loading_menu()
        
        # Запуск основного цикла
        await self.main_loop()


async def main():
    """Точка входа в программу"""
    exporter = TelegramExporter()
    await exporter.run()


if __name__ == "__main__":
    asyncio.run(main())
