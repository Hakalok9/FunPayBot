"""
core/funpay_client.py — МИНИМУМ ЛОГОВ
"""
import asyncio
import logging
from typing import Optional, Callable
from datetime import datetime, timedelta
from FunPayAPI import Account, Runner, types, enums
from utils.retry import async_retry
from utils.helpers import sanitize_for_funpay
from config import Config

logger = logging.getLogger("FunPayBot.FunPayClient")
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class FunPayClient:
    def __init__(self, token, requests_delay=4, notify_admin_callback=None):
        self.token = token
        self.requests_delay = requests_delay
        self.notify_admin_callback = notify_admin_callback
        self.account = None
        self.runner = None
        self.connected = False
        self.running = False
        self.event_handlers = {}
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "orders_received": 0,
            "connection_errors": 0,
            "reconnects": 0
        }
        self.last_event_time = None
        self.main_loop = None
        self.recently_sent = {}
        self.bot_username = None
        logger.info("✓ FunPay клиент инициализирован")

    async def connect(self):
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"🔄 Подключение к FunPay... (попытка {attempt}/{max_attempts})")
                user_agent = getattr(Config, 'USER_AGENT', DEFAULT_USER_AGENT)
                self.account = Account(self.token, user_agent=user_agent)
                
                await asyncio.get_event_loop().run_in_executor(None, self.account.get)
                
                self.runner = Runner(self.account)
                self.connected = True
                
                username = getattr(self.account, 'username', 'Unknown')
                user_id = getattr(self.account, 'id', 'Unknown')
                self.bot_username = username
                logger.info(f"✓ Авторизован как: {username} (ID: {user_id})")
                return True
            except Exception as e:
                self.stats["connection_errors"] += 1
                logger.error(f"✗ Ошибка подключения (попытка {attempt}/{max_attempts}): {e}")
                if attempt < max_attempts:
                    await asyncio.sleep(5)
                else:
                    raise

    def register_handler(self, event_type: str, handler: Callable):
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
        logger.info(f"✓ Зарегистрирован обработчик для {event_type}")

    async def _trigger_handlers(self, event_type: str, event_data):
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(event_data)
                except Exception as e:
                    logger.error(f"Ошибка в обработчике {event_type}: {e}", exc_info=True)

    def _is_echo_message(self, chat_id: int, message_text: str) -> bool:
        """Проверяем, не это ли наше сообщение, отправленное недавно"""
        if chat_id not in self.recently_sent:
            return False
        
        now = datetime.now()
        for sent_msg in self.recently_sent[chat_id]:
            time_diff = (now - sent_msg["time"]).total_seconds()
            if time_diff < 10 and sent_msg["text"] == message_text:
                return True
        
        return False

    def _cleanup_old_messages(self, chat_id: int):
        """Удаляем сообщения, отправленные более 30 секунд назад"""
        if chat_id not in self.recently_sent:
            return
        
        now = datetime.now()
        self.recently_sent[chat_id] = [
            msg for msg in self.recently_sent[chat_id]
            if (now - msg["time"]).total_seconds() < 30
        ]

    def _sync_listen_loop(self):
        logger.info("🔄 Запуск прослушивания событий FunPay (sync loop)...")
        try:
            for event in self.runner.listen(requests_delay=self.requests_delay):
                if not self.running:
                    break
                
                self.last_event_time = datetime.now()
                
                try:
                    if event.type == enums.EventTypes.LAST_CHAT_MESSAGE_CHANGED:
                        self.stats["messages_received"] += 1
                        chat_id = event.chat.id
                        author = getattr(event.chat, 'name', 'Unknown')
                        message_text = getattr(event.chat, 'last_message_text', '')
                        
                        self._cleanup_old_messages(chat_id)
                        
                        if self._is_echo_message(chat_id, message_text):
                            continue
                        
                        if author == self.bot_username:
                            continue
                        
                        logger.info(f"📥 Новое сообщение в чате {chat_id} от {author}")
                        
                        class MinimalMessage:
                            def __init__(self, chat_id, author, text):
                                self.chat_id = chat_id
                                self.author = author
                                self.text = text
                        
                        message = MinimalMessage(chat_id, author, message_text)
                        
                        asyncio.run_coroutine_threadsafe(
                            self._trigger_handlers("NEW_MESSAGE", message),
                            self.main_loop
                        )
                        
                    elif event.type == enums.EventTypes.NEW_ORDER:
                        self.stats["orders_received"] += 1
                        logger.info(f"🛒 Новый заказ получен")
                        
                        asyncio.run_coroutine_threadsafe(
                            self._trigger_handlers("NEW_ORDER", event.order),
                            self.main_loop
                        )
                        
                except Exception as e:
                    logger.error(f"⚠️ Ошибка обработки события: {e}", exc_info=True)
                    continue
                    
        except Exception as e:
            logger.error(f"Ошибка в sync listen loop: {e}", exc_info=True)
            self.running = False

    async def start_listening(self):
        if not self.connected:
            raise RuntimeError("FunPay клиент не подключен")
        
        self.main_loop = asyncio.get_event_loop()
        
        self.running = True
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_listen_loop)

    async def stop(self):
        logger.info("⏹️ Остановка FunPay клиента...")
        self.running = False
        if self.runner:
            try:
                self.runner.stop()
            except:
                pass
        self.connected = False

    async def send_message(self, chat_id: int, text: str):
        """Отправка сообщения без retry на парсинг ошибку"""
        try:
            sanitized_text = sanitize_for_funpay(text)
            loop = asyncio.get_event_loop()
            
            try:
                await loop.run_in_executor(
                    None,
                    self.account.send_message,
                    chat_id,
                    sanitized_text
                )
            except AttributeError as e:
                if "'NoneType' object has no attribute 'text'" in str(e):
                    logger.debug(f"⚠️ Сообщение отправлено, но парсинг ответа упал (FunPayAPI баг)")
                else:
                    raise
            
            if chat_id not in self.recently_sent:
                self.recently_sent[chat_id] = []
            
            self.recently_sent[chat_id].append({
                "text": sanitized_text,
                "time": datetime.now()
            })
            
            self.stats["messages_sent"] += 1
            logger.info(f"✅ Сообщение отправлено в чат {chat_id}")
            return True
        except Exception as e:
            logger.error(f"✗ Ошибка отправки сообщения в чат {chat_id}: {e}")
            raise

    def get_stats(self):
        return self.stats.copy()
