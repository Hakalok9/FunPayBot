"""
handlers/message_handler.py
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("FunPayBot.MessageHandler")

class MessageHandler:
    def __init__(self, database, telegram_bot, autoresponder, queue_manager):
        self.database = database
        self.telegram_bot = telegram_bot
        self.autoresponder = autoresponder
        self.queue_manager = queue_manager
        self.stats = {
            "messages_processed": 0,
            "autoresponses_sent": 0,
            "errors": 0
        }
        logger.info("✓ Обработчик сообщений инициализирован")

    async def handle(self, message):
        """
        Обработка нового сообщения
        НЕ пытаемся получить историю чата - работаем только с данными из события
        
        Args:
            message: Объект сообщения из FunPayAPI (types.Message)
        """
        try:
            # Извлекаем данные НАПРЯМУЮ из объекта message
            chat_id = getattr(message, 'chat_id', None)
            author = getattr(message, 'author', 'Unknown')
            text = getattr(message, 'text', '')
            
            if not chat_id:
                logger.error("❌ Сообщение без chat_id, пропускаем")
                return False

            logger.info(f"📥 Новое сообщение от {author} (chat_id={chat_id}): {text[:50]}")

            # Отправляем уведомление в Telegram (БЕЗ попыток получить историю)
            try:
                await self.telegram_bot.send_message_notification(
                    chat_id=chat_id,
                    username=author,
                    text=text
                )
                logger.info(f"✅ Уведомление отправлено в Telegram (chat_id={chat_id})")
            except Exception as e:
                logger.error(f"⚠️ Ошибка отправки уведомления: {e}", exc_info=True)

            # Сохраняем в БД
            try:
                await self.database.save_message(
                    chat_id=chat_id,
                    username=author,
                    text=text,
                    timestamp=datetime.now(),
                    is_incoming=True
                )
                logger.info(f"✅ Сообщение сохранено в БД (chat_id={chat_id})")
            except Exception as e:
                logger.error(f"⚠️ Ошибка сохранения в БД: {e}")

            self.stats["messages_processed"] += 1
            return True

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"❌ Критическая ошибка обработки сообщения: {e}", exc_info=True)
            return False

    def get_stats(self):
        """Получение статистики"""
        return self.stats.copy()
