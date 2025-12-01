import sys
import signal
import asyncio
import platform

from config import Config

# FAIL-FAST VALIDATION
if not Config.FUNPAY_TOKEN:
    raise SystemExit("FATAL: FUNPAY_TOKEN not set in .env")

if not Config.TELEGRAM_BOT_TOKEN:
    raise SystemExit("FATAL: TELEGRAM_BOT_TOKEN not set in .env")

try:
    _ = int(Config.TELEGRAM_ADMIN_ID) if Config.TELEGRAM_ADMIN_ID else None
    if not Config.TELEGRAM_ADMIN_ID:
        raise ValueError()
except (ValueError, TypeError):
    raise SystemExit("FATAL: TELEGRAM_ADMIN_ID must be valid integer")

from utils.logger import setup_logger
from database.database import Database
from core.funpay_client import FunPayClient
from core.telegram_bot import TelegramBot
from core.queue_manager import MessageQueueManager, MessagePriority
from core.event_handler import EventHandler
from handlers.message_handler import MessageHandler
from handlers.order_handler import OrderHandler

logger = setup_logger()


class FunPayBot:
    def __init__(self):
        self.running = False
        self.database = None
        self.funpay_client = None
        self.telegram_bot = None
        self.queue_manager = None
        self.message_handler = None
        self.order_handler = None
        self.event_handler = None

    async def initialize(self):
        logger.info("=" * 80)
        logger.info("🚀 ЗАПУСК FUNPAY BOT (PRODUCTION)")
        logger.info("=" * 80)
        logger.info("🔧 Инициализация компонентов...")

        # БД
        self.database = Database(Config.DATABASE_PATH)
        await self.database.connect()

        # FunPay клиент
        self.funpay_client = FunPayClient(
            token=Config.FUNPAY_TOKEN,
            requests_delay=Config.MESSAGE_SEND_DELAY
        )
        await self.funpay_client.connect()

        # Менеджер очереди
        self.queue_manager = MessageQueueManager(
            max_size=Config.MESSAGE_QUEUE_MAX_SIZE,
            send_delay=Config.MESSAGE_SEND_DELAY
        )

        # Колбэк для ответов из Telegram
        async def reply_callback(chat_id: int, text: str) -> bool:
            await self.funpay_client.send_message(chat_id, text)
            return True

        # Telegram бот
        self.telegram_bot = TelegramBot(
            token=Config.TELEGRAM_BOT_TOKEN,
            admin_id=Config.TELEGRAM_ADMIN_ID,
            on_reply_callback=reply_callback
        )

        # Обработчики
        self.message_handler = MessageHandler(
            database=self.database,
            telegram_bot=self.telegram_bot,
            autoresponder=None,
            queue_manager=self.queue_manager
        )

        self.order_handler = OrderHandler(
            database=self.database,
            telegram_bot=self.telegram_bot
        )

        self.event_handler = EventHandler(
            message_handler=self.message_handler,
            order_handler=self.order_handler
        )

        # Регистрация обработчиков событий FunPay
        self.funpay_client.register_handler(
            "NEW_MESSAGE", self.event_handler.handle_message
        )
        self.funpay_client.register_handler(
            "NEW_ORDER", self.event_handler.handle_order
        )

        logger.info("✅ Все компоненты инициализированы")

    async def start(self):
        self.running = True

        # Старт Telegram бота
        await self.telegram_bot.start()

        # Старт очереди отправки сообщений
        await self.queue_manager.start(self.funpay_client.send_message)

        logger.info("=" * 80)
        logger.info("✅ БОТ ПОЛНОСТЬЮ ЗАПУЩЕН И РАБОТАЕТ")
        logger.info("=" * 80)

        # Прослушивание событий FunPay
        await self.funpay_client.start_listening()

    async def stop(self):
        logger.info("=" * 80)
        logger.info("🛑 ОСТАНОВКА БОТА (GRACEFUL SHUTDOWN)...")
        logger.info("=" * 80)

        self.running = False

        if self.funpay_client:
            logger.info("Остановка FunPay клиента...")
            await self.funpay_client.stop()

        if self.queue_manager:
            logger.info("Остановка менеджера очереди...")
            await self.queue_manager.stop()

        if self.telegram_bot:
            logger.info("Остановка Telegram бота...")
            await self.telegram_bot.stop()

        if self.database:
            logger.info("Закрытие подключения к БД...")
            try:
                await self.database.disconnect()
            except AttributeError:
                logger.info("✓ БД закрыта (метод disconnect отсутствует)")
            except Exception as e:
                logger.error(f"⚠️ Ошибка закрытия БД: {e}")

        logger.info("✓ Все компоненты остановлены")


async def main():
    bot = FunPayBot()

    def signal_handler(sig, frame):
        logger.info(f"Получен сигнал {sig}, остановка бота...")
        asyncio.create_task(bot.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await bot.initialize()
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Получен KeyboardInterrupt, остановка...")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
    finally:
        await bot.stop()


if __name__ == "__main__":
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
