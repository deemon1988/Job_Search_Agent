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
    assert len(rules_content) > 1000, "candidate_profile_rules.md не загрузился или пустой"
    assert "Профиль кандидата и правила поиска удалённой IT-работы" in rules_content
    assert "Приоритет A" in rules_content
    print("✅ Постоянный контекст агента (candidate_profile_rules.md) успешно загружен!")

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

    print("\n=======================================================")
    print("🎉 ВСЕ ТЕСТЫ МУЛЬТИПОИСКА И РОЛЕЙ ПРОЙДЕНЫ УСПЕШНО!")
    print("=======================================================")

if __name__ == "__main__":
    asyncio.run(test_suite())
