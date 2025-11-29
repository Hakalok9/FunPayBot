"""
core/funpay_client.py - ИСПРАВЛЕННЫЙ
"""

import asyncio
import logging
from typing import Optional, Callable, Set
from datetime import datetime, timedelta
from FunPayAPI import Account, Runner, types, enums
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
        self.main_loop = None
        self.my_username = None  # Сохраняем своё имя для фильтрации
        
        # Трекинг отправленных сообщений (чтобы не дублировать)
        self.sent_messages: Set[str] = set()  # "chat_id:text_hash"
        
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "orders_received": 0,
            "connection_errors": 0,
            "reconnects": 0,
            "total_events_received": 0
        }
        self.last_event_time = None
        logger.info("✓ FunPay клиент инициализирован")

    async def connect(self):
        """Подключение к FunPay с retry"""
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"🔄 Подключение к FunPay... (попытка {attempt}/{max_attempts})")
                
                user_agent = getattr(Config, 'USER_AGENT', DEFAULT_USER_AGENT)
                self.account = Account(self.token, user_agent=user_agent)
                
                # Инициализация аккаунта
                await asyncio.get_event_loop().run_in_executor(None, self.account.get)
                
                self.runner = Runner(self.account)
                self.connected = True
                self.main_loop = asyncio.get_event_loop()
                
                # ВАЖНО: Сохраняем своё имя пользователя!
                self.my_username = getattr(self.account, 'username', None)
                
                username = self.my_username or 'Unknown'
                user_id = getattr(self.account, 'id', 'Unknown')
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
        """Регистрация обработчика событий"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
        logger.info(f"✓ Зарегистрирован обработчик для {event_type}")

    async def _trigger_handlers(self, event_type: str, event_data):
        """Вызов зарегистрированных обработчиков"""
        if event_type in self.event_handlers:
            logger.info(f"🔄 Вызываю обработчики для {event_type} (всего: {len(self.event_handlers[event_type])})")
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(event_data)
                except Exception as e:
                    logger.error(f"Ошибка в обработчике {event_type}: {e}", exc_info=True)

    def _is_my_message(self, chat) -> bool:
        """Проверяет, является ли сообщение исходящим (от нас)"""
        try:
            # Проверка по флагу unread - если False после отправки нами, то это наше сообщение
            unread = getattr(chat, 'unread', True)
            
            # Получаем текст сообщения
            text = getattr(chat, 'last_message_text', '') or ''
            chat_id = getattr(chat, 'id', 0)
            
            # Проверяем, отправляли ли мы это сообщение недавно
            msg_key = f"{chat_id}:{hash(text)}"
            if msg_key in self.sent_messages:
                logger.info(f"⏭️ Пропускаем своё сообщение: {text[:30]}...")
                self.sent_messages.discard(msg_key)  # Удаляем из трекинга
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка проверки сообщения: {e}")
            return False

    def _sync_listen_loop(self):
        """СИНХРОННЫЙ цикл прослушивания"""
        logger.info("🔄 Запуск прослушивания событий FunPay (sync loop)...")
        logger.info(f"📊 Обработчики зарегистрированы: {list(self.event_handlers.keys())}")
        logger.info(f"📍 Главный event loop: {self.main_loop}")
        
        try:
            for event in self.runner.listen(requests_delay=self.requests_delay):
                if not self.running:
                    logger.info("⏹️ Остановка прослушивания событий")
                    break
                
                self.last_event_time = datetime.now()
                self.stats["total_events_received"] += 1
                
                try:
                    # Пропускаем INITIAL_CHAT
                    if event.type == enums.EventTypes.INITIAL_CHAT:
                        continue
                    
                    event_type_name = str(event.type).split('.')[-1] if event.type else "UNKNOWN"
                    logger.info(f"🎯 СОБЫТИЕ #{self.stats['total_events_received']}: type={event_type_name}")
                    
                    if event.type == enums.EventTypes.LAST_CHAT_MESSAGE_CHANGED:
                        logger.info(f"📥 Новое/изменённое сообщение в чате!")
                        logger.info(f"   event.chat = {event.chat}")
                        
                        if hasattr(event, 'chat') and event.chat:
                            # ВАЖНО: Проверяем, не наше ли это сообщение!
                            if self._is_my_message(event.chat):
                                continue  # Пропускаем свои сообщения
                            
                            self.stats["messages_received"] += 1
                            asyncio.run_coroutine_threadsafe(
                                self._trigger_handlers("NEW_MESSAGE", event.chat),
                                self.main_loop
                            )
                        
                    elif event.type == enums.EventTypes.CHATS_LIST_CHANGED:
                        logger.info(f"📋 Список чатов изменился")
                        
                    elif event.type == enums.EventTypes.NEW_ORDER:
                        self.stats["orders_received"] += 1
                        logger.info(f"🛒 Новый заказ!")
                        asyncio.run_coroutine_threadsafe(
                            self._trigger_handlers("NEW_ORDER", event.order),
                            self.main_loop
                        )
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки события: {e}", exc_info=True)
                    continue
                    
        except Exception as e:
            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА в listen(): {e}", exc_info=True)
            self.running = False

    async def start_listening(self):
        """Запуск прослушивания событий"""
        if not self.connected:
            raise RuntimeError("FunPay клиент не подключен")
        
        self.running = True
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_listen_loop)

    async def stop(self):
        """Остановка клиента"""
        logger.info("⏹️ Остановка FunPay клиента...")
        self.running = False
        if self.runner:
            try:
                self.runner.stop()
            except:
                pass
        self.connected = False
        logger.info("✓ FunPay клиент остановлен")

    async def send_message(self, chat_id: int, text: str):
        """Отправка сообщения в FunPay"""
        try:
            if not text or not text.strip():
                logger.error(f"❌ Пустое сообщение, отправка отменена")
                return False
            
            clean_text = text.strip()
            
            logger.info(f"📤 Отправляю сообщение в чат {chat_id}: {clean_text[:50]}...")
            
            # ТРЕКИНГ: Запоминаем что отправили это сообщение
            msg_key = f"{chat_id}:{hash(clean_text)}"
            self.sent_messages.add(msg_key)
            
            # Отправляем (синхронный метод)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self.account.send_message, 
                chat_id, 
                clean_text
            )
            
            self.stats["messages_sent"] += 1
            logger.info(f"✅ Сообщение отправлено в чат {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"✗ Ошибка отправки сообщения в чат {chat_id}: {e}")
            raise

    def get_stats(self):
        """Получение статистики"""
        return self.stats.copy()
