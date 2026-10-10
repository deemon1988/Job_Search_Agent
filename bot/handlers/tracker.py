import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from agent.models import ApplicationStatus
from storage import db
from bot.keyboards import get_status_update_keyboard

logger = logging.getLogger(__name__)
router = Router()

class TrackerStates(StatesGroup):
    waiting_for_deadline = State()
    waiting_for_note = State()

@router.message(F.text.in_({"📊 Воронка откликов", "/stats"}))
async def show_funnel_stats(message: Message):
    stats = await db.get_funnel_stats()

    lines = [
        "📊 *Текущая воронка откликов:*\n",
        f"• 📤 Отправлено: `{stats.get('Отправлено', 0)}`",
        f"• 👁 Просмотрено: `{stats.get('Просмотрено', 0)}`",
        f"• 📞 Скрининг: `{stats.get('Скрининг', 0)}`",
        f"• ⏳ Тестовое задание: `{stats.get('Тестовое задание', 0)}`",
        f"• 🎙 Собеседование: `{stats.get('Собеседование', 0)}`",
        f"• 🎉 Оффер: `{stats.get('Оффер', 0)}`",
        f"• ❌ Отказ: `{stats.get('Отказ', 0)}`",
        f"\n📈 *Всего в базе:* `{stats.get('Всего откликов', 0)}` откликов"
    ]

    await message.answer("\n".join(lines), parse_mode="Markdown")

@router.message(F.text.in_({"📋 Последние отклики", "/recent"}))
async def show_recent_applications(message: Message):
    apps = await db.list_applications(limit=10)
    if not apps:
        await message.answer("В вашей базе CRM пока нет откликов. Отправьте текст первой вакансии, чтобы начать!")
        return

    for app in apps:
        dt_str = app.created_at.strftime("%d.%m.%Y")
        check_str = f" | 📅 Проверена: `{app.checked_at}`" if app.checked_at else ""
        grp_str = f" | 🏷 Группа `{app.relevance_group}`" if app.relevance_group else ""
        dl_info = f"\n⏰ Дедлайн ТЗ: *{app.test_deadline}*" if app.test_deadline else ""
        notes_info = f"\n📝 Заметка: _{app.notes}_" if app.notes else ""

        text = (
            f"📌 *Отклик #{app.id}* ({dt_str}{check_str}{grp_str})\n"
            f"🏢 *{app.company}* — {app.job_title}\n"
            f"📍 Платформа: {app.platform}\n"
            f"📊 Статус: `{app.status.value}`"
            f"{dl_info}{notes_info}"
        )
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=get_status_update_keyboard(app.id)
        )

@router.callback_query(F.data.startswith("set_st:"))
async def on_change_status(callback: CallbackQuery):
    parts = callback.data.split(":")
    app_id = int(parts[1])
    code = parts[2]

    mapping = {
        "viewed": ApplicationStatus.VIEWED,
        "screening": ApplicationStatus.SCREENING,
        "test": ApplicationStatus.TEST_TASK,
        "interview": ApplicationStatus.INTERVIEW,
        "offer": ApplicationStatus.OFFER,
        "reject": ApplicationStatus.REJECTED
    }
    new_status = mapping.get(code, ApplicationStatus.SENT)

    success = await db.update_status(app_id, new_status)
    if success:
        await callback.answer(f"Статус изменен на: {new_status.value}")
        app = await db.get_application(app_id)
        if app:
            await callback.message.edit_text(
                f"✅ *Отклик #{app.id} обновлен!*\n\n"
                f"🏢 *{app.company}* — {app.job_title}\n"
                f"📍 Платформа: {app.platform}\n"
                f"📊 Новый статус: *{app.status.value}*\n"
                f"{f'⏰ Дедлайн ТЗ: {app.test_deadline}' if app.test_deadline else ''}\n"
                f"{f'📝 Заметка: {app.notes}' if app.notes else ''}",
                parse_mode="Markdown",
                reply_markup=get_status_update_keyboard(app.id)
            )
    else:
        await callback.answer("Ошибка при обновлении статуса.", show_alert=True)

@router.callback_query(F.data.startswith("set_dl:"))
async def on_request_deadline(callback: CallbackQuery, state: FSMContext):
    app_id = int(callback.data.split(":")[1])
    await state.set_state(TrackerStates.waiting_for_deadline)
    await state.update_data(app_id=app_id)

    await callback.answer()
    await callback.message.reply(
        f"📅 Отправьте дату и время дедлайна тестового задания для отклика #{app_id}\n"
        f"Например: `12.10.2026 до 18:00` или `в четверг вечером`",
        parse_mode="Markdown"
    )

@router.message(TrackerStates.waiting_for_deadline)
async def on_receive_deadline(message: Message, state: FSMContext):
    data = await state.get_data()
    app_id = data.get("app_id")
    deadline_text = message.text.strip()

    if app_id:
        await db.update_deadline(app_id, deadline_text)
        await message.answer(f"✅ Дедлайн для отклика #{app_id} сохранен: *{deadline_text}*", parse_mode="Markdown")

    await state.clear()

@router.callback_query(F.data.startswith("set_note:"))
async def on_request_note(callback: CallbackQuery, state: FSMContext):
    app_id = int(callback.data.split(":")[1])
    await state.set_state(TrackerStates.waiting_for_note)
    await state.update_data(app_id=app_id)

    await callback.answer()
    await callback.message.reply(
        f"📝 Отправьте текст заметки для отклика #{app_id} (контакт HR, ссылка на созвон, особенности):"
    )

@router.message(TrackerStates.waiting_for_note)
async def on_receive_note(message: Message, state: FSMContext):
    data = await state.get_data()
    app_id = data.get("app_id")
    note_text = message.text.strip()

    if app_id:
        await db.update_notes(app_id, note_text)
        await message.answer(f"✅ Заметка для отклика #{app_id} сохранена: _{note_text}_", parse_mode="Markdown")

    await state.clear()
