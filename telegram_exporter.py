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
    MessageData, JSONExporter, HTMLExporter, MarkdownExporter, MediaDownloader
)
from config_manager import ConfigManager


@dataclass
class ChannelInfo:
    """Информация о канале"""
    id: int
    title: str
    username: Optional[str]
    last_message_id: int = 0
    total_messages: int = 0
    last_check: Optional[str] = None


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


class TelegramExporter:
    def __init__(self):
        self.console = Console()
        self.client: Optional[TelegramClient] = None
        self.channels: List[ChannelInfo] = []
        self.stats = ExportStats()
        self.running = True
        
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
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Ожидается список объектов ChannelInfo
            self.channels = [ChannelInfo(**item) for item in data]
            return True
        except Exception as e:
            self.logger.error(f"Error loading channels from {file_path}: {e}")
            self.console.print(f"[red]Ошибка загрузки из файла {file_path}: {e}[/red]")
            return False

    def save_channels_to_file(self, file_path: Path) -> bool:
        """Сохранение списка каналов в произвольный JSON-файл для редактирования"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump([asdict(channel) for channel in self.channels], f,
                          ensure_ascii=False, indent=2)
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
            
            self.client = TelegramClient('session_name', telegram_config.api_id, telegram_config.api_hash)
            await self.client.start(telegram_config.phone)
            
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
        if self.channels_file.exists():
            try:
                with open(self.channels_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.channels = [ChannelInfo(**item) for item in data]
                return True
            except Exception as e:
                self.logger.error(f"Error loading channels: {e}")
        return False
    
    def save_channels(self):
        """Сохранение списка каналов в файл"""
        try:
            self.channels_file = self._get_channels_file_path()
            with open(self.channels_file, 'w', encoding='utf-8') as f:
                json.dump([asdict(channel) for channel in self.channels], f, 
                         ensure_ascii=False, indent=2)
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
        """Создание статусного экрана"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )
        
        # Заголовок
        header_text = Text("Telegram Channel Exporter", style="bold magenta")
        header_text.append(" | Статус: Работает", style="bold green")
        layout["header"].update(Panel(header_text, box=box.DOUBLE))
        
        # Информация о каналах
        channels_table = Table(title="Выбранные каналы", box=box.ROUNDED)
        channels_table.add_column("Канал", style="green")
        channels_table.add_column("Последняя проверка", style="blue")
        channels_table.add_column("Сообщений", style="yellow", justify="right")
        channels_table.add_column("Объем файлов", style="cyan", justify="right")
        
        for channel in self.channels:
            last_check = channel.last_check or "Никогда"
            
            # Вычисляем объем файлов для канала
            channel_size = 0.0
            try:
                storage_cfg = self.config_manager.config.storage  # type: ignore[attr-defined]
                base_dir = getattr(storage_cfg, 'export_base_dir', 'exports') or 'exports'
                base_path = Path(base_dir)
                channel_dir = base_path / channel.title.replace('/', '_').replace('\\', '_')
                
                if channel_dir.exists() and channel_dir.is_dir():
                    # Подсчитываем размер всех файлов в папке канала
                    for file_path in channel_dir.rglob('*'):
                        if file_path.is_file():
                            try:
                                channel_size += file_path.stat().st_size
                            except (OSError, PermissionError):
                                pass
                    channel_size = channel_size / (1024 * 1024)  # Конвертируем в МБ
            except Exception:
                channel_size = 0.0
            
            # Форматируем размер файлов
            if channel_size > 0:
                if channel_size >= 1024:
                    size_str = f"{channel_size/1024:.1f} ГБ"
                else:
                    size_str = f"{channel_size:.1f} МБ"
            else:
                size_str = "—"
            
            channels_table.add_row(
                channel.title[:30] + "..." if len(channel.title) > 30 else channel.title,
                last_check,
                str(channel.total_messages),
                size_str
            )
        
        layout["left"].update(Panel(channels_table))
        
        # Статистика
        stats_text = Text()
        stats_text.append(f"Всего каналов: {self.stats.total_channels}\n", style="cyan")
        stats_text.append(f"Всего сообщений: {self.stats.total_messages}\n", style="green")
        stats_text.append(f"Объем данных: {self.stats.total_size_mb:.2f} МБ\n", style="yellow")
        stats_text.append(f"Ошибки: {self.stats.export_errors}\n", style="red")
        stats_text.append(f"Отфильтровано: {self.stats.filtered_messages}\n", style="magenta")
        stats_text.append(f"Последний экспорт: {self.stats.last_export_time or 'Никогда'}\n", style="blue")
        
        # Добавляем информацию о текущем экспорте
        if self.stats.current_export_info:
            stats_text.append(f"\nТекущий экспорт:\n", style="green")
            stats_text.append(f"{self.stats.current_export_info}\n", style="green")
        
        layout["right"].update(Panel(stats_text, title="Статистика"))
        
        # Подвал с инструкциями
        footer_text = Text("Нажмите Ctrl+C для завершения работы", style="bold red")
        layout["footer"].update(Panel(footer_text))
        
        return layout
    
    async def run_scheduler(self):
        """Запуск планировщика задач"""
        def schedule_export():
            """Функция для планировщика"""
            if self.running:
                asyncio.create_task(self.export_all_channels())
        
        schedule.every().day.at("00:00").do(schedule_export)
        
        # Также добавляем возможность запуска экспорта при первом старте
        # если каналы не проверялись больше суток
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
        
        while self.running:
            schedule.run_pending()
            await asyncio.sleep(60)  # Проверка каждую минуту
    
    async def export_all_channels(self):
        """Экспорт всех каналов"""
        self.logger.info("Starting scheduled export of all channels")
        
        for channel in self.channels:
            try:
                await self.export_channel(channel)
            except Exception as e:
                self.logger.error(f"Export error for channel {channel.title}: {e}")
                self.stats.export_errors += 1
        
        self.stats.last_export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    async def export_channel(self, channel: ChannelInfo):
        """Экспорт конкретного канала"""
        try:
            self.logger.info(f"Starting export for channel: {channel.title}")
            
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
            channel_dir = base_path / channel.title.replace('/', '_').replace('\\', '_')
            channel_dir.mkdir(exist_ok=True)
            
            # Получение канала
            entity = await self.client.get_entity(channel.id)
            
            # Сначала подсчитываем общее количество сообщений в канале
            total_messages_in_channel = 0
            try:
                async for _ in self.client.iter_messages(entity):
                    total_messages_in_channel += 1
            except Exception as e:
                self.logger.warning(f"Could not count total messages in {channel.title}: {e}")
                total_messages_in_channel = 0
            
            self.stats.total_messages_in_channel = total_messages_in_channel
            
            # Дополнительная диагностика для понимания проблемы
            if total_messages_in_channel > 0:
                self.logger.info(f"Channel {channel.title}: Found {total_messages_in_channel} total messages")
                # Проверяем доступность первых и последних сообщений
                try:
                    first_msg = await self.client.get_messages(entity, limit=1)
                    last_msg = await self.client.get_messages(entity, limit=1, reverse=True)
                    if first_msg and last_msg:
                        self.logger.info(f"Channel {channel.title}: First message ID: {first_msg[0].id}, Last message ID: {last_msg[0].id}")
                        self.logger.info(f"Channel {channel.title}: Current last_message_id: {channel.last_message_id}")
                except Exception as e:
                    self.logger.warning(f"Could not get first/last message info for {channel.title}: {e}")
            else:
                self.logger.warning(f"Channel {channel.title}: No messages found during counting - this might indicate an access issue")
            
            # Инициализация экспортеров
            json_exporter = JSONExporter(channel.title, channel_dir)
            html_exporter = HTMLExporter(channel.title, channel_dir)
            md_exporter = MarkdownExporter(channel.title, channel_dir)
            
            # Получаем количество потоков для загрузки медиа из конфигурации
            try:
                storage_cfg = self.config_manager.config.storage  # type: ignore[attr-defined]
                media_threads = getattr(storage_cfg, 'media_download_threads', 4) or 4
            except Exception:
                media_threads = 4
            
            media_downloader = MediaDownloader(channel_dir, max_workers=media_threads)

            # Получение сообщений
            messages_data = []
            total_size = 0.0
            new_messages_count = 0
            
            # Получаем сообщения начиная с последнего обработанного
            min_id = channel.last_message_id
            
            # Если last_message_id = 0, значит это первая проверка канала - экспортируем все сообщения
            if min_id == 0:
                self.logger.info(f"First time export for channel {channel.title} - will export all {total_messages_in_channel} messages")
                min_id = None  # None означает "с самого начала"
            else:
                self.logger.info(f"Exporting new messages for channel {channel.title} starting from message ID {min_id}")
            
            try:
                # Используем правильный параметр для получения сообщений
                if min_id is None:
                    # Получаем все сообщения с самого начала
                    async for message in self.client.iter_messages(entity):
                        try:
                            # Обновляем прогресс экспорта
                            self.stats.current_export_info = f"Экспорт: {channel.title} | Обработано {len(messages_data)} из {total_messages_in_channel}"
                            
                            # Фильтрация рекламных и промо-сообщений
                            should_filter, filter_reason = self.content_filter.should_filter_message(message.text or "")
                            if should_filter:
                                self.logger.info(f"Message {message.id} filtered: {filter_reason}")
                                self.stats.filtered_messages += 1
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
                                self.stats.filtered_messages += 1
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
                self.logger.warning(f"FloodWait error for channel {channel.title}: waiting {e.seconds} seconds")
                await asyncio.sleep(e.seconds)
                # Повторная попытка после ожидания
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
                
                # Параллельная загрузка всех медиафайлов
                if media_downloader.get_queue_size() > 0:
                    self.logger.info(f"Starting parallel download of {media_downloader.get_queue_size()} media files using {media_downloader.max_workers} threads")
                    self.stats.current_export_info = f"Загрузка медиа: {channel.title} | {media_downloader.get_queue_size()} файлов | {media_downloader.max_workers} потоков"
                    
                    try:
                        downloaded_files = await media_downloader.download_queue_parallel()
                        self.logger.info(f"Successfully downloaded {len(downloaded_files)} media files")
                        
                        # Обновляем пути к медиафайлам в данных сообщений
                        for msg_data in messages_data:
                            if msg_data.media_path and msg_data.media_path.startswith("media/"):
                                # Проверяем, был ли файл успешно загружен
                                actual_path = media_downloader.get_downloaded_file(msg_data.id)
                                if actual_path:
                                    msg_data.media_path = actual_path
                                    # Подсчитываем размер файла
                                    file_size = media_downloader.get_file_size_mb(channel_dir / actual_path)
                                    total_size += file_size
                                else:
                                    # Файл не был загружен, убираем ссылку
                                    msg_data.media_path = None
                                    msg_data.media_type = None
                        
                    except Exception as e:
                        self.logger.error(f"Error during parallel media download: {e}")
                        # Продолжаем без медиафайлов
                        for msg_data in messages_data:
                            msg_data.media_path = None
                            msg_data.media_type = None
                
                # Экспорт в различные форматы
                self.logger.info(f"Exporting {len(messages_data)} new messages to existing files (incremental mode)")
                json_file = json_exporter.export_messages(messages_data, append_mode=True)
                html_file = html_exporter.export_messages(messages_data, append_mode=True)
                md_file = md_exporter.export_messages(messages_data, append_mode=True)
                
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
                
                # Обновление статистики канала
                channel.total_messages += len(messages_data)
                channel.last_check = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Обновление общей статистики
                self.stats.total_messages += len(messages_data)
                self.stats.total_size_mb += total_size
                
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
                
            else:
                self.logger.info(f"No new messages found in {channel.title}")
                channel.last_check = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Если экспорт прошел без сообщений, но в канале есть сообщения - повторная проверка
                if total_messages_in_channel > 0:
                    self.logger.info(f"Re-checking channel {channel.title} - found {total_messages_in_channel} total messages")
                    self.stats.current_export_info = f"Повторная проверка: {channel.title} | Всего сообщений: {total_messages_in_channel}"
                    
                    # Если это первая проверка и сообщений нет, но в канале они есть - принудительно экспортируем все
                    if channel.last_message_id == 0 and total_messages_in_channel > 0:
                        self.logger.warning(f"Channel {channel.title} has {total_messages_in_channel} messages but export returned 0. This might indicate an access issue.")
                        # Можно добавить дополнительную диагностику здесь
            
            # Сохранение обновленной информации о каналах
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
        """Основной цикл программы"""
        try:
            with Live(self.create_status_display(), refresh_per_second=1) as live:
                # Запуск планировщика в фоне
                scheduler_task = asyncio.create_task(self.run_scheduler())
                
                # Основной цикл
                while self.running:
                    live.update(self.create_status_display())
                    await asyncio.sleep(1)
                    
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Получен сигнал завершения...[/yellow]")
            self.running = False
            
        finally:
            if self.client:
                await self.client.disconnect()
    
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
        
        # Запуск основного цикла
        await self.main_loop()


async def main():
    """Точка входа в программу"""
    exporter = TelegramExporter()
    await exporter.run()


if __name__ == "__main__":
    asyncio.run(main())
