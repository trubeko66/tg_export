#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль управления конфигурацией
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict, field
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table
from rich import box
import getpass


@dataclass
class TelegramConfig:
    """Конфигурация Telegram API"""
    api_id: Optional[str] = None
    api_hash: Optional[str] = None
    phone: Optional[str] = None


@dataclass
class BotConfig:
    """Конфигурация бота для уведомлений"""
    token: Optional[str] = None  # Изменено с bot_token на token
    chat_id: Optional[str] = None
    notifications: bool = True  # Добавлено поле notifications
    enabled: bool = False


@dataclass
class StorageConfig:
    """Конфигурация хранилища"""
    channels_path: Optional[str] = ".channels"
    export_base_dir: Optional[str] = "exports"
    media_download_threads: int = 4  # Количество потоков для загрузки медиафайлов
    adaptive_download: bool = True  # Включить адаптивное управление загрузкой
    min_download_delay: float = 0.1  # Минимальная задержка между загрузками (сек)
    max_download_delay: float = 3.0  # Максимальная задержка между загрузками (сек)


@dataclass
class WebDavConfig:
    """Конфигурация WebDAV синхронизации"""
    enabled: bool = False
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    remote_path: Optional[str] = "/channels/.channels"
    auto_sync: bool = False
    notify_on_sync: bool = True
    upload_archives: bool = False
    archives_remote_dir: Optional[str] = "/channels/archives"


@dataclass
class AppConfig:
    """Общая конфигурация приложения"""
    telegram: TelegramConfig
    bot: BotConfig
    first_run: bool = True
    storage: StorageConfig = field(default_factory=StorageConfig)
    webdav: WebDavConfig = field(default_factory=WebDavConfig)


    


