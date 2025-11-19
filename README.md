# FunPay Viper Bot (Production-Ready)

Production-ready бот для автоматизации FunPay с полным набором критических защит:
- ✅ Fail-fast валидация конфигурации
- ✅ Graceful shutdown (SIGINT/SIGTERM)
- ✅ Exponential backoff + reconnect
- ✅ Дедупликация событий по хэшу
- ✅ Watchdog (алерты при отсутствии событий)
- ✅ Rate limiting с очередью
- ✅ Ротация логов
- ✅ SQLite с увеличенным timeout

## Быстрый старт

### 1. Установка зависимостей

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Настройка .env

```bash
cp .env.example .env
nano .env
```

Заполните обязательные параметры:
- `FUNPAY_TOKEN` - golden_key из cookies FunPay
- `TELEGRAM_BOT_TOKEN` - токен от @BotFather
- `TELEGRAM_ADMIN_ID` - ваш Telegram ID

### 3. Запуск

```bash
python bot.py
```

## Production развертывание

### Systemd (рекомендуется)

```bash
# Копируем unit файл
sudo cp funpaybot.service /etc/systemd/system/

# Редактируем пути
sudo nano /etc/systemd/system/funpaybot.service

# Создаем директорию для логов
sudo mkdir -p /var/log/funpaybot
sudo chown botuser:botuser /var/log/funpaybot

# Запуск
sudo systemctl daemon-reload
sudo systemctl enable funpaybot
sudo systemctl start funpaybot
sudo systemctl status funpaybot
```

### Docker

```bash
docker build -t funpaybot .
docker run -d --name funpaybot --env-file .env --restart unless-stopped funpaybot
```

## Критические особенности

### 1. Fail-Fast валидация
Бот немедленно упадет при старте если не установлены:
- FUNPAY_TOKEN
- TELEGRAM_BOT_TOKEN
- TELEGRAM_ADMIN_ID (должен быть integer)

### 2. Graceful Shutdown
При получении SIGINT/SIGTERM корректно останавливает все компоненты:
- FunPay клиент
- Очередь сообщений
- Telegram бот
- Закрытие БД

### 3. Exponential Backoff
При падении соединения:
- Задержка: 1s → 2s → 4s → 8s → ... → 300s (макс)
- Уведомление админа при backoff >= 60s

### 4. Watchdog
Алерт в Telegram если нет событий > 10 минут (WATCHDOG_TIMEOUT)

### 5. Дедупликация
Проверка message_hash в БД перед обработкой события

## Telegram команды

- `/start` - Информация о боте
- `/help` - Справка
- `/stats` - Статистика

## Мониторинг

```bash
# Логи через systemd
sudo journalctl -u funpaybot -f

# Логи из файлов
tail -f /var/log/funpaybot/output.log
tail -f logs/funpay_bot_*.log

# Статус
sudo systemctl status funpaybot
```

## Переменные окружения

### Обязательные
- `FUNPAY_TOKEN` - Golden Key токен
- `TELEGRAM_BOT_TOKEN` - Токен Telegram бота
- `TELEGRAM_ADMIN_ID` - ID администратора

### Опциональные (с дефолтами)
- `LOG_LEVEL=INFO` - Уровень логирования
- `MESSAGE_SEND_DELAY=2.5` - Задержка между сообщениями (антиспам)
- `DB_TIMEOUT=30.0` - Timeout SQLite (против "database is locked")
- `RECONNECT_MAX_BACKOFF=300` - Макс задержка реконнекта
- `WATCHDOG_TIMEOUT=600` - Таймаут watchdog (секунды)

## Безопасность

⚠️ **КРИТИЧНО:**
1. Не коммитьте .env файл
2. Используйте VPN если FunPay заблокирован
3. Задержка MESSAGE_SEND_DELAY минимум 2.5s (риск бана)
4. Права на .env файл: `chmod 600 .env`

## Лицензия

GPL-3.0
