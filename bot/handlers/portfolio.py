import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from agent import JobAgent
from bot.keyboards import get_portfolio_hub_keyboard, get_project_actions_keyboard
from bot.utils import safe_answer, safe_reply, safe_edit_text

logger = logging.getLogger(__name__)
router = Router()
job_agent = JobAgent()

@router.message(F.text.in_({"🚀 Проекты для портфолио", "/portfolio"}))
@router.callback_query(F.data == "back_to_projects:list")
async def show_portfolio_hub(event):
    message = event if isinstance(event, Message) else event.message
    projects = job_agent.portfolio.list_projects()

    text = (
        "🚀 *Хаб проектов для портфолио и GitHub*\n\n"
        "Работодателям важны не «идеально выученный синтаксис», а:\n"
        "• Реально запущенный и работающий проект на GitHub\n"
        "• Понимание архитектуры и движения данных (Data Flow)\n"
        "• Умение тестировать негативные сценарии (ошибки API, битый JSON, дубли)\n"
        "• Способность разобрать чужой код и логи с помощью AI\n\n"
        "🎯 *Выберите проект для детального плана и генерации архитектуры:*"
    )
    if isinstance(event, CallbackQuery):
        await event.answer()
        await safe_edit_text(message, text, reply_markup=get_portfolio_hub_keyboard())
    else:
        await message.answer(text, parse_mode="Markdown", reply_markup=get_portfolio_hub_keyboard())

@router.callback_query(F.data.startswith("view_proj:"))
async def on_view_project(callback: CallbackQuery):
    proj_id = callback.data.split(":")[1]
    proj = job_agent.portfolio.get_project(proj_id)
    if not proj:
        await callback.answer("Проект не найден.", show_alert=True)
        return

    features_str = "\n".join([f"  • {f}" for f in proj.get("key_features", [])])
    stack_str = ", ".join(proj.get("stack", []))

    text = (
        f"🚀 *Проект: {proj['name']}*\n"
        f"🏷 Роль в портфолио: *{proj.get('role', 'Флагман')}*\n\n"
        f"📝 *Описание:* {proj['short_description']}\n\n"
        f"🛠 *Технологический стек:*\n`{stack_str}`\n\n"
        f"✨ *Ключевой функционал:*\n{features_str}\n\n"
        f"💡 *Секрет на собеседовании:*\n_{proj.get('interview_hook', '')}_\n\n"
        f"Выберите генерацию документации или плана ниже 👇"
    )
    await safe_reply(callback.message, text, reply_markup=get_project_actions_keyboard(proj_id))
    await callback.answer()

@router.callback_query(F.data.startswith("gen_proj_arch:"))
async def on_gen_project_architecture(callback: CallbackQuery):
    proj_id = callback.data.split(":")[1]
    proj = job_agent.portfolio.get_project(proj_id)
    if not proj:
        await callback.answer("Проект не найден.", show_alert=True)
        return

    await callback.answer("Проектирую архитектуру с помощью AI...")
    wait_msg = await safe_reply(callback.message, f"⚡ Проектирую архитектуру и Data Flow для *{proj['name']}*...")

    try:
        arch_blueprint = await job_agent.portfolio.generate_project_blueprint(proj_id, "architecture")
        await safe_edit_text(
            wait_msg,
            f"🏛 *Архитектура и схема данных: {proj['name']}*\n\n{arch_blueprint}",
            reply_markup=get_project_actions_keyboard(proj_id)
        )
    except Exception as e:
        logger.error(f"Ошибка генерации архитектуры: {e}")
        await safe_edit_text(wait_msg, f"❌ Ошибка генерации архитектуры: {e}")

