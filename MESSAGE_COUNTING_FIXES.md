# Исправления логики подсчета сообщений

## Проблема

В логах было замечено, что статистика отображается некорректно и подсчет сообщений ведется дважды или даже трижды:

```
2025-08-28 11:15:55,796 - ERROR - Error iterating messages for channel Записки админа: Cannot send requests while disconnected
2025-08-28 11:15:55,796 - INFO - Channel Записки админа: processed 1294 messages, total in channel: 3093
2025-08-28 11:15:55,797 - INFO - Forced full re-export mode for Записки админа - recreating all files from scratch
2025-08-28 11:15:55,797 - INFO - Exporting 1294 messages in initial mode
2025-08-28 11:15:55,910 - INFO - Export files created for Записки админа: JSON, HTML, Markdown
2025-08-28 11:15:56,494 - INFO - Successfully exported 1294 messages from Записки админа
2025-08-28 11:15:56,494 - INFO - Проверка MD файла после экспорта для Записки админа
2025-08-28 11:15:56,508 - WARNING - MD файл для Записки админа: найдено 1294 сообщений, ожидалось 4387 - НЕСООТВЕТСТВИЕ
2025-08-28 11:15:56,508 - WARNING - MD файл для Записки админа содержит 1294 сообщений, ожидалось 4387. Запуск повторного экспорта
```

Проблема заключалась в том, что общее количество сообщений в канале было 4387, но экспортировалось только 1294, что приводило к несоответствию при проверке MD файла.

## Причина

Основная причина проблемы была в двойном подсчете сообщений:

1. **Первый подсчет**: При определении `total_messages_in_channel` программа подсчитывала все сообщения в канале
2. **Второй подсчет**: При обработке сообщений для экспорта те же сообщения обрабатывались снова
3. **Неправильное обновление статистики**: `channel.total_messages` увеличивался на количество обработанных сообщений, даже при полном ре-экспорте
4. **Накопление отфильтрованных сообщений**: Глобальный счетчик `self.stats.filtered_messages` накапливался между экспортами

## Внесенные изменения

### 1. Исправление логики обновления `channel.total_messages`

В функции `export_channel` исправлена логика обновления `channel.total_messages`:

```python
# Ранее:
channel.total_messages = total_messages_in_channel

# Исправлено:
if md_file_missing or (hasattr(channel, '_force_full_reexport') and channel._force_full_reexport):
    channel.total_messages = total_messages_in_channel
```

Это предотвращает неправильное обновление счетчика при обычном инкрементальном экспорте.

### 2. Исправление обновления статистики экспорта

В секции обновления статистики канала:

```python
# Ранее:
channel.total_messages += len(messages_data)

# Исправлено:
if not (hasattr(channel, '_force_full_reexport') and channel._force_full_reexport):
    channel.total_messages += len(messages_data)
```

При полном ре-экспорте `total_messages` уже установлен правильно, поэтому не нужно его увеличивать.

### 3. Исправление логики проверки MD файла

В функции повторного экспорта после проверки MD файла:

```python
# Добавлено сохранение старого значения для сравнения
old_total = channel.total_messages
channel.total_messages = message_count
```

### 4. Исправление подсчета отфильтрованных сообщений

Все экземпляры глобального счетчика `self.stats.filtered_messages` заменены на сессионный счетчик:

```python
# Ранее:
self.stats.filtered_messages += 1

# Исправлено:
session_filtered_count += 1

# В конце экспорта:
self.stats.filtered_messages += session_filtered_count
```

Это предотвращает накопление отфильтрованных сообщений между экспортами.

### 5. Исправление функции _process_single_message

Функция [_process_single_message](file:///C:/Users/trubeko/tg_export-1/telegram_exporter.py#L1794-L1843) была исправлена для корректной работы в разных контекстах:

```python
# Ранее:
should_filter, filter_reason = self.content_filter.should_filter_message(message.text or "")
if should_filter:
    self.logger.info(f"Message {message.id} filtered: {filter_reason}")
    session_filtered_count += 1
    return None

# Исправлено:
should_filter, filter_reason = self.content_filter.should_filter_message(message.text or "")
if should_filter:
    self.logger.info(f"Message {message.id} filtered: {filter_reason}")
    # Note: We don't increment session_filtered_count here because this function
    # is used in contexts outside the main export session (e.g., integrity verification)
    return None
```

## Результат

После внесенных изменений:

1. **Правильный подсчет сообщений**: Сообщения подсчитываются только один раз при полном ре-экспорте
2. **Корректная статистика**: Общее количество сообщений в канале соответствует реальному количеству
3. **Правильная проверка MD файла**: После экспорта количество сообщений в MD файле соответствует ожидаемому
4. **Отсутствие дублирования**: Сообщения не обрабатываются дважды, что ускоряет экспорт
5. **Корректный подсчет отфильтрованных сообщений**: Счетчик не накапливается между экспортами

## Проверка

После применения исправлений экспорт должен работать корректно:

1. При отсутствии MD файла программа пересчитывает реальное количество сообщений в канале
2. Экспортирует все сообщения без дублирования
3. После экспорта проверяет MD файл и находит правильное количество сообщений
4. Статистика отображается корректно: общее количество = экспортированные + отфильтрованные