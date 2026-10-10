from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class CareerVector(str, Enum):
    IS_DEVELOPER = "is_developer"
    BACKEND_PYTHON = "backend_python"
    FRONTEND_FULLSTACK = "frontend_fullstack"
    AI_AUTOMATION = "ai_automation"
    QA_TESTING = "qa_testing"
    DEVOPS_INFRA = "devops_infra"

class ApplicationStatus(str, Enum):
    NEW = "Новый"
    RESERVE = "В резерве"
    SENT = "Отправлено"
    VIEWED = "Просмотрено"
    SCREENING = "Скрининг"
    TEST_TASK = "Тестовое задание"
    INTERVIEW = "Собеседование"
    OFFER = "Оффер"
    REJECTED = "Отказ"
    ARCHIVED = "Архив / Закрыта"

class RelevanceGroup(str, Enum):
    GROUP_A = "A"       # A — откликаться в первую очередь
    GROUP_B = "B"       # B — откликаться после проверки
    GROUP_C = "C"       # C — резерв
    EXCLUDE = "EXCLUDE" # Исключить (офис/гибрид, звонки, выезды)

class RemoteStatus(str, Enum):
    CONFIRMED = "Подтверждена"
    UNCLEAR = "Неясно"
    UNSUITABLE = "Не подходит"

class ParsedJob(BaseModel):
    title: str = Field(description="Название должности")
    company: str = Field(default="Компания", description="Название компании")
    platform: str = Field(default="hh.ru", description="Платформа (hh.ru, superjob.ru, habr, etc.)")
    url: Optional[str] = Field(default=None, description="Ссылка на вакансию")
    salary_raw: Optional[str] = Field(default=None, description="Зарплатная вилка")
    employment_type: str = Field(default="Полная занятость", description="Удаленка, гибрид или офис")
    location: Optional[str] = Field(default=None, description="Город или локация")
    grade: str = Field(default="Junior", description="Определенный уровень: Стажер / Junior / Middle")
    key_skills: List[str] = Field(default_factory=list, description="Ключевые технологии и навыки")
    responsibilities: List[str] = Field(default_factory=list, description="Обязанности")
    requirements_hard: List[str] = Field(default_factory=list, description="Hard skills требования")
    requirements_soft: List[str] = Field(default_factory=list, description="Soft skills требования")
    benefits: List[str] = Field(default_factory=list, description="Условия и бенефиты")
    recruiter_name: Optional[str] = Field(default=None, description="Имя контактного лица / рекрутера")
    raw_text: str = Field(default="", description="Очищенный исходный текст вакансии")

