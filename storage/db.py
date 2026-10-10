import aiosqlite
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from config import settings
from agent.models import JobApplication, ApplicationStatus, CareerVector

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.DATABASE_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    checked_at TEXT,
                    published_at TEXT,
                    platform TEXT NOT NULL,
                    company TEXT NOT NULL,
                    job_title TEXT NOT NULL,
                    job_url TEXT,
                    vector TEXT NOT NULL,
                    cover_letter TEXT,
                    status TEXT NOT NULL,
                    score INTEGER,
                    relevance_group TEXT,
                    remote_status TEXT,
                    geography TEXT,
                    salary_info TEXT,
                    experience_level TEXT,
                    phone_support_status TEXT,
                    why_fits TEXT,
                    gaps TEXT,
                    next_action TEXT,
                    test_deadline TEXT,
                    notes TEXT,
                    full_job_text TEXT
                )
            """)
            # Миграции колонок для существующей базы данных
            columns_to_add = [
                ("score", "INTEGER"),
                ("checked_at", "TEXT"),
                ("published_at", "TEXT"),
                ("relevance_group", "TEXT"),
                ("remote_status", "TEXT"),
                ("geography", "TEXT"),
                ("salary_info", "TEXT"),
                ("experience_level", "TEXT"),
                ("phone_support_status", "TEXT"),
                ("why_fits", "TEXT"),
                ("gaps", "TEXT"),
                ("next_action", "TEXT"),
            ]
            for col_name, col_type in columns_to_add:
                try:
                    await db.execute(f"ALTER TABLE applications ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass  # Колонка уже существует

            await db.commit()
            logger.info("Database initialized successfully with full vacancy tracking support.")

    async def add_application(self, app: JobApplication) -> int:
        checked_date = app.checked_at or datetime.now().strftime("%Y-%m-%d")
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO applications (
                    created_at, checked_at, published_at, platform, company, job_title, job_url,
                    vector, cover_letter, status, score, relevance_group, remote_status,
                    geography, salary_info, experience_level, phone_support_status,
                    why_fits, gaps, next_action, test_deadline, notes, full_job_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                app.created_at.isoformat(),
                checked_date,
                app.published_at,
                app.platform,
                app.company,
                app.job_title,
                app.job_url,
                app.vector.value if isinstance(app.vector, CareerVector) else str(app.vector),
                app.cover_letter,
                app.status.value if isinstance(app.status, ApplicationStatus) else str(app.status),
                app.score,
                app.relevance_group,
                app.remote_status,
                app.geography,
                app.salary_info,
                app.experience_level,
                app.phone_support_status,
                app.why_fits,
                app.gaps,
                app.next_action,
                app.test_deadline,
                app.notes,
                app.full_job_text
            ))
            await db.commit()
            app_id = cursor.lastrowid
            return app_id

    async def update_status(self, app_id: int, status: Union[ApplicationStatus, str]) -> bool:
        status_val = status.value if isinstance(status, ApplicationStatus) else str(status)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE applications SET status = ? WHERE id = ?",
                (status_val, app_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_checked_at(self, app_id: int, checked_at: Optional[str] = None) -> bool:
        """Обновляет дату проверки актуальности вакансии"""
        val = checked_at or datetime.now().strftime("%Y-%m-%d")
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE applications SET checked_at = ? WHERE id = ?",
                (val, app_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_deadline(self, app_id: int, deadline: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE applications SET test_deadline = ? WHERE id = ?",
                (deadline, app_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_notes(self, app_id: int, notes: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE applications SET notes = ? WHERE id = ?",
                (notes, app_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_application(self, app_id: int) -> Optional[JobApplication]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM applications WHERE id = ?",
                (app_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_app(row)

    async def list_applications(
        self,
        status: Optional[str] = None,
        relevance_group: Optional[str] = None,
        limit: int = 50
    ) -> List[JobApplication]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            conditions = []
            params = []
            if status:
                conditions.append("status = ?")
                params.append(status)
            if relevance_group:
                conditions.append("relevance_group = ?")
                params.append(relevance_group)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            query = f"SELECT * FROM applications {where_clause} ORDER BY id DESC LIMIT ?"
            params.append(limit)

            cursor = await db.execute(query, tuple(params))
            rows = await cursor.fetchall()
            return [self._row_to_app(r) for r in rows]

    async def get_funnel_stats(self) -> Dict[str, int]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT status, COUNT(*) FROM applications GROUP BY status"
            )
            rows = await cursor.fetchall()
            counts = {status.value: 0 for status in ApplicationStatus}
            for status_name, cnt in rows:
                counts[status_name] = cnt
            counts["Всего откликов"] = sum(cnt for _, cnt in rows)
            return counts

    def _row_to_app(self, row: aiosqlite.Row) -> JobApplication:
        keys = row.keys()
        score = row["score"] if "score" in keys else None
        return JobApplication(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]) if "created_at" in keys and row["created_at"] else datetime.now(),
            checked_at=row["checked_at"] if "checked_at" in keys else None,
            published_at=row["published_at"] if "published_at" in keys else None,
            platform=row["platform"] if "platform" in keys else "hh.ru",
            company=row["company"] if "company" in keys else "Компания",
            job_title=row["job_title"] if "job_title" in keys else "Вакансия",
            job_url=row["job_url"] if "job_url" in keys and row["job_url"] else "",
            vector=CareerVector(row["vector"]) if "vector" in keys and row["vector"] in [v.value for v in CareerVector] else CareerVector.BACKEND_PYTHON,
            cover_letter=row["cover_letter"] if "cover_letter" in keys and row["cover_letter"] else "",
            status=ApplicationStatus(row["status"]) if "status" in keys and row["status"] in [s.value for s in ApplicationStatus] else ApplicationStatus.SENT,
            score=score,
            relevance_group=row["relevance_group"] if "relevance_group" in keys else None,
            remote_status=row["remote_status"] if "remote_status" in keys else None,
            geography=row["geography"] if "geography" in keys else "РФ / Ленобласть",
            salary_info=row["salary_info"] if "salary_info" in keys else None,
            experience_level=row["experience_level"] if "experience_level" in keys else None,
            phone_support_status=row["phone_support_status"] if "phone_support_status" in keys else "Нет",
            why_fits=row["why_fits"] if "why_fits" in keys else None,
            gaps=row["gaps"] if "gaps" in keys else None,
            next_action=row["next_action"] if "next_action" in keys else None,
            test_deadline=row["test_deadline"] if "test_deadline" in keys else None,
            notes=row["notes"] if "notes" in keys else None,
            full_job_text=row["full_job_text"] if "full_job_text" in keys else None
        )

db = Database()
