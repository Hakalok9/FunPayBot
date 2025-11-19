import logging
from datetime import datetime
from utils.helpers import parse_order_id

logger = logging.getLogger("FunPayBot.OrderHandler")

class OrderHandler:
    def __init__(self, database, telegram_bot):
        self.db = database
        self.telegram_bot = telegram_bot
        self.processed_orders = set()
        logger.info("✓ Обработчик заказов инициализирован")

    async def handle(self, order):
        try:
            order_id_str = parse_order_id(order.description)
            if not order_id_str:
                order_id_str = f"order_{int(datetime.now().timestamp())}"

            if order_id_str in self.processed_orders:
                logger.debug(f"Дубликат заказа (order_id={order_id_str}), игнорируем")
                return False

            self.processed_orders.add(order_id_str)
            logger.info(f"🛒 Новый заказ от {order.buyer_username}: {order.description[:50]}...")

            await self.db.add_or_update_user(funpay_user_id=0, username=order.buyer_username)
            await self.db.add_order(
                order_id=order_id_str,
                buyer_id=0,
                buyer_username=order.buyer_username,
                description=order.description,
                price=None
            )

            if self.telegram_bot:
                await self.telegram_bot.send_order_notification(
                    order_id=order_id_str,
                    buyer_username=order.buyer_username,
                    description=order.description,
                    price=None
                )

            return True
        except Exception as e:
            logger.error(f"Ошибка обработки заказа: {e}", exc_info=True)
            return False
