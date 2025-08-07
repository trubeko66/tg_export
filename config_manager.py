#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль управления конфигурацией
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
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
class AppConfig:
    """Общая конфигурация приложения"""
    telegram: TelegramConfig
    bot: BotConfig
    first_run: bool = True


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
                
                return AppConfig(
                    telegram=telegram_config,
                    bot=bot_config,
                    first_run=data.get('first_run', True)
                )
            except Exception as e:
                self.console.print(f"[yellow]Ошибка загрузки конфигурации: {e}[/yellow]")
                self.console.print("[yellow]Создается новая конфигурация[/yellow]")
        
        # Создание конфигурации по умолчанию
        return AppConfig(
            telegram=TelegramConfig(),
            bot=BotConfig(),
            first_run=True
        )
    
    def save_config(self):
        """Сохранение конфигурации в файл"""
        try:
            config_data = {
                'telegram': asdict(self.config.telegram),
                'bot': asdict(self.config.bot),
                'first_run': self.config.first_run
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
            self.console.print("3. Показать текущую конфигурацию")
            self.console.print("4. Сбросить конфигурацию")
            self.console.print("5. Продолжить с текущими настройками")
            self.console.print("0. Выход")
            
            choice = Prompt.ask("\nВыберите действие", choices=["0", "1", "2", "3", "4", "5"])
            
            if choice == "1":
                self.setup_telegram_config(force_setup=True)
            elif choice == "2":
                self.setup_bot_config(force_setup=True)
            elif choice == "3":
                input("\nНажмите Enter для продолжения...")
            elif choice == "4":
                if Confirm.ask("Вы уверены, что хотите сбросить всю конфигурацию?"):
                    self.reset_config()
            elif choice == "5":
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
                first_run=True
            )
            
            self.console.print("[green]✓ Конфигурация сброшена[/green]")
            
        except Exception as e:
            self.console.print(f"[red]Ошибка сброса конфигурации: {e}[/red]")
    
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