class JobScoreBreakdown(BaseModel):
    total_score: int = Field(description="Итоговый скоринг соответствия (0-100)")
    priority_tier: str = Field(description="Приоритет: HIGH (Высокий), MEDIUM (Средний), LOW (Низкий)")
    relevance_group: str = Field(default="A", description="Группа соответствия: A (в первую очередь), B (после проверки), C (резерв), EXCLUDE (исключить)")
    remote_status: str = Field(default="Подтверждена", description="Подтверждена / Неясно / Не подходит")
    phone_support_status: str = Field(default="Нет", description="Нет / Есть / Неясно")
    geography_check: str = Field(default="Подтверждена (РФ)", description="Доступность для кандидата из РФ / ЛО")
    salary_assessment: str = Field(default="Соответствует (40-60k)", description="Оценка зарплаты")
    why_fits: str = Field(default="", description="Краткая аргументация по профилю кандидата")
    what_to_improve: str = Field(default="", description="Существенные пробелы стека")
    next_action: str = Field(default="Откликнуться", description="Откликнуться / Уточнить условия / Пропустить")
    remote_score: int = Field(default=25, description="Баллы за подтвержденную удаленку из РФ (до 25)")
    no_phone_score: int = Field(default=20, description="Баллы за отсутствие звонков и выездов (до 20)")
    junior_grade_score: int = Field(default=15, description="Баллы за соответствие уровню Junior/стажер/без опыта (до 15)")
    salary_score: int = Field(default=15, description="Баллы за соответствие зарплаты цели 40-60к (до 15)")
    tech_and_projects_score: int = Field(default=15, description="Баллы за соответствие опыту с ИИ, API, БД и проектами (до 15)")
    transparency_score: int = Field(default=10, description="Баллы за актуальность, прозрачность и возможность отклика (до 10)")
    hard_skills_score: int = Field(default=35, description="Баллы за Hard Skills (до 40, обратная совместимость)")
    experience_grade_score: int = Field(default=20, description="Баллы за грейд и опыт (до 25, обратная совместимость)")
    education_domain_score: int = Field(default=15, description="Баллы за профильное образование МТИ и ИС (до 15)")
    conditions_score: int = Field(default=10, description="Баллы за условия и прозрачность (до 10)")
    red_flags_penalty: int = Field(default=0, description="Штраф за Red Flags (от 0 до -25)")
    recommended_vector: CareerVector = Field(description="Рекомендуемый вектор кандидата")
    pros: List[str] = Field(default_factory=list, description="Сильные стороны вакансии и совпадения")
    cons_and_risks: List[str] = Field(default_factory=list, description="Обнаруженные риски, Red Flags или завышенные ожидания")
    missing_gaps: List[str] = Field(default_factory=list, description="Пробелы в стеке кандидата под эту вакансию")
    application_strategy: str = Field(description="Экспертная стратегия отклика")
    is_fully_remote: bool = Field(default=True, description="Действительно ли 100% удаленка из Соснового Бора/Ленобласти")
    is_junior_friendly: bool = Field(default=True, description="Подходит ли начальный уровень (без опыта / до 1 года)")
    has_phone_support_risk: bool = False
    strict_criteria_notes: List[str] = Field(default_factory=list, description="Проверка по 7 обязательным фильтрам")

# Сохраняем обратную совместимость для JobAnalysis
class JobAnalysis(BaseModel):
    title: str = Field(description="Название вакансии или роли")
    company: str = Field(default="Компания", description="Название компании")
    platform: str = Field(default="hh.ru", description="Платформа (hh.ru, habr, superjob, trudvsem, direct)")
    url: Optional[str] = Field(default=None, description="Ссылка на вакансию")
    key_technologies: List[str] = Field(default_factory=list, description="Ключевые технологии и стек вакансии")
    key_requirements: List[str] = Field(default_factory=list, description="2-3 главных требования работодателя")
    recommended_vector: CareerVector = Field(description="Рекомендуемый вектор позиционирования")
    match_score: int = Field(default=80, description="Оценка совпадения профиля (0-100)")
    match_rationale: str = Field(description="Обоснование выбора вектора и связки с проектами кандидата")
    score_breakdown: Optional[JobScoreBreakdown] = None

class CoverLetter(BaseModel):
    short_letter: str = Field(description="Краткий отклик для чата платформы hh.ru/SuperJob (500-750 знаков)")
    detailed_letter: str = Field(description="Развернутое письмо для прямого контакта / почты (800-1100 знаков)")
    char_count_short: int = Field(default=0, description="Символов в коротком")
    char_count_detailed: int = Field(default=0, description="Символов в подробном")
    hook_phrase: str = Field(default="", description="Зацепка в первых 2 строках по SuperJob Pro")
    highlighted_projects: List[str] = Field(default_factory=list, description="Проекты кандидата, упомянутые в письме")
    skills_covered: List[str] = Field(default_factory=list, description="Закрытые требования вакансии")

    # Свойство для совместимости со старым кодом
    @property
    def letter_text(self) -> str:
        return self.short_letter or self.detailed_letter

    @property
    def char_count(self) -> int:
        return self.char_count_short or len(self.letter_text)

