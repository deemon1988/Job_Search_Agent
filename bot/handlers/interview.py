import logging
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from agent import JobAgent, ParsedJob, InterviewPrep, InterviewDebrief
from bot.handlers.vacancies import vacancies_cache
from config import settings
from agent.prompts import load_profile_context
from bot.utils import safe_edit_text, safe_answer, safe_reply

logger = logging.getLogger(__name__)
router = Router()
job_agent = JobAgent()

class DebriefStates(StatesGroup):
    waiting_for_interview_notes = State()

@router.callback_query(F.data.startswith("prep_interview:"))
async def on_prep_interview(callback: CallbackQuery):
    job_id = callback.data.split(":")[1]
    item = vacancies_cache.get(job_id)
    if not item:
        await callback.answer("Сессия вакансии устарела.", show_alert=True)
        return

    await callback.answer("Готовлю программу интервью по стандартам SuperJob Pro...")
    status_msg = await callback.message.reply(
        "🎯 Формирую 3 блока подготовки:\n"
        "1. 10 вопросов технического скрининга\n"
        "2. Поведенческие вопросы по STAR-модели\n"
        "3. Вопросы работодателю для повышения конверсии..."
    )

    parsed_job: ParsedJob = item["parsed"]
    try:
        prep: InterviewPrep = await job_agent.interview.generate_prep_questions(parsed_job)
    except Exception as e:
        logger.error(f"Ошибка генерации подготовки к интервью: {e}")
        await status_msg.edit_text(f"❌ Ошибка генерации: {e}")
        return

    # Часть 1: Технический скрининг
    tech_parts = [
        f"🎯 *Подготовка к собеседованию: {parsed_job.title}* ({parsed_job.company})\n",
        f"💡 _{prep.role_summary}_\n",
        "═════════════════════════════════",
        "🛠 *БЛОК 1: Технический скрининг (10 вопросов)*\n"
    ]
    for q in prep.technical_questions:
        points = "\n".join([f"    ▹ {pt}" for pt in q.key_points])
        tech_parts.append(f"*{q.number}. [{q.topic}]* {q.question}\n{points}\n")

    # Часть 2: STAR Поведенческие вопросы
    star_parts = [
        "═════════════════════════════════",
        "🌟 *БЛОК 2: HR и Поведенческие вопросы (STAR-модель)*\n"
    ]
    for idx, s in enumerate(prep.behavioral_star_questions, 1):
        star_parts.append(
            f"*{idx}. ❓ {s.question}*\n"
            f"• *S (Ситуация):* {s.situation_context}\n"
            f"• *T (Задача):* {s.task_description}\n"
            f"• *A (Действие):* {s.action_taken}\n"
            f"• *R (Результат):* {s.result_metric}\n"
            f"💡 _Совет SuperJob Pro: {s.expert_tip}_\n"
        )

    # Часть 3: Вопросы работодателю
    employer_questions_parts = [
        "═════════════════════════════════",
        "🤝 *БЛОК 3: Умные вопросы кандидату к работодателю*\n"
    ]
    for eq in prep.questions_for_employer:
        employer_questions_parts.append(f"• _{eq}_")

    full_text_1 = "\n".join(tech_parts)
    full_text_2 = "\n".join(star_parts + employer_questions_parts)

    await safe_edit_text(status_msg, full_text_1[:4000])
    await safe_answer(callback.message, full_text_2[:4000])

@router.message(F.text.in_({"📚 Методология SuperJob Pro"}))
async def show_superjob_pro_tips(message: Message):
    text = (
        "📚 *Экспертные стандарты SuperJob Pro для соискателя:*\n\n"
        "⏱ *Правило первых 5–10 секунд:*\n"
        "Рекрутер не вчитывается в текст, а сканирует отклик по маркерам. Первые 2 строки должны содержать точное соответствие роли и живой проект в продакшене.\n\n"
        "🚫 *Главные Red Flags кандидатов:*\n"
        "• Шаблоны «Добрый день, рассмотрите мое резюме...»\n"
        "• Пустые клише: «стрессоустойчив», «быстрообучаем», «коммуникабелен»\n"
        "• Описание опыта без оцифрованных результатов\n\n"
        "🌟 *Золотой стандарт ответов STAR:*\n"
        "• **S (Situation)** — контекст и проблема\n"
        "• **T (Task)** — что конкретно требовалось сделать\n"
        "• **A (Action)** — конкретные действия, код и инструменты\n"
        "• **R (Result)** — измеримый результат (работающий сайт, оптимизация)\n\n"
        "💡 _Агент автоматически применяет эти правила при каждом отклике и подготовке._"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text.in_({"🔄 Разбор собеседования", "/debrief"}))
