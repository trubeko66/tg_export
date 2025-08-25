#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль экспортеров для различных форматов
"""

import json
import html
import re
import asyncio
import concurrent.futures
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from telethon.tl.types import Message, MessageMediaPhoto, MessageMediaDocument


@dataclass
class MessageData:
    """Структура данных сообщения"""
    id: int
    date: datetime
    text: str
    author: Optional[str] = None
    media_type: Optional[str] = None
    media_path: Optional[str] = None
    views: int = 0
    forwards: int = 0
    replies: int = 0
    edited: Optional[datetime] = None


class BaseExporter:
    """Базовый класс для экспортеров"""
    
    def __init__(self, channel_name: str, output_dir: Path):
        self.channel_name = channel_name
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
    
    def sanitize_filename(self, filename: str) -> str:
        """Очистка имени файла от недопустимых символов"""
        # Удаление недопустимых символов для файловой системы
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Ограничение длины
        if len(sanitized) > 100:
            sanitized = sanitized[:100] + "..."
        return sanitized
    
    def clean_text(self, text: str) -> str:
        """Очистка текста от неподдерживаемых символов"""
        if not text:
            return ""
        
        # Удаление анимированных эмодзи и специальных символов
        # Сохраняем базовые эмодзи, но удаляем анимации
        cleaned = re.sub(r'[\u200d\ufe0f]', '', text)  # Удаляем модификаторы эмодзи
        
        # Удаляем некоторые проблемные Unicode символы
        cleaned = re.sub(r'[\u2060-\u206f]', '', cleaned)  # Word joiner и другие
        
        # Удаляем или заменяем последовательности, которые могут вызвать ошибки KaTeX
        # Паттерны, которые KaTeX может интерпретировать как LaTeX команды
        katex_problematic_patterns = [
            (r'\\-', '-'),          # \- заменяем на обычный дефис
            (r'\\\w+', ''),         # Удаляем последовательности типа \command
            (r'\$[^$]*\$', ''),     # Удаляем потенциальные математические формулы
            (r'\\[{}[\]()]', ''),   # Удаляем экранированные скобки, которые могут конфликтовать
        ]
        
        for pattern, replacement in katex_problematic_patterns:
            cleaned = re.sub(pattern, replacement, cleaned)
        
        return cleaned.strip()


class JSONExporter(BaseExporter):
    """Экспортер в JSON формат"""
    
    def export_messages(self, messages: List[MessageData], append_mode: bool = False) -> str:
        """Экспорт сообщений в JSON
        
        Args:
            messages: Список сообщений для экспорта
            append_mode: Если True, добавляет новые сообщения к существующим
        """
        output_file = self.output_dir / f"{self.sanitize_filename(self.channel_name)}.json"
        
        existing_messages = []
        if append_mode and output_file.exists():
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    existing_messages = existing_data.get("messages", [])
                    print(f"JSON: Found {len(existing_messages)} existing messages in {output_file}")
            except Exception as e:
                # Если файл поврежден, начинаем заново
                print(f"JSON: Error reading existing file {output_file}: {e}")
                existing_messages = []
        
        # Объединяем существующие и новые сообщения
        all_messages = existing_messages + self._messages_to_dict(messages)
        print(f"JSON: Merged {len(existing_messages)} existing + {len(messages)} new = {len(all_messages)} total")
        
        # Убираем дубликаты по ID сообщения
        seen_ids = set()
        unique_messages = []
        for msg in all_messages:
            if msg["id"] not in seen_ids:
                seen_ids.add(msg["id"])
                unique_messages.append(msg)
        
        print(f"JSON: After deduplication: {len(unique_messages)} unique messages")
        
        # Сортируем по ID сообщения (старые сначала)
        unique_messages.sort(key=lambda x: x["id"])
        
        data = {
            "channel_name": self.channel_name,
            "export_date": datetime.now().isoformat(),
            "total_messages": len(unique_messages),
            "messages": unique_messages
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return str(output_file)
    
    def _messages_to_dict(self, messages: List[MessageData]) -> List[Dict[str, Any]]:
        """Преобразование сообщений в словари для JSON"""
        result = []
        for msg in messages:
            message_dict = {
                "id": msg.id,
                "date": msg.date.isoformat() if msg.date else None,
                "text": self.clean_text(msg.text),
                "author": msg.author,
                "media_type": msg.media_type,
                "media_path": msg.media_path,
                "views": msg.views,
                "forwards": msg.forwards,
                "replies": msg.replies,
                "edited": msg.edited.isoformat() if msg.edited else None
            }
            result.append(message_dict)
        return result


class HTMLExporter(BaseExporter):
    """Экспортер в HTML формат"""
    
    def export_messages(self, messages: List[MessageData], append_mode: bool = False) -> str:
        """Экспорт сообщений в HTML
        
        Args:
            messages: Список сообщений для экспорта
            append_mode: Если True, добавляет новые сообщения к существующим
        """
        output_file = self.output_dir / f"{self.sanitize_filename(self.channel_name)}.html"
        
        existing_messages = []
        if append_mode and output_file.exists():
            try:
                # Читаем существующий HTML и извлекаем сообщения
                with open(output_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    existing_messages = self._extract_messages_from_html(content)
                    print(f"HTML: Found {len(existing_messages)} existing messages in {output_file}")
            except Exception as e:
                # Если файл поврежден, начинаем заново
                print(f"HTML: Error reading existing file {output_file}: {e}")
                existing_messages = []
        
        # Объединяем существующие и новые сообщения
        all_messages = existing_messages + messages
        print(f"HTML: Merged {len(existing_messages)} existing + {len(messages)} new = {len(all_messages)} total")
        
        # Убираем дубликаты по ID сообщения
        seen_ids = set()
        unique_messages = []
        for msg in all_messages:
            if msg.id not in seen_ids:
                seen_ids.add(msg.id)
                unique_messages.append(msg)
        
        print(f"HTML: After deduplication: {len(unique_messages)} unique messages")
        
        # Сортируем по ID сообщения (старые сначала)
        unique_messages.sort(key=lambda x: x.id)
        
        html_content = self._generate_html(unique_messages)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(output_file)
    
    def _extract_messages_from_html(self, html_content: str) -> List[MessageData]:
        """Извлечение сообщений из существующего HTML файла"""
        try:
            import re
            from datetime import datetime
            
            messages = []
            # Ищем блоки сообщений в HTML
            message_pattern = r'<div class="message"[^>]*>.*?<div class="message-header">.*?<span class="message-id">#(\d+)</span>.*?<span class="message-date">([^<]+)</span>.*?</div>.*?<div class="message-text">(.*?)</div>.*?</div>'
            
            matches = re.findall(message_pattern, html_content, re.DOTALL)
            
            for msg_id, date_str, text in matches:
                try:
                    # Парсим ID сообщения
                    message_id = int(msg_id)
                    
                    # Парсим дату (пробуем несколько форматов)
                    parsed_date = None
                    date_formats = [
                        '%Y-%m-%d %H:%M:%S',
                        '%Y-%m-%d %H:%M',
                        '%d.%m.%Y %H:%M:%S',
                        '%d.%m.%Y %H:%M'
                    ]
                    
                    for fmt in date_formats:
                        try:
                            parsed_date = datetime.strptime(date_str.strip(), fmt)
                            break
                        except ValueError:
                            continue
                    
                    if not parsed_date:
                        # Если не удалось распарсить, используем текущую дату
                        parsed_date = datetime.now()
                    
                    # Очищаем HTML теги из текста
                    clean_text = re.sub(r'<[^>]+>', '', text).strip()
                    
                    # Создаем объект MessageData
                    msg_data = MessageData(
                        id=message_id,
                        date=parsed_date,
                        text=clean_text,
                        author=None,
                        media_type=None,
                        media_path=None,
                        views=0,
                        forwards=0,
                        replies=0,
                        edited=None
                    )
                    
                    messages.append(msg_data)
                    
                except (ValueError, TypeError) as e:
                    # Пропускаем сообщения с ошибками парсинга
                    continue
            
            return messages
            
        except Exception as e:
            # В случае ошибки возвращаем пустой список
            return []
    
    def _generate_html(self, messages: List[MessageData]) -> str:
        """Генерация HTML контента"""
        html_template = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{channel_name} - Экспорт</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }}
        .message {{
            background: white;
            margin: 10px 0;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            border-left: 4px solid #667eea;
        }}
        .message-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            font-size: 0.9em;
            color: #666;
        }}
        .message-id {{
            font-weight: bold;
            color: #667eea;
        }}
        .message-date {{
            font-style: italic;
        }}
        .message-text {{
            line-height: 1.6;
            white-space: pre-wrap;
        }}
        .message-stats {{
            margin-top: 10px;
            font-size: 0.8em;
            color: #888;
            display: flex;
            gap: 15px;
        }}
        .media-info {{
            background: #e8f4fd;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
            border-left: 3px solid #2196F3;
        }}
        .stats {{
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{channel_name}</h1>
        <p>Экспорт от {export_date}</p>
    </div>
    
    <div class="stats">
        <h3>Статистика</h3>
        <p>Всего сообщений: <strong>{total_messages}</strong></p>
    </div>
    
    <div class="messages">
        {messages_html}
    </div>
</body>
</html>"""
        
        messages_html = ""
        for msg in messages:
            message_html = f"""
        <div class="message">
            <div class="message-header">
                <span class="message-id">#{msg.id}</span>
                <span class="message-date">{msg.date.strftime('%Y-%m-%d %H:%M:%S') if msg.date else 'Неизвестно'}</span>
            </div>
            """
            
            if msg.text:
                escaped_text = html.escape(self.clean_text(msg.text))
                message_html += f'<div class="message-text">{escaped_text}</div>'
            
            if msg.media_type:
                message_html += f"""
            <div class="media-info">
                <strong>Медиа:</strong> {msg.media_type}
                {f'<br><strong>Файл:</strong> {msg.media_path}' if msg.media_path else ''}
            </div>"""
            
            stats_parts = []
            if msg.views > 0:
                stats_parts.append(f"👁 {msg.views}")
            if msg.forwards > 0:
                stats_parts.append(f"🔄 {msg.forwards}")
            if msg.replies > 0:
                stats_parts.append(f"💬 {msg.replies}")
            
            if stats_parts:
                message_html += f'<div class="message-stats">{" | ".join(stats_parts)}</div>'
            
            message_html += "</div>"
            messages_html += message_html
        
        return html_template.format(
            channel_name=html.escape(self.channel_name),
            export_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            total_messages=len(messages),
            messages_html=messages_html
        )


