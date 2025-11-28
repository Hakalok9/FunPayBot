"""
core/funpay_client.py
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

# Дефолтный USER_AGENT, если не задан в Config
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
        logger.info("✓ FunPay клиент инициализирован")

    async def connect(self):
        """Подключение к FunPay с retry"""
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"🔄 Подключение к FunPay... (попытка {attempt}/{max_attempts})")
                
                # Получаем USER_AGENT из Config или используем дефолтный
                user_agent = getattr(Config, 'USER_AGENT', DEFAULT_USER_AGENT)
                
                # Создаём аккаунт
                self.account = Account(self.token, user_agent=user_agent)
                
                # КРИТИЧНО: Вызываем get() для инициализации аккаунта
                await asyncio.get_event_loop().run_in_executor(None, self.account.get)
                
                # Теперь создаём Runner БЕЗ автоматического получения истории
                self.runner = Runner(self.account)
                self.connected = True
                
                username = getattr(self.account, 'username', 'Unknown')
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
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(event_data)
                except Exception as e:
                    logger.error(f"Ошибка в обработчике {event_type}: {e}", exc_info=True)

    def _sync_listen_loop(self):
        """СИНХРОННЫЙ цикл прослушивания (запускается в отдельном потоке)"""
        logger.info("🔄 Запуск прослушивания событий FunPay (sync loop)...")
        try:
            for event in self.runner.listen(requests_delay=self.requests_delay):
                if not self.running:
                    logger.info("⏹️ Остановка прослушивания событий")
                    break
                
                self.last_event_time = datetime.now()
                
                try:
                    # Обрабатываем события через asyncio
                    if event.type == enums.EventTypes.NEW_MESSAGE:
                        self.stats["messages_received"] += 1
                        logger.info(f"📥 Новое сообщение получено")
                        # Создаём задачу в главном event loop
                        asyncio.run_coroutine_threadsafe(
                            self._trigger_handlers("NEW_MESSAGE", event.message),
                            asyncio.get_event_loop()
                        )
                    elif event.type == enums.EventTypes.NEW_ORDER:
                        self.stats["orders_received"] += 1
                        logger.info(f"🛒 Новый заказ получен")
                        asyncio.run_coroutine_threadsafe(
                            self._trigger_handlers("NEW_ORDER", event.order),
                            asyncio.get_event_loop()
                        )
                except Exception as e:
                    logger.error(f"⚠️ Ошибка обработки события: {e}", exc_info=True)
                    # Продолжаем цикл, не прерываем
                    continue
                    
        except Exception as e:
            logger.error(f"Ошибка в sync listen loop: {e}", exc_info=True)
            self.running = False

    async def start_listening(self):
        """Запуск прослушивания событий в отдельном потоке"""
        if not self.connected:
            raise RuntimeError("FunPay клиент не подключен")
        
        self.running = True
        
        # Запускаем синхронный цикл в executor (отдельный поток)
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

    @async_retry(max_attempts=3, delay=2)
    async def send_message(self, chat_id: int, text: str):
        """Отправка сообщения с retry"""
        try:
            sanitized_text = sanitize_for_funpay(text)
            # FunPayAPI send_message синхронный, оборачиваем
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, 
                self.account.send_message, 
                chat_id, 
                sanitized_text
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
