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
  1. is_developer (Основное: Информационные системы / Junior Developer)
  2. backend_python (Вариант 1: Junior Backend / Python Developer)
  3. frontend_fullstack (Вариант 2: Junior Frontend / Fullstack Developer)

ПАРСИНГ ВАКАНСИИ:
{job_json}

ЭКСПЕРТНАЯ МЕТОДОЛОГИЯ СКОРИНГА SUPERJOB PRO:
1. Hard Skills Match (0-40 баллов):
   - Оцени, какой процент требуемых технологий кандидат уже закрывает своим стеком и обучением.
2. Experience & Grade Match (0-25 баллов):
   - Оцени соответствие грейда. Стажер/Junior = 20-25 баллов. Если требуют 3+ года на джуна — снижай баллы.
3. Education & Domain Match (0-15 баллов):
   - Профильное СПО МТИ («Информационные системы») и прикладные базы данных.
4. Conditions & Transparency (0-10 баллов):
   - Удаленка, понятный график, наличие описания команды.
5. Штрафы Red Flags (от 0 до -25 баллов):
   - Размытые обязанности, «10 ролей в одном» (фронт+бэк+дизайн+продажи), токсичные формулировки («стрессоустойчивость 24/7», «ненормированный рабочий день»).

Определи:
- Рекомендуемый вектор (is_developer / backend_python / frontend_fullstack).
- Приоритет: HIGH (>=80), MEDIUM (60-79), LOW (<60).
- Плюсы вакансии (почему подходит кандидату).
- Минусы и риски (Red Flags работодателя).
- Пробелы (чего не хватает в резюме под эту вакансию).
- Стратегия отклика: как податься, на что сделать упор по методологии SuperJob Pro.

Верни строго JSON:
{{
  "total_score": 85,
  "priority_tier": "HIGH",
  "hard_skills_score": 35,
  "experience_grade_score": 22,
  "education_domain_score": 15,
  "conditions_score": 10,
  "red_flags_penalty": 0,
  "recommended_vector": "backend_python",
  "pros": ["Отличное совпадение по Django и PostgreSQL", "Удаленный формат"],
  "cons_and_risks": ["Не указана вилка зарплаты"],
  "missing_gaps": ["Docker (желателен, но компенсируется опытом Linux)"],
  "application_strategy": "Отправить краткий отклик с упором на продакшен-деплой gorizont-blog.ru и предложить выполнить тестовое задание."
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