class ResumeCustomization(BaseModel):
    vector_name: str = Field(description="Название вектора/шаблона (Основное: ИС, Вариант 1: Backend/Python или Вариант 2: Frontend/Fullstack)")
    tailored_title: str = Field(description="Адаптированный заголовок резюме")
    tailored_summary: str = Field(description="Адаптированный блок 'О себе' под специфику вакансии")
    priority_skills: List[str] = Field(default_factory=list, description="Ключевые навыки, которые нужно вынести наверх")
    project_highlights: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Акценты по учебному опыту и навыкам"
    )
    full_resume_text: Optional[str] = Field(
        default=None,
        description="Полный готовый адаптированный текст резюме для hh.ru/SuperJob"
    )

class QuestionItem(BaseModel):
    number: int
    topic: str
    question: str
    key_points: List[str] = Field(description="Тезисы и ключевые факты для ответа")

class StarBehavioralItem(BaseModel):
    question: str
    situation_context: str = Field(description="S (Ситуация) из реальных проектов кандидата")
    task_description: str = Field(description="T (Задача) и стоявшие вызовы")
    action_taken: str = Field(description="A (Действие) — конкретный код, инструменты, решения")
    result_metric: str = Field(description="R (Результат) — измеримый итог")
    expert_tip: str = Field(description="Совет по самоподаче из SuperJob Pro")

class InterviewPrep(BaseModel):
    role_summary: str
    technical_questions: List[QuestionItem] = Field(description="10 технических вопросов по стеку")
    behavioral_star_questions: List[StarBehavioralItem] = Field(
        default_factory=list,
        description="Поведенческие вопросы по формуле STAR (SuperJob Pro)"
    )
    questions_for_employer: List[str] = Field(
        default_factory=list,
        description="3-5 умных вопросов кандидата к работодателю"
    )

    # Для обратной совместимости
    @property
    def questions(self) -> List[QuestionItem]:
        return self.technical_questions

class GapRemediationItem(BaseModel):
    question: str
    ideal_answer: str = Field(description="Четкий эталонный ответ на вопрос")
    quick_plan: str = Field(description="Микро-план / ссылки на что почитать или сделать, чтобы закрыть пробел")

class InterviewDebrief(BaseModel):
    strengths_observed: str
    gap_analysis: List[GapRemediationItem]
    overall_recommendations: str

class JobApplication(BaseModel):
    id: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)
    checked_at: Optional[str] = Field(default=None, description="Дата проверки объявления (ГГГГ-ММ-ДД)")
    published_at: Optional[str] = Field(default=None, description="Дата публикации объявления")
    platform: str = "hh.ru"
    company: str
    job_title: str
    job_url: str = ""
    vector: CareerVector = CareerVector.BACKEND_PYTHON
    cover_letter: str = ""
    status: ApplicationStatus = ApplicationStatus.NEW
    score: Optional[int] = None
    relevance_group: Optional[str] = Field(default="A", description="A / B / C / EXCLUDE")
    remote_status: Optional[str] = Field(default="Подтверждена", description="Подтверждена / Неясно / Не подходит")
    geography: Optional[str] = Field(default="РФ / Ленобласть", description="География найма")
    salary_info: Optional[str] = Field(default=None, description="Вилка, налоги, фикс/проект")
    experience_level: Optional[str] = Field(default="Junior / Без опыта", description="Требуемый уровень")
    phone_support_status: Optional[str] = Field(default="Нет", description="Нет / Есть / Неясно")
    why_fits: Optional[str] = Field(default=None, description="Краткая аргументация по профилю кандидата")
    gaps: Optional[str] = Field(default=None, description="Существенные пробелы, что подтянуть")
    next_action: Optional[str] = Field(default="Откликнуться", description="Откликнуться / Уточнить условия / Пропустить")
    test_deadline: Optional[str] = None
    notes: Optional[str] = None
    full_job_text: Optional[str] = None

