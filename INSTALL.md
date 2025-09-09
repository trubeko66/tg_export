# Установка и настройка

## Быстрая установка

1. **Установите Python 3.8+**
   ```bash
   # Windows
   # Скачайте с https://python.org
   
   # Linux/macOS
   sudo apt install python3 python3-pip  # Ubuntu/Debian
   brew install python3                  # macOS
   ```

2. **Установите зависимости**
   ```bash
   pip install -r requirements.txt
   ```

3. **Получите Telegram API credentials**
   - Перейдите на https://my.telegram.org/auth
   - Войдите в аккаунт Telegram
   - Создайте приложение в "API development tools"
   - Сохраните API ID и API Hash

4. **Запустите программу**
   ```bash
   python telegram_exporter.py
   ```

## Первоначальная настройка

При первом запуске программа предложит настроить:

- **Telegram API**: API ID, API Hash, номер телефона
- **Уведомления** (опционально): Bot Token и Chat ID
- **WebDAV** (опционально): для синхронизации данных

## Создание бота для уведомлений

1. Найдите @BotFather в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Сохраните Bot Token
5. Найдите Chat ID (используйте @userinfobot)

## Управление настройками

```bash
python config.py
```

## Структура файлов

- `.config.json` — настройки программы
- `.channels` — список каналов
- `export.log` — логи работы
- `exports/` — папка с экспортированными данными
