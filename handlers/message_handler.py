import logging
import asyncio
import random
from datetime import datetime

logger = logging.getLogger("FunPayBot.MessageHandler")


class MessageHandler:
    def __init__(self, database, telegram_bot, autoresponder, queue_manager):
        self.database = database
        self.telegram_bot = telegram_bot
        self.autoresponder = autoresponder
        self.queue_manager = queue_manager
        logger.info("✓ Обработчик сообщений инициализирован")

    async def handle(self, message):
        """
        Основной метод обработки входящего сообщения.
        """
        try:
            chat_id = message.chat_id
            author = str(message.author)
            text = message.text

            # --- ЛОГИКА 2: Сохранение в БД ---
            if self.database:
                try:
                    # Убрал is_bot=False, так как такого аргумента нет
                    await self.database.add_message(chat_id, author, text)
                except Exception as e:
                    logger.error(f"Ошибка БД при сохранении сообщения: {e}")

            # --- ЛОГИКА 3: Отправка уведомления в Telegram ---
            if self.telegram_bot:
                await self.telegram_bot.send_message_notification(
                    chat_id=chat_id,
                    username=author,
                    text=text
                )
            else:
                logger.error("❌ self.telegram_bot is None!")

            # --- ЛОГИКА 4: Автоответчик (AutoResponder) ---
            if self.autoresponder:
                response = await self.autoresponder.get_response(chat_id, text)
                if response:
                    logger.info(f"🤖 Автоответчик сработал для {author}: {response[:20]}...")

                    # Добавляем ответ в очередь отправки
                    if self.queue_manager:
                        await self.queue_manager.add_message(chat_id, response)

                        # Сохраняем ответ бота в БД
                        if self.database:
                            # Убрал is_bot=True
                            await self.database.add_message(chat_id, "Bot", response)
                    else:
                        logger.error("❌ QueueManager не инициализирован!")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка в handle: {e}", exc_info=True)
            return False

    async def handle_message(self, message):
        """Алиас для совместимости"""
        return await self.handle(message)
