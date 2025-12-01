import logging
import asyncio
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
            # Пытаемся получить ID автора, если он есть в объекте, иначе 0
            author_id = getattr(message, 'author_id', 0)
            author = str(message.author)
            text = message.text

            # --- ЛОГИКА 2: Сохранение в БД ---
            if self.database:
                try:
                    # Передаем все аргументы, которые ждет Database.add_message
                    # chat_id, author_id, author_username, text, is_outgoing
                    await self.database.add_message(
                        chat_id=chat_id,
                        author_id=author_id,
                        author_username=author,
                        text=text,
                        is_outgoing=False
                    )
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
                            # Сохраняем исходящее сообщение бота
                            # Для бота ID обычно 0 или ID аккаунта (если известен, но тут ставим 0)
                            await self.database.add_message(
                                chat_id=chat_id,
                                author_id=0,
                                author_username="Bot",
                                text=response,
                                is_outgoing=True
                            )
                    else:
                        logger.error("❌ QueueManager не инициализирован!")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка в handle: {e}", exc_info=True)
            return False

    async def handle_message(self, message):
        """Алиас для совместимости"""
        return await self.handle(message)