class ConfigManager:
    """Менеджер конфигурации"""
    
    def __init__(self, config_file: str = ".config.json"):
        self.config_file = Path(config_file)
        self.console = Console()
        try:
            self.config = self._load_config()
        except Exception as e:
            self.console.print(f"[yellow]⚠️ Ошибка загрузки конфигурации: {e}[/yellow]")
            self.console.print("[yellow]Создается конфигурация по умолчанию[/yellow]")
            # Создаем конфигурацию по умолчанию
            self.config = AppConfig(
                telegram=TelegramConfig(),
                bot=BotConfig(),
                first_run=True,
                storage=StorageConfig(),
                webdav=WebDavConfig()
            )
    
    def _load_config(self) -> AppConfig:
        """Загрузка конфигурации из файла"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                telegram_config = TelegramConfig(**data.get('telegram', {}))
                bot_config = BotConfig(**data.get('bot', {}))
                
                storage_cfg = StorageConfig(**data.get('storage', {})) if isinstance(data.get('storage', {}), dict) else StorageConfig()
                webdav_cfg = WebDavConfig(**data.get('webdav', {})) if isinstance(data.get('webdav', {}), dict) else WebDavConfig()
                return AppConfig(
                    telegram=telegram_config,
                    bot=bot_config,
                    first_run=data.get('first_run', True),
                    storage=storage_cfg,
                    webdav=webdav_cfg
                )
            except Exception as e:
                self.console.print(f"[yellow]Ошибка загрузки конфигурации: {e}[/yellow]")
                self.console.print("[yellow]Создается новая конфигурация[/yellow]")
        
        # Создание конфигурации по умолчанию
        return AppConfig(
            telegram=TelegramConfig(),
            bot=BotConfig(),
            first_run=True,
            storage=StorageConfig(),
            webdav=WebDavConfig()
        )
    
    def save_config(self):
        """Сохранение конфигурации в файл"""
        try:
            config_data = {
                'telegram': asdict(self.config.telegram),
                'bot': asdict(self.config.bot),
                'first_run': self.config.first_run,
                'storage': asdict(self.config.storage),
                'webdav': asdict(self.config.webdav)
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.console.print(f"[red]Ошибка сохранения конфигурации: {e}[/red]")
    
    def is_telegram_configured(self) -> bool:
        """Проверка настройки Telegram API"""
        return (self.config.telegram.api_id and 
                self.config.telegram.api_hash and 
                self.config.telegram.phone)
    
    def is_bot_configured(self) -> bool:
        """Проверка настройки бота"""
        has_token_and_chat = (self.config.bot.token and 
                             self.config.bot.chat_id)
        
        # Если токен и chat_id настроены, но enabled = False, автоматически включаем
        if has_token_and_chat and not self.config.bot.enabled:
            self.config.bot.enabled = True
            self.save_config()
        
        return has_token_and_chat
    
    def setup_telegram_config(self, force_setup: bool = False):
        """Настройка конфигурации Telegram API"""
        if self.is_telegram_configured() and not force_setup:
            if not Confirm.ask("Telegram API уже настроен. Изменить настройки?"):
                return
        
        self.console.print("\n[bold blue]Настройка Telegram API[/bold blue]")
        self.console.print(Panel(
            "Для получения API ID и API Hash:\n"
            "1. Перейдите на https://my.telegram.org/auth\n"
            "2. Войдите в свой аккаунт Telegram\n"
            "3. Перейдите в 'API development tools'\n"
            "4. Создайте новое приложение",
            title="Инструкция",
            box=box.ROUNDED
        ))
        
        # Ввод данных
        api_id = Prompt.ask("API ID", default=self.config.telegram.api_id or "")
        api_hash = Prompt.ask("API Hash", password=True, default=self.config.telegram.api_hash or "")
        phone = Prompt.ask("Номер телефона (с кодом страны, например +7)", default=self.config.telegram.phone or "")
        
        # Сохранение конфигурации
        self.config.telegram.api_id = api_id
        self.config.telegram.api_hash = api_hash
        self.config.telegram.phone = phone
        
        self.save_config()
        self.console.print("[green]✓ Конфигурация Telegram API сохранена[/green]")
    
    def setup_bot_config(self, force_setup: bool = False):
        """Настройка конфигурации бота"""
        if not force_setup and self.config.bot.enabled:
            if not Confirm.ask("Бот уже настроен. Изменить настройки?"):
                return
        
        if not Confirm.ask("Настроить уведомления через Telegram бота?"):
            self.config.bot.enabled = False
            self.save_config()
            return
        
        self.console.print("\n[bold blue]Настройка Telegram бота[/bold blue]")
        self.console.print(Panel(
            "Для создания бота:\n"
            "1. Найдите @BotFather в Telegram\n"
            "2. Отправьте команду /newbot\n"
            "3. Следуйте инструкциям и получите Bot Token\n"
            "4. Для получения Chat ID используйте @userinfobot",
            title="Инструкция",
            box=box.ROUNDED
        ))
        
        # Ввод данных
        bot_token = Prompt.ask("Bot Token", password=True, default=self.config.bot.token or "")
        chat_id = Prompt.ask("Chat ID для уведомлений", default=self.config.bot.chat_id or "")
        
        # Проверка работы бота
        if self._test_bot(bot_token, chat_id):
            self.config.bot.token = bot_token
            self.config.bot.chat_id = chat_id
            self.config.bot.enabled = True
            
            self.save_config()
            self.console.print("[green]✓ Конфигурация бота сохранена[/green]")
        else:
            self.console.print("[red]✗ Не удалось настроить бота[/red]")
            if Confirm.ask("Сохранить настройки бота несмотря на ошибку?"):
                self.config.bot.token = bot_token
                self.config.bot.chat_id = chat_id
                self.config.bot.enabled = True
                self.save_config()
            else:
                self.config.bot.enabled = False
                self.save_config()
    
    def _test_bot(self, bot_token: str, chat_id: str) -> bool:
        """Тестирование работы бота"""
        try:
            import requests
            
            # Проверка токена бота
            url = f"https://api.telegram.org/bot{bot_token}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                self.console.print("[red]✗ Неверный токен бота[/red]")
                return False
            
            # Отправка тестового сообщения
            test_message = "🤖 Тест уведомлений Telegram Channel Exporter"
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': test_message
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                self.console.print("[green]✓ Тестовое сообщение отправлено успешно[/green]")
                return True
            else:
                self.console.print(f"[red]✗ Ошибка отправки сообщения: {response.status_code}[/red]")
                return False
                
        except Exception as e:
            self.console.print(f"[red]✗ Ошибка тестирования бота: {e}[/red]")
            return False
    
    def show_current_config(self):
        """Отображение текущей конфигурации"""
        table = Table(title="Текущая конфигурация", box=box.ROUNDED)
        table.add_column("Параметр", style="cyan")
        table.add_column("Значение", style="green")
        table.add_column("Статус", style="yellow")
        
        # Telegram API
        table.add_row(
            "API ID", 
            str(self.config.telegram.api_id)[:10] + "..." if self.config.telegram.api_id and len(str(self.config.telegram.api_id)) > 10 else str(self.config.telegram.api_id) if self.config.telegram.api_id else "Не задано",
            "✓ Настроено" if self.config.telegram.api_id else "✗ Не настроено"
        )
        
        table.add_row(
            "API Hash", 
            "***скрыто***" if self.config.telegram.api_hash else "Не задано",
            "✓ Настроено" if self.config.telegram.api_hash else "✗ Не настроено"
        )
        
        table.add_row(
            "Телефон", 
            self.config.telegram.phone or "Не задано",
            "✓ Настроено" if self.config.telegram.phone else "✗ Не настроено"
        )
        
        # Бот
        table.add_row(
            "Уведомления бота", 
            "Включены" if self.config.bot.enabled else "Отключены",
            "✓ Настроено" if self.config.bot.enabled else "✗ Отключено"
        )
        
        if self.config.bot.enabled:
            table.add_row(
                "Bot Token", 
                "***скрыто***" if self.config.bot.token else "Не задано",
                "✓ Настроено" if self.config.bot.token else "✗ Не настроено"
            )
            
            table.add_row(
                "Chat ID", 
                str(self.config.bot.chat_id) if self.config.bot.chat_id else "Не задано",
                "✓ Настроено" if self.config.bot.chat_id else "✗ Не настроено"
            )
        
        # Storage config
        if self.config.storage:
            self.console.print("\n[bold blue]Хранилище:[/bold blue]")
            self.console.print(f"  Путь к списку каналов: {self.config.storage.channels_path}")
            self.console.print(f"  Каталог экспорта: {self.config.storage.export_base_dir}")
            self.console.print(f"  Потоки загрузки медиа: {self.config.storage.media_download_threads}")
            self.console.print(f"  Адаптивная загрузка: {'✅' if self.config.storage.adaptive_download else '❌'}")
            self.console.print(f"  Задержка загрузки: {self.config.storage.min_download_delay}-{self.config.storage.max_download_delay}с")
        
        self.console.print(table)
        
        # Дополнительно: Хранилище и WebDAV
        storage = self.config.storage
        webdav = self.config.webdav
        table2 = Table(title="Хранилище и WebDAV", box=box.ROUNDED)
        table2.add_column("Параметр", style="cyan")
        table2.add_column("Значение", style="green")
        table2.add_column("Статус", style="yellow")
        table2.add_row("Путь списка каналов", storage.channels_path or ".channels", "—")
        table2.add_row("WebDAV", "Включен" if webdav.enabled else "Отключен", "—")
        if webdav.enabled:
            table2.add_row("WebDAV URL", webdav.url or "—", "✓")
            table2.add_row("Удаленный путь", webdav.remote_path or "—", "✓")
            table2.add_row("Автосинхронизация", "Включена" if webdav.auto_sync else "Отключена", "—")
            table2.add_row("Уведомления", "Включены" if webdav.notify_on_sync else "Отключены", "—")
            table2.add_row("Загрузка архивов", "Включена" if webdav.upload_archives else "Отключена", "—")
            table2.add_row("Каталог архивов", webdav.archives_remote_dir or "—", "—")
        self.console.print(table2)
    
    def interactive_setup(self):
        """Интерактивная настройка конфигурации"""
        while True:
            self.console.clear()
            self.console.print(Panel.fit(
                "[bold blue]Управление конфигурацией[/bold blue]",
                box=box.DOUBLE
            ))
            
            self.show_current_config()
            
            self.console.print("\n[bold cyan]Доступные действия:[/bold cyan]")
            self.console.print("1. Настроить Telegram API")
            self.console.print("2. Настроить бота для уведомлений")
            self.console.print("3. Настроить путь хранения списка каналов")
            self.console.print("4. Настроить WebDAV синхронизацию")
            self.console.print("5. Показать текущую конфигурацию")
            self.console.print("6. Сбросить конфигурацию")
            self.console.print("7. Продолжить с текущими настройками")
            self.console.print("0. Выход")
            
            choice = Prompt.ask("\nВыберите действие", choices=["0", "1", "2", "3", "4", "5", "6", "7"])
            
            if choice == "1":
                self.setup_telegram_config(force_setup=True)
            elif choice == "2":
                self.setup_bot_config(force_setup=True)
            elif choice == "3":
                self.setup_storage_config(force_setup=True)
            elif choice == "4":
                self.setup_webdav_config(force_setup=True)
            elif choice == "5":
                input("\nНажмите Enter для продолжения...")
            elif choice == "6":
                if Confirm.ask("Вы уверены, что хотите сбросить всю конфигурацию?"):
                    self.reset_config()
            elif choice == "7":
                break
            elif choice == "0":
                return False
        
        return True
    
    def reset_config(self):
        """Сброс конфигурации"""
        try:
            if self.config_file.exists():
                self.config_file.unlink()
            
            self.config = AppConfig(
                telegram=TelegramConfig(),
                bot=BotConfig(),
                first_run=True,
                storage=StorageConfig(),
                webdav=WebDavConfig()
            )
            
            self.console.print("[green]✓ Конфигурация сброшена[/green]")
            
        except Exception as e:
            self.console.print(f"[red]Ошибка сброса конфигурации: {e}[/red]")

    def setup_storage_config(self, force_setup: bool = False):
        """Интерактивная настройка конфигурации хранилища"""
        if not force_setup and self.config.storage.channels_path and self.config.storage.export_base_dir:
            if not Confirm.ask("Настройки хранилища уже заданы. Изменить их?"):
                return True
        
        self.console.print("\n[bold blue]Настройка хранилища[/bold blue]")
        
        # Путь для файла списка каналов
        channels_path = Prompt.ask(
            "Путь для сохранения списка каналов",
            default=self.config.storage.channels_path or ".channels"
        )
        
        # Базовый каталог для экспорта
        export_base_dir = Prompt.ask(
            "Базовый каталог для экспорта каналов",
            default=self.config.storage.export_base_dir or "exports"
        )
        
        # Количество потоков для загрузки медиа
        media_threads = Prompt.ask(
            "Количество потоков для загрузки медиафайлов (1-16)",
            default=str(self.config.storage.media_download_threads or 4)
        )
        
        try:
            media_threads_int = int(media_threads)
            if media_threads_int < 1 or media_threads_int > 16:
                self.console.print("[yellow]Количество потоков должно быть от 1 до 16. Установлено значение 4.[/yellow]")
                media_threads_int = 4
        except ValueError:
            self.console.print("[yellow]Неверное значение. Установлено количество потоков 4.[/yellow]")
            media_threads_int = 4
        
        self.config.storage.channels_path = channels_path
        self.config.storage.export_base_dir = export_base_dir
        self.config.storage.media_download_threads = media_threads_int
        
        self.save_config()
        self.console.print("[green]✓ Настройки хранилища сохранены[/green]")
        return True

    def setup_webdav_config(self, force_setup: bool = False):
        """Настройка WebDAV синхронизации"""
        webdav = self.config.webdav
        self.console.print("\n[bold blue]Настройка WebDAV[/bold blue]")
        enabled = Confirm.ask("Включить синхронизацию WebDAV?", default=webdav.enabled)
        if not enabled:
            webdav.enabled = False
            self.save_config()
            self.console.print("[yellow]WebDAV синхронизация отключена[/yellow]")
            return
        base_url = Prompt.ask("Базовый URL WebDAV", default=webdav.url or "")
        username = Prompt.ask("Имя пользователя", default=webdav.username or "")
        password = Prompt.ask("Пароль", password=True, default=webdav.password or "")
        remote_path = Prompt.ask("Удаленный путь к файлу (например /channels/.channels)", default=webdav.remote_path or "/channels/.channels")
        auto_sync = Confirm.ask("Включить автосинхронизацию (загрузка/выгрузка .channels)?", default=webdav.auto_sync)
        notify_on_sync = Confirm.ask("Отправлять уведомление в Telegram при успешной синхронизации?", default=webdav.notify_on_sync)
        upload_archives = Confirm.ask("Разрешить выгрузку ZIP-архивов каналов на WebDAV?", default=webdav.upload_archives)
        archives_remote_dir = Prompt.ask("Каталог на WebDAV для архивов", default=webdav.archives_remote_dir or "/channels/archives")
        webdav.enabled = True
        webdav.url = base_url
        webdav.username = username
        webdav.password = password
        webdav.remote_path = remote_path
        webdav.auto_sync = auto_sync
        webdav.notify_on_sync = notify_on_sync
        webdav.upload_archives = upload_archives
        webdav.archives_remote_dir = archives_remote_dir
        self.save_config()
        self.console.print("[green]✓ Конфигурация WebDAV сохранена[/green]")
    
    def ensure_configured(self) -> bool:
        """Убедиться, что конфигурация настроена"""
        # Проверка первого запуска
        if self.config.first_run:
            self.console.print(Panel.fit(
                "[bold green]Добро пожаловать в Telegram Channel Exporter![/bold green]\n"
                "Для начала работы необходимо настроить конфигурацию.",
                box=box.DOUBLE
            ))
            self.config.first_run = False
            self.save_config()
        
        # Проверка настройки Telegram API
        if not self.is_telegram_configured():
            self.console.print("[yellow]⚠ Telegram API не настроен[/yellow]")
            self.setup_telegram_config()
        
        # Проверка настройки бота (опционально)
        if not self.config.bot.enabled and self.config.first_run:
            self.setup_bot_config()
        
        # Финальная проверка
        if not self.is_telegram_configured():
            self.console.print("[red]✗ Telegram API не настроен. Невозможно продолжить.[/red]")
            return False
        
        return True
    
    def get_telegram_config(self) -> TelegramConfig:
        """Получение конфигурации Telegram"""
        return self.config.telegram
    
    def get_bot_config(self) -> BotConfig:
        """Получение конфигурации бота"""
        return self.config.bot
    
    def export_channels(self, channels: list, file_path: Optional[str] = None) -> bool:
        """Экспорт списка каналов в файл"""
        try:
            if file_path is None:
                file_path = self.config.storage.channels_path or ".channels"
            
            channels_data = []
            for channel in channels:
                if hasattr(channel, 'title') and hasattr(channel, 'id'):
                    channels_data.append({
                        'id': getattr(channel, 'id', 0),
                        'title': channel.title,
                        'username': getattr(channel, 'username', ''),
                        'last_message_id': getattr(channel, 'last_message_id', 0),
                        'total_messages': getattr(channel, 'total_messages', 0),
                        'last_check': getattr(channel, 'last_check', None),
                        'media_size_mb': getattr(channel, 'media_size_mb', 0.0)
                    })
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(channels_data, f, ensure_ascii=False, indent=2)
            
            self.console.print(f"[green]✅ Каналы экспортированы в {file_path}[/green]")
            return True
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка экспорта каналов: {e}[/red]")
            return False
    
    def import_channels(self, file_path: Optional[str] = None) -> list:
        """Импорт списка каналов из файла"""
        try:
            if file_path is None:
                file_path = self.config.storage.channels_path or ".channels"
            
            if not Path(file_path).exists():
                self.console.print(f"[yellow]⚠️ Файл {file_path} не найден[/yellow]")
                return []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                channels_data = json.load(f)
            
            # Создаем объекты ChannelInfo из данных
            from telegram_exporter import ChannelInfo
            channels = []
            for data in channels_data:
                channel = ChannelInfo(
                    id=data.get('id', 0),
                    title=data.get('title', ''),
                    username=data.get('username', ''),
                    last_message_id=data.get('last_message_id', 0),
                    total_messages=data.get('total_messages', 0),
                    last_check=data.get('last_check'),
                    media_size_mb=data.get('media_size_mb', 0.0)
                )
                channels.append(channel)
            
            self.console.print(f"[green]✅ Импортировано {len(channels)} каналов из {file_path}[/green]")
            return channels
            
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка импорта каналов: {e}[/red]")
            return []
    
    def get_channels_file_path(self) -> str:
        """Получить путь к файлу каналов"""
        return self.config.storage.channels_path or ".channels"
    
    def channels_file_exists(self) -> bool:
        """Проверить существование файла каналов"""
        return Path(self.get_channels_file_path()).exists()
    
    def update_channel_last_message_id(self, channel_id: int, last_message_id: int):
        """Обновить last_message_id для канала в файле .channels"""
        try:
            file_path = self.get_channels_file_path()
            if not Path(file_path).exists():
                self.console.print(f"[yellow]⚠️ Файл {file_path} не найден[/yellow]")
                return False
            
            # Загружаем текущие данные
            with open(file_path, 'r', encoding='utf-8') as f:
                channels_data = json.load(f)
            
            # Находим и обновляем канал
            updated = False
            for channel_data in channels_data:
                if channel_data.get('id') == channel_id:
                    channel_data['last_message_id'] = last_message_id
                    updated = True
                    break
            
            if updated:
                # Сохраняем обновленные данные
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(channels_data, f, ensure_ascii=False, indent=2)
                self.console.print(f"[green]✅ Обновлен last_message_id={last_message_id} для канала {channel_id}[/green]")
                return True
            else:
                self.console.print(f"[yellow]⚠️ Канал {channel_id} не найден в файле[/yellow]")
                return False
                
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка обновления last_message_id: {e}[/red]")
            return False
    
    def add_channel_to_file(self, channel_info: dict):
        """Добавить канал в файл .channels"""
        try:
            channels_file = Path(self.get_channels_file_path())
            
            # Загружаем существующие каналы
            existing_channels = []
            if channels_file.exists():
                with open(channels_file, 'r', encoding='utf-8') as f:
                    existing_channels = json.load(f)
            
            # Проверяем, не существует ли уже канал с таким ID
            channel_id = channel_info['id']
            for existing_channel in existing_channels:
                if existing_channel.get('id') == channel_id:
                    raise ValueError(f"Канал с ID {channel_id} уже существует в файле")
            
            # Добавляем новый канал
            existing_channels.append(channel_info)
            
            # Сохраняем обновленный список
            with open(channels_file, 'w', encoding='utf-8') as f:
                json.dump(existing_channels, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            raise Exception(f"Ошибка добавления канала в файл: {e}")