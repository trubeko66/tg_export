#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Методы для управления настройками
"""

import time
from pathlib import Path
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel


class SettingsMethods:
    """Методы для управления настройками"""
    
    def __init__(self, console, config_manager):
        self.console = console
        self.config_manager = config_manager
    
    async def show_config_management(self):
        """Управление конфигурацией"""
        self.console.clear()
        
        config_panel = Panel(
            "🔧 Управление конфигурацией\n\n"
            "1. 📁 Загрузить конфигурацию из файла\n"
            "2. 💾 Сохранить конфигурацию в файл\n"
            "3. 🔄 Перезагрузить конфигурацию\n"
            "4. 📋 Показать путь к файлу конфигурации\n"
            "0. 🔙 Назад",
            title="🔧 Управление конфигурацией",
            border_style="cyan"
        )
        
        self.console.print(config_panel)
        
        choice = Prompt.ask(
            "Выберите действие",
            choices=["1", "2", "3", "4", "0"]
        )
        
        if choice == "0":
            return
        
        try:
            if choice == "1":
                file_path = Prompt.ask("Введите путь к файлу конфигурации")
                if Path(file_path).exists():
                    self.config_manager.config_file = Path(file_path)
                    self.config_manager.config = self.config_manager._load_config()
                    self.console.print("[green]✅ Конфигурация загружена[/green]")
                else:
                    self.console.print("[red]❌ Файл не найден[/red]")
            
            elif choice == "2":
                file_path = Prompt.ask("Введите путь для сохранения", default=".config.json")
                self.config_manager.config_file = Path(file_path)
                self.config_manager.save_config()
                self.console.print(f"[green]✅ Конфигурация сохранена в {file_path}[/green]")
            
            elif choice == "3":
                self.config_manager.config = self.config_manager._load_config()
                self.console.print("[green]✅ Конфигурация перезагружена[/green]")
            
            elif choice == "4":
                self.console.print(f"[blue]📁 Путь к конфигурации: {self.config_manager.config_file.absolute()}[/blue]")
                
        except Exception as e:
            self.console.print(f"[red]Ошибка: {e}[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def show_telegram_settings(self):
        """Настройки Telegram API"""
        self.console.clear()
        
        config = self.config_manager.config
        
        telegram_panel = Panel(
            f"📱 Настройки Telegram API\n\n"
            f"Текущие настройки:\n"
            f"• API ID: {config.telegram.api_id or 'Не настроен'}\n"
            f"• API Hash: {'*' * 8 if config.telegram.api_hash else 'Не настроен'}\n"
            f"• Phone: {config.telegram.phone or 'Не настроен'}\n\n"
            f"1. ✏️ Изменить API ID\n"
            f"2. ✏️ Изменить API Hash\n"
            f"3. ✏️ Изменить номер телефона\n"
            f"4. 🔄 Сбросить настройки Telegram\n"
            f"0. 🔙 Назад",
            title="📱 Настройки Telegram API",
            border_style="green"
        )
        
        self.console.print(telegram_panel)
        
        choice = Prompt.ask(
            "Выберите действие",
            choices=["1", "2", "3", "4", "0"]
        )
        
        if choice == "0":
            return
        
        try:
            if choice == "1":
                new_api_id = Prompt.ask("Введите новый API ID")
                if new_api_id.isdigit():
                    config.telegram.api_id = int(new_api_id)
                    self.console.print("[green]✅ API ID обновлен[/green]")
                else:
                    self.console.print("[red]❌ API ID должен быть числом[/red]")
            
            elif choice == "2":
                new_api_hash = Prompt.ask("Введите новый API Hash")
                config.telegram.api_hash = new_api_hash
                self.console.print("[green]✅ API Hash обновлен[/green]")
            
            elif choice == "3":
                new_phone = Prompt.ask("Введите новый номер телефона")
                config.telegram.phone = new_phone
                self.console.print("[green]✅ Номер телефона обновлен[/green]")
            
            elif choice == "4":
                if Confirm.ask("Вы уверены, что хотите сбросить настройки Telegram?"):
                    config.telegram.api_id = None
                    config.telegram.api_hash = None
                    config.telegram.phone = None
                    self.console.print("[green]✅ Настройки Telegram сброшены[/green]")
                
        except Exception as e:
            self.console.print(f"[red]Ошибка: {e}[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def show_bot_settings(self):
        """Настройки бота"""
        self.console.clear()
        
        config = self.config_manager.config
        
        bot_panel = Panel(
            f"🤖 Настройки бота\n\n"
            f"Текущие настройки:\n"
            f"• Bot Token: {'*' * 8 if config.bot.token else 'Не настроен'}\n"
            f"• Chat ID: {config.bot.chat_id or 'Не настроен'}\n"
            f"• Notifications: {config.bot.notifications}\n\n"
            f"1. ✏️ Изменить Bot Token\n"
            f"2. ✏️ Изменить Chat ID\n"
            f"3. 🔔 Включить/выключить уведомления\n"
            f"4. 🧪 Тест бота\n"
            f"0. 🔙 Назад",
            title="🤖 Настройки бота",
            border_style="magenta"
        )
        
        self.console.print(bot_panel)
        
        choice = Prompt.ask(
            "Выберите действие",
            choices=["1", "2", "3", "4", "0"]
        )
        
        if choice == "0":
            return
        
        try:
            if choice == "1":
                new_token = Prompt.ask("Введите новый Bot Token")
                config.bot.token = new_token
                self.console.print("[green]✅ Bot Token обновлен[/green]")
            
            elif choice == "2":
                new_chat_id = Prompt.ask("Введите новый Chat ID")
                if new_chat_id.lstrip('-').isdigit():
                    config.bot.chat_id = int(new_chat_id)
                    self.console.print("[green]✅ Chat ID обновлен[/green]")
                else:
                    self.console.print("[red]❌ Chat ID должен быть числом[/red]")
            
            elif choice == "3":
                config.bot.notifications = not config.bot.notifications
                status = "включены" if config.bot.notifications else "выключены"
                self.console.print(f"[green]✅ Уведомления {status}[/green]")
            
            elif choice == "4":
                await self.test_bot()
                
        except Exception as e:
            self.console.print(f"[red]Ошибка: {e}[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def show_webdav_settings(self):
        """Настройки WebDAV"""
        self.console.clear()
        
        config = self.config_manager.config
        
        webdav_panel = Panel(
            f"☁️ Настройки WebDAV\n\n"
            f"Текущие настройки:\n"
            f"• URL: {config.webdav.url or 'Не настроен'}\n"
            f"• Username: {config.webdav.username or 'Не настроен'}\n"
            f"• Password: {'*' * 8 if config.webdav.password else 'Не настроен'}\n"
            f"• Enabled: {config.webdav.enabled}\n\n"
            f"1. ✏️ Изменить URL\n"
            f"2. ✏️ Изменить Username\n"
            f"3. ✏️ Изменить Password\n"
            f"4. 🔄 Включить/выключить WebDAV\n"
            f"5. 🧪 Тест WebDAV\n"
            f"0. 🔙 Назад",
            title="☁️ Настройки WebDAV",
            border_style="blue"
        )
        
        self.console.print(webdav_panel)
        
        choice = Prompt.ask(
            "Выберите действие",
            choices=["1", "2", "3", "4", "5", "0"]
        )
        
        if choice == "0":
            return
        
        try:
            if choice == "1":
                new_url = Prompt.ask("Введите новый URL")
                config.webdav.url = new_url
                self.console.print("[green]✅ URL обновлен[/green]")
            
            elif choice == "2":
                new_username = Prompt.ask("Введите новый Username")
                config.webdav.username = new_username
                self.console.print("[green]✅ Username обновлен[/green]")
            
            elif choice == "3":
                new_password = Prompt.ask("Введите новый Password", password=True)
                config.webdav.password = new_password
                self.console.print("[green]✅ Password обновлен[/green]")
            
            elif choice == "4":
                config.webdav.enabled = not config.webdav.enabled
                status = "включен" if config.webdav.enabled else "выключен"
                self.console.print(f"[green]✅ WebDAV {status}[/green]")
            
            elif choice == "5":
                await self.test_webdav()
                
        except Exception as e:
            self.console.print(f"[red]Ошибка: {e}[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def show_storage_settings(self):
        """Настройки хранения"""
        self.console.clear()
        
        config = self.config_manager.config
        
        storage_panel = Panel(
            f"🗂️ Настройки хранения\n\n"
            f"Текущие настройки:\n"
            f"• Export Directory: {config.storage.export_base_dir}\n"
            f"• Media Threads: {config.storage.media_download_threads}\n"
            f"• Adaptive Download: {config.storage.adaptive_download}\n"
            f"• Min Delay: {config.storage.min_download_delay}s\n"
            f"• Max Delay: {config.storage.max_download_delay}s\n\n"
            f"1. ✏️ Изменить директорию экспорта\n"
            f"2. ✏️ Изменить количество потоков\n"
            f"3. ✏️ Изменить задержки\n"
            f"4. 🔄 Включить/выключить адаптивную загрузку\n"
            f"5. 📁 Проверить директорию\n"
            f"0. 🔙 Назад",
            title="🗂️ Настройки хранения",
            border_style="yellow"
        )
        
        self.console.print(storage_panel)
        
        choice = Prompt.ask(
            "Выберите действие",
            choices=["1", "2", "3", "4", "5", "0"]
        )
        
        if choice == "0":
            return
        
        try:
            if choice == "1":
                new_dir = Prompt.ask("Введите новую директорию экспорта", default=config.storage.export_base_dir)
                config.storage.export_base_dir = new_dir
                self.console.print(f"[green]✅ Директория экспорта обновлена: {new_dir}[/green]")
            
            elif choice == "2":
                new_threads = IntPrompt.ask("Введите количество потоков", default=config.storage.media_download_threads)
                if 1 <= new_threads <= 32:
                    config.storage.media_download_threads = new_threads
                    self.console.print(f"[green]✅ Количество потоков обновлено: {new_threads}[/green]")
                else:
                    self.console.print("[red]❌ Количество потоков должно быть от 1 до 32[/red]")
            
            elif choice == "3":
                min_delay = Prompt.ask("Введите минимальную задержку (секунды)", default=str(config.storage.min_download_delay))
                max_delay = Prompt.ask("Введите максимальную задержку (секунды)", default=str(config.storage.max_download_delay))
                try:
                    config.storage.min_download_delay = float(min_delay)
                    config.storage.max_download_delay = float(max_delay)
                    self.console.print("[green]✅ Задержки обновлены[/green]")
                except ValueError:
                    self.console.print("[red]❌ Задержки должны быть числами[/red]")
            
            elif choice == "4":
                config.storage.adaptive_download = not config.storage.adaptive_download
                status = "включена" if config.storage.adaptive_download else "выключена"
                self.console.print(f"[green]✅ Адаптивная загрузка {status}[/green]")
            
            elif choice == "5":
                export_dir = Path(config.storage.export_base_dir)
                if export_dir.exists():
                    self.console.print(f"[green]✅ Директория существует: {export_dir.absolute()}[/green]")
                    self.console.print(f"[blue]📁 Содержимое: {len(list(export_dir.iterdir()))} элементов[/blue]")
                else:
                    self.console.print(f"[yellow]⚠️ Директория не существует: {export_dir.absolute()}[/yellow]")
                    if Confirm.ask("Создать директорию?"):
                        export_dir.mkdir(parents=True, exist_ok=True)
                        self.console.print("[green]✅ Директория создана[/green]")
                
        except Exception as e:
            self.console.print(f"[red]Ошибка: {e}[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def reset_settings(self):
        """Сбросить настройки"""
        self.console.clear()
        
        if Confirm.ask("Вы уверены, что хотите сбросить все настройки к значениям по умолчанию?"):
            self.config_manager.config = self.config_manager._load_config()
            self.console.print("[green]✅ Настройки сброшены к значениям по умолчанию[/green]")
        else:
            self.console.print("[yellow]Отменено[/yellow]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def save_settings(self):
        """Сохранить настройки"""
        self.console.clear()
        
        try:
            self.config_manager.save_config()
            self.console.print("[green]✅ Настройки сохранены[/green]")
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка сохранения: {e}[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def test_settings(self):
        """Тест настроек"""
        self.console.clear()
        
        self.console.print("[blue]🧪 Тестирование настроек...[/blue]")
        
        config = self.config_manager.config
        
        # Тест Telegram API
        if config.telegram.api_id and config.telegram.api_hash:
            self.console.print("[green]✅ Telegram API: настроен[/green]")
        else:
            self.console.print("[red]❌ Telegram API: не настроен[/red]")
        
        # Тест бота
        if config.bot.token and config.bot.chat_id:
            self.console.print("[green]✅ Bot: настроен[/green]")
        else:
            self.console.print("[red]❌ Bot: не настроен[/red]")
        
        # Тест WebDAV
        if config.webdav.enabled and config.webdav.url:
            self.console.print("[green]✅ WebDAV: настроен[/green]")
        else:
            self.console.print("[yellow]⚠️ WebDAV: не настроен или отключен[/yellow]")
        
        # Тест директории
        export_dir = Path(config.storage.export_base_dir)
        if export_dir.exists():
            self.console.print(f"[green]✅ Директория экспорта: {export_dir.absolute()}[/green]")
        else:
            self.console.print(f"[red]❌ Директория экспорта: не существует[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def test_bot(self):
        """Тест бота"""
        self.console.clear()
        
        config = self.config_manager.config
        
        if not config.bot.token or not config.bot.chat_id:
            self.console.print("[red]❌ Bot не настроен[/red]")
            input("Нажмите Enter для продолжения...")
            return
        
        self.console.print("[blue]🧪 Тестирование бота...[/blue]")
        
        try:
            import requests
            
            # Отправляем тестовое сообщение
            url = f"https://api.telegram.org/bot{config.bot.token}/sendMessage"
            data = {
                'chat_id': config.bot.chat_id,
                'text': '🧪 Тестовое сообщение от Telegram Channel Exporter'
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                self.console.print("[green]✅ Тестовое сообщение отправлено успешно[/green]")
            else:
                self.console.print(f"[red]❌ Ошибка отправки: {response.status_code}[/red]")
                
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка тестирования бота: {e}[/red]")
        
        input("\nНажмите Enter для продолжения...")
    
    async def test_webdav(self):
        """Тест WebDAV"""
        self.console.clear()
        
        config = self.config_manager.config
        
        if not config.webdav.enabled or not config.webdav.url:
            self.console.print("[red]❌ WebDAV не настроен или отключен[/red]")
            input("Нажмите Enter для продолжения...")
            return
        
        self.console.print("[blue]🧪 Тестирование WebDAV...[/blue]")
        
        try:
            import requests
            from requests.auth import HTTPBasicAuth
            
            # Тестируем подключение
            auth = HTTPBasicAuth(config.webdav.username, config.webdav.password)
            response = requests.request('PROPFIND', config.webdav.url, auth=auth, timeout=10)
            
            if response.status_code in [200, 207]:
                self.console.print("[green]✅ WebDAV подключение успешно[/green]")
            else:
                self.console.print(f"[red]❌ Ошибка подключения: {response.status_code}[/red]")
                
        except Exception as e:
            self.console.print(f"[red]❌ Ошибка тестирования WebDAV: {e}[/red]")
        
        input("\nНажмите Enter для продолжения...")
