import asyncio
import logging
import sys

from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, Update

from config import settings
from storage import db
from bot.handlers import (
    vacancies_router,
    tracker_router,
    interview_router,
    search_router,
    plan_router,
    portfolio_router
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

class WhitelistMiddleware(BaseMiddleware):
    def __init__(self, allowed_user_ids: list[int]):
        super().__init__()
        self.allowed_user_ids = set(allowed_user_ids)

    async def __call__(self, handler, event: Update, data: dict):
        if not self.allowed_user_ids:
            # Если список пуст, разрешаем доступ всем
            return await handler(event, data)

        user = getattr(event, "from_user", None)
        if user and user.id not in self.allowed_user_ids:
            if isinstance(event, Message):
                await event.answer("⛔ Доступ ограничен. Ваш ID отсутствует в ALLOWED_USER_IDS.")
            return

        return await handler(event, data)

async def main():
    if not settings.BOT_TOKEN:
        logger.error(
            "\n" + "=" * 60 + "\n"
            "❌ ОШИБКА: BOT_TOKEN не указан в файле .env!\n"
            "1. Скопируйте .env.example в .env\n"
            "2. Получите токен у @BotFather в Telegram\n"
            "3. Укажите BOT_TOKEN=ваш_токен в .env\n"
            + "=" * 60
        )
        sys.exit(1)

    logger.info("Инициализация базы данных SQLite...")
    await db.init_db()

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware авторизации
    allowed_ids = settings.get_allowed_users()
    if allowed_ids:
        logger.info(f"Включен белый список пользователей: {allowed_ids}")
        dp.update.middleware(WhitelistMiddleware(allowed_ids))

    # Регистрация роутеров
    dp.include_router(plan_router)
    dp.include_router(portfolio_router)
    dp.include_router(search_router)
    dp.include_router(interview_router)
    dp.include_router(tracker_router)
    dp.include_router(vacancies_router)

    logger.info("AI-Агент успешно запущен и ожидает сообщений в Telegram...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
