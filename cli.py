import asyncio
import argparse
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from agent import JobAgent, CareerVector, JobApplication, ApplicationStatus
from storage import db
from config import settings

agent = JobAgent()

async def cmd_search(query: str, remote: bool = False, limit: int = 5):
    print(f"🔎 Поиск вакансий по РФ: '{query}' (remote={remote})...")
    res = await agent.searcher.search_all(query, remote_only=remote, limit_per_source=limit)

    hh_list = res.get("hh", [])
    trud_list = res.get("trudvsem", [])
    habr_list = res.get("habr", [])

    total = len(hh_list) + len(trud_list) + len(habr_list)
    print("\n" + "=" * 65)
    print(f"🎯 Найдено {total} вакансий:")
    print("=" * 65)

    all_jobs = hh_list + habr_list + trud_list
    for idx, item in enumerate(all_jobs, 1):
        print(f"\n{idx}. [{item.platform}] {item.title}")
        print(f"   🏢 Компания: {item.company} | 📍 {item.location}")
        print(f"   💰 Зарплата: {item.salary} | ⏰ {item.schedule}")
        print(f"   🔗 Ссылка: {item.url}")
        if item.snippet:
            print(f"   📝 Описание: {item.snippet[:180]}...")
    print("\n" + "=" * 65)

def cmd_internships():
    catalog = agent.searcher.get_corporate_internships()
    print("\n" + "=" * 65)
    print("🏢 Стажерские программы корпораций РФ для студентов/выпускников СПО:")
    print("=" * 65)
    for idx, it in enumerate(catalog, 1):
        print(f"\n{idx}. {it['company']} — {it['program_name']}")
        print(f"   🔗 Подать заявку: {it['url']}")
        print(f"   🎯 Стек: {it['focus']}")
        print(f"   👥 Аудитория: {it['target_audience']}")
        print(f"   💡 Примечание: {it['notes']}")
    print("\n" + "=" * 65)

def cmd_resumes():
    resumes = agent.searcher.get_three_resumes()
    r1 = resumes.get("resume_main_is", {})
    r2 = resumes.get("resume_backend_python", {})
    r3 = resumes.get("resume_frontend_fullstack", {})

    print("\n" + "=" * 65)
    print("📄 ТРИ ОСНОВНЫХ НАПРАВЛЕНИЯ РЕЗЮМЕ ДМИТРИЯ ТУРЕЙКО:")
    print("=" * 65)
    print(f"\n1️⃣ {r1.get('direction', 'Основное резюме')}")
    print(f"Должность: {r1.get('target_title')}")
    print(f"Куда: {r1.get('target_vacancies')}")
    print(f"Профиль: {r1.get('professional_profile')}")
    print(f"Навыки: {', '.join(r1.get('skills', []))}")

    print("\n" + "-" * 65)
    print(f"\n2️⃣ {r2.get('direction', 'Вариант 1 (Backend / Python)')}")
    print(f"Должность: {r2.get('target_title')}")
    print(f"Куда: {r2.get('target_vacancies')}")
    print(f"Профиль: {r2.get('professional_profile')}")
    print(f"Навыки: {', '.join(r2.get('skills', []))}")
    print(f"Примечание: {r2.get('project_examples_placeholder')}")

    print("\n" + "-" * 65)
    print(f"\n3️⃣ {r3.get('direction', 'Вариант 2 (Frontend / Fullstack)')}")
    print(f"Должность: {r3.get('target_title')}")
    print(f"Куда: {r3.get('target_vacancies')}")
    print(f"Профиль: {r3.get('professional_profile')}")
    print(f"Навыки: {', '.join(r3.get('skills', []))}")
    print(f"Примечание: {r3.get('project_examples_placeholder')}")
    print("=" * 65)
    print("\n💡 Инструкция: если вакансия отличается по названию, агент/бот создаёт адаптированное резюме под вакансию!")
    print("=" * 65)

