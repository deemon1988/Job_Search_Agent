import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from config import BASE_DIR
from agent.llm import LLMService

logger = logging.getLogger(__name__)

PORTFOLIO_BLUEPRINT_PROMPT = """Ты — ведущий технический лид и карьерный ментор.
Для кандидата Дмитрия (СПО МТИ, ищет первую удаленную IT-работу 40–60 тыс. ₽ без телефонных звонков) составь подробный пошаговый план реализации практического проекта для портфолио.

ПРОЕКТ:
{project_info}

СФОРМИРУЙ ПОЛНЫЙ ТЕХНИЧЕСКИЙ ГАЙД В ФОРМАТЕ MARKDOWN:
1. 🏗 Архитектура проекта и потоки данных (как данные идут от пользователя через webhook/API в БД и LLM).
2. 🗓 Пошаговый план разработки на 5–7 дней (по 90 минут в день):
   - День 1: Инициализация, репозиторий GitHub, структура папок, настройка .env.
   - День 2: База данных (схема таблиц, миграции, подключение).
   - День 3: Интеграция API / Webhook (прием данных, валидация).
   - День 4: Подключение LLM API (промпт, структурированный ответ, обработка задержек).
   - День 5: Обработка ошибок и негативных сценариев (что делать, если API недоступен, пустые данные, дубликаты).
   - День 6: Тестирование (Postman коллекция, проверка статусов, ручные тесты).
   - День 7: Оформление README.md на GitHub и запись видео-демонстрации (демо).
3. 🧪 Чек-лист проверки качества и негативных сценариев (что показать на интервью).
4. 📄 Шаблон идеального README.md для репозитория на GitHub (с описанием, схемой, инструкцией запуска).

Отвечай структурированно, понятно для Junior-разработчика, использующего AI как инструмент ускорения.
"""

class PortfolioManager:
    """Менеджер и генератор проектов для портфолио"""

    def __init__(self, llm_service: Optional[LLMService] = None, data_path: Optional[str] = None):
        if isinstance(llm_service, (str, Path)):
            data_path, llm_service = str(llm_service), None
        p = Path(data_path) if data_path else BASE_DIR / "data" / "action_plan_knowledge.json"
        if not p.exists():
            alt_p = Path(__file__).resolve().parent.parent / "data" / "action_plan_knowledge.json"
            if alt_p.exists():
                p = alt_p
        with open(p, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.llm = llm_service or LLMService()

    def get_catalog(self) -> List[Dict[str, Any]]:
        """Возвращает каталог всех рекомендованных проектов"""
        return self.data.get("portfolio_projects_catalog", [])

    def list_projects(self) -> List[Dict[str, Any]]:
        """Возвращает список проектов (alias)"""
        return self.get_catalog()

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает проект по id с адаптацией полей"""
        for p in self.get_catalog():
            if p.get("id") == project_id:
                # Нормализация для обработчиков
                return {
                    **p,
                    "name": p.get("title", p.get("name")),
                    "role": p.get("priority", p.get("role", "Проект")),
                    "short_description": p.get("summary", p.get("short_description", "")),
                    "key_features": p.get("core_features", p.get("key_features", [])),
                    "interview_hook": (
                        "Демонстрируйте умение читать логи, проверять сбои внешних API "
                        "и наличие продуманной схемы БД с тестами в Postman."
                    )
                }
        return None

    def format_catalog_text(self) -> str:
        """Форматирует общий список проектов"""
        projects = self.get_catalog()
        lines = [
            "🚀 *Каталог проектов для портфолио (по рекомендациям)*\n",
            "_Проекты подобраны так, чтобы наглядно доказать работодателю умение запускать код, подключать API, базы данных и проверять ошибки:_\n"
        ]

        for idx, p in enumerate(projects, 1):
            stack_str = ", ".join(p.get("stack", [])[:4])
            lines.append(f"{idx}️⃣ *{p.get('title')}*")
            lines.append(f"   🏷 _{p.get('priority')}_ | ⏱ {p.get('estimated_days')}")
            lines.append(f"   🛠 Стек: `{stack_str}`")
            lines.append(f"   📝 {p.get('summary')}\n")

        lines.append("👇 Нажмите на кнопку нужного проекта ниже, чтобы открыть подробное ТЗ и пошаговый план разработки:")
        return "\n".join(lines)

    def format_project_card(self, project_id: str) -> str:
        """Форматирует детальную карточку проекта"""
        p = self.get_project(project_id)
        if not p:
            return "Проект не найден."

        features = "\n".join([f"  • {f}" for f in p.get("core_features", [])])
        proofs = "\n".join([f"  ✅ {pf}" for pf in p.get("what_to_show_employer", [])])
        stack_str = ", ".join(p.get("stack", []))

        return (
            f"🛠 *{p.get('title')}*\n"
            f"🏷 *Статус:* _{p.get('priority')}_ | ⏱ Срок: {p.get('estimated_days')}\n\n"
            f"📌 *Назначение:*\n{p.get('summary')}\n\n"
            f"🛠 *Стек технологий:*\n`{stack_str}`\n\n"
            f"⚙️ *Ключевой функционал:*\n{features}\n\n"
            f"🎯 *Что показать работодателю в портфолио:*\n{proofs}\n\n"
            f"💡 _Нажмите «Генерировать ТЗ и план запуска», чтобы получить архитектуру, пошаговый план по дням и шаблон README!_"
        )

    async def generate_blueprint(self, project_id: str) -> str:
        """Генерирует через LLM архитектуру и пошаговый план разработки"""
        p = self.get_project(project_id)
        if not p:
            return "Проект не найден."

        project_info = json.dumps(p, ensure_ascii=False, indent=2)
        prompt = PORTFOLIO_BLUEPRINT_PROMPT.format(project_info=project_info)
        blueprint_text = await self.llm.generate_text(prompt)
        return blueprint_text
