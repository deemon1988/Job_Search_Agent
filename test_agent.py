import asyncio
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from config import settings, BASE_DIR
from agent.prompts import load_profile_context
from agent.scorer import load_superjob_knowledge
from agent.job_searcher import JobSearcher
from agent.models import (
    CareerVector,
    ApplicationStatus,
    ParsedJob,
    JobScoreBreakdown,
    JobApplication
)
from storage.db import Database

async def test_suite():
    print("=== ТЕСТ 1: База верифицированного профиля и ролевая матрица ===")
    profile = load_profile_context(settings.PROFILE_CONTEXT_PATH)
    assert "starter_roles_matrix" in profile, "starter_roles_matrix missing"
    assert "corporate_internships_catalog" in profile, "corporate_internships_catalog missing"
    assert "dual_resume_templates" in profile, "dual_resume_templates missing"

    roles = profile["starter_roles_matrix"]
    print(f"✅ Роли для старта: {list(roles.keys())}")
    assert "is_developer" in roles
    assert "backend_python" in roles
    assert "frontend_fullstack" in roles

    print("\n=== ТЕСТ 2: Три основных резюме Дмитрия Турейко (Функциональная модель) ===")
    assert "three_resume_templates" in profile, "three_resume_templates missing"
    three_resumes = profile["three_resume_templates"]
    assert "resume_fulltime" in three_resumes
    assert "resume_parttime" in three_resumes
    assert "resume_intern" in three_resumes
    print(f"✅ Резюме 1 (Full-time): {three_resumes['resume_fulltime']['target_title']}")
    print(f"✅ Резюме 2 (Part-time): {three_resumes['resume_parttime']['target_title']}")
    print(f"✅ Резюме 3 (Intern): {three_resumes['resume_intern']['target_title']}")

    print("\n=== ТЕСТ 3: Каталог корпоративных стажировок ===")
    searcher = JobSearcher()
    internships = searcher.get_corporate_internships()
    companies = [c["company"] for c in internships]
    print(f"✅ Корпоративные стажировки: {companies}")
    assert "ИнфоТеКС" in companies
    assert "Сбер" in companies
    assert "Т-Банк" in companies

    print("\n=== ТЕСТ 4: Живой поиск через открытый hh.ru API ===")
    hh_results = await searcher.search_hh("Python стажер", limit=3)
    print(f"✅ Найдено вакансий на hh.ru: {len(hh_results)}")
    if hh_results:
        top = hh_results[0]
        print(f"  • Пример: [{top.company}] {top.title} ({top.salary}) -> {top.url}")

    print("\n=== ТЕСТ 5: SQLite CRM со скорингом и изолированным хранением вакансий ===")
    from agent.prompts import load_candidate_rules
    rules_content = load_candidate_rules()
    assert len(rules_content) > 1000, "База знаний кандидата не загрузилась или пустая"
    assert "База знаний кандидата" in rules_content or "Профиль кандидата" in rules_content
    assert "Инструкция для AI-агента" in rules_content or "ИНСТРУКЦИЯ" in rules_content
    print("✅ Постоянный контекст агента (candidate_knowledge_base.md + Instruction.md) успешно загружен!")

    test_db_path = str(Path(BASE_DIR) / "data" / "test_job_agent_search.db")
    if Path(test_db_path).exists():
        Path(test_db_path).unlink()

    test_db = Database(test_db_path)
    await test_db.init_db()

    app = JobApplication(
        checked_at="2026-10-10",
        platform="hh.ru",
        company="ИнфоТеКС Партнер",
        job_title="Стажер исследователь / программист",
        job_url="https://infotecs.ru",
        vector=CareerVector.BACKEND_PYTHON,
        cover_letter="Письмо...",
        status=ApplicationStatus.NEW,
        score=92,
        relevance_group="A",
        remote_status="Подтверждена",
        salary_info="50 000 руб.",
        next_action="Откликнуться"
    )
    app_id = await test_db.add_application(app)
    assert app_id > 0
    saved_app = await test_db.get_application(app_id)
    assert saved_app is not None
    assert saved_app.checked_at == "2026-10-10"
    assert saved_app.status == ApplicationStatus.NEW
    assert saved_app.relevance_group == "A"
    print(f"✅ Вакансия изолированно сохранена: ID={app_id}, дата проверки={saved_app.checked_at}, статус={saved_app.status.value}, группа={saved_app.relevance_group}")

    # Обновление статуса и даты
    await test_db.update_status(app_id, ApplicationStatus.SENT)
    await test_db.update_checked_at(app_id, "2026-10-11")
    updated_app = await test_db.get_application(app_id)
    assert updated_app.status == ApplicationStatus.SENT
    assert updated_app.checked_at == "2026-10-11"
    print(f"✅ Статус отклика и дата проверки успешно обновлены: статус={updated_app.status.value}, проверено={updated_app.checked_at}")

    print("\n=== ТЕСТ 6: Поддержка моделей gpt-6-luna и gemini-3-flash ===")
    from agent.llm import LLMService, is_reasoning_model
    llm = LLMService(system_instruction="You are a helpful assistant.")
    print(f"✅ Активный провайдер LLM: {llm.provider}")
    print(f"✅ Модель OpenAI: {settings.OPENAI_MODEL} (reasoning_effort: {settings.OPENAI_REASONING_EFFORT})")
    print(f"✅ Модель Gemini: {settings.GEMINI_MODEL}")
    assert settings.OPENAI_MODEL == "gpt-6-luna"
    assert settings.OPENAI_REASONING_EFFORT == "medium"
    assert settings.GEMINI_MODEL == "gemini-3-flash"
    assert is_reasoning_model("gpt-6-luna") is True

    # Проверяем обработку отсутствия ключа с понятной ошибкой
    try:
        if not settings.OPENAI_API_KEY and llm.provider == "openai":
            await llm.generate_text("test")
    except ValueError as e:
        print(f"✅ Корректная обработка валидации ключей: {str(e)[:60]}...")
        assert "OPENAI_API_KEY" in str(e) or "GEMINI_API_KEY" in str(e)

    if Path(test_db_path).exists():
        Path(test_db_path).unlink()

    print("\n=== ТЕСТ 7: Рабочее пространство career-agent-workspace (CSV, Журнал, Треки) ===")
    import tempfile
    from storage.workspace import WorkspaceManager

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        dummy_journal = tmp_path / "vacancies_and_tracks.md"
        dummy_journal.write_text("## 5. Реестр вакансий\n\n## 6. Реестр откликов\n\n## 7. Карточка карьерного трека\n", encoding="utf-8")
        wm = WorkspaceManager(data_dir=tmp_path)

        # 1. Добавление вакансии в CSV и Markdown-журнал
        vac_id = wm.add_checked_vacancy(
            company="Яндекс",
            job_title="Junior Python Разработчик",
            url="https://hh.ru/vacancy/123456",
            source="hh.ru",
            salary="60 000 руб.",
            score=88,
            class_grade="A",
            gaps="Docker на базовом уровне",
            next_action="Откликнуться"
        )
        assert vac_id == "VAC-0001"
        assert wm.vacancies_csv.exists()
        assert wm.journal_md.exists()
        print(f"✅ Добавлена проверенная вакансия в CSV: {vac_id}")

        # 2. Запись отклика
        app_csv_id = wm.record_application(
            vacancy_id=vac_id,
            resume_version="Junior Python / Web Developer",
            cover_letter="Текст письма...",
            submission_method="hh.ru",
            status="Отправлено"
        )
        assert app_csv_id == "APP-0001"
        assert wm.applications_csv.exists()
        print(f"✅ Зафиксирован отклик в CSV: {app_csv_id}")

        # 3. Создание и чтение трека
        track_id = wm.get_next_track_id()
        assert track_id == "TRACK-0001"
        track_file = wm.save_track_file(track_id, "# Тестовый карьерный трек\nСтрока 2")
        assert track_file.exists()
        assert "Тестовый карьерный трек" in (wm.get_track_content(track_id) or "")
        tracks_list = wm.list_tracks()
        assert len(tracks_list) == 1
        assert tracks_list[0]["track_id"] == "TRACK-0001"
        print(f"✅ Создан и сохранён карьерный трек: {track_id}")

        # 4. Проверка статистики CSV
        stats = wm.get_csv_stats()
        assert stats["vacancies_csv"] == 1
        assert stats["applications_csv"] == 1
        assert stats["tracks_count"] == 1
        print(f"✅ Статистика CSV реестров: {stats}")

    print("\n=======================================================")
    print("🎉 ВСЕ ТЕСТЫ МУЛЬТИПОИСКА, РОЛЕЙ И РАБОЧЕГО ПРОСТРАНСТВА ПРОЙДЕНЫ УСПЕШНО!")
    print("=======================================================")

if __name__ == "__main__":
    asyncio.run(test_suite())
