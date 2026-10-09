import uuid
import logging
from typing import Dict, Any

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from agent import JobAgent, ParsedJob, JobScoreBreakdown, CoverLetter
from agent.job_searcher import JobSearchResult
from bot.keyboards import (
    get_search_categories_keyboard,
    get_job_item_action_keyboard,
    get_job_actions_keyboard
)
from bot.handlers.vacancies import vacancies_cache
from bot.utils import safe_edit_text, safe_answer, safe_reply

logger = logging.getLogger(__name__)
router = Router()
job_agent = JobAgent()

search_cache: Dict[str, JobSearchResult] = {}

class SearchStates(StatesGroup):
    waiting_for_custom_query = State()

@router.message(F.text.in_({"🔎 Поиск вакансий РФ", "/search"}))
async def open_search_menu(message: Message):
    text = (
        "🔎 *Мультиплатформенный поиск вакансий в РФ*\n\n"
        "Я ищу вакансии сразу по нескольким источникам:\n"
        "• **hh.ru** (официальный API: свежие вакансии, удаленка, без опыта / 1–3 года)\n"
        "• **Работа России (trudvsem.ru)** (госсектор, ИТ-компании, заводы, НИИ для выпускников СПО)\n"
        "• **Хабр Карьера** (аккредитованные IT-компании, стажировки)\n"
        "• **Стажерские программы корпораций** (Сбер, Т-Банк, ИнфоТеКС, Яндекс, Ростелеком, Softline)\n\n"
        "🎯 *Выберите целевое направление для старта:*"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=get_search_categories_keyboard())

@router.callback_query(F.data.startswith("search_role:"))
async def on_search_role(callback: CallbackQuery):
    role_key = callback.data.split(":")[1]
    roles = job_agent.searcher.get_starter_roles()
    role_data = roles.get(role_key, {})

    queries_map = {
        "support_l2_l3": "Специалист технической поддержки L2",
        "junior_python_dev": "Junior Python разработчик стажер",
        "ai_chatbot_integrator": "разработчик чат-ботов Python",
        "sql_data_analyst": "Младший специалист SQL базы данных"
    }
    query = queries_map.get(role_key, "Junior Python")
    role_title = role_data.get("title", query)

    await callback.answer(f"Ищу: {query}...")
    wait_msg = await safe_reply(callback.message, f"🔎 Ищу актуальные вакансии для роли: *{role_title}*...")

    # Поиск по hh.ru
    results = await job_agent.searcher.search_hh(query, limit=5)
    # Поиск по trudvsem
    trud_results = await job_agent.searcher.search_trudvsem(query, limit=2)

    # Дедупликация объединенной выдачи
    combined = []
    seen = set()
    for item in (results + trud_results):
        key = (item.company.lower().strip()[:20], item.title.lower().strip()[:25])
        if key in seen:
            continue
        seen.add(key)
        combined.append(item)

    if not combined:
        await safe_edit_text(wait_msg, f"По запросу *{query}* сейчас не найдено открытых вакансий. Попробуйте другой запрос.")
        return

    await safe_edit_text(
        wait_msg,
        f"🎯 *Найдено вакансий для старта ({len(combined)} шт.):*\n"
        f"Роль: *{role_title}*\n"
        f"Ниша: _{role_data.get('market_niche', 'IT-рынок')}_\n\n"
        f"💡 _Нажмите «Откликнуться», чтобы сгенерировать точечное письмо по SuperJob Pro._"
    )

    for item in combined[:5]:
        item_id = str(uuid.uuid4())[:8]
        search_cache[item_id] = item

        snip_block = f"\n📋 *Требования/Задачи:*\n_{item.snippet}_" if item.snippet and item.snippet != "Вакансия с hh.ru" else ""
        clean_url = item.url.split("?")[0] if item.url else ""

        card = (
            f"📌 *{item.title}*\n"
            f"🏢 *{item.company}* • 📍 _{item.location}_\n"
            f"💰 *{item.salary}* • ⏰ {item.schedule}"
            f"{snip_block}"
        )
        await safe_answer(
            callback.message,
            card,
            reply_markup=get_job_item_action_keyboard(item_id, clean_url),
            disable_web_page_preview=True
        )

@router.callback_query(F.data == "search_custom:prompt")
async def on_request_custom_query(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchStates.waiting_for_custom_query)
    await callback.answer()
    await callback.message.reply(
        "✏️ Отправьте в чат поисковый запрос (например: *'Стажер ИнфоТеКС'*, *'Django удаленно'*, *'Системный администратор стажер'*):",
        parse_mode="Markdown"
    )

