import json
import logging
from typing import Optional, Union, Dict, Any
from config import settings
from agent.models import (
    ParsedJob,
    JobAnalysis,
    InterviewPrep,
    InterviewDebrief,
    QuestionItem,
    StarBehavioralItem
)
from agent.llm import LLMService
from agent.prompts import load_profile_context, get_system_prompt, INTERVIEW_DEBRIEF_PROMPT

logger = logging.getLogger(__name__)

SUPERJOB_INTERVIEW_PREP_PROMPT = """Ты — ведущий технический рекрутер и карьерный ментор SuperJob Pro (https://www.superjob.ru/pro/).
Подготовь кандидата к собеседованию на вакансию по полному стандарту платформы SuperJob Pro.

ДАННЫЕ О ВАКАНСИИ:
{job_info}

ВЕРИФИЦИРОВАННЫЙ ПРОФИЛЬ КАНДИДАТА:
- ФИО: Турейко Дмитрий Валерьевич
- Образование: СПО МТИ («Информационные системы (по отраслям)»), квалификация «Специалист по информационным системам».
- Доп. образование: «Базы данных. SQL» (удостоверение), «Проектирование ИС и эксплуатация баз данных» (сертификат), Python/Django (Urban University), Java (Maxima IT School), Frontend (HTML/JS), AI & No-code.
- Навыки: Python (базовый, Django), SQL и реляционные БД, HTML/JS, Node.js (базовый), веб-разработка, Tilda, Telegram-боты, AI-инструменты, Git.
- Практика: учебные и самостоятельные проекты по веб-разработке, Telegram-ботам, базам данных и AI-инструментам.

ТВОЯ ЗАДАЧА — СФОРМИРОВАТЬ 3 КРИТИЧЕСКИХ БЛОКА ПОДГОТОВКИ:

БЛОК 1: Технический скрининг (ровно 10 вопросов)
- 10 точечных вопросов по стеку вакансии (junior/trainee уровень).
- Для каждого вопроса: тема и 2-4 ключевых тезиса (key_points) для уверенного ответа.

БЛОК 2: Поведенческие вопросы по формуле STAR (Situation, Task, Action, Result)
Сформируй готовые ответы для кандидата строго на основе его реального бэкграунда:
1. Самопрезентация (Elevator Pitch на 1.5 минуты): кто я + профильное СПО МТИ («Информационные системы») + ключевой стек + практический учебный опыт и готовность к тестовому.
2. «Почему именно наша компания?»: персонализированный ответ под специфику вакансии.
3. «Расскажите о сложной технической проблеме/задаче, которую вы решили»: разобрать по STAR (например, проектирование схемы реляционной БД в PostgreSQL/SQLite, составление сложных SQL выборок, разработка Telegram-бота или верстка адаптивного веб-интерфейса).
4. Вопрос о зарплатных ожиданиях: как грамотно назвать вилку junior-специалиста по стандарту SuperJob Pro.

БЛОК 3: Вопросы кандидата к работодателю (3-5 вопросов)
- Умные, зрелые вопросы, которые по статистике SuperJob Pro повышают шансы на оффер (код-ревью, процессы онбординга, первые задачи на исп. срок, менторство в команде).

Верни строго JSON:
{{
  "role_summary": "Краткий фокус и особенности собеседования для данной роли",
  "technical_questions": [
    {{
      "number": 1,
      "topic": "PostgreSQL",
      "question": "В чем разница между уровнями изоляции транзакций?",
      "key_points": ["Read Committed по умолчанию в Postgres", "MVCC предотвращает фантомное чтение", "Serializable исключает все аномалии"]
    }}
  ],
  "behavioral_star_questions": [
    {{
      "question": "Расскажите о себе (самопрезентация)",
      "situation_context": "Завершил профильное СПО МТИ по специальности 'Информационные системы'.",
      "task_description": "Цель: разработка надежных бэкенд-сервисов и автоматизация.",
      "action_taken": "Спроектировал и самостоятельно развернул в проде gorizont-blog.ru (Django, Postgres, Linux/Nginx), создал агентную систему AI Blog Generator и модуль clinic_connect.",
      "result_metric": "Работающий продакшен-сервис, практический опыт деплоя и проектирования БД.",
      "expert_tip": "Говорить бодро, уложиться в 90 секунд, фокус на сделанном коде и работающем сайте."
    }}
  ],
  "questions_for_employer": [
    "Как в вашей команде устроен процесс код-ревью и менторства начинающих инженеров?",
    "Какие задачи будут приоритетными в первые 2 месяца?",
    "Какой стек и инструменты используются для CI/CD и деплоя?"
  ]
}}
"""

class InterviewAssistant:
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.profile = load_profile_context(settings.PROFILE_CONTEXT_PATH)
        self.llm = llm_service or LLMService(system_instruction=get_system_prompt(self.profile))

    async def generate_prep_questions(self, job_or_analysis: Union[ParsedJob, JobAnalysis]) -> InterviewPrep:
        """Генерирует полную 3-блочную программу подготовки к интервью по стандартам SuperJob Pro"""
        if isinstance(job_or_analysis, ParsedJob):
            info = {
                "title": job_or_analysis.title,
                "company": job_or_analysis.company,
                "key_skills": job_or_analysis.key_skills,
                "requirements": job_or_analysis.requirements_hard,
                "responsibilities": job_or_analysis.responsibilities[:5]
            }
        else:
            info = job_or_analysis.model_dump()

        job_info_str = json.dumps(info, ensure_ascii=False, indent=2)
        prompt = SUPERJOB_INTERVIEW_PREP_PROMPT.format(job_info=job_info_str)

        return await self.llm.generate_structured(prompt, InterviewPrep)

    async def debrief_interview(self, candidate_notes: str, job_info: Optional[Union[ParsedJob, JobAnalysis]] = None) -> InterviewDebrief:
        """Разбирает вопросы, на которых кандидат запнулся, и строит микро-план ликвидации пробелов"""
        info_str = "{}"
        if job_info:
            info_str = json.dumps(job_info.model_dump(), ensure_ascii=False, indent=2)

        prompt = INTERVIEW_DEBRIEF_PROMPT.format(
            candidate_notes=candidate_notes,
            job_analysis_json=info_str
        )

        return await self.llm.generate_structured(prompt, InterviewDebrief)