class MarkdownExporter(BaseExporter):
    """Экспортер в Markdown формат"""
    
    def export_messages(self, messages: List[MessageData], append_mode: bool = False) -> str:
        """Экспорт сообщений в Markdown
        
        Args:
            messages: Список сообщений для экспорта
            append_mode: Если True, добавляет новые сообщения к существующим
        """
        output_file = self.output_dir / f"{self.sanitize_filename(self.channel_name)}.md"
        
        existing_messages = []
        if append_mode and output_file.exists():
            try:
                # Читаем существующий Markdown и извлекаем сообщения
                with open(output_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    existing_messages = self._extract_messages_from_markdown(content)
                    print(f"Markdown: Found {len(existing_messages)} existing messages in {output_file}")
            except Exception as e:
                # Если файл поврежден, начинаем заново
                print(f"Markdown: Error reading existing file {output_file}: {e}")
                existing_messages = []
        
        # Объединяем существующие и новые сообщения
        all_messages = existing_messages + messages
        print(f"Markdown: Merged {len(existing_messages)} existing + {len(messages)} new = {len(all_messages)} total")
        
        # Убираем дубликаты по ID сообщения
        seen_ids = set()
        unique_messages = []
        for msg in all_messages:
            if msg.id not in seen_ids:
                seen_ids.add(msg.id)
                unique_messages.append(msg)
        
        print(f"Markdown: After deduplication: {len(unique_messages)} unique messages")
        
        # Сортируем по ID сообщения (старые сначала)
        unique_messages.sort(key=lambda x: x.id)
        
        markdown_content = self._generate_markdown(unique_messages)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        return str(output_file)
    
    def _extract_messages_from_markdown(self, md_content: str) -> List[MessageData]:
        """Извлечение сообщений из существующего Markdown файла"""
        try:
            import re
            from datetime import datetime
            
            messages = []
            # Ищем блоки сообщений в Markdown
            message_pattern = r'## Сообщение #(\d+)\n\n\*\*Дата:\*\* ([^\n]+).*?\n\n(.*?)(?=\n## Сообщение #|\n---\n|$)'
            
            matches = re.findall(message_pattern, md_content, re.DOTALL)
            
            for msg_id, date_str, content in matches:
                try:
                    # Парсим ID сообщения
                    message_id = int(msg_id)
                    
                    # Парсим дату (пробуем несколько форматов)
                    parsed_date = None
                    date_formats = [
                        '%Y-%m-%d %H:%M:%S',
                        '%Y-%m-%d %H:%M',
                        '%d.%m.%Y %H:%M:%S',
                        '%d.%m.%Y %H:%M'
                    ]
                    
                    for fmt in date_formats:
                        try:
                            parsed_date = datetime.strptime(date_str.strip(), fmt)
                            break
                        except ValueError:
                            continue
                    
                    if not parsed_date:
                        # Если не удалось распарсить, используем текущую дату
                        parsed_date = datetime.now()
                    
                    # Извлекаем текст сообщения (убираем статистику и другую информацию)
                    lines = content.split('\n')
                    text_lines = []
                    
                    for line in lines:
                        line = line.strip()
                        # Пропускаем строки с метаданными
                        if (line.startswith('**') or 
                            line.startswith('👁') or 
                            line.startswith('🔄') or 
                            line.startswith('💬') or
                            line.startswith('*Отредактировано:') or
                            line.startswith('---')):
                            continue
                        if line:  # Добавляем только непустые строки
                            text_lines.append(line)
                    
                    clean_text = '\n'.join(text_lines).strip()
                    
                    # Создаем объект MessageData
                    msg_data = MessageData(
                        id=message_id,
                        date=parsed_date,
                        text=clean_text,
                        author=None,
                        media_type=None,
                        media_path=None,
                        views=0,
                        forwards=0,
                        replies=0,
                        edited=None
                    )
                    
                    messages.append(msg_data)
                    
                except (ValueError, TypeError) as e:
                    # Пропускаем сообщения с ошибками парсинга
                    continue
            
            return messages
            
        except Exception as e:
            # В случае ошибки возвращаем пустой список
            return []
    
    def _generate_markdown(self, messages: List[MessageData]) -> str:
        """Генерация Markdown контента"""
        # Безопасное название канала для заголовка
        safe_channel_name = self._safe_markdown_text(self.channel_name)
        
        md_content = f"""# {safe_channel_name}

**Экспорт от:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Всего сообщений:** {len(messages)}

---

"""
        
        for msg in messages:
            md_content += f"\n## Сообщение #{msg.id}\n\n"
            
            # Дата и время
            if msg.date:
                md_content += f"**Дата:** {msg.date.strftime('%Y-%m-%d %H:%M:%S')}  \n"
            
            # Автор (если есть)
            if msg.author:
                md_content += f"**Автор:** {msg.author}  \n"
            
            # Медиа информация
            if msg.media_type:
                md_content += f"**Медиа:** {msg.media_type}  \n"
                if msg.media_path:
                    md_content += f"**Файл:** `{msg.media_path}`  \n"
            
            md_content += "\n"
            
            # Текст сообщения
            if msg.text:
                # Используем безопасную функцию для предотвращения ошибок KaTeX
                safe_text = self._safe_markdown_text(msg.text)
                md_content += f"{safe_text}\n\n"
            
            # Статистика
            stats_parts = []
            if msg.views > 0:
                stats_parts.append(f"👁 Просмотры: {msg.views}")
            if msg.forwards > 0:
                stats_parts.append(f"🔄 Пересылки: {msg.forwards}")
            if msg.replies > 0:
                stats_parts.append(f"💬 Ответы: {msg.replies}")
            
            if stats_parts:
                md_content += f"*{' | '.join(stats_parts)}*\n\n"
            
            if msg.edited:
                md_content += f"*Отредактировано: {msg.edited.strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
            
            md_content += "---\n"
        
        return md_content
    
    def _escape_markdown(self, text: str) -> str:
        """Экранирование специальных символов Markdown"""
        if not text:
            return ""
        
        # Сначала экранируем обратные слеши, чтобы избежать двойного экранирования
        text = text.replace('\\', '\\\\')
        
        # Экранируем символы, которые могут конфликтовать с KaTeX
        # Порядок важен - некоторые символы нужно обрабатывать в определенной последовательности
        replacements = [
            ('$', '\\$'),      # Экранирование знака доллара (KaTeX delimiter)
            ('`', '\\`'),      # Обратные кавычки
            ('*', '\\*'),      # Звездочки
            ('_', '\\_'),      # Подчеркивания
            ('{', '\\{'),      # Фигурные скобки
            ('}', '\\}'),      # Фигурные скобки
            ('[', '\\['),      # Квадратные скобки
            (']', '\\]'),      # Квадратные скобки
            ('(', '\\('),      # Круглые скобки
            (')', '\\)'),      # Круглые скобки
            ('#', '\\#'),      # Решетка
            ('+', '\\+'),      # Плюс
            ('-', '\\-'),      # Дефис (основная причина ошибки KaTeX)
            ('.', '\\.'),      # Точка
            ('!', '\\!'),      # Восклицательный знак
            ('|', '\\|'),      # Вертикальная черта
            ('^', '\\^'),      # Каретка
            ('~', '\\~'),      # Тильда
        ]
        
        for original, escaped in replacements:
            text = text.replace(original, escaped)
        
        # Дополнительная обработка для предотвращения конфликтов с KaTeX
        # Экранирование последовательностей, которые KaTeX может интерпретировать как команды
        text = text.replace('\\-', '\\\\-')  # Двойное экранирование для \-
        text = text.replace('\\\\\\-', '\\\\-')  # Исправление тройного экранирования
        
        return text
    
    def _safe_markdown_text(self, text: str) -> str:
        """Создание безопасного для KaTeX текста Markdown"""
        if not text:
            return ""
        
        # Сначала очищаем от проблемных символов
        cleaned = self.clean_text(text)
        
        # Применяем минимальное экранирование только для критичных символов
        # Избегаем экранирования дефисов и других символов, которые вызывают проблемы с KaTeX
        safe_replacements = [
            ('*', '\\*'),      # Звездочки для выделения
            ('_', '\\_'),      # Подчеркивания для выделения
            ('`', '\\`'),      # Обратные кавычки для кода
            ('#', '\\#'),      # Решетка для заголовков
            ('[', '\\['),      # Квадратные скобки для ссылок
            (']', '\\]'),      # Квадратные скобки для ссылок
        ]
        
        for original, escaped in safe_replacements:
            cleaned = cleaned.replace(original, escaped)
        
        return cleaned


class MediaDownloader:
    """Класс для загрузки медиафайлов с поддержкой многопоточности"""
    
    def __init__(self, output_dir: Path, max_workers: int = 4):
        self.output_dir = output_dir
        self.media_dir = output_dir / "media"
        self.media_dir.mkdir(exist_ok=True)
        self.max_workers = max_workers
        self.download_queue = []
        self.downloaded_files = {}
    
    async def download_media(self, client, message: Message) -> Optional[str]:
        """Загрузка медиафайла из сообщения (синхронная версия для совместимости)"""
        if not message.media:
            return None
        
        try:
            # Определение типа медиа и расширения файла
            if isinstance(message.media, MessageMediaPhoto):
                extension = ".jpg"
                media_type = "photo"
            elif isinstance(message.media, MessageMediaDocument):
                # Получаем расширение из атрибутов документа
                extension = ".bin"  # По умолчанию
                media_type = "document"
                
                if hasattr(message.media.document, 'attributes'):
                    for attr in message.media.document.attributes:
                        if hasattr(attr, 'file_name') and attr.file_name:
                            extension = Path(attr.file_name).suffix or ".bin"
                            break
            else:
                return None
            
            # Генерация имени файла
            filename = f"msg_{message.id}_{media_type}{extension}"
            file_path = self.media_dir / filename
            
            # Загрузка файла
            await client.download_media(message, file_path)
            
            return f"media/{filename}"
            
        except Exception as e:
            print(f"Ошибка загрузки медиа для сообщения {message.id}: {e}")
            return None
    
    def add_to_download_queue(self, client, message: Message) -> str:
        """Добавление сообщения в очередь загрузки"""
        if not message.media:
            return ""
        
        try:
            # Определение типа медиа и расширения файла
            if isinstance(message.media, MessageMediaPhoto):
                extension = ".jpg"
                media_type = "photo"
            elif isinstance(message.media, MessageMediaDocument):
                extension = ".bin"
                media_type = "document"
                
                if hasattr(message.media.document, 'attributes'):
                    for attr in message.media.document.attributes:
                        if hasattr(attr, 'file_name') and attr.file_name:
                            extension = Path(attr.file_name).suffix or ".bin"
                            break
            else:
                return ""
            
            # Генерация имени файла
            filename = f"msg_{message.id}_{media_type}{extension}"
            file_path = self.media_dir / filename
            
            # Проверяем, не существует ли уже файл с правильным размером
            if file_path.exists() and file_path.stat().st_size > 0:
                # Файл уже существует и имеет размер больше 0
                return f"media/{filename}"
            
            # Добавляем в очередь загрузки
            self.download_queue.append({
                'client': client,
                'message': message,
                'file_path': file_path,
                'filename': filename,
                'media_type': media_type
            })
            
            return f"media/{filename}"
            
        except Exception as e:
            print(f"Ошибка добавления в очередь загрузки для сообщения {message.id}: {e}")
            return ""
    
    async def download_queue_parallel(self) -> Dict[int, str]:
        """Параллельная загрузка всех файлов из очереди с использованием asyncio.gather"""
        if not self.download_queue:
            return {}
        
        results = {}
        failed_downloads = []
        
        print(f"Начинаем параллельную загрузку {len(self.download_queue)} файлов используя {self.max_workers} одновременных задач")
        
        # Создаем семафор для ограничения количества одновременных загрузок
        semaphore = asyncio.Semaphore(self.max_workers)
        
        # Создаем async задачи для загрузки
        download_tasks = []
        for item in self.download_queue:
            task = self._download_single_file_async(item, semaphore)
            download_tasks.append(task)
        
        # Выполняем все задачи параллельно
        download_results = await asyncio.gather(*download_tasks, return_exceptions=True)
        
        # Обрабатываем результаты
        for i, result in enumerate(download_results):
            item = self.download_queue[i]
            
            if isinstance(result, Exception):
                failed_downloads.append(item)
                print(f"✗ Ошибка загрузки файла {item['filename']} для сообщения {item['message'].id}: {result}")
            elif result:
                results[item['message'].id] = f"media/{item['filename']}"
                self.downloaded_files[item['message'].id] = f"media/{item['filename']}"
                print(f"✓ Загружен файл {item['filename']} ({len(results)}/{len(self.download_queue)})")
            else:
                failed_downloads.append(item)
                print(f"✗ Не удалось загрузить файл {item['filename']} ({len(results)}/{len(self.download_queue)})")
        
        # Пытаемся повторить загрузку неудачных файлов
        if failed_downloads:
            print(f"Повторная попытка загрузки {len(failed_downloads)} неудачных файлов...")
            retry_semaphore = asyncio.Semaphore(min(2, len(failed_downloads)))
            
            retry_tasks = []
            for item in failed_downloads:
                task = self._download_single_file_async(item, retry_semaphore)
                retry_tasks.append(task)
            
            retry_results_list = await asyncio.gather(*retry_tasks, return_exceptions=True)
            
            for i, result in enumerate(retry_results_list):
                item = failed_downloads[i]
                if isinstance(result, Exception):
                    print(f"✗ Повторная загрузка не удалась: {item['filename']} - {result}")
                elif result:
                    results[item['message'].id] = f"media/{item['filename']}"
                    self.downloaded_files[item['message'].id] = f"media/{item['filename']}"
                    print(f"✓ Повторная загрузка успешна: {item['filename']}")
        
        # Сохраняем общее количество файлов до очистки очереди
        total_files = len(self.download_queue)
        
        # Очищаем очередь
        self.download_queue.clear()
        
        successful_count = len(results)
        failed_count = total_files - successful_count
        print(f"Загрузка завершена. Успешно: {successful_count}, Неудачно: {failed_count}")
        
        return results
    
    async def _download_single_file_async(self, item: Dict, semaphore: asyncio.Semaphore) -> bool:
        """Асинхронная загрузка одного файла с ограничением через семафор"""
        async with semaphore:  # Ограничиваем количество одновременных загрузок
            try:
                client = item['client']
                message = item['message']
                file_path = item['file_path']
                filename = item['filename']
                
                # Проверяем, что файл еще не существует
                if file_path.exists():
                    # Если файл уже существует, проверяем его размер
                    if file_path.stat().st_size > 0:
                        return True
                    else:
                        # Удаляем файл с нулевым размером
                        try:
                            file_path.unlink()
                        except OSError:
                            pass
                
                # Проверяем доступность медиа перед загрузкой
                if not message.media:
                    print(f"✗ Нет медиа в сообщении для файла {filename}")
                    return False
                
                # Загружаем файл с тайм-аутом
                try:
                    # Используем тайм-аут 60 секунд для загрузки одного файла
                    await asyncio.wait_for(
                        client.download_media(message, file_path),
                        timeout=60.0
                    )
                    
                    # Даем небольшую паузу для завершения записи файла
                    await asyncio.sleep(0.1)
                    
                    # Проверяем, что файл был создан и имеет размер больше 0
                    if file_path.exists() and file_path.stat().st_size > 0:
                        file_size = file_path.stat().st_size
                        print(f"✓ Файл {filename} успешно загружен, размер: {file_size:,} байт ({file_size/1024/1024:.2f} МБ)")
                        return True
                    else:
                        print(f"✗ Файл {filename} загружен, но имеет размер 0 байт или не существует")
                        # Удаляем пустой файл
                        try:
                            if file_path.exists():
                                file_path.unlink()
                        except OSError:
                            pass
                        return False
                        
                except asyncio.TimeoutError:
                    print(f"✗ Тайм-аут при загрузке файла {filename} (превышено 60 секунд)")
                    # Удаляем частично загруженный файл
                    try:
                        if file_path.exists():
                            file_path.unlink()
                    except OSError:
                        pass
                    return False
                    
                except Exception as e:
                    print(f"✗ Ошибка загрузки файла {filename}: {type(e).__name__}: {e}")
                    # Удаляем частично загруженный файл
                    try:
                        if file_path.exists():
                            file_path.unlink()
                    except OSError:
                        pass
                    return False
                    
            except Exception as e:
                print(f"✗ Общая ошибка при загрузке файла {item.get('filename', 'unknown')}: {type(e).__name__}: {e}")
                return False
    
    def _download_single_file(self, item: Dict) -> bool:
        """Загрузка одного файла (устаревший метод для обратной совместимости)"""
        # Этот метод оставляем для обратной совместимости, но он не должен использоваться
        # в новой реализации с asyncio.gather
        print(f"⚠️  Используется устаревший метод _download_single_file для {item.get('filename', 'unknown')}")
        return False
    
    def get_downloaded_file(self, message_id: int) -> Optional[str]:
        """Получение пути к загруженному файлу"""
        return self.downloaded_files.get(message_id)
    
    def get_file_size_mb(self, file_path: str) -> float:
        """Получение размера файла в МБ"""
        try:
            size_bytes = Path(file_path).stat().st_size
            return size_bytes / (1024 * 1024)
        except:
            return 0.0
    
    def get_queue_size(self) -> int:
        """Получение размера очереди загрузки"""
        return len(self.download_queue)
    
    def clear_queue(self):
        """Очистка очереди загрузки"""
        self.download_queue.clear()
        self.downloaded_files.clear()