import logging
from datetime import datetime

logger = logging.getLogger("FunPayBot.Autoresponder")

class AutoResponder:
    def __init__(self, template_manager, enabled=True):
        self.template_manager = template_manager
        self.enabled = enabled
        self.stats = {"responses_sent": 0, "templates_matched": 0}
        logger.info(f"✓ Автоответчик инициализирован ({'включен' if enabled else 'выключен'})")

    async def get_response(self, message_text):
        if not self.enabled:
            return None
        try:
            template = await self.template_manager.find_matching_template(message_text)
            if template:
                self.stats["templates_matched"] += 1
                response = self._process_variables(template.response)
                await self.template_manager.db.increment_template_usage(template.id)
                logger.info(f"🤖 Автоответ по шаблону '{template.name}': {response[:50]}...")
                self.stats["responses_sent"] += 1
                return response
            return None
        except Exception as e:
            logger.error(f"Ошибка генерации автоответа: {e}")
            return None

    def _process_variables(self, text):
        now = datetime.now()
        replacements = {
            "{time}": now.strftime("%H:%M"),
            "{date}": now.strftime("%d.%m.%Y"),
            "{datetime}": now.strftime("%d.%m.%Y %H:%M")
        }
        for var, value in replacements.items():
            text = text.replace(var, value)
        return text

    def enable(self):
        self.enabled = True
        logger.info("✓ Автоответчик включен")

    def disable(self):
        self.enabled = False
        logger.info("✓ Автоответчик выключен")

    def get_stats(self):
        return {**self.stats, "enabled": self.enabled}
