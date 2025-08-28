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
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from telethon.tl.types import Message, MessageMediaPhoto, MessageMediaDocument
from telethon.errors import FloodWaitError
import time
import random


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
        pre {{
            background: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #007acc;
            overflow-x: auto;
            font-family: 'Courier New', Consolas, monospace;
            font-size: 14px;
            line-height: 1.4;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', Consolas, monospace;
            font-size: 14px;
        }}
        pre code {{
            background: none;
            padding: 0;
            border-radius: 0;
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
                formatted_text = self._format_html_text(msg.text)
                message_html += f'<div class="message-text">{formatted_text}</div>'
            
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
    
    def _format_html_text(self, text: str) -> str:
        """Форматирование текста для HTML с поддержкой блоков кода"""
        if not text:
            return ""
        
        # Сначала очищаем от проблемных символов
        cleaned = self.clean_text(text)
        
        import re
        
        # Обрабатываем многострочные блоки кода (```)
        def format_multiline_code(match):
            code_content = match.group(1).strip()
            escaped_code = html.escape(code_content)
            return f'<pre><code>{escaped_code}</code></pre>'
        
        # Обрабатываем однострочные блоки кода (`code`)
        def format_inline_code(match):
            code_content = match.group(1)
            escaped_code = html.escape(code_content)
            return f'<code>{escaped_code}</code>'
        
        # Применяем форматирование блоков кода
        formatted = re.sub(r'```([\s\S]*?)```', format_multiline_code, cleaned)
        formatted = re.sub(r'`([^`\n]+)`', format_inline_code, formatted)
        
        # Экранируем остальной текст
        formatted = html.escape(formatted)
        
        # Восстанавливаем уже отформатированные блоки кода
        formatted = re.sub(r'&lt;pre&gt;&lt;code&gt;([\s\S]*?)&lt;/code&gt;&lt;/pre&gt;', r'<pre><code>\1</code></pre>', formatted)
        formatted = re.sub(r'&lt;code&gt;([^&]*)&lt;/code&gt;', r'<code>\1</code>', formatted)
        
        # Преобразуем переносы строк в HTML
        formatted = formatted.replace('\n', '<br>')
        
        return formatted


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
    

    def _safe_markdown_text(self, text: str) -> str:
        """Создание безопасного для KaTeX текста Markdown с сохранением блоков кода"""
        if not text:
            return ""
        
        # Сначала очищаем от проблемных символов
        cleaned = self.clean_text(text)
        
        import re
        
        # Находим и защищаем блоки кода (многострочные и однострочные)
        code_blocks = []
        code_counter = 0
        
        # Защищаем многострочные блоки кода (```)
        def protect_multiline_code(match):
            nonlocal code_counter
            code_blocks.append(match.group(0))
            placeholder = f"MDCODEBLOCK{code_counter}PLACEHOLDER"
            code_counter += 1
            return placeholder
        
        # Защищаем однострочные блоки кода (`code`)
        def protect_inline_code(match):
            nonlocal code_counter
            code_blocks.append(match.group(0))
            placeholder = f"MDCODEBLOCK{code_counter}PLACEHOLDER"
            code_counter += 1
            return placeholder
        
        # Сначала защищаем многострочные блоки кода
        cleaned = re.sub(r'```[\s\S]*?```', protect_multiline_code, cleaned)
        
        # Затем защищаем однострочные блоки кода
        cleaned = re.sub(r'`[^`\n]+`', protect_inline_code, cleaned)
        
        # Минимальное экранирование только проблемных символов KaTeX
        # НЕ экранируем Markdown символы разметки (*, _, [, ])
        # Экранируем решетку только в начале строки (для заголовков), но не в блоках кода
        # cleaned = re.sub(r'^#', '\\#', cleaned, flags=re.MULTILINE)  # Отключаем экранирование заголовков
        
        # Восстанавливаем защищенные блоки кода
        for i, code_block in enumerate(code_blocks):
            placeholder = f"MDCODEBLOCK{i}PLACEHOLDER"
            cleaned = cleaned.replace(placeholder, code_block)
        
        return cleaned


class MediaDownloader:
    """Класс для загрузки медиафайлов с интеллектуальной системой управления нагрузкой"""
    
    def __init__(self, output_dir: Path, max_workers: int = 4):
        # Валидация параметров
        if not isinstance(output_dir, Path):
            raise TypeError("output_dir must be a Path object")
        if not isinstance(max_workers, int) or max_workers < 1 or max_workers > 32:
            raise ValueError("max_workers must be an integer between 1 and 32")
        
        self.output_dir = output_dir
        self.media_dir = output_dir / "media"
        
        # Создаем директорию с проверкой прав
        try:
            self.media_dir.mkdir(exist_ok=True, parents=True)
        except (OSError, PermissionError) as e:
            raise RuntimeError(f"Cannot create media directory {self.media_dir}: {e}")
        
        # Динамическое управление потоками с ограничениями
        self.max_workers = min(max_workers, 16)  # Ограничиваем максимум 16 потоков
        self.current_workers = min(2, self.max_workers)  # Начинаем с меньшего количества
        self.download_queue = []
        self.downloaded_files = {}
        
        # Колбэк для отчета о прогрессе загрузок в реальном времени
        self.progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        
        # Система управления нагрузкой с улучшенными параметрами
        self.flood_wait_count = 0
        self.last_flood_wait = 0
        self.success_count = 0
        self.consecutive_successes = 0  # Подряд идущие успешные загрузки
        self.adaptive_delay = 0.5  # Начальная задержка между запросами
        self.min_delay = 0.1
        self.max_delay = 5.0  # Увеличили максимальную задержку
        
        # Статистика для адаптации
        self.download_stats = {
            'total_attempts': 0,
            'successful_downloads': 0,
            'flood_waits': 0,
            'average_speed': 0.0,
            'session_start_time': time.time()
        }
    
    def _adapt_to_flood_wait(self, flood_wait_seconds: int):
        """Адаптация к flood wait с улучшенной логикой"""
        self.flood_wait_count += 1
        self.last_flood_wait = time.time()
        self.download_stats['flood_waits'] += 1
        self.consecutive_successes = 0  # Сбрасываем счетчик успешных загрузок
        
        # Более агрессивное увеличение задержки для длительных flood wait
        if flood_wait_seconds > 10:
            multiplier = 2.0
        elif flood_wait_seconds > 5:
            multiplier = 1.8
        else:
            multiplier = 1.5
        
        # Увеличиваем задержку и уменьшаем количество потоков
        self.adaptive_delay = min(self.max_delay, self.adaptive_delay * multiplier)
        self.current_workers = max(1, self.current_workers - 1)
        
        print(f"🚫 Flood wait {flood_wait_seconds}s - адаптация: задержка {self.adaptive_delay:.1f}s, потоков {self.current_workers}")
    
    def _adapt_to_success(self):
        """Адаптация к успешным загрузкам с улучшенной логикой"""
        self.success_count += 1
        self.consecutive_successes += 1
        self.download_stats['successful_downloads'] += 1
        
        # Более консервативное ускорение
        time_since_flood = time.time() - self.last_flood_wait
        
        # Ускоряемся только если давно не было flood wait и есть подряд идущие успехи
        if time_since_flood > 120 and self.consecutive_successes >= 15:  # 2 минуты без flood wait и 15 успехов подряд
            old_delay = self.adaptive_delay
            old_workers = self.current_workers
            
            # Постепенное ускорение
            self.adaptive_delay = max(self.min_delay, self.adaptive_delay * 0.95)
            if self.consecutive_successes % 20 == 0:  # Каждые 20 успешных загрузок
                self.current_workers = min(self.max_workers, self.current_workers + 1)
            
            # Логируем только если были изменения
            if old_delay != self.adaptive_delay or old_workers != self.current_workers:
                print(f"⚡ Постепенное ускорение: задержка {self.adaptive_delay:.1f}s, потоков {self.current_workers}")
    
    def _get_smart_delay(self) -> float:
        """Получение умной задержки с джиттером"""
        # Добавляем случайность для избежания синхронизации запросов
        jitter = random.uniform(0.8, 1.2)
        return self.adaptive_delay * jitter
    
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
        """Интеллектуальная параллельная загрузка с адаптивным управлением нагрузкой"""
        if not self.download_queue:
            return {}
        
        results = {}
        total_files = len(self.download_queue)
        bytes_downloaded_total = 0
        
        print(f"🚀 Начинаем интеллектуальную загрузку {total_files} файлов")
        print(f"📊 Начальные настройки: потоков {self.current_workers}, задержка {self.adaptive_delay:.1f}s")
        
        start_time = time.time()
        
        # Разбиваем очередь на батчи для лучшего контроля
        batch_size = max(5, self.current_workers * 2)
        batches = [self.download_queue[i:i + batch_size] for i in range(0, len(self.download_queue), batch_size)]
        
        for batch_num, batch in enumerate(batches, 1):
            print(f"📦 Обработка батча {batch_num}/{len(batches)} ({len(batch)} файлов)")
            
            # Создаем семафор с текущим количеством потоков
            semaphore = asyncio.Semaphore(self.current_workers)
            
            # Создаем задачи для текущего батча
            batch_tasks = []
            for item in batch:
                task = self._download_single_file_async_smart(item, semaphore)
                batch_tasks.append(task)
            
            # Выполняем батч
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Обрабатываем результаты батча
            batch_successful = 0
            for i, result in enumerate(batch_results):
                item = batch[i]
                
                if isinstance(result, Exception):
                    print(f"✗ Ошибка загрузки файла {item['filename']}: {result}")
                elif result:
                    results[item['message'].id] = f"media/{item['filename']}"
                    self.downloaded_files[item['message'].id] = f"media/{item['filename']}"
                    batch_successful += 1
                    if isinstance(result, int):
                        bytes_downloaded_total += result
                    self._adapt_to_success()
            
            print(f"📊 Батч {batch_num}: успешно {batch_successful}/{len(batch)}, "
                  f"всего {len(results)}/{total_files}")
            # Репортим прогресс после батча
            if self.progress_callback:
                elapsed = max(1e-6, time.time() - start_time)
                files_per_sec = len(results) / elapsed
                mb_per_sec = (bytes_downloaded_total / (1024 * 1024)) / elapsed
                remaining = max(0, total_files - len(results))
                try:
                    self.progress_callback({
                        'total': total_files,
                        'completed': len(results),
                        'remaining': remaining,
                        'files_per_sec': files_per_sec,
                        'mb_per_sec': mb_per_sec
                    })
                except Exception:
                    pass
            
            # Небольшая пауза между батчами для стабильности
            if batch_num < len(batches):
                await asyncio.sleep(0.5)
        
        # Повторная попытка для неудачных загрузок
        failed_items = [item for item in self.download_queue if item['message'].id not in results]
        
        if failed_items and len(failed_items) < total_files * 0.3:  # Повторяем только если неудач < 30%
            print(f"🔄 Повторная попытка для {len(failed_items)} файлов с консервативными настройками...")
            
            # Более консервативные настройки для повтора
            retry_semaphore = asyncio.Semaphore(1)  # Только 1 поток для повтора
            
            retry_tasks = []
            for item in failed_items:
                # Увеличиваем задержку для повторных попыток
                task = self._download_single_file_async_smart(item, retry_semaphore, retry_mode=True)
                retry_tasks.append(task)
            
            retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)
            
            retry_successful = 0
            for i, result in enumerate(retry_results):
                item = failed_items[i]
                if isinstance(result, Exception):
                    print(f"✗ Повторная загрузка не удалась: {item['filename']}")
                elif result:
                    results[item['message'].id] = f"media/{item['filename']}"
                    self.downloaded_files[item['message'].id] = f"media/{item['filename']}"
                    retry_successful += 1
                    if isinstance(result, int):
                        bytes_downloaded_total += result
            
            print(f"🔄 Повторная попытка: успешно {retry_successful}/{len(failed_items)}")
        
        # Очищаем очередь
        self.download_queue.clear()
        
        # Статистика
        elapsed_time = time.time() - start_time
        successful_count = len(results)
        failed_count = total_files - successful_count
        avg_speed = successful_count / elapsed_time if elapsed_time > 0 else 0
        
        self.download_stats['average_speed'] = avg_speed
        
        print(f"✅ Загрузка завершена за {elapsed_time:.1f}с")
        print(f"📊 Результат: успешно {successful_count}, неудачно {failed_count}")
        print(f"⚡ Средняя скорость: {avg_speed:.1f} файлов/сек")
        print(f"🚫 Flood wait событий: {self.download_stats['flood_waits']}")
        
        # Финальный репорт прогресса
        if self.progress_callback:
            try:
                self.progress_callback({
                    'total': total_files,
                    'completed': successful_count,
                    'remaining': 0,
                    'files_per_sec': successful_count / max(1e-6, elapsed_time),
                    'mb_per_sec': (bytes_downloaded_total / (1024 * 1024)) / max(1e-6, elapsed_time)
                })
            except Exception:
                pass
        
        return results
    
    async def _download_single_file_async_smart(self, item: Dict, semaphore: asyncio.Semaphore, retry_mode: bool = False) -> bool | int:
        """Умная загрузка файла с обработкой flood wait и адаптивными задержками"""
        async with semaphore:
            try:
                client = item['client']
                message = item['message']
                file_path = item['file_path']
                filename = item['filename']
                
                self.download_stats['total_attempts'] += 1
                
                # Проверяем существующий файл
                if file_path.exists() and file_path.stat().st_size > 0:
                    return file_path.stat().st_size
                
                # Удаляем пустые файлы
                if file_path.exists():
                    try:
                        file_path.unlink()
                    except OSError:
                        pass
                
                # Проверяем медиа
                if not message.media:
                    return False
                
                # Умная задержка перед загрузкой
                delay = self._get_smart_delay()
                if retry_mode:
                    delay *= 2  # Удваиваем задержку для повторных попыток
                
                await asyncio.sleep(delay)
                
                # Попытка загрузки с обработкой flood wait
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        download_start = time.time()
                        
                        # Загрузка с тайм-аутом
                        timeout = 120 if retry_mode else 60
                        await asyncio.wait_for(
                            client.download_media(message, file_path),
                            timeout=timeout
                        )
                        
                        download_time = time.time() - download_start
                        
                        # Небольшая пауза для завершения записи
                        await asyncio.sleep(0.1)
                        
                        # Проверка результата
                        if file_path.exists() and file_path.stat().st_size > 0:
                            file_size = file_path.stat().st_size
                            speed = file_size / download_time / 1024 / 1024 if download_time > 0 else 0
                            print(f"✓ {filename}: {file_size:,} байт за {download_time:.1f}с ({speed:.1f} МБ/с)")
                            return file_size
                        else:
                            print(f"✗ {filename}: файл пуст или не создан")
                            return False
                            
                    except FloodWaitError as e:
                        flood_wait_seconds = e.seconds
                        self._adapt_to_flood_wait(flood_wait_seconds)
                        
                        if attempt < max_retries - 1:
                            # Ждем указанное время + небольшой буфер
                            wait_time = flood_wait_seconds + random.uniform(1, 3)
                            print(f"⏳ {filename}: flood wait {flood_wait_seconds}s, ожидание {wait_time:.1f}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            print(f"✗ {filename}: превышено количество попыток после flood wait")
                            return False
                            
                    except asyncio.TimeoutError:
                        if attempt < max_retries - 1:
                            print(f"⏰ {filename}: тайм-аут, попытка {attempt + 2}/{max_retries}")
                            await asyncio.sleep(random.uniform(2, 5))
                            continue
                        else:
                            print(f"✗ {filename}: превышено время загрузки")
                            return False
                            
                    except Exception as e:
                        error_type = type(e).__name__
                        error_msg = str(e).lower()
                        
                        # Специальная обработка различных типов ошибок
                        if "flood" in error_msg or "rate limit" in error_msg:
                            # Обработка других типов flood wait ошибок
                            flood_wait_seconds = 10  # По умолчанию
                            # Пытаемся извлечь время ожидания из сообщения
                            import re
                            match = re.search(r'(\d+)\s*second', error_msg)
                            if match:
                                flood_wait_seconds = int(match.group(1))
                            
                            self._adapt_to_flood_wait(flood_wait_seconds)
                            
                            if attempt < max_retries - 1:
                                wait_time = flood_wait_seconds + random.uniform(1, 3)
                                print(f"⏳ {filename}: обнаружен flood wait, ожидание {wait_time:.1f}s...")
                                await asyncio.sleep(wait_time)
                                continue
                        elif "connection" in error_msg or "network" in error_msg:
                            # Сетевые ошибки - увеличиваем задержку
                            if attempt < max_retries - 1:
                                wait_time = random.uniform(3, 8)
                                print(f"🌐 {filename}: сетевая ошибка, ожидание {wait_time:.1f}s...")
                                await asyncio.sleep(wait_time)
                                continue
                        elif "permission" in error_msg or "access" in error_msg:
                            # Ошибки доступа - не повторяем
                            print(f"🔒 {filename}: ошибка доступа: {e}")
                            return False
                        elif "file" in error_msg and ("not found" in error_msg or "does not exist" in error_msg):
                            # Файл не найден - не повторяем
                            print(f"📂 {filename}: файл недоступен: {e}")
                            return False
                        
                        # Общая обработка других ошибок
                        if attempt < max_retries - 1:
                            wait_time = random.uniform(1, 4)
                            print(f"⚠️ {filename}: ошибка {error_type}, попытка {attempt + 2}/{max_retries} через {wait_time:.1f}s")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            print(f"✗ {filename}: {error_type}: {e}")
                            return False
                
                return False
                
            except Exception as e:
                print(f"✗ {filename}: критическая ошибка {type(e).__name__}: {e}")
                return False
            finally:
                # Очистка пустых файлов
                try:
                    if file_path.exists() and file_path.stat().st_size == 0:
                        file_path.unlink()
                except OSError:
                    pass
    
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
    
    def get_download_stats(self) -> Dict[str, Any]:
        """Получение подробной статистики загрузок"""
        session_time = time.time() - self.download_stats['session_start_time']
        
        return {
            'total_attempts': self.download_stats['total_attempts'],
            'successful_downloads': self.download_stats['successful_downloads'],
            'flood_waits': self.download_stats['flood_waits'],
            'average_speed': self.download_stats['average_speed'],
            'current_workers': self.current_workers,
            'max_workers': self.max_workers,
            'adaptive_delay': self.adaptive_delay,
            'consecutive_successes': self.consecutive_successes,
            'success_rate': (self.download_stats['successful_downloads'] / max(1, self.download_stats['total_attempts'])) * 100,
            'flood_wait_rate': (self.download_stats['flood_waits'] / max(1, self.download_stats['total_attempts'])) * 100,
            'session_duration': session_time,
            'downloads_per_minute': (self.download_stats['successful_downloads'] / max(1, session_time / 60)) if session_time > 0 else 0,
            'time_since_last_flood': time.time() - self.last_flood_wait if self.last_flood_wait > 0 else 0
        }
    
    def clear_queue(self):
        """Очистка очереди загрузки"""
        self.download_queue.clear()
        self.downloaded_files.clear()
        
        # Сброс статистики
        self.download_stats = {
            'total_attempts': 0,
            'successful_downloads': 0,
            'flood_waits': 0,
            'average_speed': 0.0
        }