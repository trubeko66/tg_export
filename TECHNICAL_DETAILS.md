# 🔧 Технические детали системы загрузки

## Архитектура интеллектуальной загрузки

### Основные компоненты

#### MediaDownloader
Основной класс для управления загрузкой медиафайлов с адаптивными алгоритмами.

**Ключевые параметры:**
- `max_workers` (1-32): Максимальное количество потоков
- `current_workers` (1-16): Текущее количество активных потоков
- `adaptive_delay` (0.1-5.0с): Текущая задержка между запросами
- `consecutive_successes`: Счетчик последовательных успешных загрузок

#### Адаптивные алгоритмы

```python
# При flood wait
if flood_wait_seconds > 10:
    multiplier = 2.0  # Агрессивное увеличение задержки
elif flood_wait_seconds > 5:
    multiplier = 1.8
else:
    multiplier = 1.5

adaptive_delay = min(max_delay, adaptive_delay * multiplier)
current_workers = max(1, current_workers - 1)
```

```python
# При успешных загрузках
if time_since_flood > 120 and consecutive_successes >= 15:
    adaptive_delay = max(min_delay, adaptive_delay * 0.95)
    if consecutive_successes % 20 == 0:
        current_workers = min(max_workers, current_workers + 1)
```

### Обработка ошибок

#### FloodWaitError
- **Автоматическое извлечение времени ожидания** из исключения
- **Адаптивное увеличение задержек** в зависимости от длительности блокировки
- **Уменьшение количества потоков** для снижения нагрузки на API

#### Сетевые ошибки
```python
if "connection" in error_msg or "network" in error_msg:
    wait_time = random.uniform(3, 8)  # Увеличенная задержка
    await asyncio.sleep(wait_time)
```

#### Ошибки доступа
```python
if "permission" in error_msg or "access" in error_msg:
    return False  # Не повторяем загрузку
```

### Оптимизации производительности

#### Кеширование размеров файлов
```python
# Кеш действителен 5 минут
cache_key = f"media_size_{channel.title}"
if cache_key in cache and time.time() - cache[cache_key][0] < 300:
    return cache[cache_key][1]
```

#### Батчевая обработка
```python
batch_size = max(5, current_workers * 2)
batches = [queue[i:i + batch_size] for i in range(0, len(queue), batch_size)]
```

#### Джиттер для предотвращения синхронизации
```python
def _get_smart_delay(self) -> float:
    jitter = random.uniform(0.8, 1.2)
    return self.adaptive_delay * jitter
```

## Статистика и мониторинг

### Ключевые метрики

1. **success_rate**: Процент успешных загрузок
2. **flood_wait_rate**: Процент запросов с flood wait
3. **downloads_per_minute**: Скорость загрузки
4. **time_since_last_flood**: Время стабильной работы

### Пример статистики
```python
{
    'total_attempts': 150,
    'successful_downloads': 142,
    'flood_waits': 3,
    'success_rate': 94.67,
    'flood_wait_rate': 2.0,
    'downloads_per_minute': 12.5,
    'current_workers': 4,
    'adaptive_delay': 0.8,
    'consecutive_successes': 25
}
```

## Конфигурация

### Новые параметры в config
```python
@dataclass
class StorageConfig:
    media_download_threads: int = 4
    adaptive_download: bool = True
    min_download_delay: float = 0.1
    max_download_delay: float = 3.0
```

### Применение настроек
```python
media_downloader = MediaDownloader(channel_dir, max_workers=media_threads)
if adaptive_download:
    media_downloader.min_delay = min_delay
    media_downloader.max_delay = max_delay
```

## Решенные проблемы

### 1. Файлы нулевого размера
**Проблема**: ThreadPoolExecutor создавал новый event loop в каждом потоке
```python
# Было (неправильно)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(client.download_media(message, file_path))
```

**Решение**: Использование asyncio.gather в одном event loop
```python
# Стало (правильно)
download_results = await asyncio.gather(*download_tasks, return_exceptions=True)
```

### 2. Частые Flood Wait
**Проблема**: Слишком агрессивная загрузка без адаптации

**Решение**: Интеллектуальная система адаптации
- Консервативный старт (2 потока, 0.5с задержка)
- Автоматическое снижение нагрузки при блокировках
- Постепенное ускорение при стабильной работе

### 3. Производительность UI
**Проблема**: Пересчет размеров файлов при каждом обновлении

**Решение**: Кеширование с TTL и ограничением размера
```python
# Кеш с временными метками
self._media_size_cache[cache_key] = (time.time(), size_mb)

# Автоочистка при превышении лимита
if len(self._media_size_cache) > 100:
    oldest_keys = sorted(cache.keys(), key=lambda k: cache[k][0])[:50]
    for key in oldest_keys:
        del cache[key]
```

## Рекомендации по настройке

### Для быстрых соединений
```python
media_download_threads = 8
min_download_delay = 0.1
max_download_delay = 2.0
```

### Для медленных соединений
```python
media_download_threads = 2
min_download_delay = 0.5
max_download_delay = 5.0
```

### Для нестабильных соединений
```python
media_download_threads = 4
min_download_delay = 1.0
max_download_delay = 10.0
adaptive_download = True  # Обязательно
```

## Отладка

### Включение подробного логирования
```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

### Мониторинг статистики
```python
stats = media_downloader.get_download_stats()
print(f"Success rate: {stats['success_rate']:.1f}%")
print(f"Flood waits: {stats['flood_waits']}")
print(f"Current settings: {stats['current_workers']} workers, {stats['adaptive_delay']:.1f}s delay")
```

### Анализ логов
Ищите в логах:
- `🚫 Flood wait` - события блокировки API
- `⚡ Постепенное ускорение` - адаптация параметров
- `✓ Файл ... успешно загружен` - успешные загрузки с размером и скоростью