async def start_debrief(message: Message, state: FSMContext):
    await state.set_state(DebriefStates.waiting_for_interview_notes)
    await message.answer(
        "🎙 *Режим разбора собеседования (Interview Debrief)*\n\n"
        "Отправьте список вопросов или тем, на которых вы запнулись, ответили неуверенно или которые вызвали сомнения.\n"
        "Можно прислать текст в свободной форме (например: *'Спросили про уровни изоляции в Postgres и как работает event loop в asyncio'*).\n\n"
        "Я дам четкие эталонные ответы и составлю микро-план ликвидации пробела за 30 минут 🚀",
        parse_mode="Markdown"
    )

@router.message(DebriefStates.waiting_for_interview_notes)
async def process_debrief(message: Message, state: FSMContext):
    notes = message.text.strip()
    status_msg = await message.answer("🧠 Анализирую вопросы и готовлю эталонные ответы...")

    try:
        debrief: InterviewDebrief = await job_agent.interview.debrief_interview(notes)
    except Exception as e:
        logger.error(f"Ошибка дебрифинга: {e}")
        await status_msg.edit_text(f"❌ Ошибка разбора: {e}")
        await state.clear()
        return

    parts = [
        "🏆 *Разбор собеседования:*\n",
        f"💪 *Сильные стороны:* {debrief.strengths_observed}\n",
        "─────────────────────\n"
    ]

    for idx, item in enumerate(debrief.gap_analysis, 1):
        parts.append(
            f"❓ *Вопрос {idx}: {item.question}*\n\n"
            f"✅ *Эталонный ответ:*\n{item.ideal_answer}\n\n"
            f"📚 *Микро-план (ликвидация за 30 мин):*\n_{item.quick_plan}_\n"
            "─────────────────────\n"
        )

    parts.append(f"🎯 *Рекомендации:* {debrief.overall_recommendations}")

    full_text = "\n".join(parts)
    if len(full_text) > 4000:
        chunk1 = full_text[:3800]
        chunk2 = full_text[3800:]
        await safe_edit_text(status_msg, chunk1)
        await safe_answer(message, chunk2)
    else:
        await safe_edit_text(status_msg, full_text)

    await state.clear()

@router.message(F.text.in_({"👤 Мой профиль", "/profile"}))
async def show_profile(message: Message):
    profile = load_profile_context(settings.PROFILE_CONTEXT_PATH)
    personal = profile.get("personal", {})
    edu = personal.get("education", {})

    lines = [
        "👤 *Верифицированный профиль кандидата:*\n",
        f"🎓 *Образование:* {edu.get('degree_type')} {edu.get('institution')}",
        f"📚 *Специальность:* {edu.get('specialty')}",
        f"🌐 *Сайт в проде:* [gorizont-blog.ru](https://gorizont-blog.ru)\n",
        "📂 *Ключевые проекты:*",
        "1. `gorizont-blog.ru` — боевой Django + PostgreSQL на Ubuntu (Nginx, systemd, SSL)",
        "2. `AI Blog Generator` — оркестрация субагентов, мультипостинг TG/Дзен/VK",
        "3. `clinic_connect` — Node.js/Express + сложные транзакции/индексы PostgreSQL",
        "4. `Telegram-боты` — асинхронные боты на aiogram с LLM интеграцией\n",
        "🎯 *Векторы позиционирования:*",
        "• *Вектор А:* Junior Python / Django Developer",
        "• *Вектор Б:* AI-интеграции / Боты / Автоматизация",
        "• *Вектор В:* DevOps / Стажер инфраструктуры / Системный инженер\n",
        "💡 _Факты берутся строго из data/profile_context.json без галлюцинаций._"
    ]
    await message.answer("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)

@router.message(F.text.in_({"ℹ️ Помощь", "/help", "/start"}))
async def show_help(message: Message):
    text = (
        "👋 *Привет! Я ваш AI-агент для поиска работы и подготовки откликов.*\n"
        "База знаний построена на экспертных методиках портала [SuperJob Pro](https://www.superjob.ru/pro/).\n\n"
        "🚀 *Что умеет агент:*\n"
        "1. **Глубокий парсинг вакансий**: отправьте ссылку (hh.ru, SuperJob, Habr) или вставьте текст.\n"
        "2. **Продвинутый скоринг (0-100)**: оценка соответствия стека, грейда, условий и выявление Red Flags работодателя.\n"
        "3. **Генерация откликов под вакансию**:\n"
        "   • ⚡ *Краткий отклик* (для формы hh.ru / SuperJob с правилом первых 2 строк).\n"
        "   • ✉️ *Развернутое письмо* (для прямого контакта с HR/тимлидом).\n"
        "4. **Подготовка к интервью в 3 блока**:\n"
        "   • 10 технических вопросов скрининга\n"
        "   • Ответы на HR-вопросы по формуле STAR (самопрезентация, сложная задача, зарплата)\n"
        "   • Умные вопросы работодателю\n"
        "5. **Ведение воронки CRM**: сохранение статусов отклика и дедлайнов тестовых заданий."
    )
    from bot.keyboards import get_main_menu_keyboard
    await message.answer(text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard(), disable_web_page_preview=True)
