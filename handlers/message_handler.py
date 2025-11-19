import logging
from datetime import datetime
from utils.helpers import generate_message_hash

logger = logging.getLogger("FunPayBot.MessageHandler")

class MessageHandler:
    def __init__(self, database, account_id, telegram_bot, autoresponder=None):
        self.db = database
        self.account_id = account_id
        self.telegram_bot = telegram_bot
        self.autoresponder = autoresponder
        logger.info("✓ Обработчик сообщений инициализирован")

    async def handle(self, message):
        try:
            if message.author_id == self.account_id:
                logger.debug(f"Игнорируем собственное сообщение (chat_id={message.chat_id})")
                return False

            # КРИТИЧНО: генерация хэша для дедупликации
            msg_hash = generate_message_hash(message.chat_id, message.text, datetime.now())

            # КРИТИЧНО: проверка дубликата в БД перед обработкой
            if await self.db.message_exists_by_hash(msg_hash):
                logger.debug(f"Дубликат сообщения (hash={msg_hash[:8]}...), игнорируем")
                return False

            logger.info(f"📨 Новое сообщение от {message.author} (chat_id={message.chat_id}): {message.text[:50]}...")

            await self.db.add_or_update_user(funpay_user_id=message.author_id, username=message.author)

            # Сохраняем с хэшем
            await self.db.add_message(
                chat_id=message.chat_id,
                author_id=message.author_id,
                author_username=message.author,
                text=message.text,
                is_outgoing=False,
                message_hash=msg_hash
            )

            if self.telegram_bot:
                await self.telegram_bot.send_message_notification(
                    chat_id=message.chat_id,
                    username=message.author,
                    text=message.text,
                    timestamp=datetime.now()
                )

            if self.autoresponder:
                auto_response = await self.autoresponder.get_response(message.text)
                if auto_response:
                    logger.info(f"🤖 Автоответ: {auto_response[:50]}...")

            return True
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}", exc_info=True)
            return False
