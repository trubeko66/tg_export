#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль экспортеров для различных форматов
"""

import json
import html
import re
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
        
        return cleaned.strip()


class JSONExporter(BaseExporter):
    """Экспортер в JSON формат"""
    
    def export_messages(self, messages: List[MessageData]) -> str:
        """Экспорт сообщений в JSON"""
        output_file = self.output_dir / f"{self.sanitize_filename(self.channel_name)}.json"
        
        data = {
            "channel_name": self.channel_name,
            "export_date": datetime.now().isoformat(),
            "total_messages": len(messages),
            "messages": []
        }
        
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
            data["messages"].append(message_dict)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return str(output_file)


class HTMLExporter(BaseExporter):
    """Экспортер в HTML формат"""
    
    def export_messages(self, messages: List[MessageData]) -> str:
        """Экспорт сообщений в HTML"""
        output_file = self.output_dir / f"{self.sanitize_filename(self.channel_name)}.html"
        
        html_content = self._generate_html(messages)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(output_file)
    
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
    
    def export_messages(self, messages: List[MessageData]) -> str:
        """Экспорт сообщений в Markdown"""
        output_file = self.output_dir / f"{self.sanitize_filename(self.channel_name)}.md"
        
        markdown_content = self._generate_markdown(messages)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        return str(output_file)
    
    def _generate_markdown(self, messages: List[MessageData]) -> str:
        """Генерация Markdown контента"""
        md_content = f"""# {self.channel_name}

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
                cleaned_text = self.clean_text(msg.text)
                # Экранирование специальных символов Markdown
                cleaned_text = self._escape_markdown(cleaned_text)
                md_content += f"{cleaned_text}\n\n"
            
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
        # Экранируем основные символы Markdown
        special_chars = ['\\', '`', '*', '_', '{', '}', '[', ']', '(', ')', '#', '+', '-', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text


class MediaDownloader:
    """Класс для загрузки медиафайлов"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.media_dir = output_dir / "media"
        self.media_dir.mkdir(exist_ok=True)
    
    async def download_media(self, client, message: Message) -> Optional[str]:
        """Загрузка медиафайла из сообщения"""
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
    
    def get_file_size_mb(self, file_path: str) -> float:
        """Получение размера файла в МБ"""
        try:
            size_bytes = Path(file_path).stat().st_size
            return size_bytes / (1024 * 1024)
        except:
            return 0.0