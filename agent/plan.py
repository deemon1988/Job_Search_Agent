import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from config import BASE_DIR

logger = logging.getLogger(__name__)

class ActionPlanManager:
    """Менеджер плана действий на 30 и 90 дней и ежедневного тайм-менеджмента"""

    def __init__(self, data_path: Optional[str] = None):
        p = Path(data_path) if data_path else BASE_DIR / "data" / "action_plan_knowledge.json"
        if not p.exists():
            alt_p = Path(__file__).resolve().parent.parent / "data" / "action_plan_knowledge.json"
            if alt_p.exists():
                p = alt_p
        with open(p, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_monthly_plan(self) -> Dict[str, Any]:
        """Возвращает план откликов и задач на 30 дней (по неделям)"""
        return self.data.get("monthly_plan_30_days", {})

    def get_week_details(self, week_num: int) -> Optional[Dict[str, Any]]:
        """Возвращает цели и чек-лист конкретной недели (1-4)"""
        weeks = self.get_monthly_plan().get("weeks", [])
        for w in weeks:
            if w.get("week_number") == week_num:
                return w
        return None

    def get_plan_overview(self) -> Dict[str, Any]:
        """Возвращает обзор месячного плана (alias)"""
        m = self.get_monthly_plan()
        return {
            "title": "План поиска первой удаленной IT-работы на 30 дней",
            "target_goal": "Выход на оффер удаленно (40–60 тыс. ₽)",
            "total_applications_target": m.get("target_applications", "55–75 откликов"),
            "weeks": m.get("weeks", [])
        }

    def get_week(self, week_num: int) -> Optional[Dict[str, Any]]:
        """Возвращает детальную инфо по номеру недели"""
        w = self.get_week_details(week_num)
        if not w:
            return None
        return {
            "week_number": w.get("week_number"),
            "theme": w.get("title"),
            "focus": "; ".join(w.get("goals", [])[:2]),
            "target_applications": f"{10 + (week_num-1)*5}–{15 + (week_num-1)*5} откликов",
            "checklist": w.get("checklist", []) + w.get("goals", []),
            "deliverable": w.get("checklist", ["Готовый артефакт"])[-1]
        }

    def get_strict_filter_rules(self) -> Dict[str, Any]:
        """Возвращает строгие критерии отбора"""
        sc = self.data.get("strict_vacancy_criteria", {})
        return {
            "title": "Строгие критерии отбора вакансий",
            "filters": {
                "no_phone_calls": {
                    "rule": sc.get("filter_3_no_phone_calls", {}).get("rule", "Без звонков и телефонов"),
                    "exception": "Допустимо только текстовое общение (тикеты, чаты, почта)"
                },
                "remote_only": {
                    "rule": sc.get("filter_1_remote", {}).get("rule", "100% удаленка"),
                    "location": "Ленинградская область / Сосновый Бор (без офиса)"
                },
                "experience_level": {
                    "rule": sc.get("filter_2_junior_grade", {}).get("rule", "Junior / без опыта / до 1 года")
                },
                "salary_range": {
                    "target": "40 000 – 60 000+ ₽/мес"
                }
            },
            "ai_philosophy_summary": "AI — основной множитель скорости. Кандидат умеет запускать код, проверять негативные сценарии, читать логи и отвечать за архитектуру."
        }

    def get_daily_routine(self) -> Dict[str, Any]:
        """Возвращает ежедневный регламент при 3–4 часах в день"""
        sched = self.data.get("daily_schedule_3_4_hours", {})
        blocks = []
        for b in sched.get("blocks", []):
            blocks.append({
                "duration": b.get("time"),
                "block": b.get("task"),
                "focus": b.get("description"),
                "output": "Коммит, отклик или разобранная тема"
            })
        return {
            "title": "Распорядок дня для поиска работы",
            "daily_hours": sched.get("total_time", "3–4 часа в день"),
            "schedule": blocks,
            "principles": [
                "Отклики и проект идут ПАРАЛЛЕЛЬНО каждый день",
                "Каждый отклик точечный: адаптированное резюме + письмо",
                "В проекте главное — коммиты в GitHub и негативные тесты"
            ]
        }

    def format_daily_routine_text(self) -> str:
        """Форматирует текст распорядка дня"""
        routine = self.get_daily_routine()
        blocks = routine.get("blocks", [])
        lines = [
            "⏱ *Ежедневный график (3–4 часа в день)*\n",
            "_Как эффективно распределить время между откликами, проектом и подготовкой:_\n"
        ]
        for b in blocks:
            lines.append(f"▫️ *{b.get('time')}* — *{b.get('task')}*")
            lines.append(f"   _{b.get('description')}_\n")
        lines.append("💡 *Ключевое правило:* Не ждать окончания обучения — отправлять отклики ежедневно параллельно с проектом!")
        return "\n".join(lines)

    def format_month_overview_text(self) -> str:
        """Форматирует общий обзор плана на 30 дней"""
        plan = self.get_monthly_plan()
        target = plan.get("target_applications", "55–75 откликов")
        weeks = plan.get("weeks", [])

        lines = [
            "📅 *План поиска первой удаленной IT-работы на 30 дней*\n",
            f"🎯 *Цель месяца:* `{target}` (удаленка, 40–60 тыс. ₽)\n",
            "═════════════════════════════════"
        ]

        for w in weeks:
            lines.append(f"📌 *{w.get('title')}*")
            for g in w.get("goals", [])[:2]:
                lines.append(f"  • {g}")
            lines.append("")

        lines.append("═════════════════════════════════")
        lines.append("👇 Выберите неделю, чтобы открыть подробный чек-лист задач:")
        return "\n".join(lines)
