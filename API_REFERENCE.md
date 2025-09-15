# 🔧 API Reference - Telegram Channel Exporter

## 📋 Содержание

1. [Основные классы](#основные-классы)
2. [Методы TelegramExporter](#методы-telegramexporter)
3. [Методы ConfigManager](#методы-configmanager)
4. [Система тем](#система-тем)
5. [Модули экспорта](#модули-экспорта)
6. [Фильтрация контента](#фильтрация-контента)
7. [Уведомления](#уведомления)
8. [Структуры данных](#структуры-данных)
9. [Константы](#константы)

---

## 🏗️ Основные классы

### `TelegramExporter`

Главный класс программы для экспорта Telegram каналов.

```python
class TelegramExporter:
    """Основной класс для экспорта Telegram каналов"""
    
    # Константы
    BATCH_SIZE = 1000                    # Размер батча для обработки сообщений
    MAX_MESSAGES_PER_EXPORT = 50000      # Максимум сообщений за один экспорт
    MAX_RETRIES = 3                      # Максимум попыток повтора
    RETRY_DELAY = 5                      # Задержка между попытками (сек)
    
    def __init__(self):
        """Инициализация экспортера"""
```

### `ChannelInfo`

Структура данных для хранения информации о канале.

```python
@dataclass
class ChannelInfo:
    """Информация о канале"""
    id: int                              # ID канала
    title: str                           # Название канала
    username: Optional[str]              # Username канала
    last_message_id: int = 0             # ID последнего сообщения
    total_messages: int = 0              # Общее количество сообщений
    last_check: Optional[str] = None     # Время последней проверки
    media_size_mb: float = 0.0           # Размер медиафайлов в МБ
    export_type: ExportType = ExportType.BOTH  # Тип экспорта
```

### `ExportStats`

Структура данных для хранения статистики экспорта.

```python
@dataclass
class ExportStats:
    """Статистика экспорта"""
    total_channels: int = 0
    total_messages: int = 0
    total_size_mb: float = 0.0
    export_errors: int = 0
    filtered_messages: int = 0
    last_export_time: Optional[str] = None
    current_export_info: Optional[str] = None
    total_messages_in_channel: int = 0
    download_speed_files_per_sec: float = 0.0
    download_speed_mb_per_sec: float = 0.0
    remaining_files_to_download: int = 0
    discovered_messages: int = 0
    exported_messages: int = 0
    md_verification_status: Optional[str] = None
    md_verification_channel: Optional[str] = None
    md_reexport_count: int = 0
    md_verification_progress: Optional[str] = None
    current_channel_name: Optional[str] = None
    last_exported_message_id: Optional[int] = None
    current_processing_message_id: Optional[int] = None
    latest_telegram_message_id: Optional[int] = None
```

### `ExportType`

Перечисление типов экспорта.

```python
class ExportType(Enum):
    """Типы экспорта"""
    BOTH = "both"                        # Сообщения и файлы
    MESSAGES_ONLY = "messages_only"      # Только сообщения
    FILES_ONLY = "files_only"            # Только файлы
```

---

## 🔧 Методы TelegramExporter

### Инициализация и подключение

#### `__init__(self)`
Инициализация экспортера.
```python
def __init__(self):
    """Инициализация экспортера"""
```

#### `initialize_client(self, force_reauth: bool = False)`
Инициализация клиента Telegram.
```python
async def initialize_client(self, force_reauth: bool = False):
    """
    Инициализация клиента Telegram
    
    Args:
        force_reauth (bool): Принудительная повторная аутентификация
    """
```

#### `_clear_session(self, session_name: str)`
Очистка сессии Telegram.
```python
async def _clear_session(self, session_name: str):
    """
    Очистка сессии Telegram
    
    Args:
        session_name (str): Имя сессии
    """
```

#### `_check_and_unlock_session(self, session_name: str)`
Проверка и разблокировка сессии.
```python
async def _check_and_unlock_session(self, session_name: str):
    """
    Проверка и разблокировка сессии
    
    Args:
        session_name (str): Имя сессии
    """
```

### Управление каналами

#### `load_channels(self) -> bool`
Загрузка списка каналов из файла.
```python
def load_channels(self) -> bool:
    """
    Загрузка списка каналов из файла
    
    Returns:
        bool: True если загрузка успешна
    """
```

#### `save_channels(self)`
Сохранение списка каналов в файл.
```python
def save_channels(self):
    """Сохранение списка каналов в файл"""
```

#### `select_channels(self)`
Интерактивный выбор каналов для мониторинга.
```python
async def select_channels(self):
    """Интерактивный выбор каналов для мониторинга"""
```

#### `display_channels_page(self, dialogs: list, page: int, selected_ids: Optional[set] = None, page_size: int = 10) -> Table`
Отображение страницы каналов в таблице.
```python
def display_channels_page(self, dialogs: list, page: int, selected_ids: Optional[set] = None, page_size: int = 10) -> Table:
    """
    Отображение страницы каналов в таблице
    
    Args:
        dialogs (list): Список диалогов
        page (int): Номер страницы
        selected_ids (Optional[set]): Множество выбранных ID
        page_size (int): Размер страницы
        
    Returns:
        Table: Таблица каналов
    """
```

### Экспорт данных

#### `export_channel(self, channel: ChannelInfo)`
Экспорт канала.
```python
async def export_channel(self, channel: ChannelInfo):
    """
    Экспорт канала
    
    Args:
        channel (ChannelInfo): Информация о канале
    """
```

#### `export_all_channels(self)`
Экспорт всех каналов.
```python
async def export_all_channels(self):
    """Экспорт всех каналов"""
```

#### `_check_and_append_new_messages(self, channel: ChannelInfo) -> int`
Проверка и добавление новых сообщений.
```python
async def _check_and_append_new_messages(self, channel: ChannelInfo) -> int:
    """
    Проверка и добавление новых сообщений
    
    Args:
        channel (ChannelInfo): Информация о канале
        
    Returns:
        int: Количество новых сообщений
    """
```

### Повторный экспорт

#### `_reexport_all_channels_to_markdown(self)`
Повторный экспорт всех каналов в Markdown.
```python
async def _reexport_all_channels_to_markdown(self):
    """Повторный экспорт всех каналов в Markdown"""
```

#### `_reexport_channel_to_markdown(self, channel: ChannelInfo)`
Повторный экспорт канала в Markdown.
```python
async def _reexport_channel_to_markdown(self, channel: ChannelInfo):
    """
    Повторный экспорт канала в Markdown
    
    Args:
        channel (ChannelInfo): Информация о канале
    """
```

#### `_reexport_channel_to_all_formats(self, channel: ChannelInfo)`
Повторный экспорт канала во всех форматах.
```python
async def _reexport_channel_to_all_formats(self, channel: ChannelInfo):
    """
    Повторный экспорт канала во всех форматах
    
    Args:
        channel (ChannelInfo): Информация о канале
    """
```

### Мониторинг и планировщик

#### `run_scheduler(self)`
Запуск планировщика задач.
```python
async def run_scheduler(self):
    """Запуск планировщика задач"""
```

#### `_daily_check_new_messages(self)`
Ежедневная проверка новых сообщений.
```python
async def _daily_check_new_messages(self):
    """Ежедневная проверка новых сообщений"""
```

### Интерфейс пользователя

#### `create_status_display(self) -> Layout`
Создание отображения статуса.
```python
def create_status_display(self) -> Layout:
    """
    Создание отображения статуса
    
    Returns:
        Layout: Макет интерфейса
    """
```

#### `_create_detailed_channels_table(self) -> Table`
Создание детальной таблицы каналов.
```python
def _create_detailed_channels_table(self) -> Table:
    """
    Создание детальной таблицы каналов
    
    Returns:
        Table: Таблица каналов
    """
```

#### `_create_detailed_statistics(self) -> Text`
Создание детальной статистики.
```python
def _create_detailed_statistics(self) -> Text:
    """
    Создание детальной статистики
    
    Returns:
        Text: Текст статистики
    """
```

#### `_create_footer_info(self) -> Text`
Создание информации в футере.
```python
def _create_footer_info(self) -> Text:
    """
    Создание информации в футере
    
    Returns:
        Text: Текст футера
    """
```

### Настройки экспорта

#### `configure_export_types(self)`
Настройка типов экспорта.
```python
def configure_export_types(self):
    """Настройка типов экспорта"""
```

#### `_configure_single_channel_export_type(self)`
Настройка типа экспорта для одного канала.
```python
def _configure_single_channel_export_type(self):
    """Настройка типа экспорта для одного канала"""
```

#### `_configure_all_channels_export_type(self)`
Настройка типа экспорта для всех каналов.
```python
def _configure_all_channels_export_type(self):
    """Настройка типа экспорта для всех каналов"""
```

#### `_choose_export_type(self) -> Optional[ExportType]`
Выбор типа экспорта.
```python
def _choose_export_type(self) -> Optional[ExportType]:
    """
    Выбор типа экспорта
    
    Returns:
        Optional[ExportType]: Выбранный тип экспорта
    """
```

### Утилиты

#### `_sanitize_channel_filename(self, channel_title: str) -> str`
Очистка названия канала для использования в имени файла.
```python
def _sanitize_channel_filename(self, channel_title: str) -> str:
    """
    Очистка названия канала для использования в имени файла
    
    Args:
        channel_title (str): Название канала
        
    Returns:
        str: Очищенное название
    """
```

#### `_get_channels_file_path(self) -> Path`
Получение пути к файлу каналов.
```python
def _get_channels_file_path(self) -> Path:
    """
    Получение пути к файлу каналов
    
    Returns:
        Path: Путь к файлу
    """
```

#### `reset_channel_export_state(self, channel_title: str) -> bool`
Сброс состояния экспорта канала.
```python
def reset_channel_export_state(self, channel_title: str) -> bool:
    """
    Сброс состояния экспорта канала
    
    Args:
        channel_title (str): Название канала
        
    Returns:
        bool: True если сброс успешен
    """
```

#### `list_channels_with_issues(self) -> List[str]`
Список каналов с проблемами.
```python
def list_channels_with_issues(self) -> List[str]:
    """
    Список каналов с проблемами
    
    Returns:
        List[str]: Список названий каналов с проблемами
    """
```

### Основной цикл

#### `run(self)`
Основной метод запуска программы.
```python
async def run(self):
    """Основной метод запуска программы"""
```

#### `main_loop(self)`
Главный цикл программы.
```python
async def main_loop(self):
    """Главный цикл программы"""
```

#### `_post_loading_menu(self)`
Меню после загрузки.
```python
async def _post_loading_menu(self):
    """Меню после загрузки"""
```

---

## ⚙️ Методы ConfigManager

### Инициализация

#### `__init__(self, config_file: str = ".config.json")`
Инициализация менеджера конфигурации.
```python
def __init__(self, config_file: str = ".config.json"):
    """
    Инициализация менеджера конфигурации
    
    Args:
        config_file (str): Путь к файлу конфигурации
    """
```

### Загрузка и сохранение

#### `load_config(self) -> bool`
Загрузка конфигурации из файла.
```python
def load_config(self) -> bool:
    """
    Загрузка конфигурации из файла
    
    Returns:
        bool: True если загрузка успешна
    """
```

#### `save_config(self) -> bool`
Сохранение конфигурации в файл.
```python
def save_config(self) -> bool:
    """
    Сохранение конфигурации в файл
    
    Returns:
        bool: True если сохранение успешно
    """
```

### Интерактивная настройка

#### `interactive_setup(self) -> bool`
Интерактивная настройка конфигурации.
```python
def interactive_setup(self) -> bool:
    """
    Интерактивная настройка конфигурации
    
    Returns:
        bool: True если настройка завершена
    """
```

#### `setup_telegram_config(self) -> bool`
Настройка конфигурации Telegram.
```python
def setup_telegram_config(self) -> bool:
    """
    Настройка конфигурации Telegram
    
    Returns:
        bool: True если настройка завершена
    """
```

#### `setup_bot_config(self) -> bool`
Настройка конфигурации бота.
```python
def setup_bot_config(self) -> bool:
    """
    Настройка конфигурации бота
    
    Returns:
        bool: True если настройка завершена
    """
```

#### `setup_webdav_config(self) -> bool`
Настройка конфигурации WebDAV.
```python
def setup_webdav_config(self) -> bool:
    """
    Настройка конфигурации WebDAV
    
    Returns:
        bool: True если настройка завершена
    """
```

#### `setup_filter_config(self) -> bool`
Настройка конфигурации фильтрации.
```python
def setup_filter_config(self) -> bool:
    """
    Настройка конфигурации фильтрации
    
    Returns:
        bool: True если настройка завершена
    """
```

### Отображение конфигурации

#### `show_current_config(self)`
Отображение текущей конфигурации.
```python
def show_current_config(self):
    """Отображение текущей конфигурации"""
```

#### `show_telegram_config(self)`
Отображение конфигурации Telegram.
```python
def show_telegram_config(self):
    """Отображение конфигурации Telegram"""
```

#### `show_bot_config(self)`
Отображение конфигурации бота.
```python
def show_bot_config(self):
    """Отображение конфигурации бота"""
```

#### `show_webdav_config(self)`
Отображение конфигурации WebDAV.
```python
def show_webdav_config(self):
    """Отображение конфигурации WebDAV"""
```

#### `show_filter_config(self)`
Отображение конфигурации фильтрации.
```python
def show_filter_config(self):
    """Отображение конфигурации фильтрации"""
```

#### `configure_theme(self)`
Настройка темы оформления.
```python
def configure_theme(self):
    """Настройка темы оформления"""
```

#### `set_theme(self, theme_id: str) -> bool`
Установка темы оформления.
```python
def set_theme(self, theme_id: str) -> bool:
    """
    Установка темы оформления
    
    Args:
        theme_id (str): ID темы
        
    Returns:
        bool: True если тема установлена успешно
    """
```

---

## 🌈 Система тем

### `ThemeManager`

Менеджер тем оформления.

```python
class ThemeManager:
    """Менеджер тем оформления"""
    
    def __init__(self):
        """Инициализация менеджера тем"""
```

#### `get_available_themes(self) -> Dict[str, str]`
Получение списка доступных тем.
```python
def get_available_themes(self) -> Dict[str, str]:
    """
    Получение списка доступных тем
    
    Returns:
        Dict[str, str]: Словарь {theme_id: theme_name}
    """
```

#### `get_theme(self, theme_type: ThemeType) -> ThemeColors`
Получение цветовой схемы темы.
```python
def get_theme(self, theme_type: ThemeType) -> ThemeColors:
    """
    Получение цветовой схемы темы
    
    Args:
        theme_type (ThemeType): Тип темы
        
    Returns:
        ThemeColors: Цветовая схема темы
    """
```

#### `set_theme(self, theme_type: ThemeType)`
Установка активной темы.
```python
def set_theme(self, theme_type: ThemeType):
    """
    Установка активной темы
    
    Args:
        theme_type (ThemeType): Тип темы
    """
```

### `ThemeType`

Перечисление типов тем.

```python
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
```

### `ThemeColors`

Структура цветовой схемы темы.

```python
@dataclass
class ThemeColors:
    """Цветовая схема темы"""
    # Основные цвета
    primary: str          # Основной цвет
    secondary: str        # Вторичный цвет
    accent: str           # Акцентный цвет
    background: str       # Цвет фона
    surface: str          # Цвет поверхностей
    
    # Текст
    text_primary: str     # Основной текст
    text_secondary: str   # Вторичный текст
    text_muted: str       # Приглушенный текст
    
    # Статусы
    success: str          # Успех
    warning: str          # Предупреждение
    error: str            # Ошибка
    info: str             # Информация
    
    # Элементы интерфейса
    border: str           # Границы
    border_bright: str    # Яркие границы
    panel_bg: str         # Фон панелей
    
    # Анимации
    animation_primary: str    # Основная анимация
    animation_secondary: str  # Вторичная анимация
    
    # Специальные
    progress_bar: str     # Прогресс-бары
    progress_bg: str      # Фон прогресс-баров
    table_header: str     # Заголовки таблиц
    table_row: str        # Строки таблиц
```

### `ThemeConfig`

Конфигурация темы.

```python
@dataclass
class ThemeConfig:
    """Конфигурация темы оформления"""
    theme: str = "default"    # Текущая тема
    auto_apply: bool = True   # Автоматически применять тему при запуске
```

---

## 📤 Модули экспорта

### `BaseExporter`

Базовый класс для всех экспортеров.

```python
class BaseExporter:
    """Базовый класс для экспортеров"""
    
    def __init__(self, export_dir: Path):
        """
        Инициализация экспортера
        
        Args:
            export_dir (Path): Директория экспорта
        """
```

### `JSONExporter`

Экспортер в формат JSON.

```python
class JSONExporter(BaseExporter):
    """Экспортер в формат JSON"""
    
    def export_messages(self, messages: List[MessageData], channel_name: str) -> bool:
        """
        Экспорт сообщений в JSON
        
        Args:
            messages (List[MessageData]): Список сообщений
            channel_name (str): Название канала
            
        Returns:
            bool: True если экспорт успешен
        """
```

### `HTMLExporter`

Экспортер в формат HTML.

```python
class HTMLExporter(BaseExporter):
    """Экспортер в формат HTML"""
    
    def export_messages(self, messages: List[MessageData], channel_name: str) -> bool:
        """
        Экспорт сообщений в HTML
        
        Args:
            messages (List[MessageData]): Список сообщений
            channel_name (str): Название канала
            
        Returns:
            bool: True если экспорт успешен
        """
    
    def generate_index(self, channels: List[str]) -> bool:
        """
        Генерация индексной страницы
        
        Args:
            channels (List[str]): Список каналов
            
        Returns:
            bool: True если генерация успешна
        """
```

### `MarkdownExporter`

Экспортер в формат Markdown.

```python
class MarkdownExporter(BaseExporter):
    """Экспортер в формат Markdown"""
    
    def export_messages(self, messages: List[MessageData], channel_name: str) -> bool:
        """
        Экспорт сообщений в Markdown
        
        Args:
            messages (List[MessageData]): Список сообщений
            channel_name (str): Название канала
            
        Returns:
            bool: True если экспорт успешен
        """
    
    def format_message(self, message: MessageData) -> str:
        """
        Форматирование сообщения в Markdown
        
        Args:
            message (MessageData): Данные сообщения
            
        Returns:
            str: Отформатированное сообщение
        """
```

### `MediaDownloader`

Загрузчик медиафайлов.

```python
class MediaDownloader:
    """Загрузчик медиафайлов"""
    
    def __init__(self, export_dir: Path, max_threads: int = 4):
        """
        Инициализация загрузчика
        
        Args:
            export_dir (Path): Директория экспорта
            max_threads (int): Максимальное количество потоков
        """
    
    def download_media(self, message: MessageData, channel_name: str) -> Optional[str]:
        """
        Загрузка медиафайла
        
        Args:
            message (MessageData): Данные сообщения
            channel_name (str): Название канала
            
        Returns:
            Optional[str]: Путь к загруженному файлу
        """
    
    def get_media_path(self, message: MessageData, channel_name: str) -> Path:
        """
        Получение пути к медиафайлу
        
        Args:
            message (MessageData): Данные сообщения
            channel_name (str): Название канала
            
        Returns:
            Path: Путь к медиафайлу
        """
```

---

## 🔍 Фильтрация контента

### `ContentFilter`

Класс для фильтрации контента.

```python
class ContentFilter:
    """Фильтр контента"""
    
    def __init__(self, config: FilterConfig):
        """
        Инициализация фильтра
        
        Args:
            config (FilterConfig): Конфигурация фильтра
        """
    
    def should_filter(self, text: str) -> bool:
        """
        Проверка, нужно ли фильтровать текст
        
        Args:
            text (str): Текст для проверки
            
        Returns:
            bool: True если текст нужно отфильтровать
        """
    
    def filter_message(self, message: MessageData) -> bool:
        """
        Фильтрация сообщения
        
        Args:
            message (MessageData): Данные сообщения
            
        Returns:
            bool: True если сообщение отфильтровано
        """
```

### `FilterConfig`

Конфигурация фильтра.

```python
@dataclass
class FilterConfig:
    """Конфигурация фильтра"""
    enabled: bool = True                   # Включен ли фильтр
    keywords: List[str] = field(default_factory=list)  # Ключевые слова
    case_sensitive: bool = False           # Учитывать регистр
    exclude_patterns: List[str] = field(default_factory=list)  # Паттерны исключения
```

---

## 🔔 Уведомления

### `TelegramNotifications`

Класс для отправки уведомлений через Telegram бота.

```python
class TelegramNotifications:
    """Уведомления через Telegram бота"""
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Инициализация уведомлений
        
        Args:
            bot_token (str): Токен бота
            chat_id (str): ID чата
        """
    
    async def send_notification(self, message: str) -> bool:
        """
        Отправка уведомления
        
        Args:
            message (str): Текст уведомления
            
        Returns:
            bool: True если отправка успешна
        """
    
    async def send_daily_summary(self, summary: str) -> bool:
        """
        Отправка ежедневной сводки
        
        Args:
            summary (str): Текст сводки
            
        Returns:
            bool: True если отправка успешна
        """
```

---

## 📊 Структуры данных

### `MessageData`

Структура данных сообщения.

```python
@dataclass
class MessageData:
    """Данные сообщения"""
    id: int                                # ID сообщения
    date: datetime                         # Дата сообщения
    text: str                              # Текст сообщения
    media: Optional[MessageMedia] = None   # Медиафайл
    channel: str                           # Название канала
    author: Optional[str] = None           # Автор сообщения
    views: Optional[int] = None            # Количество просмотров
    forwards: Optional[int] = None         # Количество пересылок
```

### `TelegramConfig`

Конфигурация Telegram API.

```python
@dataclass
class TelegramConfig:
    """Конфигурация Telegram API"""
    api_id: Optional[str] = None           # API ID
    api_hash: Optional[str] = None         # API Hash
    phone: Optional[str] = None            # Номер телефона
```

### `BotConfig`

Конфигурация бота.

```python
@dataclass
class BotConfig:
    """Конфигурация бота"""
    token: Optional[str] = None            # Токен бота
    chat_id: Optional[str] = None          # ID чата
    notifications: bool = True             # Включены ли уведомления
    enabled: bool = False                  # Включен ли бот
```

### `StorageConfig`

Конфигурация хранилища.

```python
@dataclass
class StorageConfig:
    """Конфигурация хранилища"""
    channels_path: Optional[str] = ".channels"  # Путь к файлу каналов
    export_base_dir: Optional[str] = "exports"  # Базовая директория экспорта
    media_download_threads: int = 4             # Количество потоков загрузки
    adaptive_download: bool = True              # Адаптивная загрузка
    min_download_delay: float = 0.1             # Минимальная задержка
    max_download_delay: float = 3.0             # Максимальная задержка
```

### `WebDavConfig`

Конфигурация WebDAV.

```python
@dataclass
class WebDavConfig:
    """Конфигурация WebDAV"""
    enabled: bool = False                  # Включен ли WebDAV
    url: Optional[str] = None              # URL сервера
    username: Optional[str] = None         # Имя пользователя
    password: Optional[str] = None         # Пароль
    remote_path: Optional[str] = None      # Удаленный путь
```

---

## 🔧 Константы

### Константы TelegramExporter

```python
class TelegramExporter:
    BATCH_SIZE = 1000                      # Размер батча для обработки сообщений
    MAX_MESSAGES_PER_EXPORT = 50000        # Максимум сообщений за один экспорт
    MAX_RETRIES = 3                        # Максимум попыток повтора
    RETRY_DELAY = 5                        # Задержка между попытками (сек)
```

### Константы экспорта

```python
# Форматы экспорта
EXPORT_FORMATS = ["json", "html", "markdown"]

# Типы медиафайлов
MEDIA_TYPES = {
    "photo": "photos",
    "video": "videos", 
    "document": "documents",
    "audio": "audio",
    "voice": "voice",
    "video_note": "video_notes"
}
```

### Константы интерфейса

```python
# Размеры интерфейса
UI_CONSTANTS = {
    "PAGE_SIZE": 10,                       # Размер страницы каналов
    "MAX_TITLE_LENGTH": 50,                # Максимальная длина названия
    "REFRESH_INTERVAL": 1,                 # Интервал обновления (сек)
    "ANIMATION_SPEED": 0.5                 # Скорость анимации
}
```

---

## 🎯 Примеры использования API

### Пример 1: Создание экспортера

```python
from telegram_exporter import TelegramExporter, ChannelInfo, ExportType

# Создание экспортера
exporter = TelegramExporter()

# Создание информации о канале
channel = ChannelInfo(
    id=123456789,
    title="Test Channel",
    username="testchannel",
    export_type=ExportType.BOTH
)

# Добавление канала в список
exporter.channels.append(channel)
```

### Пример 2: Настройка конфигурации

```python
from config_manager import ConfigManager, TelegramConfig, BotConfig

# Создание менеджера конфигурации
config_manager = ConfigManager()

# Настройка Telegram
config_manager.config.telegram = TelegramConfig(
    api_id="your_api_id",
    api_hash="your_api_hash",
    phone="+1234567890"
)

# Настройка бота
config_manager.config.bot = BotConfig(
    token="your_bot_token",
    chat_id="your_chat_id",
    enabled=True
)

# Сохранение конфигурации
config_manager.save_config()
```

### Пример 3: Экспорт канала

```python
import asyncio
from telegram_exporter import TelegramExporter, ChannelInfo

async def export_channel_example():
    # Создание экспортера
    exporter = TelegramExporter()
    
    # Инициализация клиента
    await exporter.initialize_client()
    
    # Создание канала
    channel = ChannelInfo(
        id=123456789,
        title="Example Channel",
        username="examplechannel"
    )
    
    # Экспорт канала
    await exporter.export_channel(channel)

# Запуск
asyncio.run(export_channel_example())
```

### Пример 4: Работа с фильтром

```python
from content_filter import ContentFilter, FilterConfig

# Создание конфигурации фильтра
filter_config = FilterConfig(
    enabled=True,
    keywords=["реклама", "спам"],
    case_sensitive=False,
    exclude_patterns=["*реклама*"]
)

# Создание фильтра
content_filter = ContentFilter(filter_config)

# Проверка текста
text = "Это рекламное сообщение"
is_filtered = content_filter.should_filter(text)
print(f"Сообщение отфильтровано: {is_filtered}")
```

### Пример 5: Работа с темами оформления

```python
from themes import ThemeManager, ThemeType, ThemeColors
from config_manager import ConfigManager, ThemeConfig

# Создание менеджера тем
theme_manager = ThemeManager()

# Получение списка доступных тем
available_themes = theme_manager.get_available_themes()
print("Доступные темы:")
for theme_id, theme_name in available_themes.items():
    print(f"  {theme_id}: {theme_name}")

# Установка темы
theme_manager.set_theme(ThemeType.SOLARIZED_DARK)

# Получение цветовой схемы темы
colors = theme_manager.get_theme(ThemeType.SOLARIZED_DARK)
print(f"Основной цвет: {colors.primary}")
print(f"Цвет фона: {colors.background}")

# Настройка темы через конфигурацию
config_manager = ConfigManager()
config_manager.config.theme = ThemeConfig(
    theme="solarized_dark",
    auto_apply=True
)
config_manager.save_config()
```

### Пример 6: Отправка уведомлений

```python
import asyncio
from telegram_notifications import TelegramNotifications

async def send_notification_example():
    # Создание уведомлений
    notifications = TelegramNotifications(
        bot_token="your_bot_token",
        chat_id="your_chat_id"
    )
    
    # Отправка уведомления
    success = await notifications.send_notification(
        "🆕 Новые сообщения в канале Test Channel"
    )
    
    print(f"Уведомление отправлено: {success}")

# Запуск
asyncio.run(send_notification_example())
```

---

## 📝 Примечания

### Обработка ошибок

Все методы API могут вызывать исключения. Рекомендуется использовать try-except блоки:

```python
try:
    await exporter.export_channel(channel)
except Exception as e:
    print(f"Ошибка экспорта: {e}")
```

### Асинхронность

Большинство методов являются асинхронными и должны вызываться с `await` или в `asyncio.run()`.

### Типизация

Все методы используют типизацию для лучшей читаемости и отладки кода.

---

*API Reference обновлен: 15.01.2024*
*Версия: 2.0*
