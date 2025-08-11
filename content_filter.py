#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль фильтрации контента
"""

from typing import Tuple
from dataclasses import dataclass


@dataclass
class FilterConfig:
    """Конфигурация фильтров"""
    filter_ads: bool = True
    filter_schools: bool = True


class ContentFilter:
    """Фильтр контента для удаления рекламы и постов от интернет-школ"""
    
    def __init__(self, config: FilterConfig = None):
        self.config = config or FilterConfig()
        self.filtered_count = 0
        
        # Рекламные маркеры
        self.ad_markers = {
            'erid', 'реклама', 'промокод', 'скидка', 'акция',
            'спонсор', 'партнер', 'collaboration', 'sponsored',
            'только сегодня', 'успей купить', 'не упусти'
        }
        
        # IT-школы
        self.school_keywords = {
            'skillbox', 'скиллбокс', 'нетология', 'netology',
            'geekbrains', 'гикбрейнс', 'яндекс практикум',
            'otus', 'отус', 'hexlet', 'хекслет', 'фоксфорд',
            'skillactory', 'productstar', 'contented', 'skyeng',
            'тетрика', 'skysmart', 'stepik', 'coursera', 'умскул'
        }
        
        # События
        self.event_keywords = {
            'митап', 'meetup', 'конференция', 'вебинар',
            'воркшоп', 'мастер-класс', 'семинар', 'хакатон',
            'регистрация на', 'записаться на', 'приглашаем на'
        }
    
    def should_filter_message(self, text: str) -> Tuple[bool, str]:
        """Определяет, нужно ли фильтровать сообщение"""
        if not text:
            return False, ""
        
        text_lower = text.lower()
        
        # Проверка на рекламу
        if self.config.filter_ads:
            for marker in self.ad_markers:
                if marker in text_lower:
                    self.filtered_count += 1
                    return True, "Реклама"
        
        # Проверка на школы и события
        if self.config.filter_schools:
            for school in self.school_keywords:
                if school in text_lower:
                    self.filtered_count += 1
                    return True, "Интернет-школа"
            
            for event in self.event_keywords:
                if event in text_lower:
                    self.filtered_count += 1
                    return True, "Митап/Конференция"
        
        return False, ""
