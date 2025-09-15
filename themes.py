#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Система тем оформления для Telegram Channel Exporter
"""

from dataclasses import dataclass
from typing import Dict, Any
from enum import Enum


class ThemeType(Enum):
    """Типы доступных тем"""
    SOLARIZED_DARK = "solarized_dark"
    SOLARIZED_LIGHT = "solarized_light"
    KANAGAWA = "kanagawa"
    DARCULA = "darcula"
    MONOKAI = "monokai"
    GRUVBOX = "gruvbox"
    NORD = "nord"
    TOKYO_NIGHT = "tokyo_night"
    CATPPUCCIN = "catppuccin"
    DEFAULT = "default"


@dataclass
class ThemeColors:
    """Цветовая схема темы"""
    # Основные цвета
    primary: str
    secondary: str
    accent: str
    background: str
    surface: str
    
    # Текст
    text_primary: str
    text_secondary: str
    text_muted: str
    
    # Статусы
    success: str
    warning: str
    error: str
    info: str
    
    # Элементы интерфейса
    border: str
    border_bright: str
    panel_bg: str
    
    # Анимации и индикаторы
    animation_primary: str
    animation_secondary: str
    
    # Специальные цвета
    progress_bar: str
    progress_bg: str
    table_header: str
    table_row: str


class ThemeManager:
    """Менеджер тем оформления"""
    
    def __init__(self):
        self.current_theme = ThemeType.DEFAULT
        self.themes = self._initialize_themes()
    
    def _initialize_themes(self) -> Dict[ThemeType, ThemeColors]:
        """Инициализация всех доступных тем"""
        return {
            ThemeType.DEFAULT: ThemeColors(
                primary="blue",
                secondary="cyan",
                accent="magenta",
                background="black",
                surface="bright_black",
                text_primary="white",
                text_secondary="bright_white",
                text_muted="dim",
                success="green",
                warning="yellow",
                error="red",
                info="blue",
                border="blue",
                border_bright="bright_blue",
                panel_bg="bright_black",
                animation_primary="cyan",
                animation_secondary="magenta",
                progress_bar="green",
                progress_bg="dim",
                table_header="bold white",
                table_row="white"
            ),
            
            ThemeType.SOLARIZED_DARK: ThemeColors(
                primary="#268bd2",  # blue
                secondary="#2aa198",  # cyan
                accent="#d33682",  # magenta
                background="#002b36",  # base03
                surface="#073642",  # base02
                text_primary="#93a1a1",  # base1
                text_secondary="#eee8d5",  # base2
                text_muted="#586e75",  # base01
                success="#859900",  # green
                warning="#b58900",  # yellow
                error="#dc322f",  # red
                info="#268bd2",  # blue
                border="#586e75",  # base01
                border_bright="#93a1a1",  # base1
                panel_bg="#073642",  # base02
                animation_primary="#2aa198",  # cyan
                animation_secondary="#d33682",  # magenta
                progress_bar="#859900",  # green
                progress_bg="#586e75",  # base01
                table_header="bold #eee8d5",  # base2
                table_row="#93a1a1"  # base1
            ),
            
            ThemeType.SOLARIZED_LIGHT: ThemeColors(
                primary="#268bd2",  # blue
                secondary="#2aa198",  # cyan
                accent="#d33682",  # magenta
                background="#fdf6e3",  # base3
                surface="#eee8d5",  # base2
                text_primary="#586e75",  # base01
                text_secondary="#073642",  # base02
                text_muted="#93a1a1",  # base1
                success="#859900",  # green
                warning="#b58900",  # yellow
                error="#dc322f",  # red
                info="#268bd2",  # blue
                border="#93a1a1",  # base1
                border_bright="#586e75",  # base01
                panel_bg="#eee8d5",  # base2
                animation_primary="#2aa198",  # cyan
                animation_secondary="#d33682",  # magenta
                progress_bar="#859900",  # green
                progress_bg="#93a1a1",  # base1
                table_header="bold #073642",  # base02
                table_row="#586e75"  # base01
            ),
            
            ThemeType.KANAGAWA: ThemeColors(
                primary="#7e9cd8",  # blue
                secondary="#6a9589",  # teal
                accent="#c34043",  # red
                background="#1f1f28",  # sumiInk0
                surface="#16161d",  # sumiInk1
                text_primary="#dcd7ba",  # fujiWhite
                text_secondary="#c8c093",  # oldWhite
                text_muted="#727169",  # fujiGray
                success="#76946a",  # green
                warning="#c0a36e",  # yellow
                error="#c34043",  # red
                info="#7e9cd8",  # blue
                border="#54546d",  # sumiInk3
                border_bright="#727169",  # fujiGray
                panel_bg="#16161d",  # sumiInk1
                animation_primary="#6a9589",  # teal
                animation_secondary="#c34043",  # red
                progress_bar="#76946a",  # green
                progress_bg="#54546d",  # sumiInk3
                table_header="bold #dcd7ba",  # fujiWhite
                table_row="#c8c093"  # oldWhite
            ),
            
            ThemeType.DARCULA: ThemeColors(
                primary="#4fc1ff",  # blue
                secondary="#56b6c2",  # cyan
                accent="#c678dd",  # purple
                background="#2b2b2b",  # background
                surface="#3c3f41",  # panel
                text_primary="#a9b7c6",  # text
                text_secondary="#ffffff",  # bright text
                text_muted="#808080",  # muted
                success="#629755",  # green
                warning="#d19a66",  # orange
                error="#f44747",  # red
                info="#4fc1ff",  # blue
                border="#555555",  # border
                border_bright="#808080",  # bright border
                panel_bg="#3c3f41",  # panel
                animation_primary="#56b6c2",  # cyan
                animation_secondary="#c678dd",  # purple
                progress_bar="#629755",  # green
                progress_bg="#555555",  # border
                table_header="bold #ffffff",  # bright text
                table_row="#a9b7c6"  # text
            ),
            
            ThemeType.MONOKAI: ThemeColors(
                primary="#66d9ef",  # blue
                secondary="#a6e22e",  # green
                accent="#f92672",  # pink
                background="#272822",  # background
                surface="#3e3d32",  # surface
                text_primary="#f8f8f2",  # text
                text_secondary="#ffffff",  # bright text
                text_muted="#75715e",  # muted
                success="#a6e22e",  # green
                warning="#e6db74",  # yellow
                error="#f92672",  # red
                info="#66d9ef",  # blue
                border="#75715e",  # muted
                border_bright="#f8f8f2",  # text
                panel_bg="#3e3d32",  # surface
                animation_primary="#a6e22e",  # green
                animation_secondary="#f92672",  # pink
                progress_bar="#a6e22e",  # green
                progress_bg="#75715e",  # muted
                table_header="bold #ffffff",  # bright text
                table_row="#f8f8f2"  # text
            ),
            
            ThemeType.GRUVBOX: ThemeColors(
                primary="#83a598",  # blue
                secondary="#8ec07c",  # green
                accent="#d3869b",  # pink
                background="#282828",  # bg0
                surface="#3c3836",  # bg1
                text_primary="#ebdbb2",  # fg1
                text_secondary="#fbf1c7",  # fg0
                text_muted="#928374",  # gray
                success="#b8bb26",  # green
                warning="#fabd2f",  # yellow
                error="#fb4934",  # red
                info="#83a598",  # blue
                border="#504945",  # bg2
                border_bright="#928374",  # gray
                panel_bg="#3c3836",  # bg1
                animation_primary="#8ec07c",  # green
                animation_secondary="#d3869b",  # pink
                progress_bar="#b8bb26",  # green
                progress_bg="#504945",  # bg2
                table_header="bold #fbf1c7",  # fg0
                table_row="#ebdbb2"  # fg1
            ),
            
            ThemeType.NORD: ThemeColors(
                primary="#81a1c1",  # blue
                secondary="#88c0d0",  # cyan
                accent="#b48ead",  # purple
                background="#2e3440",  # polar night 0
                surface="#3b4252",  # polar night 1
                text_primary="#d8dee9",  # snow storm 0
                text_secondary="#eceff4",  # snow storm 2
                text_muted="#4c566a",  # polar night 2
                success="#a3be8c",  # green
                warning="#ebcb8b",  # yellow
                error="#bf616a",  # red
                info="#81a1c1",  # blue
                border="#4c566a",  # polar night 2
                border_bright="#d8dee9",  # snow storm 0
                panel_bg="#3b4252",  # polar night 1
                animation_primary="#88c0d0",  # cyan
                animation_secondary="#b48ead",  # purple
                progress_bar="#a3be8c",  # green
                progress_bg="#4c566a",  # polar night 2
                table_header="bold #eceff4",  # snow storm 2
                table_row="#d8dee9"  # snow storm 0
            ),
            
            ThemeType.TOKYO_NIGHT: ThemeColors(
                primary="#7aa2f7",  # blue
                secondary="#7dcfff",  # cyan
                accent="#bb9af7",  # purple
                background="#1a1b26",  # background
                surface="#24283b",  # surface
                text_primary="#a9b1d6",  # text
                text_secondary="#ffffff",  # bright text
                text_muted="#565f89",  # muted
                success="#9ece6a",  # green
                warning="#e0af68",  # yellow
                error="#f7768e",  # red
                info="#7aa2f7",  # blue
                border="#565f89",  # muted
                border_bright="#a9b1d6",  # text
                panel_bg="#24283b",  # surface
                animation_primary="#7dcfff",  # cyan
                animation_secondary="#bb9af7",  # purple
                progress_bar="#9ece6a",  # green
                progress_bg="#565f89",  # muted
                table_header="bold #ffffff",  # bright text
                table_row="#a9b1d6"  # text
            ),
            
            ThemeType.CATPPUCCIN: ThemeColors(
                primary="#89b4fa",  # blue
                secondary="#89dceb",  # sky
                accent="#cba6f7",  # mauve
                background="#1e1e2e",  # base
                surface="#313244",  # surface0
                text_primary="#cdd6f4",  # text
                text_secondary="#ffffff",  # bright text
                text_muted="#6c7086",  # overlay0
                success="#a6e3a1",  # green
                warning="#f9e2af",  # yellow
                error="#f38ba8",  # red
                info="#89b4fa",  # blue
                border="#6c7086",  # overlay0
                border_bright="#cdd6f4",  # text
                panel_bg="#313244",  # surface0
                animation_primary="#89dceb",  # sky
                animation_secondary="#cba6f7",  # mauve
                progress_bar="#a6e3a1",  # green
                progress_bg="#6c7086",  # overlay0
                table_header="bold #ffffff",  # bright text
                table_row="#cdd6f4"  # text
            )
        }
    
    def get_theme(self, theme_type: ThemeType = None) -> ThemeColors:
        """Получить цвета текущей или указанной темы"""
        if theme_type is None:
            theme_type = self.current_theme
        return self.themes.get(theme_type, self.themes[ThemeType.DEFAULT])
    
    def set_theme(self, theme_type: ThemeType):
        """Установить текущую тему"""
        if theme_type in self.themes:
            self.current_theme = theme_type
    
    def get_available_themes(self) -> Dict[str, str]:
        """Получить список доступных тем с описаниями"""
        return {
            "default": "Стандартная тема (синяя)",
            "solarized_dark": "Solarized Dark (классическая темная)",
            "solarized_light": "Solarized Light (классическая светлая)",
            "kanagawa": "Kanagawa (японская эстетика)",
            "darcula": "Darcula (IntelliJ IDEA)",
            "monokai": "Monokai (Sublime Text)",
            "gruvbox": "Gruvbox (ретро-стиль)",
            "nord": "Nord (минималистичная)",
            "tokyo_night": "Tokyo Night (современная темная)",
            "catppuccin": "Catppuccin (пастельная)"
        }
    
    def get_theme_name(self, theme_type: ThemeType) -> str:
        """Получить человекочитаемое название темы"""
        names = {
            ThemeType.DEFAULT: "Стандартная",
            ThemeType.SOLARIZED_DARK: "Solarized Dark",
            ThemeType.SOLARIZED_LIGHT: "Solarized Light",
            ThemeType.KANAGAWA: "Kanagawa",
            ThemeType.DARCULA: "Darcula",
            ThemeType.MONOKAI: "Monokai",
            ThemeType.GRUVBOX: "Gruvbox",
            ThemeType.NORD: "Nord",
            ThemeType.TOKYO_NIGHT: "Tokyo Night",
            ThemeType.CATPPUCCIN: "Catppuccin"
        }
        return names.get(theme_type, "Неизвестная")
