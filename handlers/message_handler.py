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

    async def handle(self, chat):
        """
        Обработка нового сообщения
        
        Args:
            chat: Объект ChatShortcut из FunPayAPI
                  Атрибуты ChatShortcut:
                  - id: int - ID чата
                  - name: str - имя собеседника
                  - last_message_text: str - текст последнего сообщения (может быть пусто если медиа)
                  - last_message_type: тип сообщения (text, image, sticker и т.д.)
                  - unread: bool - есть ли непрочитанные
        """
        try:
            # ChatShortcut использует эти атрибуты:
            chat_id = getattr(chat, 'id', None)
            username = getattr(chat, 'name', 'Unknown')
            text = getattr(chat, 'last_message_text', None)
            last_message_type = getattr(chat, 'last_message_type', None)
            unread = getattr(chat, 'unread', False)
            
            logger.info(f"📥 Сообщение: chat_id={chat_id}, username={username}, unread={unread}")
            logger.info(f"   Тип: {last_message_type}, Текст: {text[:100] if text else '(пусто)'}")
            
            if not chat_id:
                logger.error(f"❌ Не удалось получить chat_id")
                return False
            
            # Если текст пуст - это медиа (фото, видео, стикер, файл и т.д.)
            if not text:
                message_type = str(last_message_type).upper() if last_message_type else "UNKNOWN"
                text = f"[{message_type}]"
                logger.info(f"📷 Получено медиа-сообщение: {message_type}")
            
            logger.info(f"📥 Новое сообщение от {username} (chat_id={chat_id}): {text[:50]}")
            
            # Отправляем уведомление в Telegram
            try:
                await self.telegram_bot.send_message_notification(
                    chat_id=chat_id,
                    username=username,
                    text=text
                )
                logger.info(f"✅ Уведомление отправлено в Telegram (chat_id={chat_id})")
            except Exception as e:
                logger.error(f"⚠️ Ошибка отправки уведомления: {e}", exc_info=True)
                # НЕ падаем, продолжаем работу
            
            # Сохраняем в БД (если доступна)
            try:
                if self.database and hasattr(self.database, 'save_message'):
                    await self.database.save_message(
                        chat_id=chat_id,
                        username=username,
                        text=text,
                        timestamp=datetime.now(),
                        is_incoming=True
                    )
                    logger.info(f"✅ Сообщение сохранено в БД (chat_id={chat_id})")
                else:
                    logger.warning(f"⚠️ БД не имеет метода save_message, пропускаем сохранение")
                    
            except Exception as e:
                logger.warning(f"⚠️ Ошибка сохранения в БД (бот продолжает работу): {e}")
                # НЕ падаем, продолжаем работу!
            
            self.stats["messages_processed"] += 1
            return True
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"❌ Критическая ошибка обработки сообщения: {e}", exc_info=True)
            # Даже при критической ошибке - возвращаем False вместо падения
            return False

    def get_stats(self):
        """Получение статистики"""
        return self.stats.copy()
