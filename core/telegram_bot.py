"""
bots/telegram_bot.py - Telegram бот с поддержкой ответов в FunPay
"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

logger = logging.getLogger("FunPayBot.TelegramBot")

class TelegramBot:
    def __init__(self, token, admin_id, on_reply_callback=None, funpay_client=None):
        self.token = token
        self.admin_id = int(admin_id)
        self.on_reply_callback = on_reply_callback
        self.funpay_client = funpay_client  # Ссылка на FunPayClient для отправки сообщений
        self.app = None
        self.active_chat = None  # Текущий активный чат для ответа
        self.stats = {
            "notifications_sent": 0,
            "replies_sent": 0,
            "commands_processed": 0
        }
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
            self.app.add_handler(CommandHandler("chats", self._cmd_chats))
            self.app.add_handler(CallbackQueryHandler(self._handle_callback))
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
                    text="🤖 FunPay Bot запущен!\n\nБот активен и слушает события FunPay.\n\n/chats - показать активные чаты",
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
                "🤖 FunPay Bot (Production)\n\n"
                "Бот активен!\n\n"
                "Команды:\n"
                "/start - Запуск\n"
                "/chats - Список активных чатов\n"
                "/help - Справка\n"
                "/stats - Статистика\n\n"
                "💡 Когда придёт сообщение, нажми кнопку 'Ответить' и напиши ответ",
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
                "📖 Справка\n\n"
                "Команды для управления ботом:\n"
                "/start - Запуск\n"
                "/chats - Показать активные чаты\n"
                "/help - Эта справка\n"
                "/stats - Статистика\n\n"
                "Как отвечать:\n"
                "1️⃣ Получишь уведомление о новом сообщении\n"
                "2️⃣ Нажми кнопку 'Ответить' чтобы выбрать чат\n"
                "3️⃣ Напиши ответ обычным сообщением\n"
                "4️⃣ Ответ автоматически отправится в FunPay",
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
            
            active_str = f"chat_id={self.active_chat}" if self.active_chat else "нет активного"
            
            await update.message.reply_text(
                f"📊 Статистика\n\n"
                f"Уведомлений отправлено: {self.stats['notifications_sent']}\n"
                f"Ответов отправлено: {self.stats['replies_sent']}\n"
                f"Команд обработано: {self.stats['commands_processed']}\n\n"
                f"Активный чат: {active_str}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"❌ Ошибка в _cmd_stats: {e}", exc_info=True)

    async def _cmd_chats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /chats - показать список чатов"""
        try:
            user_id = update.effective_user.id
            logger.info(f"📥 /chats от user_id={user_id}")
            self.stats["commands_processed"] += 1
            
            if not self.funpay_client or not self.funpay_client.account:
                await update.message.reply_text("❌ FunPay клиент не инициализирован")
                return
            
            try:
                # Получаем список чатов
                account = self.funpay_client.account
                chats = account.get_chats()
                
                if not chats:
                    await update.message.reply_text("📭 Активных чатов не найдено")
                    return
                
                # Создаём кнопки для каждого чата
                keyboard = []
                for chat in chats[:10]:  # Максимум 10 кнопок
                    chat_id = chat.id if hasattr(chat, 'id') else str(chat)
                    chat_name = chat.name if hasattr(chat, 'name') else f"Chat {chat_id}"
                    
                    keyboard.append([
                        InlineKeyboardButton(
                            f"💬 {chat_name}",
                            callback_data=f"select_chat:{chat_id}"
                        )
                    ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "📋 Выбери чат для ответа:",
                    reply_markup=reply_markup
                )
                logger.info(f"✅ Показано {len(chats)} чатов")
                
            except Exception as e:
                logger.error(f"⚠️ Ошибка получения чатов: {e}")
                await update.message.reply_text(f"❌ Ошибка получения чатов: {str(e)[:100]}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка в _cmd_chats: {e}", exc_info=True)

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатия на кнопки"""
        try:
            query = update.callback_query
            await query.answer()  # Убираем "loading"
            
            if query.data.startswith("select_chat:"):
                chat_id = int(query.data.split(":")[1])
                self.active_chat = chat_id
                
                logger.info(f"✅ Выбран чат: {chat_id}")
                
                await query.edit_message_text(
                    f"✅ Чат выбран! (ID: {chat_id})\n\n"
                    f"Теперь напиши ответ обычным сообщением"
                )
                
        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_callback: {e}", exc_info=True)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        try:
            user_id = update.effective_user.id
            text = update.message.text
            
            logger.info(f"📥 Сообщение от user_id={user_id}: {text[:50]}")
            
            # Если есть активный чат - отправляем ответ в FunPay
            if self.active_chat:
                logger.info(f"📤 Отправляю ответ в чат {self.active_chat}: {text[:50]}")
                
                if self.funpay_client:
                    try:
                        # Отправляем сообщение в FunPay
                        await self.funpay_client.send_message(self.active_chat, text)
                        
                        self.stats["replies_sent"] += 1
                        await update.message.reply_text("✅ Ответ отправлен в FunPay!")
                        logger.info(f"✅ Ответ отправлен в FunPay (chat_id={self.active_chat})")
                        
                        # Очищаем активный чат
                        self.active_chat = None
                        
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки: {e}")
                        await update.message.reply_text(f"❌ Ошибка: {str(e)[:100]}")
                else:
                    await update.message.reply_text("❌ FunPay клиент не инициализирован")
            else:
                await update.message.reply_text(
                    "❓ Нет активного чата\n\n"
                    "Варианты:\n"
                    "1. Используй /chats для выбора чата\n"
                    "2. Нажми кнопку 'Ответить' в уведомлении о сообщении"
                )
                
        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_message: {e}", exc_info=True)

    async def send_message_notification(self, chat_id, username, text, timestamp=None):
        """Отправка уведомления о новом сообщении с кнопкой ответа"""
        try:
            if not self.app:
                logger.error("❌ Бот не инициализирован")
                return
            
            notification = f"💬 Новое сообщение от <b>{username}</b>\n\n{text[:200]}"
            
            # Создаём кнопку для быстрого ответа
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Ответить", callback_data=f"select_chat:{chat_id}")]
            ])
            
            await self.app.bot.send_message(
                chat_id=self.admin_id,
                text=notification,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
            self.stats["notifications_sent"] += 1
            logger.info(f"✅ Уведомление о сообщении отправлено (с кнопкой ответа)")
            
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

    def get_stats(self):
        """Получение статистики"""
        return self.stats.copy()
