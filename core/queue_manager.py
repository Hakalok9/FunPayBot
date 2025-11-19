import asyncio
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger("FunPayBot.QueueManager")

class MessagePriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass(order=True)
class QueuedMessage:
    priority: int = field(compare=True)
    chat_id: int = field(compare=False)
    text: str = field(compare=False)
    callback: Optional[callable] = field(default=None, compare=False)
    metadata: Dict[str, Any] = field(default_factory=dict, compare=False)
    timestamp: datetime = field(default_factory=datetime.now, compare=False)

class MessageQueueManager:
    def __init__(self, max_size=100, send_delay=2.5, max_retries=3):
        self.max_size = max_size
        self.send_delay = send_delay
        self.max_retries = max_retries
        self.queue = asyncio.PriorityQueue(maxsize=max_size)
        self.stats = {"total_queued": 0, "total_sent": 0, "total_failed": 0, "queue_full_count": 0}
        self.running = False
        self.worker_task = None
        self.last_send_time = None
        logger.info(f"✓ Менеджер очереди инициализирован (max_size={max_size}, delay={send_delay}s)")

    async def add_message(self, chat_id, text, priority=MessagePriority.NORMAL, callback=None, metadata=None):
        try:
            message = QueuedMessage(
                priority=-priority.value,
                chat_id=chat_id,
                text=text,
                callback=callback,
                metadata=metadata or {}
            )
            self.queue.put_nowait(message)
            self.stats["total_queued"] += 1
            logger.debug(f"✓ Сообщение в очередь (chat_id={chat_id}, priority={priority.name}, queue_size={self.queue.qsize()})")
            return True
        except asyncio.QueueFull:
            self.stats["queue_full_count"] += 1
            logger.warning(f"⚠️ Очередь переполнена! (размер={self.queue.qsize()}/{self.max_size})")
            return False
        except Exception as e:
            logger.error(f"✗ Ошибка добавления в очередь: {e}")
            return False

    async def start(self, send_callback):
        if self.running:
            logger.warning("⚠️ Менеджер очереди уже запущен")
            return
        self.running = True
        self.worker_task = asyncio.create_task(self._worker(send_callback))
        logger.info("✓ Менеджер очереди запущен")

    async def stop(self):
        if not self.running:
            return
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        logger.info("✓ Менеджер очереди остановлен")

    async def _worker(self, send_callback):
        logger.info("🔄 Обработчик очереди запущен")
        while self.running:
            try:
                try:
                    message = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                await self._enforce_rate_limit()
                success = await self._send_with_retry(message, send_callback)
                if success:
                    self.stats["total_sent"] += 1
                else:
                    self.stats["total_failed"] += 1
                if message.callback:
                    try:
                        if asyncio.iscoroutinefunction(message.callback):
                            await message.callback(success, message.metadata)
                        else:
                            message.callback(success, message.metadata)
                    except Exception as e:
                        logger.error(f"Ошибка в callback: {e}")
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в обработчике очереди: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _enforce_rate_limit(self):
        if self.last_send_time is None:
            self.last_send_time = datetime.now()
            return
        elapsed = (datetime.now() - self.last_send_time).total_seconds()
        if elapsed < self.send_delay:
            wait_time = self.send_delay - elapsed
            await asyncio.sleep(wait_time)
        self.last_send_time = datetime.now()

    async def _send_with_retry(self, message, send_callback):
        for attempt in range(1, self.max_retries + 1):
            try:
                success = await send_callback(message.chat_id, message.text)
                if success:
                    return True
                if attempt < self.max_retries:
                    await asyncio.sleep(attempt * 2)
            except Exception as e:
                logger.error(f"Ошибка отправки (попытка {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(attempt * 2)
        return False

    def get_stats(self):
        return {**self.stats, "queue_size": self.queue.qsize(), "is_running": self.running}
