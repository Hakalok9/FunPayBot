import logging
import re
from datetime import datetime

logger = logging.getLogger("FunPayBot.Templates")

class TemplateManager:
    def __init__(self, database):
        self.db = database
        self.templates_cache = []
        self.cache_updated = None
        logger.info("✓ Менеджер шаблонов инициализирован")

    async def reload_templates(self):
        try:
            self.templates_cache = await self.db.get_active_templates()
            self.cache_updated = datetime.now()
            logger.info(f"✓ Загружено {len(self.templates_cache)} шаблонов")
        except Exception as e:
            logger.error(f"Ошибка загрузки шаблонов: {e}")

    async def find_matching_template(self, text):
        if not self.templates_cache:
            await self.reload_templates()
        text_lower = text.lower()
        for template in self.templates_cache:
            if template.trigger.lower() in text_lower:
                return template
            if template.trigger.startswith("^"):
                try:
                    if re.search(template.trigger, text, re.IGNORECASE):
                        return template
                except re.error:
                    logger.warning(f"Некорректный regex в шаблоне {template.id}")
        return None

    async def add_template(self, name, trigger, response):
        try:
            template_id = await self.db.add_template(name, trigger, response)
            await self.reload_templates()
            return template_id
        except Exception as e:
            logger.error(f"Ошибка добавления шаблона: {e}")
            return None
