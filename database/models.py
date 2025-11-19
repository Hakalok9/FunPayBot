from dataclasses import dataclass
from datetime import datetime
from typing import Optional

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    funpay_user_id INTEGER UNIQUE NOT NULL,
    username TEXT NOT NULL,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_messages INTEGER DEFAULT 0,
    total_orders INTEGER DEFAULT 0,
    is_blocked BOOLEAN DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    message_id TEXT,
    author_id INTEGER NOT NULL,
    author_username TEXT,
    text TEXT NOT NULL,
    is_outgoing BOOLEAN DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivered BOOLEAN DEFAULT 1,
    message_hash TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE NOT NULL,
    buyer_id INTEGER NOT NULL,
    buyer_username TEXT NOT NULL,
    description TEXT,
    price REAL,
    status TEXT DEFAULT 'new',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    trigger TEXT NOT NULL,
    response TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    use_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS message_hashes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_hash TEXT UNIQUE NOT NULL,
    chat_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_hash ON messages(message_hash);
CREATE INDEX IF NOT EXISTS idx_orders_buyer_id ON orders(buyer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
"""

@dataclass
class User:
    id: Optional[int] = None
    funpay_user_id: int = 0
    username: str = ""
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    total_messages: int = 0
    total_orders: int = 0
    is_blocked: bool = False
    notes: Optional[str] = None

@dataclass
class Message:
    id: Optional[int] = None
    chat_id: int = 0
    message_id: Optional[str] = None
    author_id: int = 0
    author_username: str = ""
    text: str = ""
    is_outgoing: bool = False
    timestamp: Optional[datetime] = None
    delivered: bool = True
    message_hash: Optional[str] = None

@dataclass
class Order:
    id: Optional[int] = None
    order_id: str = ""
    buyer_id: int = 0
    buyer_username: str = ""
    description: str = ""
    price: Optional[float] = None
    status: str = "new"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None

@dataclass
class Template:
    id: Optional[int] = None
    name: str = ""
    trigger: str = ""
    response: str = ""
    is_active: bool = True
    use_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
