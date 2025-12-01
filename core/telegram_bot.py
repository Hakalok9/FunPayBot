"""
core/telegram_bot.py — ТОЛЬКО HELP И STATS (БЕЗ DEBUG)
"""
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

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
            
            self.app = Application.builder().token(self.token).build()
            
            self.app.add_handler(CommandHandler("help", self._cmd_help))
            self.app.add_handler(CommandHandler("stats", self._cmd_stats))
            self.app.add_handler(CallbackQueryHandler(self._button_callback))
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
            
            await self.app.initialize()
            await self.app.start()
            
            await self.app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
            logger.info("✓ Telegram бот запущен (polling активен)")
            
            try:
                await self.app.bot.send_message(
                    chat_id=self.admin_id,
                    text="🤖 FunPay Bot запущен!\n\nБот активен и слушает события FunPay.",
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

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        try:
            self.stats["commands_processed"] += 1
            
            await update.message.reply_text(
                "📖 <b>Справка</b>\n\n"
                "Доступные команды:\n"
                "/help - Эта справка\n"
                "/stats - Статистика бота\n\n"
                "<b>Как это работает:</b>\n"
                "1️⃣ Когда приходит сообщение из FunPay, я отправляю тебе уведомление\n"
                "2️⃣ Нажимаешь кнопку <b>\"✍️ Ответить\"</b>\n"
                "3️⃣ Пишешь ответ в этот чат\n"
                "4️⃣ Ответ автоматически отправится в FunPay",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"❌ Ошибка в _cmd_help: {e}", exc_info=True)

    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stats"""
        try:
            self.stats["commands_processed"] += 1
            
            await update.message.reply_text(
                f"📊 <b>Статистика</b>\n\n"
                f"📬 Уведомлений отправлено: <b>{self.stats['notifications_sent']}</b>\n"
                f"💬 Ответов отправлено: <b>{self.stats['replies_sent']}</b>\n"
                f"⌨️ Команд обработано: <b>{self.stats['commands_processed']}</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"❌ Ошибка в _cmd_stats: {e}", exc_info=True)

    async def _button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий кнопок"""
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data.startswith("reply_"):
                chat_id = int(query.data.split("_")[1])
                self.awaiting_reply[query.from_user.id] = chat_id
                
                await query.edit_message_text(
                    text=query.message.text + "\n\n✍️ <b>Режим ответа активирован.</b> Напиши ответ:",
                    parse_mode="HTML"
                )
                
            elif query.data == "skip":
                await query.edit_message_text(
                    text=query.message.text + "\n\n⏭️ <b>Пропущено.</b>",
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"❌ Ошибка в _button_callback: {e}", exc_info=True)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        try:
            user_id = update.effective_user.id
            text = update.message.text
            
            if user_id in self.awaiting_reply:
                chat_id = self.awaiting_reply[user_id]
                
                if self.on_reply_callback:
                    try:
                        success = await self.on_reply_callback(chat_id, text)
                        if success:
                            self.stats["replies_sent"] += 1
                            await update.message.reply_text("✅ Ответ отправлен в FunPay!")
                        else:
                            await update.message.reply_text("❌ Ошибка отправки ответа")
                    except Exception as e:
                        logger.error(f"❌ Ошибка: {e}", exc_info=True)
                        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
                
                del self.awaiting_reply[user_id]
            else:
                await update.message.reply_text(
                    "ℹ️ Нет активных сообщений для ответа.\n\n"
                    "Когда приходит сообщение из FunPay, нажми кнопку <b>'✍️ Ответить'</b>.",
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_message: {e}", exc_info=True)

    async def send_message_notification(self, chat_id, username, text, timestamp=None):
        """Отправка уведомления о новом сообщении с кнопками"""
        try:
            if not self.app:
                logger.error("❌ Бот не инициализирован")
                return
            
            notification = (
                f"💬 <b>Новое сообщение от {username}</b>\n\n"
                f"<b>Сообщение:</b>\n{text[:500]}"
            )
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✍️ Ответить", callback_data=f"reply_{chat_id}"),
                    InlineKeyboardButton("⏭️ Пропустить", callback_data="skip")
                ]
            ])
            
            await self.app.bot.send_message(
                chat_id=self.admin_id, 
                text=notification,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
            self.stats["notifications_sent"] += 1
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")

    async def send_order_notification(self, order_id, buyer_username, description, price=None):
        """Отправка уведомления о новом заказе"""
        try:
            if not self.app:
                logger.error("❌ Бот не инициализирован")
                return
            
            price_str = f"{price:.2f} ₽" if price else "не указана"
            notification = f"🛒 <b>Новый заказ!</b>\n\n<b>ID:</b> {order_id}\n<b>Покупатель:</b> {buyer_username}\n<b>Описание:</b> {description}\n<b>Цена:</b> {price_str}"
            
            await self.app.bot.send_message(
                chat_id=self.admin_id, 
                text=notification,
                parse_mode="HTML"
            )
            self.stats["notifications_sent"] += 1
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о заказе: {e}")
