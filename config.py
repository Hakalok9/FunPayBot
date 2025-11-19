import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    FUNPAY_TOKEN = os.getenv("FUNPAY_TOKEN", "")
    FUNPAY_REQUESTS_DELAY = int(os.getenv("FUNPAY_REQUESTS_DELAY", "4"))
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", "")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "database.db")
    MESSAGE_QUEUE_MAX_SIZE = int(os.getenv("MESSAGE_QUEUE_MAX_SIZE", "100"))
    MESSAGE_SEND_DELAY = float(os.getenv("MESSAGE_SEND_DELAY", "2.5"))
    AUTO_RESPONDER_ENABLED = os.getenv("AUTO_RESPONDER_ENABLED", "true").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    # Новые параметры для production
    DB_TIMEOUT = float(os.getenv("DB_TIMEOUT", "30.0"))  # таймаут для sqlite
    RECONNECT_MAX_BACKOFF = int(os.getenv("RECONNECT_MAX_BACKOFF", "300"))  # макс. задержка реконнекта
    WATCHDOG_TIMEOUT = int(os.getenv("WATCHDOG_TIMEOUT", "600"))  # watchdog через 10 мин без событий
