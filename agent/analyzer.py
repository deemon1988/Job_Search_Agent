import json
import logging
import re
from typing import Optional
from config import settings
from agent.models import JobAnalysis, CareerVector
from agent.llm import LLMService
from agent.prompts import (
    load_profile_context,
    get_system_prompt,
    JOB_ANALYSIS_PROMPT
)

logger = logging.getLogger(__name__)

class JobAnalyzer:
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.profile = load_profile_context(settings.PROFILE_CONTEXT_PATH)
        self.llm = llm_service or LLMService(system_instruction=get_system_prompt(self.profile))

    def detect_platform(self, text: str, url: Optional[str] = None) -> str:
        check = f"{text} {url or ''}".lower()
        if "hh.ru" in check or "headhunter" in check:
            return "hh.ru"
        elif "habr.com" in check or "career.habr" in check:
            return "Хабр Карьера"
        elif "superjob.ru" in check:
            return "SuperJob"
        elif "trudvsem.ru" in check:
            return "Работа России (Трудвсем)"
        elif "t.me" in check or "telegram" in check:
            return "Telegram канал"
        return "Прямой контакт"

    async def analyze(self, job_text: str, url: Optional[str] = None) -> JobAnalysis:
        """Анализирует текст вакансии через LLM"""
        prompt = JOB_ANALYSIS_PROMPT.format(job_text=job_text)
        analysis: JobAnalysis = await self.llm.generate_structured(prompt, JobAnalysis)

        # Дополнительно обогащаем платформой и url если переданы
        if url:
            analysis.url = url
            analysis.platform = self.detect_platform(job_text, url)
        elif not analysis.platform or analysis.platform == "hh.ru":
            analysis.platform = self.detect_platform(job_text)

        return analysis
