import json
import logging
from typing import Optional, Dict, Any, List
from config import settings
from agent.models import JobAnalysis, ResumeCustomization, CareerVector
from agent.llm import LLMService
from agent.prompts import (
    load_profile_context,
    get_system_prompt,
    RESUME_TAILOR_PROMPT
)

logger = logging.getLogger(__name__)

class ResumeCustomizer:
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.profile = load_profile_context(settings.PROFILE_CONTEXT_PATH)
        self.llm = llm_service or LLMService(system_instruction=get_system_prompt(self.profile))

    def get_three_resumes(self) -> Dict[str, Any]:
        """Возвращает 3 базовых резюме из профиля"""
        return self.profile.get("three_resume_templates", {})

    def get_base_template(self, vector: CareerVector) -> Dict[str, Any]:
        """Возвращает базовый статичный шаблон из профиля по вектору или ключу занятости"""
        vector_key = vector.value if isinstance(vector, CareerVector) else str(vector)
        resumes = self.get_three_resumes()
        # Прямой поиск по id или variant_type
        if vector_key in resumes:
            return resumes[vector_key]
        for r_id, r_data in resumes.items():
            if r_data.get("variant_type") == vector_key or r_data.get("vector_key") == vector_key:
                return r_data
        # Сопоставление векторов карьерных направлений
        mapping = {
            "backend_python": "resume_fulltime",
            "frontend_fullstack": "resume_parttime",
            "is_developer": "resume_fulltime",
            "ai_automation": "resume_fulltime",
            "qa_testing": "resume_intern"
        }
        target_id = mapping.get(vector_key, "resume_fulltime")
        return resumes.get(target_id, {})

    def render_base_resume(self, resume_key: str) -> str:
        """Рендерит готовый результат резюме по функциональной модели (Контакты, Шапка, Навыки, О себе)"""
        resumes = self.get_three_resumes()
        r = resumes.get(resume_key)
        if not r:
            # Поддержка старых ключей для обратной совместимости
            compat_map = {
                "resume_main_is": "resume_fulltime",
                "resume_backend_python": "resume_fulltime",
                "resume_frontend_fullstack": "resume_parttime"
            }
            target_key = compat_map.get(resume_key, "resume_fulltime")
            r = resumes.get(target_key)
            if not r:
                return "Резюме не найдено."

        p = self.profile.get("personal", {})
        contacts = (
            f"👤 {p.get('full_name', 'Турейко Дмитрий Валерьевич')}\n"
            f"📍 {p.get('location', 'Ленинградская область, гор. Сосновый Бор')}\n"
            f"📞 {p.get('phone', '+79516601092')} · ✉️ {p.get('email', 'dmn72835@yandex.ru')}\n"
            f"💻 GitHub: {p.get('github', 'https://github.com/deemon1988')}"
        )

        superjob_link = r.get("superjob_link", "")
        pdf_download_link = r.get("pdf_download_link", "")
        sj_block = f"\n🔗 SuperJob: {superjob_link}" if superjob_link else ""
        pdf_block = f"\n📥 PDF (Google Drive): {pdf_download_link}" if pdf_download_link else ""

        skills_list = ", ".join(r.get("skills", []))

        text = (
            f"═══════════════════════════════════════\n"
            f"📄 {r.get('direction', 'РЕЗЮМЕ')}\n"
            f"═══════════════════════════════════════\n\n"
            f"📌 КОНТАКТЫ И ССЫЛКИ:\n"
            f"{contacts}{sj_block}{pdf_block}\n\n"
            f"🎯 ШАПКА РЕЗЮМЕ:\n"
            f"• Желаемая должность: {r.get('target_title')}\n"
            f"• Зарплата: {r.get('salary', 'Не указана')}\n"
            f"• Занятость: {r.get('employment_type')}\n"
            f"• График: {r.get('work_schedule')}\n"
            f"• Опыт работы: {r.get('experience_status')}\n\n"
            f"⭐ КЛЮЧЕВЫЕ НАВЫКИ (SKILLS):\n"
            f"`{skills_list}`\n\n"
            f"📝 БЛОК «О СЕБЕ» (ГОТОВ К ВСТАВКЕ):\n"
            f"{r.get('about_me')}\n\n"
            f"🎓 ОБРАЗОВАНИЕ:\n"
            f"{r.get('education_text')}\n\n"
            f"📚 ДОПОЛНИТЕЛЬНОЕ ОБРАЗОВАНИЕ:\n"
            f"{r.get('courses_text')}\n"
            f"═══════════════════════════════════════"
        )
        return text

    async def tailor(self, analysis: JobAnalysis) -> ResumeCustomization:
        """Адаптирует заголовок, блок 'О себе' и проекты под конкретную вакансию"""
        analysis_json = json.dumps(analysis.model_dump(), ensure_ascii=False, indent=2)
        prompt = RESUME_TAILOR_PROMPT.format(job_analysis_json=analysis_json)

        customization: ResumeCustomization = await self.llm.generate_structured(
            prompt,
            ResumeCustomization
        )

        # Если модель не сгенерировала полный текст резюме, формируем его
        if not customization.full_resume_text:
            p = self.profile.get("personal", {})
            contacts = (
                f"👤 {p.get('full_name', 'Турейко Дмитрий Валерьевич')}\n"
                f"📍 {p.get('location', 'Ленинградская область, гор. Сосновый Бор')}\n"
                f"📞 {p.get('phone', '+79516601092')} · ✉️ {p.get('email', 'dmn72835@yandex.ru')}\n"
                f"💻 GitHub: {p.get('github', 'https://github.com/deemon1988')}"
            )
            skills_str = ", ".join(customization.priority_skills) if customization.priority_skills else "Python, SQL, Django, REST API, Git, HTML/CSS"

            customization.full_resume_text = (
                f"═══════════════════════════════════════\n"
                f"📄 АДАПТИРОВАННОЕ РЕЗЮМЕ ПОД ВАКАНСИЮ\n"
                f"═══════════════════════════════════════\n\n"
                f"📌 КОНТАКТЫ:\n"
                f"{contacts}\n\n"
                f"🎯 ШАПКА РЕЗЮМЕ:\n"
                f"• Желаемая должность: {customization.tailored_title}\n"
                f"• Занятость: Удаленная работа (Full-time / Part-time)\n"
                f"• Опыт работы: Без опыта коммерческой разработки / Проектная практика\n\n"
                f"⭐ КЛЮЧЕВЫЕ НАВЫКИ (7–10 ТЕХНОЛОГИЙ):\n"
                f"`{skills_str}`\n\n"
                f"📝 БЛОК «О СЕБЕ» (БУЛЛЕТЫ ДЛЯ HR НА 5-7 СЕКУНД):\n"
                f"{customization.tailored_summary}\n\n"
                f"🎓 ОБРАЗОВАНИЕ:\n"
                f"Московский технологический институт (ОАНО ВО МТИ) | Информационные системы (по отраслям)\n\n"
                f"📚 ДОПОЛНИТЕЛЬНОЕ ОБРАЗОВАНИЕ:\n"
                f"• «Базы данных. SQL» (удостоверение) • Проектирование ИС (сертификат)\n"
                f"• Python / Django (Urban University) • AI и автоматизация (Zerocoder)\n"
                f"═══════════════════════════════════════"
            )

        return customization
