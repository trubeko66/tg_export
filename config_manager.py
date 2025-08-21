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
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    enabled: bool = False


@dataclass
class StorageConfig:
    """Конфигурация локального хранилища"""
    channels_path: Optional[str] = ".channels"
    export_base_dir: Optional[str] = "exports"


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
        self.config = self._load_config()
    
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
        return (self.config.bot.enabled and 
                self.config.bot.bot_token and 
                self.config.bot.chat_id)
    
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
        bot_token = Prompt.ask("Bot Token", password=True, default=self.config.bot.bot_token or "")
        chat_id = Prompt.ask("Chat ID для уведомлений", default=self.config.bot.chat_id or "")
        
        # Проверка работы бота
        if self._test_bot(bot_token, chat_id):
            self.config.bot.bot_token = bot_token
            self.config.bot.chat_id = chat_id
            self.config.bot.enabled = True
            
            self.save_config()
            self.console.print("[green]✓ Конфигурация бота сохранена[/green]")
        else:
            self.console.print("[red]✗ Не удалось настроить бота[/red]")
            if Confirm.ask("Сохранить настройки бота несмотря на ошибку?"):
                self.config.bot.bot_token = bot_token
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
            self.config.telegram.api_id[:10] + "..." if self.config.telegram.api_id and len(self.config.telegram.api_id) > 10 else self.config.telegram.api_id or "Не задано",
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
                "***скрыто***" if self.config.bot.bot_token else "Не задано",
                "✓ Настроено" if self.config.bot.bot_token else "✗ Не настроено"
            )
            
            table.add_row(
                "Chat ID", 
                self.config.bot.chat_id or "Не задано",
                "✓ Настроено" if self.config.bot.chat_id else "✗ Не настроено"
            )
        
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
        """Настройка пути хранения списка каналов"""
        storage = self.config.storage
        self.console.print("\n[bold blue]Настройка хранилища каналов[/bold blue]")
        default_path = storage.channels_path or ".channels"
        new_path = Prompt.ask("Путь к локальному файлу со списком каналов", default=default_path)
        export_dir_default = storage.export_base_dir or "exports"
        export_dir = Prompt.ask("Каталог для сохранения экспортируемых каналов", default=export_dir_default)
        self.config.storage.channels_path = new_path
        self.config.storage.export_base_dir = export_dir
        self.save_config()
        self.console.print(f"[green]✓ Пути сохранены: channels={new_path}, export_dir={export_dir}[/green]")

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