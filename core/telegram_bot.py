"""
ПЕРЕРАБОТАННЫЙ telegram_bot.py
Основан на рабочем тестовом боте - упрощённый и надёжный
"""

import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logger = logging.getLogger("FunPayBot.TelegramBot")

class TelegramBot:
    def __init__(self, token, admin_id, on_reply_callback=None):
        self.token = token
        self.admin_id = int(admin_id)
        self.on_reply_callback = on_reply_callback
        self.app = None
        self.awaiting_reply = {}
        self.stats = {"notifications_sent": 0, "replies_sent": 0, "commands_processed": 0}
        logger.info("✓ Telegram бот инициализирован")

    async def start(self):
        """Запуск бота"""
        try:
            logger.info("🔄 Запуск Telegram бота...")
            
            # Создаём приложение
            self.app = Application.builder().token(self.token).build()
            
            # Регистрируем обработчики
            self.app.add_handler(CommandHandler("start", self._cmd_start))
            self.app.add_handler(CommandHandler("help", self._cmd_help))
            self.app.add_handler(CommandHandler("stats", self._cmd_stats))
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
            
            # Инициализируем
            await self.app.initialize()
            await self.app.start()
            
            # Запускаем polling
            await self.app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            
            logger.info("✓ Telegram бот запущен (polling активен)")
            
            # Отправляем уведомление о запуске
            try:
                await self.app.bot.send_message(
                    chat_id=self.admin_id,
                    text="🤖 <b>FunPay Bot запущен!</b>\n\nБот активен и слушает события FunPay.",
                    parse_mode="HTML"
                )
                logger.info("✅ Уведомление о запуске отправлено")
            except Exception as e:
                logger.error(f"⚠️ Не удалось отправить уведомление: {e}")
            
        except Exception as e:
            logger.error(f"✗ Ошибка запуска Telegram бота: {e}", exc_info=True)
            raise

    async def stop(self):
        """Остановка бота"""
        try:
            if self.app:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
            logger.info("✓ Telegram бот остановлен")
        except Exception as e:
            logger.error(f"Ошибка при остановке: {e}")

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        try:
            user_id = update.effective_user.id
            logger.info(f"📥 /start от user_id={user_id}")
            self.stats["commands_processed"] += 1
            
            await update.message.reply_text(
                "🤖 <b>FunPay Bot (Production)</b>\n\n"
                "Бот активен!\n\n"
                "<b>Команды:</b>\n"
                "/start - Запуск\n"
                "/help - Справка\n"
                "/stats - Статистика",
                parse_mode="HTML"
            )
            logger.info(f"✅ Ответ на /start отправлен")
        except Exception as e:
            logger.error(f"❌ Ошибка в _cmd_start: {e}", exc_info=True)

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        try:
            user_id = update.effective_user.id
            logger.info(f"📥 /help от user_id={user_id}")
            self.stats["commands_processed"] += 1
            
            await update.message.reply_text(
                "📖 <b>Справка</b>\n\n"
                "Команды для управления ботом:\n"
                "/start - Запуск\n"
                "/help - Эта справка\n"
                "/stats - Статистика",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"❌ Ошибка в _cmd_help: {e}", exc_info=True)

    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stats"""
        try:
            user_id = update.effective_user.id
            logger.info(f"📥 /stats от user_id={user_id}")
            self.stats["commands_processed"] += 1
            
            await update.message.reply_text(
                f"📊 <b>Статистика</b>\n\n"
                f"Уведомлений отправлено: {self.stats['notifications_sent']}\n"
                f"Ответов отправлено: {self.stats['replies_sent']}\n"
                f"Команд обработано: {self.stats['commands_processed']}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"❌ Ошибка в _cmd_stats: {e}", exc_info=True)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        try:
            user_id = update.effective_user.id
            text = update.message.text
            logger.info(f"📥 Сообщение от user_id={user_id}: {text[:50]}")
            
            # Если ожидаем ответ
            if user_id in self.awaiting_reply:
                chat_id = self.awaiting_reply[user_id]
                if self.on_reply_callback:
                    try:
                        success = await self.on_reply_callback(chat_id, text)
                        if success:
                            self.stats["replies_sent"] += 1
                            await update.message.reply_text("✅ Ответ отправлен!")
                        else:
                            await update.message.reply_text("❌ Ошибка отправки")
                    except Exception as e:
                        logger.error(f"Ошибка: {e}")
                        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
                del self.awaiting_reply[user_id]
        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_message: {e}", exc_info=True)

    async def send_message_notification(self, chat_id, username, text, timestamp=None):
        """Отправка уведомления о новом сообщении"""
        try:
            if not self.app:
                logger.error("❌ Бот не инициализирован")
                return
            
            notification = f"💬 Новое сообщение от {username}\n\n{text[:200]}"
            await self.app.bot.send_message(chat_id=self.admin_id, text=notification)
            self.stats["notifications_sent"] += 1
            logger.info(f"✅ Уведомление о сообщении отправлено")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")

    async def send_order_notification(self, order_id, buyer_username, description, price=None):
        """Отправка уведомления о новом заказе"""
        try:
            if not self.app:
                logger.error("❌ Бот не инициализирован")
                return
            
            price_str = f"{price:.2f} ₽" if price else "не указана"
            notification = f"🛒 Новый заказ!\n\nID: {order_id}\nПокупатель: {buyer_username}\nОписание: {description}\nЦена: {price_str}"
            await self.app.bot.send_message(chat_id=self.admin_id, text=notification)
            self.stats["notifications_sent"] += 1
            logger.info(f"✅ Уведомление о заказе отправлено")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о заказе: {e}")
