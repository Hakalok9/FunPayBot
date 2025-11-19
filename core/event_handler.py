import logging

logger = logging.getLogger("FunPayBot.EventHandler")

class EventHandler:
    def __init__(self, message_handler, order_handler):
        self.message_handler = message_handler
        self.order_handler = order_handler
        self.stats = {"messages_handled": 0, "orders_handled": 0, "errors": 0}
        logger.info("✓ Обработчик событий инициализирован")

    async def handle_message(self, message):
        try:
            success = await self.message_handler.handle(message)
            if success:
                self.stats["messages_handled"] += 1
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Критическая ошибка обработки сообщения: {e}", exc_info=True)

    async def handle_order(self, order):
        try:
            success = await self.order_handler.handle(order)
            if success:
                self.stats["orders_handled"] += 1
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Критическая ошибка обработки заказа: {e}", exc_info=True)

    def get_stats(self):
        return self.stats.copy()
