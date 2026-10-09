import aiosqlite
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
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
                    platform TEXT NOT NULL,
                    company TEXT NOT NULL,
                    job_title TEXT NOT NULL,
                    job_url TEXT,
                    vector TEXT NOT NULL,
                    cover_letter TEXT,
                    status TEXT NOT NULL,
                    score INTEGER,
                    test_deadline TEXT,
                    notes TEXT,
                    full_job_text TEXT
                )
            """)
            # Проверяем наличие колонки score для обратной совместимости
            try:
                await db.execute("ALTER TABLE applications ADD COLUMN score INTEGER")
            except Exception:
                pass # колонка уже существует

            await db.commit()
            logger.info("Database initialized successfully.")

    async def add_application(self, app: JobApplication) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO applications (
                    created_at, platform, company, job_title, job_url,
                    vector, cover_letter, status, score, test_deadline, notes, full_job_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                app.created_at.isoformat(),
                app.platform,
                app.company,
                app.job_title,
                app.job_url,
                app.vector.value if isinstance(app.vector, CareerVector) else str(app.vector),
                app.cover_letter,
                app.status.value if isinstance(app.status, ApplicationStatus) else str(app.status),
                app.score,
                app.test_deadline,
                app.notes,
                app.full_job_text
            ))
            await db.commit()
            app_id = cursor.lastrowid
            return app_id

    async def update_status(self, app_id: int, status: ApplicationStatus) -> bool:
        status_val = status.value if isinstance(status, ApplicationStatus) else str(status)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE applications SET status = ? WHERE id = ?",
                (status_val, app_id)
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

    async def list_applications(self, status: Optional[str] = None, limit: int = 50) -> List[JobApplication]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if status:
                cursor = await db.execute(
                    "SELECT * FROM applications WHERE status = ? ORDER BY id DESC LIMIT ?",
                    (status, limit)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM applications ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
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
            created_at=datetime.fromisoformat(row["created_at"]),
            platform=row["platform"],
            company=row["company"],
            job_title=row["job_title"],
            job_url=row["job_url"] or "",
            vector=CareerVector(row["vector"]) if row["vector"] in [v.value for v in CareerVector] else CareerVector.BACKEND_PYTHON,
            cover_letter=row["cover_letter"] or "",
            status=ApplicationStatus(row["status"]) if row["status"] in [s.value for s in ApplicationStatus] else ApplicationStatus.SENT,
            score=score,
            test_deadline=row["test_deadline"],
            notes=row["notes"],
            full_job_text=row["full_job_text"]
        )

db = Database()
