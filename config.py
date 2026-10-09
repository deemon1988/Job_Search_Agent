import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: str = Field(default="", description="Telegram Bot Token from @BotFather")
    ALLOWED_USER_IDS: str = Field(default="", description="Comma-separated Telegram user IDs")

    # LLM Provider: 'gemini' or 'openai' (or local compatible)
    LLM_PROVIDER: str = Field(default="openai")

    # Google Gemini
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = Field(default="gemini-3-flash")

    # OpenAI Chat GPT
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_BASE_URL: str = Field(default="https://api.openai.com/v1")
    OPENAI_MODEL: str = Field(default="gpt-6-luna")
    # Оптимальный уровень рассуждений: 'low', 'medium', 'high'
    OPENAI_REASONING_EFFORT: str = Field(default="medium")

    # Database
    DATABASE_PATH: str = Field(default=str(BASE_DIR / "data" / "job_agent.db"))

    # Google Sheets (Optional)
    GOOGLE_SHEETS_CREDENTIALS_FILE: str = Field(default=str(BASE_DIR / "credentials.json"))
    GOOGLE_SHEET_NAME_OR_ID: str = Field(default="")

    # Profile context path
    PROFILE_CONTEXT_PATH: str = Field(default=str(BASE_DIR / "data" / "profile_context.json"))

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_allowed_users(self) -> list[int]:
        if not self.ALLOWED_USER_IDS:
            return []
        res = []
        for uid in self.ALLOWED_USER_IDS.split(","):
            uid = uid.strip()
            if uid.isdigit():
                res.append(int(uid))
        return res

settings = Settings()
