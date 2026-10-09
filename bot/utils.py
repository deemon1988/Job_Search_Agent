import logging
import re
from typing import Optional, Any
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)

def clean_markdown_special_chars(text: str) -> str:
    """Удаляет ломающие разметку символы для безопасной отправки без форматирования"""
    # Удаляем маркеры форматирования markdown
    text = re.sub(r"[*_`]", "", text)
    # Заменяем markdown ссылки [text](url) на text (url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1: \2", text)
    return text

async def safe_edit_text(
    message: Message,
    text: str,
    reply_markup: Optional[Any] = None,
    disable_web_page_preview: bool = True
):
    """Безопасное редактирование сообщения с автоматическим fallback при ошибках Markdown"""
    try:
        return await message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview
        )
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e).lower() or "entity" in str(e).lower():
            logger.warning(f"Telegram Markdown parse error, retrying without formatting: {e}")
            clean_text = clean_markdown_special_chars(text)
            return await message.edit_text(
                clean_text,
                parse_mode=None,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview
            )
        raise

async def safe_answer(
    message: Message,
    text: str,
    reply_markup: Optional[Any] = None,
    disable_web_page_preview: bool = True
):
    """Безопасная отправка ответа с автоматическим fallback при ошибках Markdown"""
    try:
        return await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview
        )
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e).lower() or "entity" in str(e).lower():
            logger.warning(f"Telegram Markdown parse error, retrying without formatting: {e}")
            clean_text = clean_markdown_special_chars(text)
            return await message.answer(
                clean_text,
                parse_mode=None,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview
            )
        raise

async def safe_reply(
    message: Message,
    text: str,
    reply_markup: Optional[Any] = None,
    disable_web_page_preview: bool = True
):
    """Безопасный ответ на сообщение с fallback"""
    try:
        return await message.reply(
            text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview
        )
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e).lower() or "entity" in str(e).lower():
            logger.warning(f"Telegram Markdown parse error, retrying without formatting: {e}")
            clean_text = clean_markdown_special_chars(text)
            return await message.reply(
                clean_text,
                parse_mode=None,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview
            )
        raise
