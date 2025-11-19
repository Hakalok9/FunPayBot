import re
import html
import hashlib
from datetime import datetime

def escape_html(text):
    """Экранирование HTML для Telegram"""
    return html.escape(str(text))

def truncate_text(text, max_length=4000, suffix="..."):
    """Обрезка текста с проверкой emoji"""
    if not text:
        return ""
    try:
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    except Exception as e:
        # Если проблема с кодировкой
        return text.encode('utf-8', errors='ignore').decode('utf-8')[:max_length]

def sanitize_for_funpay(text):
    """Очистка текста для FunPay API"""
    if not text:
        return ""
    try:
        # Удаление HTML тегов
        text = re.sub(r'<[^>]+>', '', text)
        # Удаление множественных пробелов
        text = re.sub(r'\s+', ' ', text)
        # Удаление control characters кроме \n и \t
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        return text.strip()
    except Exception as e:
        # Если проблема с кодировкой
        return text.encode('utf-8', errors='ignore').decode('utf-8').strip()

def generate_message_hash(chat_id, text, timestamp=None):
    """Генерация хэша для дедупликации"""
    if timestamp is None:
        timestamp = datetime.now()
    # Округляем до минуты для группировки дублей
    hash_string = f"{chat_id}:{text}:{timestamp.strftime('%Y%m%d%H%M')}"
    return hashlib.sha256(hash_string.encode('utf-8')).hexdigest()

def parse_order_id(order_text):
    """Парсинг ID заказа из текста"""
    match = re.search(r'#(\d+)', order_text)
    return match.group(1) if match else None

def time_ago(dt):
    """Форматирование времени"""
    if not dt:
        return "неизвестно"
    now = datetime.now()
    diff = now - dt
    seconds = diff.total_seconds()

    if seconds < 60:
        return "только что"
    elif seconds < 3600:
        return f"{int(seconds / 60)} мин. назад"
    elif seconds < 86400:
        return f"{int(seconds / 3600)} ч. назад"
    else:
        return f"{int(seconds / 86400)} дн. назад"
