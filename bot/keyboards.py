from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from agent.models import ApplicationStatus

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔎 Поиск вакансий РФ"), KeyboardButton(text="🏢 Стажировки корпораций")],
            [KeyboardButton(text="📅 План на 30 дней"), KeyboardButton(text="🚀 Проекты для портфолио")],
            [KeyboardButton(text="📊 Воронка откликов"), KeyboardButton(text="📋 Последние отклики")],
            [KeyboardButton(text="🎯 Подготовка к интервью"), KeyboardButton(text="🔄 Разбор собеседования")],
            [KeyboardButton(text="📄 Три готовых резюме"), KeyboardButton(text="📚 Методология SuperJob Pro")],
            [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )

def get_search_categories_keyboard() -> InlineKeyboardMarkup:
    """Выбор роли для поиска вакансий с учетом приоритетов и фильтра звонков"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🤖 AI Automation / n8n / Боты", callback_data="search_role:ai_automation"),
            ],
            [
                InlineKeyboardButton(text="🐍 Python / Backend стажер", callback_data="search_role:backend_python"),
            ],
            [
                InlineKeyboardButton(text="🧪 Junior QA (без звонков / API)", callback_data="search_role:qa_testing"),
            ],
            [
                InlineKeyboardButton(text="💻 Информационные системы / Младший Dev", callback_data="search_role:is_developer"),
            ],
            [
                InlineKeyboardButton(text="🌐 Frontend / Fullstack разработчик", callback_data="search_role:frontend_fullstack"),
            ],
            [
                InlineKeyboardButton(text="🔍 Свой поисковый запрос...", callback_data="search_custom:prompt"),
                InlineKeyboardButton(text="🏢 Стажировки корпораций", callback_data="show_internships:all")
            ]
        ]
    )

def get_resumes_inline_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для просмотра 3 резюме по форматам занятости и SuperJob профилей"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1️⃣ Полный день (50–60k / Remote)", callback_data="view_resume:resume_fulltime"),
            ],
            [
                InlineKeyboardButton(text="2️⃣ Подработка / Проектно (25–35k)", callback_data="view_resume:resume_parttime"),
            ],
            [
                InlineKeyboardButton(text="3️⃣ Стажёр с обучением (Intern)", callback_data="view_resume:resume_intern"),
            ],
            [
                InlineKeyboardButton(text="🔗 Мои резюме на SuperJob", callback_data="view_resume:superjob_links"),
                InlineKeyboardButton(text="📋 Правила и логика системы", callback_data="view_resume:guidelines"),
            ]
        ]
    )

def get_job_item_action_keyboard(search_item_id: str, url: str) -> InlineKeyboardMarkup:
    """Кнопки действия под карточкой найденной вакансии"""
    buttons = [
        [
            InlineKeyboardButton(text="⚡ Откликнуться (Письмо)", callback_data=f"act_cover:{search_item_id}"),
            InlineKeyboardButton(text="📊 Скоринг & Риски", callback_data=f"act_score:{search_item_id}")
        ]
    ]
    if url:
        buttons.append([InlineKeyboardButton(text="🔗 Открыть на сайте", url=url)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_job_actions_keyboard(job_id: str) -> InlineKeyboardMarkup:
    """Кнопки действий после парсинга и скоринга вакансии"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡ Краткий отклик (hh/SJ)", callback_data=f"gen_cover_short:{job_id}"),
                InlineKeyboardButton(text="✉️ Полное письмо (HR)", callback_data=f"gen_cover_det:{job_id}")
            ],
            [
                InlineKeyboardButton(text="📄 Адаптировать резюме", callback_data=f"gen_resume:{job_id}"),
                InlineKeyboardButton(text="🎯 Интервью (STAR + Tech)", callback_data=f"prep_interview:{job_id}")
            ],
            [
                InlineKeyboardButton(text="🔍 Детальный скоринг и риски", callback_data=f"show_scoring:{job_id}"),
                InlineKeyboardButton(text="💾 Сохранить в CRM", callback_data=f"save_crm:{job_id}")
            ]
        ]
    )