@router.message(SearchStates.waiting_for_custom_query)
async def process_custom_query(message: Message, state: FSMContext):
    query = message.text.strip()
    wait_msg = await message.answer(f"🔎 Ищу по всем площадкам РФ: *{query}*...", parse_mode="Markdown")

    results = await job_agent.searcher.search_hh(query, limit=5)
    trud = await job_agent.searcher.search_trudvsem(query, limit=2)
    combined = results + trud

    if not combined:
        await wait_msg.edit_text(f"По запросу *{query}* вакансий не найдено. Попробуйте уточнить запрос.")
        await state.clear()
        return

    await wait_msg.edit_text(f"🎯 *Найдено вакансий по запросу '{query}' ({len(combined)} шт.):*", parse_mode="Markdown")

    for item in combined[:5]:
        item_id = str(uuid.uuid4())[:8]
        search_cache[item_id] = item
        card = (
            f"📌 *{item.title}*\n"
            f"🏢 *{item.company}* | {item.platform}\n"
            f"💰 Зарплата: *{item.salary}* | 📍 {item.location}\n"
            f"⏰ График: {item.schedule}\n"
            f"📝 _{item.snippet[:200]}_"
        )
        await message.answer(
            card,
            parse_mode="Markdown",
            reply_markup=get_job_item_action_keyboard(item_id, item.url),
            disable_web_page_preview=True
        )

    await state.clear()

@router.callback_query(F.data.startswith("act_cover:") | F.data.startswith("act_score:"))
async def on_action_from_search(callback: CallbackQuery):
    action, item_id = callback.data.split(":")
    item = search_cache.get(item_id)
    if not item:
        await callback.answer("Сессия вакансии устарела.", show_alert=True)
        return

    job_text = f"Вакансия: {item.title}\nКомпания: {item.company}\nОписание: {item.snippet}\nСсылка: {item.url}"

    await callback.answer("Обрабатываю вакансию...")
    status_msg = await safe_reply(callback.message, "⏳ Запускаю глубокий анализ и скоринг вакансии...")

    parsed = await job_agent.parser.parse(job_text, url=item.url)
    score = await job_agent.scorer.score(parsed)

    full_job_id = str(uuid.uuid4())[:8]
    vacancies_cache[full_job_id] = {
        "parsed": parsed,
        "score": score,
        "cover_letter": None,
        "app_id": None
    }

    if action == "act_cover":
        cover = await job_agent.cover_letter.generate(parsed)
        vacancies_cache[full_job_id]["cover_letter"] = cover.short_letter

        resp = (
            f"✉️ *Краткий отклик по формуле SuperJob Pro* ({len(cover.short_letter)} знаков)\n"
            f"🎯 Вакансия: *{parsed.title}* ({parsed.company})\n"
            f"🪝 *Hook:* _{cover.hook_phrase}_\n\n"
            f"```\n{cover.short_letter}\n```\n\n"
            f"💡 _Готово для отправки на {item.platform}!_"
        )
        await safe_edit_text(status_msg, resp, reply_markup=get_job_actions_keyboard(full_job_id))
    else:
        resp = (
            f"📊 *Скоринг соответствия: {score.total_score}/100 [{score.priority_tier}]*\n"
            f"📌 Вакансия: *{parsed.title}* ({parsed.company})\n\n"
            f"• Hard Skills: `{score.hard_skills_score}/40`\n"
            f"• Соответствие грейду: `{score.experience_grade_score}/25`\n"
            f"• СПО МТИ / ИС: `{score.education_domain_score}/15`\n"
            f"• Red Flags штрафы: `{score.red_flags_penalty} б.`\n\n"
            f"💡 *Стратегия:* _{score.application_strategy}_"
        )
        await safe_edit_text(status_msg, resp, reply_markup=get_job_actions_keyboard(full_job_id))

@router.message(F.text.in_({"🏢 Стажировки корпораций", "/internships"}))
@router.callback_query(F.data == "show_internships:all")
async def show_corporate_internships(event):
    message = event if isinstance(event, Message) else event.message
    catalog = job_agent.searcher.get_corporate_internships()

    lines = [
        "🏢 *Стажерские программы ведущих корпораций РФ*\n",
        "Программы, которые регулярно проводят отборы для студентов и выпускников СПО:\n"
    ]

    for item in catalog:
        clean_item_url = item["url"].split("?")[0]
        lines.append(
            f"🔹 *{item['company']}* — [{item['program_name']}]({clean_item_url})\n"
            f"🎯 Фокус: `{item['focus']}`\n"
            f"👥 Для кого: {item['target_audience']}\n"
            f"💡 _{item['notes']}_\n"
        )

    lines.append("⚡ _Переходите по ссылкам выше для подачи заявок в текущие наборы._")

    full_text = "\n".join(lines)
    if isinstance(event, CallbackQuery):
        await event.answer()
    await safe_answer(message, full_text, disable_web_page_preview=True)

