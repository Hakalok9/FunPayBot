import sys
import signal
import asyncio
import platform
from config import Config

# ============================================
# FAIL-FAST VALIDATION (критично)
# ============================================
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
from autoresponder.templates import TemplateManager
from autoresponder.autoresponder import AutoResponder

class FunPayBot:
    def __init__(self):
        self.logger = setup_logger(level=Config.LOG_LEVEL)
        self.logger.info("=" * 80)
        self.logger.info("🚀 ЗАПУСК FUNPAY BOT (PRODUCTION)")
        self.logger.info("=" * 80)
        self.db = None
        self.funpay_client = None
        self.telegram_bot = None
        self.queue_manager = None
        self.event_handler = None
        self.autoresponder = None
        self.running = False

    async def initialize(self):
        try:
            self.logger.info("🔧 Инициализация компонентов...")
            
            self.db = Database(Config.DATABASE_PATH)
            await self.db.connect()
            await self.db.initialize()
            
            self.funpay_client = FunPayClient(
                token=Config.FUNPAY_TOKEN,
                requests_delay=Config.FUNPAY_REQUESTS_DELAY,
                notify_admin_callback=self._notify_admin
            )
            await self.funpay_client.connect()
            if not self.funpay_client.account:
                raise RuntimeError("Не удалось подключиться к FunPay. Проверь golden_key и интернет (может нужен VPN)")
            self.queue_manager = MessageQueueManager(
                max_size=Config.MESSAGE_QUEUE_MAX_SIZE,
                send_delay=Config.MESSAGE_SEND_DELAY
            )
            
            template_manager = TemplateManager(self.db)
            await template_manager.reload_templates()
            self.autoresponder = AutoResponder(template_manager, Config.AUTO_RESPONDER_ENABLED)
            
            self.telegram_bot = TelegramBot(
                token=Config.TELEGRAM_BOT_TOKEN,
                admin_id=Config.TELEGRAM_ADMIN_ID,
                on_reply_callback=self._handle_telegram_reply
            )
            
            message_handler = MessageHandler(
                database=self.db,
                account_id=self.funpay_client.account.id,
                telegram_bot=self.telegram_bot,
                autoresponder=self.autoresponder
            )
            order_handler = OrderHandler(
                database=self.db,
                telegram_bot=self.telegram_bot
            )
            self.event_handler = EventHandler(message_handler, order_handler)
            
            self.funpay_client.on("on_message", self.event_handler.handle_message)
            self.funpay_client.on("on_order", self.event_handler.handle_order)
            
            self.logger.info("✅ Все компоненты инициализированы")
            
        except Exception as e:
            self.logger.error(f"❌ Критическая ошибка инициализации: {e}", exc_info=True)
            await self.shutdown()
            raise

    async def start(self):
        self.running = True
        await self.telegram_bot.start()
        await self.queue_manager.start(self._send_message_callback)
        self.logger.info("=" * 80)
        self.logger.info("✅ БОТ ПОЛНОСТЬЮ ЗАПУЩЕН И РАБОТАЕТ")
        self.logger.info("=" * 80)
        await self.funpay_client.start_listening()

    async def shutdown(self):
        if not self.running:
            return
        self.logger.info("=" * 80)
        self.logger.info("🛑 ОСТАНОВКА БОТА (GRACEFUL SHUTDOWN)...")
        self.logger.info("=" * 80)
        self.running = False
        
        try:
            if self.funpay_client:
                self.logger.info("Остановка FunPay клиента...")
                await self.funpay_client.stop()
            if self.queue_manager:
                self.logger.info("Остановка менеджера очереди...")
                await self.queue_manager.stop()
            if self.telegram_bot:
                self.logger.info("Остановка Telegram бота...")
                await self.telegram_bot.stop()
            if self.db:
                self.logger.info("Закрытие соединения с БД...")
                await self.db.disconnect()
            self.logger.info("✅ БОТ ОСТАНОВЛЕН")
        except Exception as e:
            self.logger.error(f"Ошибка при остановке: {e}")

    async def _send_message_callback(self, chat_id: int, text: str) -> bool:
        try:
            success = await self.funpay_client.send_message(chat_id, text)
            if success:
                await self.db.add_message(
                    chat_id=chat_id,
                    author_id=self.funpay_client.account.id,
                    author_username=self.funpay_client.account.username,
                    text=text,
                    is_outgoing=True
                )
            return success
        except Exception as e:
            self.logger.error(f"Ошибка отправки сообщения: {e}")
            return False

    async def _handle_telegram_reply(self, chat_id: int, text: str) -> bool:
        return await self.queue_manager.add_message(
            chat_id=chat_id,
            text=text,
            priority=MessagePriority.HIGH
        )
    
    async def _notify_admin(self, message: str):
        """Уведомление админа о критических проблемах"""
        if self.telegram_bot and self.telegram_bot.app:
            try:
                await self.telegram_bot.app.bot.send_message(
                    chat_id=self.telegram_bot.admin_id,
                    text=f"⚠️ <b>ALERT</b>\n\n{message}",
                    parse_mode="HTML"
                )
            except Exception as e:
                self.logger.error(f"Не удалось отправить уведомление админу: {e}")

# ============================================
# GRACEFUL SHUTDOWN (КРОСС-ПЛАТФОРМЕННЫЙ)
# ============================================
async def main():
    bot = FunPayBot()
    
    # Обработчик сигналов (только для Unix/Linux)
    if platform.system() != 'Windows':
        loop = asyncio.get_event_loop()
        
        def signal_handler(sig):
            bot.logger.info(f"Получен сигнал {sig}, остановка...")
            asyncio.create_task(bot.shutdown())
        
        # Регистрация обработчиков SIGINT и SIGTERM (только Linux)
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
    
    try:
        await bot.initialize()
        await bot.start()
    except KeyboardInterrupt:
        bot.logger.info("\n⚠️ Прервано пользователем (Ctrl+C)")
    except Exception as e:
        bot.logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
    finally:
        await bot.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Бот остановлен")