def get_tailored_resume_actions_keyboard(job_id: str) -> InlineKeyboardMarkup:
    """Кнопки под адаптированным резюме"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Полный текст для hh.ru", callback_data=f"show_full_resume:{job_id}"),
                InlineKeyboardButton(text="✉️ Сгенерировать отклик", callback_data=f"gen_cover_short:{job_id}")
            ],
            [
                InlineKeyboardButton(text="💾 Сохранить в CRM", callback_data=f"save_crm:{job_id}"),
                InlineKeyboardButton(text="🎯 Подготовка к интервью", callback_data=f"prep_interview:{job_id}")
            ]
        ]
    )

def get_status_update_keyboard(app_id: int) -> InlineKeyboardMarkup:
    """Кнопки смены статуса отклика в CRM"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👁 Просмотрено", callback_data=f"set_st:{app_id}:viewed"),
                InlineKeyboardButton(text="📞 Скрининг", callback_data=f"set_st:{app_id}:screening")
            ],
            [
                InlineKeyboardButton(text="⏳ Тестовое задание", callback_data=f"set_st:{app_id}:test"),
                InlineKeyboardButton(text="🎙 Собеседование", callback_data=f"set_st:{app_id}:interview")
            ],
            [
                InlineKeyboardButton(text="🎉 Оффер!", callback_data=f"set_st:{app_id}:offer"),
                InlineKeyboardButton(text="❌ Отказ", callback_data=f"set_st:{app_id}:reject")
            ],
            [
                InlineKeyboardButton(text="📅 Задать дедлайн ТЗ", callback_data=f"set_dl:{app_id}"),
                InlineKeyboardButton(text="📝 Добавить заметку", callback_data=f"set_note:{app_id}")
            ]
        ]
    )

def get_copy_letter_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 Адаптировать резюме", callback_data=f"gen_resume:{job_id}"),
                InlineKeyboardButton(text="💾 Сохранить в CRM", callback_data=f"save_crm:{job_id}")
            ],
            [
                InlineKeyboardButton(text="🎯 Подготовка к интервью", callback_data=f"prep_interview:{job_id}")
            ]
        ]
    )

def get_action_plan_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для 30-дневного плана действий"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1️⃣ Неделя 1: База & Флагман", callback_data="view_week:1"),
                InlineKeyboardButton(text="2️⃣ Неделя 2: Тестирование", callback_data="view_week:2"),
            ],
            [
                InlineKeyboardButton(text="3️⃣ Неделя 3: Масштабирование", callback_data="view_week:3"),
                InlineKeyboardButton(text="4️⃣ Неделя 4: Оффер & Конверсия", callback_data="view_week:4"),
            ],
            [
                InlineKeyboardButton(text="⏱ Распорядок дня (3–4 часа)", callback_data="view_plan_routine:show"),
                InlineKeyboardButton(text="🎯 Фильтры & Правила отбора", callback_data="view_plan_rules:show")
            ]
        ]
    )

def get_portfolio_hub_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура каталога проектов для портфолио"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🤖 Флагман: AI Ticket Processor", callback_data="view_proj:ai_ticket_processor"),
            ],
            [
                InlineKeyboardButton(text="🏥 REST API: Сервис клиники (Django/FastAPI)", callback_data="view_proj:clinic_rest_api"),
            ],
            [
                InlineKeyboardButton(text="🧪 QA Suite: Тестирование API & Баг-репорты", callback_data="view_proj:qa_test_suite"),
            ],
            [
                InlineKeyboardButton(text="📖 Как презентовать AI в портфолио", callback_data="view_proj_philosophy:show")
            ]
        ]
    )

def get_project_actions_keyboard(proj_id: str) -> InlineKeyboardMarkup:
    """Кнопки действий внутри проекта портфолио"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡ Архитектура & Схема данных", callback_data=f"gen_proj_arch:{proj_id}"),
                InlineKeyboardButton(text="🗓 План разработки на 7 дней", callback_data=f"gen_proj_plan:{proj_id}")
            ],
            [
                InlineKeyboardButton(text="🧪 Негативные сценарии & Тесты", callback_data=f"gen_proj_tests:{proj_id}"),
                InlineKeyboardButton(text="📄 Шаблон README.md", callback_data=f"gen_proj_readme:{proj_id}")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад в каталог проектов", callback_data="back_to_projects:list")
            ]
        ]
    )
