import asyncio
import functools
import logging

logger = logging.getLogger("FunPayBot.Retry")

def async_retry(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(Exception,)):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(f"❌ {func.__name__} провалился после {max_attempts} попыток: {e}")
                        raise
                    logger.warning(f"⚠️ {func.__name__} попытка {attempt}/{max_attempts} провалилась: {e}. Повтор через {current_delay:.1f}s")
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

            if last_exception:
                raise last_exception
        return wrapper
    return decorator
