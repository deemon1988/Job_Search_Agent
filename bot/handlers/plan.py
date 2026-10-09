import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from agent import JobAgent
from bot.keyboards import get_action_plan_keyboard
from bot.utils import safe_answer, safe_reply

logger = logging.getLogger(__name__)
router = Router()
job_agent = JobAgent()

@router.message(F.text.in_({"📅 План на 30 дней", "/plan"}))
async def show_plan_overview(message: Message):
    overview = job_agent.plan.get_plan_overview()
    routine = job_agent.plan.get_daily_routine()

    text = (
        f"📅 *{overview['title']}*\n"
        f"🎯 *Цель:* _{overview['target_goal']}_\n"
        f"📊 *Плановый объем откликов:* `{overview['total_applications_target']}`\n\n"
        f"⏱ *Ежедневный фокус ({routine['daily_hours']}):*\n"
    )
    for block in routine["schedule"]:
        text += f"• *{block['duration']}* — {block['block']}: _{block['focus']}_\n"

    text += (
        "\n🚀 *Нажмите на неделю ниже, чтобы открыть подробный чек-лист и задачи:*"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=get_action_plan_keyboard())

@router.callback_query(F.data.startswith("view_week:"))
async def on_view_week_detail(callback: CallbackQuery):
    week_num = int(callback.data.split(":")[1])
    week_info = job_agent.plan.get_week(week_num)
    if not week_info:
        await callback.answer("Данные недели не найдены.", show_alert=True)
        return

    checklist_items = "\n".join([f"  ✅ {item}" for item in week_info.get("checklist", [])])

    text = (
        f"🗓 *Неделя {week_info['week_number']}: {week_info['theme']}*\n"
        f"🎯 *Главный фокус:* _{week_info['focus']}_\n"
        f"📈 *Норма откликов на неделю:* `{week_info['target_applications']}`\n\n"
        f"📋 *Чек-лист ключевых задач:*\n{checklist_items}\n\n"
        f"🏁 *Результат к концу недели:*\n💡 _{week_info['deliverable']}_"
    )
    await safe_reply(callback.message, text)
    await callback.answer()

@router.callback_query(F.data == "view_plan_routine:show")
async def on_view_plan_routine(callback: CallbackQuery):
    routine = job_agent.plan.get_daily_routine()
    tips = "\n".join([f"• {t}" for t in routine.get("principles", [])])

    text = (
        f"⏱ *{routine['title']} ({routine['daily_hours']})*\n\n"
        f"Расписание продуктивного дня для поиска работы:\n\n"
    )
    for b in routine["schedule"]:
        text += (
            f"🔹 *{b['block']}* (`{b['duration']}`)\n"
            f"   Задачи: {b['focus']}\n"
            f"   Результат: _{b['output']}_\n\n"
        )

    text += f"💡 *Ключевые принципы:*\n{tips}"
    await safe_reply(callback.message, text)
    await callback.answer()

@router.callback_query(F.data == "view_plan_rules:show")
async def on_view_plan_rules(callback: CallbackQuery):
    rules = job_agent.plan.get_strict_filter_rules()
    fl = rules.get("filters", {})

    text = (
        f"🎯 *{rules.get('title', 'Критерии отбора вакансий')}*\n\n"
        f"🚫 *1. Запрет на телефоны/звонки:*\n"
        f"   {fl.get('no_phone_calls', {}).get('rule')}\n"
        f"   _Исключение:_ {fl.get('no_phone_calls', {}).get('exception')}\n\n"
        f"🏡 *2. Удаленная работа:*\n"
        f"   {fl.get('remote_only', {}).get('rule')}\n"
        f"   _Локация:_ {fl.get('remote_only', {}).get('location')}\n\n"
        f"👶 *3. Уровень опыта:*\n"
        f"   {fl.get('experience_level', {}).get('rule')}\n\n"
        f"💰 *4. Зарплатный ориентир:*\n"
        f"   {fl.get('salary_range', {}).get('target')}\n\n"
        f"💡 *Философия AI:* {rules.get('ai_philosophy_summary', 'AI — основной ускоритель разработки.')}"
    )
    await safe_reply(callback.message, text)
    await callback.answer()
