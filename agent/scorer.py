import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from config import settings
from agent.models import ParsedJob, JobScoreBreakdown, CareerVector
from agent.llm import LLMService
from agent.prompts import load_profile_context, get_system_prompt

logger = logging.getLogger(__name__)

def load_superjob_knowledge() -> Dict[str, Any]:
    p = Path(__file__).resolve().parent.parent / "data" / "superjob_pro_knowledge.json"
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

SCORER_PROMPT = """Ты — ведущий эксперт по подбору IT-персонала и карьерный ментор.
Твоя задача — провести глубокий скоринг вакансии для кандидата Турейко Дмитрия Валерьевича на основе 100-балльной системы оценки (Раздел 7 базы знаний).

ВЕРИФИЦИРОВАННЫЙ ПРОФИЛЬ КАНДИДАТА:
- ФИО: Турейко Дмитрий Валерьевич
- Локация: Россия, Ленинградская область, г. Сосновый Бор.
- Формат: СТРОГО 100% удалённая работа из Соснового Бора. Никаких офисов, гибридов, поездок или выездов.
- Специальность: СПО МТИ («Информационные системы (по отраслям)», квалификация «Специалист по информационным системам»).
- Опыт: без коммерческого опыта, создавал и публиковал проекты с ИИ, подключал базы данных (SQL/PostgreSQL) и API (webhooks, REST), Telegram-боты, n8n, Python/Django базовый.
- Целевая зарплата: 40 000 – 60 000 ₽.
- Запрещено: телефонная линия, входящие звонки, call-центр, выезды, монтаж сетей.
- Приоритеты:
  * A: AI Automation / автоматизация с ИИ (n8n, API, LLM, боты, SQL)
  * B: Junior Backend / разработка с ИИ (Python, Django, API, базы данных)
  * C: Junior QA / тестирование ПО (тест-кейсы, баг-репорты, Postman, SQL, DevTools)
  * D: Веб-продукты / CMS / low-code

ПАРСИНГ ВАКАНСИИ:
{job_json}

ЖЕСТКИЕ ФИЛЬТРЫ И 100-БАЛЛЬНАЯ ШКАЛА ОЦЕНКИ (РАЗДЕЛ 7):
1. Полная удалёнка и доступность из России подтверждены (0-25 баллов):
   - Если офис, гибрид или выезды -> 0 баллов, группа EXCLUDE, remote_status="Не подходит".
   - Если неясно -> 10-15 баллов, группа B, remote_status="Неясно".
   - Если 100% удаленка из РФ подтверждена -> 25 баллов, remote_status="Подтверждена".
2. Нет постоянных звонков, call-центра и выездов (0-20 баллов):
   - Если есть звонки, горячая линия или телефонный саппорт -> 0 баллов, группа EXCLUDE, phone_support_status="Есть".
   - Если неясно -> 10 баллов, phone_support_status="Неясно".
   - Если чисто техническая работа без звонков -> 20 баллов, phone_support_status="Нет".
3. Соответствие уровню Junior / стажёр / без опыта (0-15 баллов):
   - Без опыта / стажёр / до 1 года -> 15 баллов.
   - Опыт желателен (1-2 года) -> 10 баллов.
   - Требуется строгий опыт 3+ года -> 0-5 баллов.
4. Зарплата соответствует цели 40–60 тыс. ₽ (0-15 баллов):
   - Попадает в 40-60k фиксированно -> 15 баллов.
   - Зарплата не указана -> 8-10 баллов (резерв).
   - Заметно ниже 35k или только процент со сделок -> 0-5 баллов.
5. Соответствие опыту с ИИ, API, БД и опубликованными проектами (0-15 баллов):
   - Прямой стек: n8n, AI, Python, SQL, REST API, QA веб-приложений, боты -> 12-15 баллов.
   - Смежный стек -> 7-11 баллов.
6. Актуальность, прозрачность описания и возможность отклика (0-10 баллов):
   - Четкие обязанности, известный работодатель, прямая ссылка -> 10 баллов.

ГРУППЫ СООТВЕТСТВИЯ:
- "A" (откликаться в первую очередь): условия подтверждены, навыки близки, нет критических препятствий (score >= 75).
- "B" (откликаться после проверки): один важный параметр неясен или есть пробелы для быстрого закрытия.
- "C" (резерв): зарплата не указана или требования выше, но вакансия полезна.
- "EXCLUDE" (исключить): офис/гибрид, телефонная линия, выезды, неподходящая география.

Верни строго JSON:
{{
  "total_score": 85,
  "priority_tier": "HIGH",
  "relevance_group": "A",
  "remote_status": "Подтверждена",
  "phone_support_status": "Нет",
  "geography_check": "Подтверждена (РФ / Ленобласть)",
  "salary_assessment": "Соответствует вилке (40-60k)",
  "why_fits": "Краткая аргументация по профилю кандидата (СПО МТИ, опыт с API/БД)...",
  "what_to_improve": "Существенные пробелы, которые нужно подтянуть...",
  "next_action": "Откликнуться",
  "remote_score": 25,
  "no_phone_score": 20,
  "junior_grade_score": 15,
  "salary_score": 15,
  "tech_and_projects_score": 15,
  "transparency_score": 10,
  "hard_skills_score": 35,
  "experience_grade_score": 20,
  "education_domain_score": 15,
  "conditions_score": 10,
  "red_flags_penalty": 0,
  "recommended_vector": "ai_automation | backend_python | qa_testing | is_developer | frontend_fullstack",
  "is_fully_remote": true,
  "is_junior_friendly": true,
  "has_phone_support_risk": false,
  "strict_criteria_notes": [
    "✅ 100% удаленка подтверждена",
    "✅ Нет требований к телефонной поддержке",
    "✅ Начальный уровень подходит"
  ],
  "pros": ["Удаленный формат", "Стек совпадает с базой знаний"],
  "cons_and_risks": [],
  "missing_gaps": [],
  "application_strategy": "Сделать точечный отклик с упором на СПО МТИ и проект AI-помощника."
}}
"""

class JobScorer:
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.profile = load_profile_context(settings.PROFILE_CONTEXT_PATH)
        self.sj_knowledge = load_superjob_knowledge()
        self.llm = llm_service or LLMService(system_instruction=get_system_prompt(self.profile))

    async def score(self, job: ParsedJob) -> JobScoreBreakdown:
        job_json = json.dumps(job.model_dump(), ensure_ascii=False, indent=2)
        prompt = SCORER_PROMPT.format(job_json=job_json)

        score_res: JobScoreBreakdown = await self.llm.generate_structured(prompt, JobScoreBreakdown)
        return score_res
