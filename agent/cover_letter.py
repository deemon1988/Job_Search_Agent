import json
import logging
from typing import Optional, Union
from config import settings
from agent.models import ParsedJob, JobAnalysis, CoverLetter, JobScoreBreakdown
from agent.llm import LLMService
from agent.prompts import load_profile_context, get_system_prompt

logger = logging.getLogger(__name__)

SUPERJOB_COVER_LETTER_PROMPT = """Ты — ведущий эксперт SuperJob Pro (https://www.superjob.ru/pro/) по написанию конвертящих откликов на IT-вакансии.
Составь сопроводительное письмо для кандидата Дмитрия Турейко строго по экспертной формуле SuperJob Pro.

ИНФОРМАЦИЯ О ВАКАНСИИ:
{job_info}

ВЕРИФИЦИРОВАННЫЙ ПРОФИЛЬ КАНДИДАТА:
- ФИО: Турейко Дмитрий Валерьевич
- Образование: Профильное СПО, Московский технологический институт (ОАНО ВО МТИ), специальность «Информационные системы (по отраслям)», квалификация «Специалист по информационным системам».
- Доп. образование: «Базы данных. SQL» (удостоверение), «Проектирование ИС и баз данных» (сертификат), Python/Django (Urban University), Java (Maxima IT School), Frontend (HTML/JS), AI & No-code.
- Стек и навыки: Python (базовый, Django), SQL и проектирование баз данных, JavaScript/HTML, Node.js (базовый), веб-разработка, Tilda, Telegram-боты, интеграция AI-инструментов, Git.
- Контакты: +79516601092, dmn72835@yandex.ru, https://github.com/deemon1988

СТАНДАРТЫ SUPERJOB PRO (КРИТИЧЕСКИ ВАЖНО):
1. ПРАВИЛО ПЕРВЫХ 2 СТРОК (HOOK): Рекрутер тратит 5-10 секунд. Первые две строки должны сразу зацепить:
   - Имя рекрутера (если указано в вакансии), точная позиция, профильное СПО МТИ («Информационные системы») и релевантный стек.
2. СВЯЗКА С БОЛЯМИ КОМПАНИИ:
   - Чем профиль кандидата полезен конкретно их задачам (базы данных, Python, веб-разработка, автоматизация).
   - Для ИС / баз данных -> СПО МТИ, проектирование схем БД, составление SQL-запросов, удостоверение по базам данных.
   - Для Python / Backend -> базовая серверная разработка на Python/Django, реляционные БД, API, боты.
   - Для Frontend / Web -> верстка HTML/JS, веб-интерфейсы, Tilda.
3. ЧЕСТНОСТЬ И НИКАКИХ ВЫМЫСЛОВ:
   - Не завышать квалификацию (Junior/стажер), не придумывать опыт работы в коммерческих компаниях.
   - Запрещены шаблонные клише («легко обучаем», «стрессоустойчив», «коммуникабелен»).
4. КАНОНИЧЕСКИЙ КАРКАС ИЗ БАЗЫ ЗНАНИЙ (РАЗДЕЛ 8):
   «Здравствуйте! Откликаюсь на вакансию [название]. У меня среднее профессиональное образование по специальности «Специалист по информационным системам». Я создавал и публиковал проекты с использованием AI-инструментов, подключал API и базы данных. Готов применять эти навыки, быстро осваивать необходимые технологии и разбираться в работе готового продукта. Примеры проектов: [ссылки]. Рассматриваю полностью удалённую работу из России.»
   Адаптируй этот каркас под стек и требования конкретной вакансии.
5. CALL TO ACTION (CTA): Готовность оперативно выполнить тестовое задание и пройти собеседование.

Сгенерируй два формата письма:
1. "short_letter": Краткий отклик для чата платформы (hh.ru / SuperJob), строго 500-750 символов.
2. "detailed_letter": Развернутое письмо для прямого контакта / email / Telegram, строго 800-1100 символов.

Верни строго JSON:
{{
  "hook_phrase": "Первая зацепляющая фраза...",
  "short_letter": "Текст краткого отклика...",
  "detailed_letter": "Текст развернутого письма...",
  "char_count_short": 620,
  "char_count_detailed": 950,
  "highlighted_projects": ["СПО МТИ", "Базы данных SQL", "Учебные проекты Python/JS"],
  "skills_covered": ["SQL", "Python", "Веб-разработка"]
}}
"""

class CoverLetterGenerator:
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.profile = load_profile_context(settings.PROFILE_CONTEXT_PATH)
        self.llm = llm_service or LLMService(system_instruction=get_system_prompt(self.profile))

    async def generate(self, job_or_analysis: Union[ParsedJob, JobAnalysis]) -> CoverLetter:
        """Генерирует два формата сопроводительного письма по стандарту SuperJob Pro"""
        if isinstance(job_or_analysis, ParsedJob):
            info = {
                "title": job_or_analysis.title,
                "company": job_or_analysis.company,
                "platform": job_or_analysis.platform,
                "recruiter_name": job_or_analysis.recruiter_name,
                "key_skills": job_or_analysis.key_skills,
                "requirements": job_or_analysis.requirements_hard + job_or_analysis.requirements_soft,
                "responsibilities": job_or_analysis.responsibilities[:5]
            }
        else:
            info = job_or_analysis.model_dump()

        job_info_str = json.dumps(info, ensure_ascii=False, indent=2)
        prompt = SUPERJOB_COVER_LETTER_PROMPT.format(job_info=job_info_str)

        cover: CoverLetter = await self.llm.generate_structured(prompt, CoverLetter)
        cover.char_count_short = len(cover.short_letter)
        cover.char_count_detailed = len(cover.detailed_letter)
        return cover
