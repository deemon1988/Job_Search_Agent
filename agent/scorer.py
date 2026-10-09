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

SCORER_PROMPT = """Ты — ведущий эксперт по подбору IT-персонала и карьерный консультант SuperJob Pro (https://www.superjob.ru/pro/).
Твоя задача — провести глубокий скоринг вакансии для кандидата на основе методологии рекрутерских фильтров и выявления Red Flags.

ВЕРИФИЦИРОВАННЫЙ ПРОФИЛЬ КАНДИДАТА:
- ФИО: Турейко Дмитрий Валерьевич
- Образование: СПО МТИ («Информационные системы (по отраслям)»), профильное.
- Квалификация: Специалист по информационным системам.
- Дополнительное образование: удостоверение «Базы данных. SQL», «Проектирование ИС и эксплуатация БД», Python/Django (Urban University), Java (Maxima IT School), Frontend (HTML/JS), AI & No-code.
- Навыки и опыт: базовый Python/Django, SQL и реляционные БД, HTML/JS, Node.js базовый, веб-разработка, Tilda, Telegram-боты, AI-инструменты. Учебный и самостоятельный опыт.
- Векторы резюме:
  1. ai_automation (Приоритет A: AI Automation / n8n / ИИ-агенты / интеграции)
  2. backend_python (Приоритет B: Junior Backend / Python Developer)
  3. qa_testing (Приоритет C: Junior QA / ручное тестирование без звонков)
  4. is_developer (Основное: Информационные системы / Junior Developer / БД)
  5. frontend_fullstack (Вариант 2: Junior Frontend / Fullstack)

ПАРСИНГ ВАКАНСИИ:
{job_json}

ЭКСПЕРТНАЯ МЕТОДОЛОГИЯ СКОРИНГА SUPERJOB PRO И 3 ОБЯЗАТЕЛЬНЫХ ФИЛЬТРА ДМИТРИЯ:
1. КРИТИЧЕСКИЙ ФИЛЬТР 1: 100% УДАЛЁНКА (Ленинградская область / Сосновый Бор)
   - Если требуется гибрид, офис или проживание строго в Москве — штраф и пометка в strict_criteria_notes.
2. КРИТИЧЕСКИЙ ФИЛЬТР 2: РЕАЛЬНЫЙ JUNIOR / СТАЖЁР
   - Должен подходить кандидат без коммерческого опыта или до 1 года. Если требуют 3+ года — снижать баллы.
3. КРИТИЧЕСКИЙ ФИЛЬТР 3: БЕЗ ПОСТОЯННОЙ ТЕЛЕФОННОЙ ПОДДЕРЖКИ
   - Никаких дежурств на телефоне, оператора колл-центра, холодных/горячих звонков. Допустимы тикеты, почта, чаты. Если есть звонки — has_phone_support_risk=true и жесткий штраф!

Шкалы скоринга:
- Hard Skills Match (0-40 баллов)
- Experience & Grade Match (0-25 баллов)
- Education & Domain Match (0-15 баллов за СПО МТИ и БД)
- Conditions & Transparency (0-10 баллов за удаленку и прозрачность)
- Штрафы Red Flags (от 0 до -25 баллов)

Верни строго JSON:
{{
  "total_score": 85,
  "priority_tier": "HIGH",
  "hard_skills_score": 35,
  "experience_grade_score": 22,
  "education_domain_score": 15,
  "conditions_score": 10,
  "red_flags_penalty": 0,
  "recommended_vector": "ai_automation | backend_python | qa_testing | is_developer | frontend_fullstack",
  "is_fully_remote": true,
  "is_junior_friendly": true,
  "has_phone_support_risk": false,
  "strict_criteria_notes": [
    "✅ 100% удаленный формат подтвержден",
    "✅ Подходит для начинающего специалиста без опыта",
    "✅ Нет требований к работе на телефоне"
  ],
  "pros": ["Отличное совпадение по n8n и API", "Удаленный формат"],
  "cons_and_risks": ["Не указана вилка зарплаты"],
  "missing_gaps": ["Postman тесты (легко освоить за 1-2 дня)"],
  "application_strategy": "Отправить отклик с упором на СПО МТИ и проект AI-помощника обработки заявок."
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
