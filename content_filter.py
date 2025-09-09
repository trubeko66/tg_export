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
            # Общие
            'erid', 'ерид', 'реклама', '#реклама', '#ad', '#ads', 'advertisement', 'sponsored',
            'спонсор', 'спонсорский', 'партнер', 'партнёр', 'партнерский материал', 'на правах рекламы',
            'промокод', 'промо код', 'купон', 'скидка', 'акция', 'скидки', 'бонус',
            'только сегодня', 'успей купить', 'не упусти', 'выгодно', 'спецпредложение',
            # Хэштеги
            '#спецпроект', 'спецпроект', '#партнерский', '#партнёрский', '#промо'
        }
        
        # IT-школы (основные и распространенные варианты написания)
        self.school_keywords = {
            'skillbox', 'скиллбокс',
            'нетология', 'netology',
            'geekbrains', 'гикбрейнс', 'гикбрэйнс',
            'яндекс практикум', 'практикум', 'yandex practicum',
            'otus', 'отус',
            'hexlet', 'хекслет',
            'skypro', 'скайпро', 'skyeng', 'скайэнг',
            'skillfactory', 'skill factory', 'скиллфэктори',
            'productstar', 'продактстар',
            'contented', 'контентед',
            'tetrika', 'тетрика',
            'skysmart', 'скайсмарт',
            'stepik', 'степик',
            'coursera', 'курсера',
            'udemy', 'юдеми',
            'умскул', 'foxford', 'фоксфорд',
            'яндекс лице', 'лицей яндекса',
            # Добавленные платформы
            'proglib', 'proglib academy', 'проглиб', 'проглиб академи',
            'elbrus', 'elbrus bootcamp', 'эльбрус', 'эльбрус буткемп',
            'itmo', 'итмо',
            'hse', 'hse university', 'вышка', 'вшэ',
            'saint code', 'saint code bootcamp', 'сэйнт код', 'сэйнт код буткемп'
        }
        
        # События
        self.event_keywords = {
            'митап', 'meetup', 'конференция', 'вебинар',
            'воркшоп', 'мастер-класс', 'мастер класс', 'семинар', 'хакатон',
            'день открытых дверей', 'открытый урок', 'гостевая лекция', 'демо-день', 'демо день',
            'регистрация', 'зарегистрируйся', 'зарегистрируйтесь', 'записаться', 'приглашаем'
        }

        # Промо-маркеры для образовательных предложений
        self.promo_keywords = {
            'курс', 'курсы', 'обучение', 'профессия', 'интенсив', 'марафон',
            'набор', 'старт потока', 'старт курса', 'учись', 'стань разработчиком',
            'гарантия трудоустройства', 'трудоустройство', 'ментор', 'портфолио'
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
        
        # Проверка на школы и их промо-мероприятия/материалы
        if self.config.filter_schools:
            contains_school = any(school in text_lower for school in self.school_keywords)
            contains_event = any(event in text_lower for event in self.event_keywords)
            contains_promo = any(promo in text_lower for promo in self.promo_keywords)

            # Фильтруем только если есть упоминание школы и это похоже на промо/мероприятие
            if contains_school and (contains_event or contains_promo):
                self.filtered_count += 1
                return True, "Промо ИТ‑школы/мероприятие"
        
        return False, ""
