import uuid
import logging
import re
from datetime import datetime
from typing import Dict, Any

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from agent import (
    JobAgent,
    ParsedJob,
    JobScoreBreakdown,
    JobAnalysis,
    CoverLetter,
    JobApplication,
    ApplicationStatus
)
from storage import db, google_sheets
from bot.keyboards import get_job_actions_keyboard, get_copy_letter_keyboard, get_status_update_keyboard
from bot.utils import safe_edit_text, safe_answer, safe_reply

logger = logging.getLogger(__name__)
router = Router()
job_agent = JobAgent()

# Временное хранилище вакансий в сессии
vacancies_cache: Dict[str, Dict[str, Any]] = {}

@router.message(F.text & ~F.text.startswith("/"))
async def handle_vacancy_input(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return

    text = message.text.strip()
    is_url = bool(re.search(r"https?://[^\s]+", text))
    if len(text) < 25 and not is_url:
        await message.answer("⚠️ Текст вакансии слишком короткий. Отправьте ссылку на вакансию (hh.ru / SuperJob / Habr) или скопируйте её текст.")
        return

    wait_msg = await message.answer("🔎 Парсю вакансию и рассчитываю скоринг по методологии SuperJob Pro...")

    try:
        # 1. Глубокий парсинг вакансии
        parsed_job: ParsedJob = await job_agent.parser.parse(text)

        # 2. Экспертный скоринг по SuperJob Pro
        score_res: JobScoreBreakdown = await job_agent.scorer.score(parsed_job)

        job_id = str(uuid.uuid4())[:8]
        vacancies_cache[job_id] = {
            "parsed": parsed_job,
            "score": score_res,
            "cover_letter": None,
            "app_id": None
        }

        tier_emoji = {
            "HIGH": "🔥 Высокий приоритет (Идеальный матч)",
            "MEDIUM": "⚡ Средний приоритет (Хороший матч)",
            "LOW": "⚠️ Низкий приоритет (Риски / Завышенные требования)"
        }
        tier_label = tier_emoji.get(score_res.priority_tier, score_res.priority_tier)

        check_date = datetime.now().strftime("%d.%m.%Y")
        group_badge = {
            "A": "🟢 Группа A (Откликаться в первую очередь)",
            "B": "🟡 Группа B (Откликаться после проверки)",
            "C": "⚪ Группа C (Резерв)",
            "EXCLUDE": "🔴 ИСКЛЮЧИТЬ (Не соответствует жестким фильтрам)"
        }.get(score_res.relevance_group, f"Группа {score_res.relevance_group}")

        strict_alerts = []
        if score_res.has_phone_support_risk or score_res.phone_support_status == "Есть":
            strict_alerts.append("🚩 *ВНИМАНИЕ: Обнаружен риск работы на телефоне / звонков!*")
        if score_res.remote_status == "Не подходит" or not score_res.is_fully_remote:
            strict_alerts.append("⚠️ *Проверьте формат: возможно требуется офис/гибрид!*")
        if not score_res.is_junior_friendly:
            strict_alerts.append("⚠️ *Требования к опыту могут превышать уровень Junior*")

        alerts_block = ("\n" + "\n".join(strict_alerts) + "\n") if strict_alerts else ""

        salary_str = parsed_job.salary_raw or "Не указана"
        skills_str = ", ".join(parsed_job.key_skills[:6]) if parsed_job.key_skills else "В описании"
        clean_url = (parsed_job.url or "").split("?")[0]

        reply_text = (
            f"📋 *Карточка проверки вакансии (Раздел 11)*\n\n"
            f"📌 *Должность:* {parsed_job.title}\n"
            f"🏢 *Компания:* {parsed_job.company} | {parsed_job.platform}\n"
            f"{f'🔗 [Прямая ссылка на вакансию]({clean_url})' if clean_url else '🔗 Ссылка: не указана'}\n"
            f"📅 *Дата проверки:* `{check_date}`\n"
            f"🧭 *Направление:* `{score_res.recommended_vector.value}`\n"
            f"🏠 *Удалённость:* `{score_res.remote_status}`\n"
            f"🗺 *География:* `{score_res.geography_check}`\n"
            f"💰 *Зарплата:* *{salary_str}*\n"
            f"🎓 *Опыт:* `{parsed_job.grade}`\n"
            f"☎️ *Телефонная поддержка:* `{score_res.phone_support_status}`\n"
            f"{alerts_block}\n"
            f"📊 *Скоринг:* `{score_res.total_score}/100` | {tier_label}\n"
            f"🏷 *Соответствие:* {group_badge}\n"
            f"🛠 *Ключевые требования:* {skills_str}\n\n"
            f"💡 *Почему подходит:*\n_{score_res.why_fits or score_res.application_strategy}_\n\n"
            f"📚 *Что подтянуть:*\n_{score_res.what_to_improve or 'Критических пробелов нет'}_\n\n"
            f"🎯 *Следующее действие:* *{score_res.next_action}*\n\n"
            f"Выберите действие ниже 👇"
        )

        await safe_edit_text(
            wait_msg,
            reply_text,
            reply_markup=get_job_actions_keyboard(job_id),
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Ошибка обработки вакансии: {e}", exc_info=True)
        await safe_edit_text(
            wait_msg,
            f"❌ Ошибка обработки вакансии: {e}\n\n"
            f"Попробуйте отправить текст вакансии или проверьте настройки API ключей."
        )

@router.callback_query(F.data.startswith("show_scoring:"))
async def on_show_scoring(callback: CallbackQuery):
    job_id = callback.data.split(":")[1]
    item = vacancies_cache.get(job_id)
    if not item:
        await callback.answer("Сессия вакансии устарела.", show_alert=True)
        return

    score: JobScoreBreakdown = item["score"]

    pros_str = "\n".join([f"  ✅ {p}" for p in score.pros]) or "  • Не выделены"
    cons_str = "\n".join([f"  ⚠️ {c}" for c in score.cons_and_risks]) or "  • Критических рисков не выявлено"
    gaps_str = "\n".join([f"  ▹ {g}" for g in score.missing_gaps]) or "  • Пробелов в ключевом стеке нет"

    detail_text = (
        f"🔍 *Детальный скоринг вакансии (SuperJob Pro)*\n\n"
        f"📈 *Баллы по шкалам:*\n"
        f"• Hard Skills: `{score.hard_skills_score}/40`\n"
        f"• Соответствие грейду: `{score.experience_grade_score}/25`\n"
        f"• Образование (СПО МТИ / ИС): `{score.education_domain_score}/15`\n"
        f"• Условия и прозрачность: `{score.conditions_score}/10`\n"
        f"• Штрафы за Red Flags: `{score.red_flags_penalty} б.`\n"
        f"════════════════════\n"
        f"🏆 *Итоговый балл:* `{score.total_score}/100` ({score.priority_tier})\n\n"
        f"👍 *Плюсы вакансии:*\n{pros_str}\n\n"
        f"🚩 *Риски и Red Flags работодателя:*\n{cons_str}\n\n"
        f"📚 *Пробелы стека кандидата:*\n{gaps_str}\n\n"
        f"🎯 *Экспертная рекомендация:*\n_{score.application_strategy}_"
    )

    await safe_reply(callback.message, detail_text)
    await callback.answer()

@router.callback_query(F.data.startswith("gen_cover_short:") | F.data.startswith("gen_cover_det:"))
async def on_generate_cover_mode(callback: CallbackQuery):
    action, job_id = callback.data.split(":")
    is_short = action == "gen_cover_short"

    item = vacancies_cache.get(job_id)
    if not item:
        await callback.answer("Сессия вакансии устарела.", show_alert=True)
        return

    await callback.answer("Генерирую отклик по формуле SuperJob Pro...")
    status_msg = await safe_reply(
        callback.message,
        "✍️ " + ("Формирую краткий отклик для чата..." if is_short else "Составляю развернутое письмо для HR...")
    )

    parsed_job: ParsedJob = item["parsed"]
    try:
        cover: CoverLetter = await job_agent.cover_letter.generate(parsed_job)
        item["cover_letter"] = cover.short_letter if is_short else cover.detailed_letter
    except Exception as e:
        logger.error(f"Ошибка генерации письма: {e}")
        await safe_edit_text(status_msg, f"❌ Ошибка генерации: {e}")
        return

    text_to_show = cover.short_letter if is_short else cover.detailed_letter
    char_count = len(text_to_show)
    format_title = "⚡ Краткий отклик для чата" if is_short else "✉️ Развернутое письмо для рекрутера"

    response = (
        f"*{format_title}* ({char_count} знаков)\n"
        f"🎯 *Вакансия:* {parsed_job.title} ({parsed_job.company})\n"
        f"🪝 *Hook (зацепка):* _{cover.hook_phrase}_\n"
        f"📂 *Использованные пруфы:* `{', '.join(cover.highlighted_projects)}`\n\n"
        f"```\n{text_to_show}\n```\n\n"
        f"💡 _Текст подготовлен по правилу первых 2 строк SuperJob Pro без шаблонных клише._"
    )

    await safe_edit_text(
        status_msg,
        response,
        reply_markup=get_copy_letter_keyboard(job_id)
    )

@router.callback_query(F.data.startswith("gen_resume:"))
async def on_tailor_resume(callback: CallbackQuery):
    job_id = callback.data.split(":")[1]
    item = vacancies_cache.get(job_id)
    if not item:
        await callback.answer("Сессия вакансии устарела.", show_alert=True)
        return

    await callback.answer("Адаптирую резюме под вакансию...")
    status_msg = await safe_reply(callback.message, "📄 Подбираю акценты и навыки для резюме...")

    parsed: ParsedJob = item["parsed"]
    analysis = JobAnalysis(
        title=parsed.title,
        company=parsed.company,
        platform=parsed.platform,
        url=parsed.url,
        key_technologies=parsed.key_skills,
        key_requirements=parsed.requirements_hard,
        recommended_vector=item["score"].recommended_vector
    )

    try:
        tailored = await job_agent.resume.tailor(analysis)
        item["tailored_resume"] = tailored
    except Exception as e:
        logger.error(f"Ошибка адаптации резюме: {e}")
        await safe_edit_text(status_msg, f"❌ Ошибка адаптации резюме: {e}")
        return

    skills_text = ", ".join(tailored.priority_skills)
    highlights_text = "\n".join([f"• *{p.get('project')}*: {p.get('focus')}" for p in tailored.project_highlights])

    from bot.keyboards import get_tailored_resume_actions_keyboard
    response = (
        f"📄 *Адаптация резюме под вакансию*\n"
        f"🎯 *Базовый вектор:* {tailored.vector_name}\n"
        f"🏷 *Адаптированный заголовок:* `{tailored.tailored_title}`\n\n"
        f"📝 *Блок «О себе» (Summary):*\n"
        f"> {tailored.tailored_summary}\n\n"
        f"⭐ *Приоритетные навыки (вынести наверх):*\n"
        f"`{skills_text}`\n\n"
        f"🚀 *Акценты в опыте / задачах:*\n"
        f"{highlights_text}\n\n"
        f"💡 _Нажмите «📋 Полный текст для hh.ru», чтобы получить готовое резюме целиком!_"
    )

    await safe_edit_text(status_msg, response, reply_markup=get_tailored_resume_actions_keyboard(job_id))

@router.callback_query(F.data.startswith("show_full_resume:"))
async def on_show_full_resume(callback: CallbackQuery):
    job_id = callback.data.split(":")[1]
    item = vacancies_cache.get(job_id)
    if not item or not item.get("tailored_resume"):
        await callback.answer("Данные резюме устарели. Нажмите 'Адаптировать резюме' снова.", show_alert=True)
        return

    tailored = item["tailored_resume"]
    text = (
        f"📋 *Готовое адаптированное резюме для отклика:*\n\n"
        f"```\n{tailored.full_resume_text}\n```\n\n"
        f"💡 _Скопируйте текст выше и обновите свое резюме на hh.ru / SuperJob перед отправкой отклика._"
    )
    await safe_reply(callback.message, text)
    await callback.answer()

@router.callback_query(F.data.startswith("save_crm:"))
async def on_save_to_crm(callback: CallbackQuery):
    job_id = callback.data.split(":")[1]
    item = vacancies_cache.get(job_id)
    if not item:
        await callback.answer("Сессия вакансии устарела.", show_alert=True)
        return

    parsed: ParsedJob = item["parsed"]
    score: JobScoreBreakdown = item["score"]
    cover_letter = item.get("cover_letter") or ""

    if item.get("app_id"):
        await callback.answer("Этот отклик уже сохранен в CRM!", show_alert=True)
        return

    check_date = datetime.now().strftime("%Y-%m-%d")
    app_status = ApplicationStatus.SENT if cover_letter else ApplicationStatus.NEW

    app = JobApplication(
        checked_at=check_date,
        published_at=None,
        platform=parsed.platform,
        company=parsed.company,
        job_title=parsed.title,
        job_url=parsed.url or "",
        vector=score.recommended_vector,
        cover_letter=cover_letter,
        status=app_status,
        score=score.total_score,
        relevance_group=score.relevance_group,
        remote_status=score.remote_status,
        geography=score.geography_check,
        salary_info=parsed.salary_raw or "Не указана",
        experience_level=parsed.grade,
        phone_support_status=score.phone_support_status,
        why_fits=score.why_fits or score.application_strategy,
        gaps=score.what_to_improve,
        next_action=score.next_action,
        full_job_text=parsed.raw_text
    )

    app_id = await db.add_application(app)
    app.id = app_id
    item["app_id"] = app_id

    sheets_status = "не подключена"
    if google_sheets.is_configured():
        synced = await google_sheets.append_application(app)
        sheets_status = "✅ синхронизировано" if synced else "⚠️ ошибка синхронизации"

    await callback.answer("Вакансия успешно сохранена в реестр!")
    await safe_reply(
        callback.message,
        f"✅ *Вакансия #{app_id} сохранена в отдельный реестр!*\n\n"
        f"🏢 *{app.company}* — {app.job_title}\n"
        f"📅 Проверена агентом: `{check_date}`\n"
        f"🏷 Группа соответствия: `{app.relevance_group}`\n"
        f"🏠 Формат: `{app.remote_status}` | ☎️ Звонки: `{app.phone_support_status}`\n"
        f"📊 Скоринг: `{score.total_score}/100` ({score.priority_tier})\n"
        f"📈 Статус отклика: `{app.status.value}`\n"
        f"📑 Google Таблица: {sheets_status}\n\n"
        f"База знаний остаётся чистой и постоянной, а статус и дата проверки вакансии отслеживаются в CRM 👇",
        reply_markup=get_status_update_keyboard(app_id)
    )