async def cmd_parse(text: str):
    print("🔎 Глубокий парсинг вакансии...")
    parsed = await agent.parser.parse(text)
    print("\n" + "=" * 55)
    print(f"📌 Должность: {parsed.title}")
    print(f"🏢 Компания: {parsed.company} | Платформа: {parsed.platform}")
    print(f"💰 Зарплата: {parsed.salary_raw or 'Не указана'} | График: {parsed.employment_type}")
    print(f"📍 Локация: {parsed.location or 'Не указана'} | Грейд: {parsed.grade}")
    if parsed.url:
        print(f"🔗 Ссылка: {parsed.url}")
    print(f"🛠 Стек: {', '.join(parsed.key_skills)}")
    print("\n🔍 Hard Skills требования:")
    for r in parsed.requirements_hard:
        print(f"  • {r}")
    if parsed.responsibilities:
        print("\n📋 Обязанности:")
        for resp in parsed.responsibilities[:5]:
            print(f"  ▹ {resp}")
    print("=" * 55)
    return parsed

async def cmd_score(text: str):
    parsed = await agent.parser.parse(text)
    print("📊 Расчет скоринга по методологии SuperJob Pro...")
    score = await agent.scorer.score(parsed)

    print("\n" + "=" * 55)
    print(f"📌 {parsed.title} ({parsed.company})")
    print(f"🏆 Скоринг соответствия: {score.total_score}/100 [{score.priority_tier}]")
    print(f"🎯 Рекомендуемый вектор: {score.recommended_vector.value}")
    print("-" * 55)
    print(f"• Hard Skills: {score.hard_skills_score}/40")
    print(f"• Опыт и грейд: {score.experience_grade_score}/25")
    print(f"• Образование (МТИ / ИС): {score.education_domain_score}/15")
    print(f"• Условия и прозрачность: {score.conditions_score}/10")
    print(f"• Штраф за Red Flags: {score.red_flags_penalty} б.")
    print("-" * 55)
    print("👍 Плюсы вакансии:")
    for p in score.pros:
        print(f"  ✅ {p}")
    print("\n🚩 Риски / Red Flags:")
    for c in score.cons_and_risks:
        print(f"  ⚠️ {c}")
    print("\n📚 Пробелы в стеке:")
    for g in score.missing_gaps:
        print(f"  ▹ {g}")
    print(f"\n💡 Стратегия отклика (SuperJob Pro):\n{score.application_strategy}")
    print("=" * 55)
    return parsed, score

async def cmd_cover(text: str, detailed: bool = False):
    parsed = await agent.parser.parse(text)
    print("✍️ Генерация отклика по стандартам SuperJob Pro...")
    cover = await agent.cover_letter.generate(parsed)

    text_to_show = cover.detailed_letter if detailed else cover.short_letter
    title_format = "Развернутое письмо для HR" if detailed else "Краткий отклик для чата hh.ru/SuperJob"

    print("\n" + "=" * 55)
    print(f"✉️ {title_format} ({len(text_to_show)} знаков):")
    print(f"🪝 Hook: {cover.hook_phrase}")
    print("-" * 55)
    print(text_to_show)
    print("-" * 55)
    print(f"📂 Упомянутые проекты: {', '.join(cover.highlighted_projects)}")
    print(f"🎯 Закрытые требования: {', '.join(cover.skills_covered)}")
    print("=" * 55)

async def cmd_interview(text: str):
    parsed = await agent.parser.parse(text)
    print("🎯 Подготовка к собеседованию (3 блока SuperJob Pro)...")
    prep = await agent.interview.generate_prep_questions(parsed)

    print("\n" + "=" * 60)
    print(f"📌 Должность: {parsed.title} ({parsed.company})")
    print(f"💡 Фокус интервью: {prep.role_summary}")
    print("=" * 60)
    print("\n🛠 БЛОК 1: Технический скрининг (10 вопросов):")
    for q in prep.technical_questions:
        print(f"{q.number}. [{q.topic}] {q.question}")
        for pt in q.key_points:
            print(f"    ▹ {pt}")
        print()

    print("-" * 60)
    print("🌟 БЛОК 2: Поведенческие вопросы по STAR-модели:")
    for idx, s in enumerate(prep.behavioral_star_questions, 1):
        print(f"\n{idx}. ❓ {s.question}")
        print(f"  • S (Ситуация): {s.situation_context}")
        print(f"  • T (Задача): {s.task_description}")
        print(f"  • A (Действие): {s.action_taken}")
        print(f"  • R (Результат): {s.result_metric}")
        print(f"  💡 Совет SuperJob Pro: {s.expert_tip}")

    print("-" * 60)
    print("🤝 БЛОК 3: Умные вопросы кандидату к работодателю:")
    for eq in prep.questions_for_employer:
        print(f"  • {eq}")
    print("=" * 60)

