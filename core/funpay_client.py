import asyncio
import logging
from typing import Optional, Callable
from datetime import datetime, timedelta
from FunPayAPI import Account, Runner, types, enums
from utils.retry import async_retry
from utils.helpers import sanitize_for_funpay
from config import Config

logger = logging.getLogger("FunPayBot.FunPayClient")

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
                
                # Увеличенный таймаут через asyncio.wait_for
                self.account = await asyncio.wait_for(
                    asyncio.to_thread(lambda: Account(self.token).get()),
                    timeout=30.0  # 30 секунд на попытку
                )
                
                logger.info(f"✓ Авторизован как: {self.account.username} (ID: {self.account.id})")
                self.runner = Runner(self.account)
                self.connected = True
                return True
                
            except asyncio.TimeoutError:
                logger.error(f"✗ Таймаут подключения к FunPay (попытка {attempt}/{max_attempts})")
                if attempt < max_attempts:
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"✗ Ошибка подключения к FunPay: {e}")
                self.stats["connection_errors"] += 1
                if attempt < max_attempts:
                    await asyncio.sleep(2)
        
        # Все попытки провалились
        return False
            
    async def start_listening(self):
        """Прослушивание с exponential backoff и watchdog"""
        if not self.connected:
            raise RuntimeError("Сначала нужно подключиться через connect()")
        
        self.running = True
        backoff = 1
        max_backoff = Config.RECONNECT_MAX_BACKOFF
        watchdog_timeout = Config.WATCHDOG_TIMEOUT
        self.last_event_time = datetime.now()
        
        # Запуск watchdog
        asyncio.create_task(self._watchdog(watchdog_timeout))
        
        while self.running:
            try:
                logger.info("🔄 Запуск прослушивания событий FunPay...")
                
                # Обработка событий в отдельном потоке
                for event in self.runner.listen(requests_delay=self.requests_delay):
                    if not self.running:
                        break
                    self.last_event_time = datetime.now()
                    await self._handle_event(event)
                
                # Успешная работа - сброс backoff
                backoff = 1
                
            except KeyboardInterrupt:
                logger.info("⚠️ Получен сигнал остановки")
                break
            except Exception as e:
                self.stats["connection_errors"] += 1
                logger.error(f"✗ Ошибка прослушивания FunPay: {e}")
                
                # Уведомление админа при долгом backoff
                if backoff >= 60 and self.notify_admin_callback:
                    await self.notify_admin_callback(
                        f"FunPay connection unstable\nBackoff: {backoff}s\nError: {str(e)[:100]}"
                    )
                
                logger.warning(f"Переподключение через {backoff}s...")
                await asyncio.sleep(backoff)
                
                # Exponential backoff с капом
                backoff = min(backoff * 2, max_backoff)
                
                try:
                    await self.reconnect()
                    backoff = 1  # Успешно переподключились
                except Exception as reconnect_error:
                    logger.error(f"✗ Ошибка переподключения: {reconnect_error}")
                    
    async def _watchdog(self, timeout_seconds):
        """Watchdog: уведомление если нет событий > N минут"""
        while self.running:
            await asyncio.sleep(60)  # Проверка каждую минуту
            if not self.last_event_time:
                continue
            elapsed = (datetime.now() - self.last_event_time).total_seconds()
            if elapsed > timeout_seconds:
                logger.warning(f"⚠️ WATCHDOG: Нет событий уже {elapsed:.0f}s")
                if self.notify_admin_callback:
                    await self.notify_admin_callback(
                        f"⚠️ WATCHDOG ALERT\n\nНет событий от FunPay уже {elapsed/60:.1f} минут\n\nВозможно проблема с подключением"
                    )
                self.last_event_time = datetime.now()  # Сброс чтобы не спамить
                    
    async def reconnect(self):
        logger.info("🔄 Попытка переподключения...")
        self.stats["reconnects"] += 1
        self.connected = False
        success = await self.connect()
        if success:
            logger.info("✓ Переподключение успешно")
        else:
            raise RuntimeError("Не удалось переподключиться")
            
    async def stop(self):
        logger.info("⏹️ Остановка FunPay клиента...")
        self.running = False
        self.connected = False
        
    async def _handle_event(self, event):
        try:
            if event.type is enums.EventTypes.NEW_MESSAGE:
                self.stats["messages_received"] += 1
                handler = self.event_handlers.get("on_message")
                if handler:
                    await handler(event.message)
            elif event.type is enums.EventTypes.NEW_ORDER:
                self.stats["orders_received"] += 1
                handler = self.event_handlers.get("on_order")
                if handler:
                    await handler(event.order)
            # ORDER_UPDATE не существует в FunPayAPI - убрано
        except Exception as e:
            logger.error(f"✗ Ошибка обработки события: {e}", exc_info=True)
            
    def on(self, event_name, handler):
        self.event_handlers[event_name] = handler
        logger.debug(f"✓ Обработчик зарегистрирован: {event_name}")
        
    @async_retry(max_attempts=3, delay=2.0, backoff=2.0)
    async def send_message(self, chat_id, text):
        try:
            clean_text = sanitize_for_funpay(text)
            await asyncio.to_thread(self.account.send_message, chat_id, clean_text)
            self.stats["messages_sent"] += 1
            logger.debug(f"✓ Сообщение отправлено в чат {chat_id}")
            return True
        except Exception as e:
            logger.error(f"✗ Ошибка отправки сообщения: {e}")
            raise
            
    def get_stats(self):
        return {**self.stats, "connected": self.connected, "running": self.running}