@router.callback_query(F.data.startswith("gen_proj_plan:"))
async def on_gen_project_plan(callback: CallbackQuery):
    proj_id = callback.data.split(":")[1]
    proj = job_agent.portfolio.get_project(proj_id)
    if not proj:
        await callback.answer("Проект не найден.", show_alert=True)
        return

    await callback.answer("Составляю пошаговый 7-дневный план...")
    wait_msg = await safe_reply(callback.message, f"🗓 Составляю спринт-план запуска для *{proj['name']}*...")

    try:
        plan_blueprint = await job_agent.portfolio.generate_project_blueprint(proj_id, "plan")
        await safe_edit_text(
            wait_msg,
            f"🗓 *7-дневный план реализации: {proj['name']}*\n\n{plan_blueprint}",
            reply_markup=get_project_actions_keyboard(proj_id)
        )
    except Exception as e:
        logger.error(f"Ошибка генерации плана: {e}")
        await safe_edit_text(wait_msg, f"❌ Ошибка генерации плана: {e}")

@router.callback_query(F.data.startswith("gen_proj_tests:"))
async def on_gen_project_tests(callback: CallbackQuery):
    proj_id = callback.data.split(":")[1]
    proj = job_agent.portfolio.get_project(proj_id)
    if not proj:
        await callback.answer("Проект не найден.", show_alert=True)
        return

    await callback.answer("Формирую негативные тест-кейсы...")
    wait_msg = await safe_reply(callback.message, f"🧪 Формирую список критических тестов для *{proj['name']}*...")

    try:
        test_blueprint = await job_agent.portfolio.generate_project_blueprint(proj_id, "tests")
        await safe_edit_text(
            wait_msg,
            f"🧪 *Тест-кейсы и негативные сценарии: {proj['name']}*\n\n{test_blueprint}",
            reply_markup=get_project_actions_keyboard(proj_id)
        )
    except Exception as e:
        logger.error(f"Ошибка генерации тестов: {e}")
        await safe_edit_text(wait_msg, f"❌ Ошибка генерации тестов: {e}")

@router.callback_query(F.data.startswith("gen_proj_readme:"))
async def on_gen_project_readme(callback: CallbackQuery):
    proj_id = callback.data.split(":")[1]
    proj = job_agent.portfolio.get_project(proj_id)
    if not proj:
        await callback.answer("Проект не найден.", show_alert=True)
        return

    await callback.answer("Создаю README.md шаблон...")
    wait_msg = await safe_reply(callback.message, f"📄 Генерирую образцовый README.md для *{proj['name']}*...")

    try:
        readme_blueprint = await job_agent.portfolio.generate_project_blueprint(proj_id, "readme")
        await safe_edit_text(
            wait_msg,
            f"📄 *Шаблон README.md для GitHub: {proj['name']}*\n\n{readme_blueprint}",
            reply_markup=get_project_actions_keyboard(proj_id)
        )
    except Exception as e:
        logger.error(f"Ошибка генерации README: {e}")
        await safe_edit_text(wait_msg, f"❌ Ошибка генерации README: {e}")

@router.callback_query(F.data == "view_proj_philosophy:show")
async def on_view_proj_philosophy(callback: CallbackQuery):
    text = (
        "📖 *Как правильно говорить про AI в проектах на собеседовании:*\n\n"
        "1. **AI — не замена программиста, а множитель продуктивности:**\n"
        "«Я использовал AI для ускорения написания каркаса, генерации фикстур данных и поиска краевых случаев».\n\n"
        "2. **Контроль и инженерная ответственность:**\n"
        "«Код, сгенерированный ИИ, я обязательно тестирую: проверяю негативные сценарии (битый JSON, падение внешнего API, дубли), смотрю в логи и рефакторю под безопасность».\n\n"
        "3. **Архитектурное мышление:**\n"
        "«Я понимаю движение данных от вебхука до таблицы БД, понимаю транзакции и почему нужен retry-механизм».\n\n"
        "4. **Git и версионирование:**\n"
        "«Все коммиты структурированы, зависимости в requirements.txt/poetry, проект разворачивается по инструкции в README за 5 минут»."
    )
    await safe_reply(callback.message, text)
    await callback.answer()