async def cmd_debrief(notes: str):
    print("⏳ Разбор вопросов собеседования...")
    debrief = await agent.interview.debrief_interview(notes)
    print("\n" + "=" * 50)
    print(f"💪 Сильные стороны: {debrief.strengths_observed}\n")
    print("🔍 Разбор пробелов:")
    for idx, item in enumerate(debrief.gap_analysis, 1):
        print(f"\nВопрос {idx}: {item.question}")
        print(f"✅ Эталонный ответ:\n{item.ideal_answer}")
        print(f"📚 Микро-план:\n{item.quick_plan}")
    print(f"\n🎯 Рекомендации:\n{debrief.overall_recommendations}")
    print("=" * 50)

async def cmd_stats():
    await db.init_db()
    stats = await db.get_funnel_stats()
    print("\n" + "=" * 40)
    print("📊 Воронка откликов (SQLite):")
    print("-" * 40)
    for status, count in stats.items():
        print(f"  {status:<22} : {count}")
    print("=" * 40)

def main():
    parser = argparse.ArgumentParser(description="Job Search AI Agent CLI (SuperJob Pro + Multi-Platform Search)")
    subparsers = parser.add_subparsers(dest="command")

    # search
    p_srch = subparsers.add_parser("search", help="Мультипоиск вакансий по РФ (hh, trudvsem, habr)")
    p_srch.add_argument("query", help="Поисковый запрос (например: 'Python стажер', 'Техподдержка L2')")
    p_srch.add_argument("--remote", action="store_true", help="Только удаленная работа")
    p_srch.add_argument("--limit", type=int, default=5, help="Количество вакансий на источник")

    # internships
    subparsers.add_parser("internships", help="Стажерские программы корпораций (Сбер, Т-Банк, ИнфоТеКС и др.)")

    # resumes
    subparsers.add_parser("resumes", help="Два готовых специализированных резюме под разные цели")

    # parse
    p_parse = subparsers.add_parser("parse", help="Глубокий парсинг вакансии")
    p_parse.add_argument("source", help="Текст вакансии, URL (hh.ru/SuperJob) или путь к файлу")

    # score
    p_sc = subparsers.add_parser("score", help="Скоринг вакансии и рисков (SuperJob Pro)")
    p_sc.add_argument("source", help="Текст вакансии, URL или путь к файлу")

    # cover
    p_cov = subparsers.add_parser("cover", help="Генерация отклика по формуле SuperJob Pro")
    p_cov.add_argument("source", help="Текст вакансии или путь к файлу")
    p_cov.add_argument("--detailed", action="store_true", help="Развернутое письмо для HR")

    # interview
    p_int = subparsers.add_parser("interview", help="3-блочная подготовка к интервью (STAR + Tech)")
    p_int.add_argument("source", help="Текст вакансии или путь к файлу")

    # debrief
    p_deb = subparsers.add_parser("debrief", help="Разбор вопросов после собеседования")
    p_deb.add_argument("notes", help="Текст с вопросами")

    # stats
    subparsers.add_parser("stats", help="Статистика воронки откликов")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    def get_text(source: str) -> str:
        p = Path(source)
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8")
        return source

    if args.command == "search":
        asyncio.run(cmd_search(args.query, remote=args.remote, limit=args.limit))
    elif args.command == "internships":
        cmd_internships()
    elif args.command == "resumes":
        cmd_resumes()
    elif args.command == "parse":
        asyncio.run(cmd_parse(get_text(args.source)))
    elif args.command == "score":
        asyncio.run(cmd_score(get_text(args.source)))
    elif args.command == "cover":
        asyncio.run(cmd_cover(get_text(args.source), detailed=args.detailed))
    elif args.command == "interview":
        asyncio.run(cmd_interview(get_text(args.source)))
    elif args.command == "debrief":
        asyncio.run(cmd_debrief(args.notes))
    elif args.command == "stats":
        asyncio.run(cmd_stats())

if __name__ == "__main__":
    main()
