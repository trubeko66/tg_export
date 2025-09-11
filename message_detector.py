#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для обнаружения новых сообщений по ID из существующих файлов
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass
import logging

@dataclass
class ChannelMessageInfo:
    """Информация о сообщениях в канале"""
    channel_name: str
    last_known_id: int
    total_exported: int
    total_filtered: int
    last_export_date: Optional[datetime] = None
    file_path: Optional[Path] = None

class MessageDetector:
    """Класс для обнаружения новых сообщений по ID из существующих файлов"""
    
    def __init__(self, export_base_dir: str = "exports"):
        self.export_base_dir = Path(export_base_dir)
        self.logger = logging.getLogger('message_detector')
        
    def get_channel_last_message_id(self, channel_name: str, sanitized_title: str) -> Optional[int]:
        """Получить ID последнего сообщения из существующих файлов канала"""
        try:
            channel_dir = self.export_base_dir / sanitized_title
            
            if not channel_dir.exists():
                self.logger.debug(f"Channel directory not found: {channel_dir}")
                return None
            
            # Ищем MD файл
            md_file = channel_dir / f"{sanitized_title}.md"
            if md_file.exists():
                return self._extract_last_id_from_markdown(md_file)
            
            # Ищем JSON файл
            json_file = channel_dir / f"{sanitized_title}.json"
            if json_file.exists():
                return self._extract_last_id_from_json(json_file)
            
            # Ищем HTML файл
            html_file = channel_dir / f"{sanitized_title}.html"
            if html_file.exists():
                return self._extract_last_id_from_html(html_file)
            
            self.logger.debug(f"No export files found for channel: {channel_name}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting last message ID for {channel_name}: {e}")
            return None
    
    def _extract_last_id_from_markdown(self, md_file: Path) -> Optional[int]:
        """Извлечь ID последнего сообщения из Markdown файла"""
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Ищем паттерн: ## Сообщение ID: 12345
            pattern = r'## Сообщение ID:\s*(\d+)'
            matches = re.findall(pattern, content)
            
            if matches:
                # Возвращаем максимальный ID
                max_id = max(int(match) for match in matches)
                self.logger.debug(f"Found last message ID {max_id} in Markdown file: {md_file}")
                return max_id
            
            # Альтернативный паттерн: [ID: 12345]
            pattern2 = r'\[ID:\s*(\d+)\]'
            matches2 = re.findall(pattern2, content)
            
            if matches2:
                max_id = max(int(match) for match in matches2)
                self.logger.debug(f"Found last message ID {max_id} in Markdown file (pattern2): {md_file}")
                return max_id
            
            self.logger.debug(f"No message IDs found in Markdown file: {md_file}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error reading Markdown file {md_file}: {e}")
            return None
    
    def _extract_last_id_from_json(self, json_file: Path) -> Optional[int]:
        """Извлечь ID последнего сообщения из JSON файла"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            messages = data.get('messages', [])
            if not messages:
                self.logger.debug(f"No messages found in JSON file: {json_file}")
                return None
            
            # Находим максимальный ID
            max_id = max(msg.get('id', 0) for msg in messages if isinstance(msg.get('id'), int))
            
            if max_id > 0:
                self.logger.debug(f"Found last message ID {max_id} in JSON file: {json_file}")
                return max_id
            
            self.logger.debug(f"No valid message IDs found in JSON file: {json_file}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error reading JSON file {json_file}: {e}")
            return None
    
    def _extract_last_id_from_html(self, html_file: Path) -> Optional[int]:
        """Извлечь ID последнего сообщения из HTML файла"""
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Ищем паттерн: <div class="message" data-id="12345">
            pattern = r'data-id="(\d+)"'
            matches = re.findall(pattern, content)
            
            if matches:
                max_id = max(int(match) for match in matches)
                self.logger.debug(f"Found last message ID {max_id} in HTML file: {html_file}")
                return max_id
            
            # Альтернативный паттерн: <!-- Message ID: 12345 -->
            pattern2 = r'<!-- Message ID:\s*(\d+)\s*-->'
            matches2 = re.findall(pattern2, content)
            
            if matches2:
                max_id = max(int(match) for match in matches2)
                self.logger.debug(f"Found last message ID {max_id} in HTML file (pattern2): {html_file}")
                return max_id
            
            self.logger.debug(f"No message IDs found in HTML file: {html_file}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error reading HTML file {html_file}: {e}")
            return None
    
    def get_channel_message_stats(self, channel_name: str, sanitized_title: str) -> ChannelMessageInfo:
        """Получить статистику сообщений канала"""
        try:
            channel_dir = self.export_base_dir / sanitized_title
            
            if not channel_dir.exists():
                return ChannelMessageInfo(
                    channel_name=channel_name,
                    last_known_id=0,
                    total_exported=0,
                    total_filtered=0
                )
            
            # Получаем последний ID
            last_known_id = self.get_channel_last_message_id(channel_name, sanitized_title) or 0
            
            # Подсчитываем экспортированные сообщения
            total_exported = self._count_exported_messages(channel_dir, sanitized_title)
            
            # Подсчитываем отфильтрованные сообщения из логов
            total_filtered = self._count_filtered_messages(channel_name)
            
            # Получаем дату последнего экспорта
            last_export_date = self._get_last_export_date(channel_dir, sanitized_title)
            
            return ChannelMessageInfo(
                channel_name=channel_name,
                last_known_id=last_known_id,
                total_exported=total_exported,
                total_filtered=total_filtered,
                last_export_date=last_export_date,
                file_path=channel_dir
            )
            
        except Exception as e:
            self.logger.error(f"Error getting channel stats for {channel_name}: {e}")
            return ChannelMessageInfo(
                channel_name=channel_name,
                last_known_id=0,
                total_exported=0,
                total_filtered=0
            )
    
    def _count_exported_messages(self, channel_dir: Path, sanitized_title: str) -> int:
        """Подсчитать количество экспортированных сообщений"""
        try:
            # Проверяем JSON файл
            json_file = channel_dir / f"{sanitized_title}.json"
            if json_file.exists():
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return len(data.get('messages', []))
            
            # Проверяем MD файл
            md_file = channel_dir / f"{sanitized_title}.md"
            if md_file.exists():
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Подсчитываем количество заголовков сообщений
                pattern = r'## Сообщение ID:\s*\d+'
                matches = re.findall(pattern, content)
                return len(matches)
            
            # Проверяем HTML файл
            html_file = channel_dir / f"{sanitized_title}.html"
            if html_file.exists():
                with open(html_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Подсчитываем количество div с сообщениями
                pattern = r'<div class="message"'
                matches = re.findall(pattern, content)
                return len(matches)
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Error counting exported messages in {channel_dir}: {e}")
            return 0
    
    def _count_filtered_messages(self, channel_name: str) -> int:
        """Подсчитать количество отфильтрованных сообщений из логов"""
        try:
            ads_log_file = Path("ads.log")
            if not ads_log_file.exists():
                return 0
            
            count = 0
            with open(ads_log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if f"Канал: {channel_name}" in line and "ОТФИЛЬТРОВАНО" in line:
                        count += 1
            
            return count
            
        except Exception as e:
            self.logger.error(f"Error counting filtered messages for {channel_name}: {e}")
            return 0
    
    def _get_last_export_date(self, channel_dir: Path, sanitized_title: str) -> Optional[datetime]:
        """Получить дату последнего экспорта"""
        try:
            # Проверяем JSON файл
            json_file = channel_dir / f"{sanitized_title}.json"
            if json_file.exists():
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                export_date_str = data.get('export_date')
                if export_date_str:
                    return datetime.fromisoformat(export_date_str)
            
            # Используем дату модификации файла как fallback
            files_to_check = [
                channel_dir / f"{sanitized_title}.json",
                channel_dir / f"{sanitized_title}.md",
                channel_dir / f"{sanitized_title}.html"
            ]
            
            latest_date = None
            for file_path in files_to_check:
                if file_path.exists():
                    file_date = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if latest_date is None or file_date > latest_date:
                        latest_date = file_date
            
            return latest_date
            
        except Exception as e:
            self.logger.error(f"Error getting last export date for {channel_dir}: {e}")
            return None
    
    def get_all_channels_stats(self, channels: List[Any]) -> Dict[str, ChannelMessageInfo]:
        """Получить статистику для всех каналов"""
        stats = {}
        
        for channel in channels:
            try:
                # Получаем sanitized название канала
                sanitized_title = self._sanitize_channel_filename(channel.title)
                stats[channel.id] = self.get_channel_message_stats(channel.title, sanitized_title)
            except Exception as e:
                self.logger.error(f"Error getting stats for channel {channel.title}: {e}")
                stats[channel.id] = ChannelMessageInfo(
                    channel_name=channel.title,
                    last_known_id=0,
                    total_exported=0,
                    total_filtered=0
                )
        
        return stats
    
    def _sanitize_channel_filename(self, channel_title: str) -> str:
        """Очистка имени канала для использования в имени файла"""
        # Удаляем недопустимые символы
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', channel_title)
        # Удаляем лишние пробелы и заменяем на подчеркивания
        sanitized = re.sub(r'\s+', '_', sanitized.strip())
        # Ограничиваем длину
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        return sanitized
