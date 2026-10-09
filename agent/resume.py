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
        """Возвращает базовый статичный шаблон из профиля по вектору"""
        vector_key = vector.value if isinstance(vector, CareerVector) else str(vector)
        resumes = self.get_three_resumes()
        for r_id, r_data in resumes.items():
            if r_data.get("vector_key") == vector_key:
                return r_data
        return self.profile.get("vectors", {}).get(vector_key, {})

    def render_base_resume(self, resume_key: str) -> str:
        """Рендерит полный текст одного из трех базовых резюме"""
        resumes = self.get_three_resumes()
        r = resumes.get(resume_key)
        if not r:
            # fallback
            return "Резюме не найдено."

        p = self.profile.get("personal", {})
        contacts = (
            f"{p.get('location', 'Ленинградская область, гор. Сосновый Бор')} · "
            f"{p.get('phone', '+79516601092')} · {p.get('email', 'dmn72835@yandex.ru')} · "
            f"{p.get('github', 'https://github.com/deemon1988')}"
        )

        skills_list = "\n".join([f"• {s}" for s in r.get("skills", [])])
        
        # Опыт и проекты
        exp_parts = []
        for exp in r.get("projects_experience", []):
            cat = exp.get("category", "")
            det = exp.get("details", "")
            exp_parts.append(f"**{cat}**\n{det}")
        exp_str = "\n\n".join(exp_parts) if exp_parts else "Учебные и самостоятельные задачи."

        # Если есть примечание о примерах проектов
        note = r.get("project_examples_placeholder", "")
        if note:
            exp_str += f"\n\n*Примеры проектов:* _{note}_"

        text = (
            f"РЕЗЮМЕ\n"
            f"{p.get('full_name', 'Турейко Дмитрий Валерьевич')}\n"
            f"{contacts}\n\n"
            f"ЖЕЛАЕМАЯ ДОЛЖНОСТЬ\n"
            f"{r.get('target_title')}\n"
            f"Альтернативные: {', '.join(r.get('alternative_titles', []))}\n\n"
            f"ПРОФЕССИОНАЛЬНЫЙ ПРОФИЛЬ\n"
            f"{r.get('professional_profile')}\n\n"
            f"КЛЮЧЕВЫЕ НАВЫКИ\n"
            f"{skills_list}\n\n"
            f"ПРОЕКТЫ И ПРАКТИЧЕСКИЙ ОПЫТ\n"
            f"{exp_str}\n\n"
            f"ОБРАЗОВАНИЕ\n"
            f"{r.get('education_text')}\n\n"
            f"ДОПОЛНИТЕЛЬНОЕ ОБРАЗОВАНИЕ\n"
            f"{r.get('courses_text')}\n\n"
            f"ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ\n"
            f"{p.get('additional_info', 'Готов выполнить тестовое задание и пройти собеседование.')}"
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
                f"{p.get('location', 'Ленинградская область, гор. Сосновый Бор')} · "
                f"{p.get('phone', '+79516601092')} · {p.get('email', 'dmn72835@yandex.ru')} · "
                f"{p.get('github', 'https://github.com/deemon1988')}"
            )
            skills_str = "\n".join([f"• {s}" for s in customization.priority_skills])
            highlights = "\n".join([f"• {h.get('project', '')}: {h.get('focus', '')}" for h in customization.project_highlights])

            customization.full_resume_text = (
                f"РЕЗЮМЕ (АДАПТИРОВАННОЕ ПОД ВАКАНСИЮ)\n"
                f"{p.get('full_name', 'Турейко Дмитрий Валерьевич')}\n"
                f"{contacts}\n\n"
                f"ЖЕЛАЕМАЯ ДОЛЖНОСТЬ\n"
                f"{customization.tailored_title}\n\n"
                f"ПРОФЕССИОНАЛЬНЫЙ ПРОФИЛЬ\n"
                f"{customization.tailored_summary}\n\n"
                f"ПРИОРИТЕТНЫЕ НАВЫКИ\n"
                f"{skills_str}\n\n"
                f"АКЦЕНТЫ В ПРАКТИКЕ И ПРОЕКТАХ\n"
                f"{highlights}\n\n"
                f"ОБРАЗОВАНИЕ\n"
                f"Московский технологический институт (ОАНО ВО МТИ) | Специальность: Информационные системы (по отраслям)\n\n"
                f"ДОПОЛНИТЕЛЬНОЕ ОБРАЗОВАНИЕ\n"
                f"• Базы данных. SQL — удостоверение\n• Проектирование ИС и баз данных — сертификат\n"
                f"• Python/Django (Urban University) • Java (Maxima IT School) • AI и No-code\n\n"
                f"ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ\n"
                f"Готов выполнить тестовое задание и быстро освоить стек проекта."
            )

        return customization
