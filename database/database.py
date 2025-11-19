import aiosqlite
import logging
from datetime import datetime
from typing import Optional, List
from .models import CREATE_TABLES_SQL, User, Message, Order, Template
from config import Config

logger = logging.getLogger("FunPayBot.Database")

class Database:
    def __init__(self, db_path="database.db"):
        self.db_path = db_path
        self.connection = None
        self.timeout = Config.DB_TIMEOUT  # Критично для sqlite под нагрузкой

    async def connect(self):
        try:
            self.connection = await aiosqlite.connect(
                self.db_path,
                timeout=self.timeout  # Увеличенный таймаут против "database is locked"
            )
            await self.connection.execute("PRAGMA foreign_keys = ON")
            await self.connection.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging для конкурентности
            logger.info(f"✓ Подключение к БД: {self.db_path} (timeout={self.timeout}s)")
        except Exception as e:
            logger.error(f"✗ Ошибка подключения к БД: {e}")
            raise

    async def disconnect(self):
        if self.connection:
            await self.connection.close()
            logger.info("✓ БД закрыта")

    async def initialize(self):
        try:
            await self.connection.executescript(CREATE_TABLES_SQL)
            await self.connection.commit()
            logger.info("✓ Схема БД инициализирована")
        except Exception as e:
            logger.error(f"✗ Ошибка инициализации схемы БД: {e}")
            raise

    async def message_exists_by_hash(self, message_hash: str) -> bool:
        """Проверка дубликата по хэшу (КРИТИЧНО)"""
        try:
            cursor = await self.connection.execute(
                "SELECT 1 FROM messages WHERE message_hash = ? LIMIT 1",
                (message_hash,)
            )
            row = await cursor.fetchone()
            return row is not None
        except Exception as e:
            logger.error(f"Ошибка проверки message_hash: {e}")
            return False

    async def add_or_update_user(self, funpay_user_id, username):
        try:
            cursor = await self.connection.execute(
                """INSERT INTO users (funpay_user_id, username, last_seen)
                VALUES (?, ?, ?)
                ON CONFLICT(funpay_user_id) DO UPDATE SET
                    username = excluded.username,
                    last_seen = excluded.last_seen
                RETURNING id""",
                (funpay_user_id, username, datetime.now())
            )
            row = await cursor.fetchone()
            await self.connection.commit()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"Ошибка add_or_update_user: {e}")
            raise

    async def add_message(self, chat_id, author_id, author_username, text, is_outgoing=False, message_hash=None):
        """Добавление сообщения с проверкой дубликата"""
        try:
            # Дедупликация (КРИТИЧНО)
            if message_hash and await self.message_exists_by_hash(message_hash):
                logger.debug(f"Дубликат сообщения игнорируется (hash: {message_hash[:8]}...)")
                return None

            cursor = await self.connection.execute(
                """INSERT INTO messages (chat_id, author_id, author_username, text, is_outgoing, message_hash)
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING id""",
                (chat_id, author_id, author_username, text, is_outgoing, message_hash)
            )
            row = await cursor.fetchone()
            await self.connection.commit()

            await self.connection.execute(
                "UPDATE users SET total_messages = total_messages + 1 WHERE funpay_user_id = ?",
                (author_id,)
            )
            await self.connection.commit()

            return row[0] if row else None
        except aiosqlite.IntegrityError as e:
            logger.debug(f"Дубликат сообщения (IntegrityError): {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка add_message: {e}")
            raise

    async def get_chat_messages(self, chat_id, limit=50):
        cursor = await self.connection.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY timestamp DESC LIMIT ?",
            (chat_id, limit)
        )
        rows = await cursor.fetchall()
        messages = []
        for row in rows:
            messages.append(Message(
                id=row[0], chat_id=row[1], message_id=row[2],
                author_id=row[3], author_username=row[4], text=row[5],
                is_outgoing=bool(row[6]),
                timestamp=datetime.fromisoformat(row[7]) if row[7] else None,
                delivered=bool(row[8]), message_hash=row[9]
            ))
        return messages

    async def add_order(self, order_id, buyer_id, buyer_username, description="", price=None):
        try:
            cursor = await self.connection.execute(
                """INSERT INTO orders (order_id, buyer_id, buyer_username, description, price)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(order_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                RETURNING id""",
                (order_id, buyer_id, buyer_username, description, price)
            )
            row = await cursor.fetchone()
            await self.connection.commit()

            await self.connection.execute(
                "UPDATE users SET total_orders = total_orders + 1 WHERE funpay_user_id = ?",
                (buyer_id,)
            )
            await self.connection.commit()

            return row[0] if row else None
        except Exception as e:
            logger.error(f"Ошибка add_order: {e}")
            raise

    async def update_order_status(self, order_id, status):
        completed_at = datetime.now() if status == "completed" else None
        await self.connection.execute(
            "UPDATE orders SET status = ?, updated_at = ?, completed_at = ? WHERE order_id = ?",
            (status, datetime.now(), completed_at, order_id)
        )
        await self.connection.commit()

    async def get_active_orders(self):
        cursor = await self.connection.execute(
            "SELECT * FROM orders WHERE status IN ('new', 'active') ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        orders = []
        for row in rows:
            orders.append(Order(
                id=row[0], order_id=row[1], buyer_id=row[2],
                buyer_username=row[3], description=row[4], price=row[5],
                status=row[6],
                created_at=datetime.fromisoformat(row[7]) if row[7] else None,
                updated_at=datetime.fromisoformat(row[8]) if row[8] else None,
                completed_at=datetime.fromisoformat(row[9]) if row[9] else None,
                notes=row[10]
            ))
        return orders

    async def add_template(self, name, trigger, response):
        cursor = await self.connection.execute(
            "INSERT INTO templates (name, trigger, response) VALUES (?, ?, ?) RETURNING id",
            (name, trigger, response)
        )
        row = await cursor.fetchone()
        await self.connection.commit()
        return row[0] if row else None

    async def get_active_templates(self):
        cursor = await self.connection.execute(
            "SELECT * FROM templates WHERE is_active = 1"
        )
        rows = await cursor.fetchall()
        templates = []
        for row in rows:
            templates.append(Template(
                id=row[0], name=row[1], trigger=row[2], response=row[3],
                is_active=bool(row[4]), use_count=row[5],
                created_at=datetime.fromisoformat(row[6]) if row[6] else None,
                updated_at=datetime.fromisoformat(row[7]) if row[7] else None
            ))
        return templates

    async def increment_template_usage(self, template_id):
        await self.connection.execute(
            "UPDATE templates SET use_count = use_count + 1 WHERE id = ?",
            (template_id,)
        )
        await self.connection.commit()
