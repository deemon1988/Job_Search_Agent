import logging
from pathlib import Path
from typing import Optional, List
from config import settings
from agent.models import JobApplication

logger = logging.getLogger(__name__)

HEADERS = [
    "ID",
    "Дата отклика",
    "Платформа",
    "Компания",
    "Вакансия",
    "Ссылка",
    "Вектор резюме",
    "Статус",
    "Дедлайн тестового",
    "Сопроводительное письмо",
    "Заметки"
]

class GoogleSheetsClient:
    def __init__(self):
        self.credentials_file = settings.GOOGLE_SHEETS_CREDENTIALS_FILE
        self.sheet_name = settings.GOOGLE_SHEET_NAME_OR_ID
        self._gc = None
        self._worksheet = None

    def is_configured(self) -> bool:
        return bool(
            self.sheet_name and
            self.credentials_file and
            Path(self.credentials_file).exists()
        )

    def _connect(self):
        if not self.is_configured():
            return False

        try:
            import gspread
            self._gc = gspread.service_account(filename=self.credentials_file)
            try:
                sheet = self._gc.open(self.sheet_name)
            except gspread.exceptions.SpreadsheetNotFound:
                try:
                    sheet = self._gc.open_by_key(self.sheet_name)
                except Exception:
                    logger.info(f"Создание новой Google Таблицы: {self.sheet_name}")
                    sheet = self._gc.create(self.sheet_name)

            self._worksheet = sheet.sheet1

            # Проверяем заголовки
            existing_headers = self._worksheet.row_values(1)
            if not existing_headers or existing_headers != HEADERS:
                self._worksheet.insert_row(HEADERS, 1)

            return True
        except Exception as e:
            logger.error(f"Не удалось подключиться к Google Sheets: {e}")
            return False

    async def append_application(self, app: JobApplication) -> bool:
        """Добавляет запись об отклике в Google Таблицу"""
        if not self.is_configured():
            logger.debug("Google Sheets не настроен, пропуск записи.")
            return False

        try:
            if not self._worksheet:
                if not self._connect():
                    return False

            row = [
                str(app.id or ""),
                app.created_at.strftime("%Y-%m-%d %H:%M"),
                app.platform,
                app.company,
                app.job_title,
                app.job_url or "",
                str(app.vector.value if hasattr(app.vector, "value") else app.vector),
                str(app.status.value if hasattr(app.status, "value") else app.status),
                app.test_deadline or "",
                app.cover_letter or "",
                app.notes or ""
            ]
            self._worksheet.append_row(row)
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления строки в Google Sheets: {e}")
            return False

google_sheets = GoogleSheetsClient()