@router.message(F.text.in_({"📄 Три готовых резюме", "📄 Два готовых резюме", "/resumes"}))
async def show_resumes_menu(message: Message):
    resumes = job_agent.searcher.get_three_resumes()
    r1 = resumes.get("resume_main_is", {})
    r2 = resumes.get("resume_backend_python", {})
    r3 = resumes.get("resume_frontend_fullstack", {})

    text = (
        "📄 *Три основных направления резюме Дмитрия Турейко:*\n\n"
        "═════════════════════════════════\n"
        f"1️⃣ *{r1.get('direction', 'Основное: Информационные системы / Junior Dev')}*\n"
        f"• Должность: `{r1.get('target_title')}`\n"
        f"• Куда: {r1.get('target_vacancies')}\n\n"
        "═════════════════════════════════\n"
        f"2️⃣ *{r2.get('direction', 'Вариант 1: Junior Backend / Python Developer')}*\n"
        f"• Должность: `{r2.get('target_title')}`\n"
        f"• Акцент: {r2.get('accent', 'Логика, данные, серверная часть, Python, Django, SQL, API')}\n"
        f"• Куда: {r2.get('target_vacancies')}\n\n"
        "═════════════════════════════════\n"
        f"3️⃣ *{r3.get('direction', 'Вариант 2: Junior Frontend / Fullstack Developer')}*\n"
        f"• Должность: `{r3.get('target_title')}`\n"
        f"• Акцент: {r3.get('accent', 'Интерфейсы, сайты, интерактивность, JavaScript, HTML, Tilda')}\n"
        f"• Куда: {r3.get('target_vacancies')}\n\n"
        "═════════════════════════════════\n"
        "💡 *Инструкция бота по адаптации:*\n"
        "Если вакансия отличается по названию — отправьте ссылку или текст вакансии в чат. Бот автоматически сформирует точечно **адаптированное резюме** и сопроводительное письмо!\n\n"
        "Нажмите кнопку ниже, чтобы открыть полный текст любого резюме или сравнительную таблицу 👇"
    )
    from bot.keyboards import get_resumes_inline_keyboard
    await message.answer(text, parse_mode="Markdown", reply_markup=get_resumes_inline_keyboard())

@router.callback_query(F.data.startswith("view_resume:"))
async def on_view_resume(callback: CallbackQuery):
    resume_key = callback.data.split(":")[1]
    if resume_key == "guidelines":
        guidelines_text = (
            "📊 *Рекомендации по выбору и использованию резюме:*\n\n"
            "| Направление | Основной акцент | Стек | Что показать |\n"
            "|---|---|---|---|\n"
            "| **Основное (ИС)** | Комплексный профиль ИС | SQL, БД, Python, Веб | СПО МТИ, БД, боты, интерфейсы |\n"
            "| **Backend / Python** | Логика, сервер, данные | Python, Django, SQL, API | Запросы БД, боты, API |\n"
            "| **Frontend / Fullstack** | Интерфейсы, сайты | JS, HTML, Tilda, Node.js | Страницы, интерактивность |\n\n"
            "📌 *Инструкция для откликов:*\n"
            "1. **Основное резюме** — для вакансий по информационным системам, специалиста по ИС, работы с БД и общего Junior Developer.\n"
            "2. **Вариант 1 (Backend/Python)** — для Junior Python Developer, стажёра-разработчика, Junior Backend Developer, сервисов и интеграций.\n"
            "3. **Вариант 2 (Frontend/Fullstack)** — для Junior Frontend Developer, веб-разработчика, верстки, сайтов и Fullstack.\n"
            "4. **Примеры проектов** для 2 и 3 резюме пока не заполняются (указываются учебные задачи и направления).\n"
            "5. Честно указывайте базовый уровень, без вымышленного опыта.\n"
            "6. **Если вакансия отличается по названию** — бот создаст адаптированное резюме автоматически!"
        )
        await safe_reply(callback.message, guidelines_text)
        await callback.answer()
        return

    full_text = job_agent.resume.render_base_resume(resume_key)
    resumes = job_agent.searcher.get_three_resumes()
    title = resumes.get(resume_key, {}).get("target_title", "Резюме")

    response_text = (
        f"📄 *Полный текст резюме:* `{title}`\n\n"
        f"```\n{full_text}\n```\n\n"
        f"💡 _Вы можете скопировать этот текст и сохранить в своем кабинете на hh.ru / SuperJob._"
    )
    await safe_reply(callback.message, response_text)
    await callback.answer()
