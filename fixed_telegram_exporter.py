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
        
    async def initialize_client(self):
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
                
            self.client = TelegramClient('session_name', api_id, api_hash)
            await self.client.start(phone=phone)
            
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
  
                if not ok:
                    self.console.print("[red]❌ Неверная команда[/red]")
                    input("Нажмите Enter для продолжения...")
                    continue
            
            # Сохраняем выбранные каналы
            new_channels = []
            for dialog in all_dialogs:
                if getattr(dialog.entity, 'id', None) in selected_ids:
                    channel_info = ChannelInfo(
                        id=getattr(dialog.entity, 'id', 0),
                        title=dialog.title,
                        username=getattr(dialog.entity, 'username', None),
                        export_type=ExportType.BOTH
                    )
                    new_channels.append(channel_info)
            
            if new_channels:
                self.channels = new_channels
                self.save_channels()
                self.console.print(f"[green]✓ Выбрано {len(new_channels)} каналов[/green]")
            else:
                self.console.print("[yellow]⚠ Каналы не выбраны[/yellow]")
                
        except Exception as e:
            self.logger.error(f"Error selecting channels: {e}")
            self.console.print(f"[red]Ошибка выбора каналов: {e}[/red]")

    def _start_key_listener(self):
        """Запуск потока для прослушивания клавиш"""
        if self.key_thread_running:
            return
            
        self.key_thread_running = True
        self.key_thread = threading.Thread(target=self._key_listener_thread, daemon=True)
        self.key_thread.start()

    def _key_listener_thread(self):
        """Поток для прослушивания клавиш"""
        import msvcrt
        while self.key_thread_running:
            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8').lower()
                self.key_queue.put(key)
            time.sleep(0.1)

    def _stop_key_listener(self):
        """Остановка потока для прослушивания клавиш"""
        self.key_thread_running = False
        if self.key_thread:
            self.key_thread.join()
            self.key_thread = None

    def create_status_display(self) -> Layout:
        """Создание отображения статуса с двумя панелями"""
        layout = Layout()
        
        # Убираем фиксированные header и footer - таблица займёт всё доступное пространство
        layout.split_row(
            Layout(name="left", ratio=2),   # Левая панель (список каналов) - 2/3 ширины
            Layout(name="right", ratio=1)   # Правая панель (статистика) - 1/3 ширины
        )
        
        # Создаем таблицу каналов для левой панели
        channels_table = self._create_detailed_channels_table()
        
        # Заголовок с текущим статусом
        title_text = "📡 Каналы"
        if self.stats.current_export_info:
            title_text += f" | {self.stats.current_export_info}"
        
        layout["left"].update(Panel(channels_table, title=title_text, border_style="blue"))
        
        # Создаем статистику для правой панели
        stats_text = self._create_detailed_statistics()
        stats_title = "📊 Статистика | Статус: Работает"
        layout["right"].update(Panel(stats_text, title=stats_title, border_style="green"))
        
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
        max_visible_channels = 50  # Значительно увеличиваем для использования всего вертикального пространства
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
            
            # Подсвечиваем текущий экспортируемый канал с ярким выделением
            if actual_index == current_channel_index:
                status = "[bold yellow on red]⚡ ЭКСПОРТ[/bold yellow on red]"
                channel_name = f"[bold white on blue]▶ {channel_name}[/bold white on blue]"
                last_check = f"[bold white on blue]{last_check}[/bold white on blue]"
                msg_str = f"[bold white on blue]{msg_str}[/bold white on blue]"
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
            if actual_index != current_channel_index:  # Не перезаписываем уже отформатированное
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
                info_text += f" | [bold green on black]⚡ Текущий: #{current_channel_index + 1}[/bold green on black]"
            
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
                            data = json.load(f)
                            exported += len(data)
                    except Exception as e:
                        self.logger.warning(f"Error reading export file for {channel.title}: {e}")
                else:
                    # Если файл не существует, считаем что экспортировано 0 сообщений
                    exported += 0
            
            self.stats.discovered_messages = discovered
            self.stats.exported_messages = exported
            
        except Exception as e:
            self.logger.error(f"Error updating discovered/exported stats: {e}")

    async def run_scheduler(self):
        """Запуск планировщика"""
        try:
            # Планируем экспорт всех каналов каждые 60 минут
            schedule.every(60).minutes.do(lambda: asyncio.create_task(self.export_all_channels()))
            
            while self.running:
                schedule.run_pending()
                await asyncio.sleep(1)
        except Exception as e:
            self.logger.error(f"Scheduler error: {e}")

    async def _process_single_message(self, message: Message, channel: ChannelInfo, media_downloader) -> Optional[MessageData]:
        """Обработка одного сообщения с учетом типа экспорта"""
        try:
            # Проверяем тип экспорта - если только файлы, пропускаем сообщения без медиа
            if channel.export_type == ExportType.FILES_ONLY and not message.media:
                return None
                
            # Фильтрация рекламных и промо-сообщений
            should_filter, filter_reason = self.content_filter.should_filter_message(message.text or "")
            if should_filter:
                self.logger.info(f"Message {message.id} filtered: {filter_reason}")
                # Note: We don't increment session_filtered_count here because this function
                # is used in contexts outside the main export session (e.g., integrity verification)
                return None

            # Загрузка медиафайлов (только если не режим "только сообщения")
            media_path = None
            media_type = None
            
            if message.media and channel.export_type != ExportType.MESSAGES_ONLY:
                # Добавляем в очередь загрузки вместо немедленной загрузки
                media_path = media_downloader.add_to_download_queue(self.client, message)
                
                # Определение типа медиа
                if isinstance(message.media, MessageMediaPhoto):
                    media_type = "Фото"
                elif isinstance(message.media, MessageMediaDocument):
                    media_type = "Документ"
                else:
                    media_type = "Другое медиа"
            
            # Безопасное получение количества ответов
            replies_count = 0
            if hasattr(message, 'replies') and message.replies:
                if hasattr(message.replies, 'replies'):
                    replies_count = message.replies.replies
                elif hasattr(message.replies, 'replies_pts'):
                    replies_count = getattr(message.replies, 'replies_pts', 0)
            
            return MessageData(
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
                            
        except Exception as e:
            self.logger.error(f"Error processing message {message.id}: {e}")
            self.stats.export_errors += 1
            return None
    
    async def _save_batch_progress(self, messages_batch: List, batch_number: int, channel: ChannelInfo, exporters: tuple) -> None:
        """Сохраняет батч сообщений в файлы экспорта"""
        if not messages_batch:
            return
            
        json_exporter, html_exporter, md_exporter = exporters
        
        try:
            # Сортируем сообщения по дате (старые сначала)
            messages_batch.sort(key=lambda x: x.date or datetime.min)
            
            # Сохраняем в всех форматах (аппенд режим)
            json_exporter.export_messages(messages_batch, append_mode=True)
            html_exporter.export_messages(messages_batch, append_mode=True)
            md_exporter.export_messages(messages_batch, append_mode=True)
            
            self.logger.info(f"Батч {batch_number}: сохранено {len(messages_batch)} сообщений для канала {channel.title}")
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения батча {batch_number}: {e}")
    
    def _calculate_channel_media_size(self, channel: ChannelInfo) -> float:
        """Вычисление общего размера медиафайлов канала в МБ с кешированием"""
        # Кеширование для избежания повторных вычислений
        cache_key = f"media_size_{channel.title}"
        if hasattr(self, '_media_size_cache') and cache_key in self._media_size_cache:
            cache_time, cached_size = self._media_size_cache[cache_key]
            # Кеш действителен 5 минут
            if time.time() - cache_time < 300:
                return cached_size
        
        if not hasattr(self, '_media_size_cache'):
            self._media_size_cache = {}
        
        try:
            # Получаем путь к директории канала
            export_base_dir = Path(self.config_manager.config.storage.export_base_dir or "exports")
            channel_dir = export_base_dir / channel.title
            media_dir = channel_dir / "media"
            
            if not media_dir.exists():
                size_mb = 0.0
            else:
                total_size = 0
                media_files = 0
                
                # Оптимизированный подсчет с использованием iterdir для лучшей производительности
                try:
                    for file_path in media_dir.iterdir():
                        if file_path.is_file():
                            try:
                                file_size = file_path.stat().st_size
                                if file_size > 0:  # Игнорируем файлы нулевого размера
                                    total_size += file_size
                                    media_files += 1
                            except (OSError, IOError, PermissionError):
                                # Пропускаем файлы, к которым нет доступа
                                continue
                except (OSError, IOError, PermissionError):
                    # Если нет доступа к директории
                    total_size = 0
                    media_files = 0
                
                # Конвертируем в мегабайты
                size_mb = total_size / (1024 * 1024)
                
                # Логируем только если есть файлы и включен debug режим
                if media_files > 0 and self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"Channel {channel.title}: {media_files} media files, {size_mb:.2f} MB total")
            
            # Кешируем результат
            self._media_size_cache[cache_key] = (time.time(), size_mb)
            
            # Ограничиваем размер кеша
            if len(self._media_size_cache) > 100:
                # Удаляем самые старые записи
                oldest_keys = sorted(self._media_size_cache.keys(), 
                                   key=lambda k: self._media_size_cache[k][0])[:50]
                for key in oldest_keys:
                    del self._media_size_cache[key]
            
            return size_mb
            
        except Exception as e:
            self.logger.warning(f"Error calculating media size for channel {channel.title}: {e}")
            return 0.0
    
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
            
            # Инициализируем экспортеров
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
                await self.export_channel(channel)
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
                md_file = md_exporter.export_messages(messages_data, append_mode=append_mode)
                
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
                if md_file and Path(md_file).exists():
                    self.logger.info(f"Проверка MD файла после экспорта для {channel.title}")
                    self.stats.md_verification_status = "Проверка MD файла"
                    self.stats.md_verification_channel = channel.title
                    self.stats.md_verification_progress = "Проверка количества сообщений в MD файле"
                    
                    # Используем нашу функцию проверки
                    md_matches, actual_md_count = self._verify_md_file_count(channel)
                    
                    if not md_matches:
                        self.logger.warning(f"MD файл для {channel.title} содержит {actual_md_count} сообщений, ожидалось {channel.total_messages}. Запуск повторного экспорта")
                        self.stats.md_reexport_count += 1
                        self.stats.md_verification_progress = f"Несоответствие: {actual_md_count}/{channel.total_messages}, ре-экспорт #{self.stats.md_reexport_count}"
                        
                        # Проверяем максимальное количество попыток ре-экспорта
                        max_reexport_attempts = 3
                        if self.stats.md_reexport_count <= max_reexport_attempts:
                            try:
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
                                old_total = channel.total_messages
                                channel.total_messages = message_count
                                
                                # Сбрасываем параметры для полного ре-экспорта
                                channel.last_message_id = 0
                                channel._force_full_reexport = True
                                
                                self.stats.md_verification_progress = f"Запуск повторного экспорта ({message_count} сообщений)"
                                
                                # Рекурсивный вызов экспорта для повторного экспорта
                                await self.export_channel(channel)
                                return  # Выходим чтобы избежать дублирования операций
                                
                            except Exception as e:
                                self.logger.error(f"Ошибка повторного экспорта для {channel.title}: {e}")
                                self.stats.export_errors += 1
                        else:
                            self.logger.error(f"Превышено максимальное количество попыток ре-экспорта для {channel.title} ({max_reexport_attempts})")
                            self.stats.md_verification_status = "Ошибка: превышено макс. кол-во попыток"
                    else:
                        self.logger.info(f"MD файл для {channel.title} прошел проверку: {actual_md_count} сообщений")
                        self.stats.md_verification_status = "Проверка пройдена успешно"
                        self.stats.md_verification_progress = f"Подтверждено: {actual_md_count} сообщений"
                else:
                    self.logger.warning(f"MD файл не найден после экспорта для {channel.title}")
                
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
                            if format_name == "JSON":
                                with open(exporter.output_dir / f"{exporter.sanitize_filename(exporter.channel_name)}.json", 'w', encoding='utf-8') as f:
                                    json.dump([], f, ensure_ascii=False, indent=2)
                            elif format_name == "HTML":
                                exporter.export_messages([], append_mode=False)
                            elif format_name == "Markdown":
                                exporter.export_messages([], append_mode=False)
                            self.logger.info(f"Created empty {format_name} file for {channel.title}")
                        except Exception as e:
                            self.logger.error(f"Error creating empty {format_name} file for {channel.title}: {e}")
                            self.stats.export_errors += 1
                else:
                    self.logger.info(f"All export files already exist for {channel.title}")
                    
                # Обновляем статистику канала даже если новых сообщений нет
                channel.last_check = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Отправляем уведомление о проверке без новых сообщений
                notification = self._create_notification(channel, 0, True)
                await self.send_notification(notification)
                
        except Exception as e:
            self.logger.error(f"Critical error in export_channel for {channel.title}: {e}")
            self.stats.export_errors += 1
            # Отправляем уведомление об ошибке
            notification = self._create_notification(channel, 0, False, str(e))
            await self.send_notification(notification)

    def _verify_md_file_count(self, channel: ChannelInfo) -> tuple[bool, int]:
        """Проверяет количество сообщений в MD файле"""
        try:
            # Получаем путь к MD файлу
            try:
                storage_cfg = self.config_manager.config.storage  # type: ignore[attr-defined]
                base_dir = getattr(storage_cfg, 'export_base_dir', 'exports') or 'exports'
            except Exception:
                base_dir = 'exports'
            
            base_path = Path(base_dir)
            sanitized_title = self._sanitize_channel_filename(channel.title)
            channel_dir = base_path / sanitized_title
            md_file = channel_dir / f"{sanitized_title}.md"
            
            if not md_file.exists():
                self.logger.warning(f"MD file not found for channel {channel.title}")
                return False, 0
            
            # Подсчитываем количество сообщений в MD файле
            message_count = 0
            with open(md_file, 'r', encoding='utf-8') as f:
                for line in f:
                    # Ищем строки, которые начинаются с заголовка сообщения (обычно ## или ###)
                    if line.strip().startswith('## ') or line.strip().startswith('### '):
                        # Проверяем, что это действительно заголовок сообщения, а не другой заголовок
                        # Обычно заголовки сообщений содержат дату в формате DD.MM.YYYY HH:MM
                        import re
                        # Паттерн для даты в заголовке сообщения
                        date_pattern = r'\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}'
                        if re.search(date_pattern, line):
                            message_count += 1
            
            self.logger.info(f"MD file for {channel.title} contains {message_count} messages, expected {channel.total_messages}")
            
            # Сравниваем с ожидаемым количеством
            return message_count == channel.total_messages, message_count
            
        except Exception as e:
            self.logger.error(f"Error verifying MD file count for {channel.title}: {e}")
            return False, 0

    def _create_notification(self, channel: ChannelInfo, messages_count: int, success: bool, error: str = None) -> str:
        """Создание текста уведомления"""
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
                async def export_missing_channels():
                    for channel in channels_needing_export:
                        try:
                            await self.export_channel(channel)
                        except Exception as e:
                            self.logger.error(f"Error exporting channel {channel.title} for missing MD file: {e}")
                
                # Создаем задачу для асинхронного выполнения
                asyncio.create_task(export_missing_channels())
                
        except Exception as e:
            self.logger.error(f"Error checking missing MD files: {e}")

    async def run(self):
        """Запуск приложения"""
        try:
            self.console.print("[bold blue]🚀 Telegram Channel Exporter запускается...[/bold blue]")
            
            # Инициализация клиента
            if not await self.initialize_client():
                return
            
            # Загрузка каналов
            self.load_channels()
            
            # Если каналы не загружены, предлагаем выбрать
            if not self.channels:
                self.console.print("[yellow]⚠ Каналы не найдены. Выберите каналы для мониторинга.[/yellow]")
                await self.select_channels()
            
            if not self.channels:
                self.console.print("[red]❌ Каналы не выбраны. Завершение работы.[/red]")
                return
            
            self.stats.total_channels = len(self.channels)
            
            # Запуск основного цикла
            await self.main_loop()
            
        except Exception as e:
            self.logger.error(f"Application error: {e}")
            self.console.print(f"[red]❌ Критическая ошибка приложения: {e}[/red]")
        finally:
            self.console.print("[bold blue]👋 До свидания![/bold blue]")


async def main():
    """Точка входа в приложение"""
    exporter = TelegramExporter()
    await exporter.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПолучен сигнал завершения (Ctrl+C)...")
    except Exception as e:
        print(f"Критическая ошибка: {e}")