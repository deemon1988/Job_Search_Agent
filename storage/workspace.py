import csv
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from config import BASE_DIR

logger = logging.getLogger(__name__)

class WorkspaceManager:
    """Менеджер рабочих файлов и журналов career-agent-workspace (CSV, Markdown, Tracks)"""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or (BASE_DIR / "data")
        self.tracks_dir = self.data_dir / "tracks"
        self.tracks_dir.mkdir(parents=True, exist_ok=True)

        self.vacancies_csv = self.data_dir / "vacancies.csv"
        self.applications_csv = self.data_dir / "applications.csv"
        self.learning_csv = self.data_dir / "learning_plan.csv"
        self.portfolio_csv = self.data_dir / "portfolio_projects.csv"
        self.interview_csv = self.data_dir / "interview_log.csv"
        self.journal_md = self.data_dir / "vacancies_and_tracks.md"
        self.kb_md = self.data_dir / "candidate_knowledge_base.md"
        self.instruction_md = self.data_dir / "Instruction.md"

    def _get_next_id(self, file_path: Path, prefix: str, id_col_idx: int = 0) -> str:
        max_num = 0
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if row and len(row) > id_col_idx:
                        val = row[id_col_idx].strip()
                        m = re.match(rf"^{prefix}-(\d+)$", val)
                        if m:
                            num = int(m.group(1))
                            if num > max_num:
                                max_num = num
        return f"{prefix}-{max_num + 1:04d}"

    def get_next_vacancy_id(self) -> str:
        return self._get_next_id(self.vacancies_csv, "VAC")

    def get_next_application_id(self) -> str:
        return self._get_next_id(self.applications_csv, "APP")

    def get_next_track_id(self) -> str:
        max_num = 0
        for p in self.tracks_dir.glob("TRACK-*.md"):
            m = re.match(r"^TRACK-(\d+)\.md$", p.name)
            if m:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
        return f"TRACK-{max_num + 1:04d}"

    def add_checked_vacancy(
        self,
        company: str,
        job_title: str,
        url: str = "",
        source: str = "hh.ru",
        posting_date: str = "",
        status: str = "Подходит",
        remote_confirmed: str = "Да",
        work_from_russia_confirmed: str = "Да",
        salary: str = "Не указана",
        score: int = 80,
        class_grade: str = "A",
        gaps: str = "Критических пробелов нет",
        next_action: str = "Откликнуться",
        next_action_date: str = "",
        result: str = ""
    ) -> str:
        """Добавляет проверенную вакансию в vacancies.csv и журнал vacancies_and_tracks.md"""
        vac_id = self.get_next_vacancy_id()
        date_checked = datetime.now().strftime("%Y-%m-%d")

        row = [
            vac_id,
            date_checked,
            source,
            company,
            job_title,
            url,
            posting_date,
            status,
            remote_confirmed,
            work_from_russia_confirmed,
            salary,
            str(score),
            class_grade,
            gaps,
            next_action,
            next_action_date or date_checked,
            result
        ]

        # Запись в CSV
        file_exists = self.vacancies_csv.exists()
        with open(self.vacancies_csv, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "id", "date_checked", "source", "company", "job_title", "url",
                    "posting_date", "status", "remote_confirmed", "work_from_russia_confirmed",
                    "salary", "score", "class", "gaps", "next_action", "next_action_date", "result"
                ])
            writer.writerow(row)

        # Синхронизация строки в vacancies_and_tracks.md
        self._append_to_journal_vacancies(row)

        logger.info(f"Вакансия {vac_id} ({company} - {job_title}) добавлена в vacancies.csv")
        return vac_id

    def record_application(
        self,
        vacancy_id: str,
        resume_version: str = "Версия 1 (AI Automation/Backend)",
        cover_letter: str = "",
        submission_method: str = "hh.ru",
        status: str = "Отклик отправлен",
        employer_response: str = "",
        next_action: str = "Ожидание ответа работодателя",
        next_action_date: str = ""
    ) -> str:
        """Регистрирует отклик в applications.csv и обновляет статус в vacancies.csv"""
        app_id = self.get_next_application_id()
        app_date = datetime.now().strftime("%Y-%m-%d")

        app_row = [
            app_id,
            vacancy_id,
            app_date,
            resume_version,
            cover_letter[:100].replace("\n", " ") + "...",
            submission_method,
            status,
            employer_response,
            next_action,
            next_action_date or app_date
        ]

        file_exists = self.applications_csv.exists()
        with open(self.applications_csv, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "application_id", "vacancy_id", "date", "resume_version",
                    "cover_letter", "submission_method", "status", "employer_response",
                    "next_action", "next_action_date"
                ])
            writer.writerow(app_row)

        # Обновляем статус в vacancies.csv
        self._update_vacancy_status(vacancy_id, status)
        self._append_to_journal_applications(app_row)

        logger.info(f"Отклик {app_id} для {vacancy_id} добавлен в applications.csv")
        return app_id

    def save_track_file(
        self,
        track_id: str,
        content: str,
        vac_id: str = "",
        company: str = "",
        title: str = ""
    ) -> Path:
        """Сохраняет персональный файл TRACK-XXXX.md в data/tracks/"""
        t_id = track_id or self.get_next_track_id()
        file_path = self.tracks_dir / f"{t_id}.md"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Файл карьерного трека сохранён: {file_path}")
        return file_path

    def list_tracks(self) -> List[Dict[str, str]]:
        """Возвращает список существующих карьерных треков"""
        tracks = []
        for p in sorted(self.tracks_dir.glob("TRACK-*.md")):
            name = p.stem
            title = "Карьерный трек"
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("# "):
                            title = line.replace("# ", "").strip()
                            break
            except Exception:
                pass
            tracks.append({
                "track_id": name,
                "title": title,
                "path": str(p),
                "modified": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            })
        return tracks

    def get_track_content(self, track_id: str) -> Optional[str]:
        p = self.tracks_dir / f"{track_id}.md"
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def get_csv_stats(self) -> Dict[str, int]:
        def count_rows(p: Path) -> int:
            if not p.exists():
                return 0
            with open(p, "r", encoding="utf-8") as f:
                return max(0, sum(1 for line in f if line.strip()) - 1)

        return {
            "vacancies_csv": count_rows(self.vacancies_csv),
            "applications_csv": count_rows(self.applications_csv),
            "learning_plan_csv": count_rows(self.learning_csv),
            "portfolio_projects_csv": count_rows(self.portfolio_csv),
            "interview_log_csv": count_rows(self.interview_csv),
            "vacancies_count": count_rows(self.vacancies_csv),
            "applications_count": count_rows(self.applications_csv),
            "learning_count": count_rows(self.learning_csv),
            "portfolio_count": count_rows(self.portfolio_csv),
            "interview_count": count_rows(self.interview_csv),
            "tracks_count": len(list(self.tracks_dir.glob("TRACK-*.md")))
        }

    def _update_vacancy_status(self, vac_id: str, new_status: str):
        if not self.vacancies_csv.exists():
            return
        rows = []
        with open(self.vacancies_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header:
                rows.append(header)
            for r in reader:
                if r and r[0] == vac_id and len(r) > 7:
                    r[7] = new_status
                rows.append(r)

        with open(self.vacancies_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

    def _append_to_journal_vacancies(self, row: List[str]):
        """Добавляет строку в Markdown таблицу вакансий vacancies_and_tracks.md"""
        if not self.journal_md.exists():
            return
        md_row = f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6] or '—'} | {row[7]} | {row[8]} | {row[9]} | {row[10]} | {row[11]} | {row[12]} | {row[13]} | {row[14]} | {row[15]} | {row[16] or '—'} |\n"
        try:
            with open(self.journal_md, "r", encoding="utf-8") as f:
                content = f.read()

            target_header = "## 5. Реестр вакансий"
            if target_header in content:
                # Вставляем строку после последней строки таблицы секции 5
                parts = content.split("## 6. Реестр откликов")
                if len(parts) == 2:
                    section_5, section_6 = parts[0], parts[1]
                    new_section_5 = section_5.rstrip() + "\n" + md_row + "\n\n"
                    new_content = new_section_5 + "## 6. Реестр откликов" + section_6
                    with open(self.journal_md, "w", encoding="utf-8") as f:
                        f.write(new_content)
        except Exception as e:
            logger.warning(f"Не удалось обновить Markdown-журнал: {e}")

    def _append_to_journal_applications(self, row: List[str]):
        """Добавляет строку в Markdown таблицу откликов vacancies_and_tracks.md"""
        if not self.journal_md.exists():
            return
        md_row = f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} | {row[7] or '—'} | {row[8]} | {row[9]} |\n"
        try:
            with open(self.journal_md, "r", encoding="utf-8") as f:
                content = f.read()

            target_header = "## 6. Реестр откликов"
            if target_header in content:
                parts = content.split("## 7. Карточка карьерного трека")
                if len(parts) == 2:
                    section_6, section_7 = parts[0], parts[1]
                    new_section_6 = section_6.rstrip() + "\n" + md_row + "\n\n"
                    new_content = new_section_6 + "## 7. Карточка карьерного трека" + section_7
                    with open(self.journal_md, "w", encoding="utf-8") as f:
                        f.write(new_content)
        except Exception as e:
            logger.warning(f"Не удалось обновить Markdown-журнал откликов: {e}")

workspace_manager = WorkspaceManager()
