import json
import logging
import urllib.parse
import re
from typing import List, Optional, Dict, Any
import aiohttp
from bs4 import BeautifulSoup

from config import settings
from agent.models import ParsedJob
from agent.prompts import load_profile_context

logger = logging.getLogger(__name__)

class JobSearchResult:
    def __init__(
        self,
        title: str,
        company: str,
        platform: str,
        url: str,
        salary: str = "Не указана",
        location: str = "Россия",
        snippet: str = "",
        schedule: str = "Полная занятость",
        published_at: str = ""
    ):
        self.title = title
        self.company = company
        self.platform = platform
        self.url = url
        self.salary = salary
        self.location = location
        self.snippet = snippet
        self.schedule = schedule
        self.published_at = published_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "company": self.company,
            "platform": self.platform,
            "url": self.url,
            "salary": self.salary,
            "location": self.location,
            "snippet": self.snippet,
            "schedule": self.schedule,
            "published_at": self.published_at
        }

class JobSearcher:
    """Мультиплатформенный поисковик вакансий по площадкам РФ"""

    def __init__(self):
        self.profile = load_profile_context(settings.PROFILE_CONTEXT_PATH)

    async def search_hh(
        self,
        query: str,
        remote_only: bool = False,
        no_experience_only: bool = False,
        limit: int = 10
    ) -> List[JobSearchResult]:
        """Поиск по HeadHunter через официальный открытый API"""
        params = {
            "text": query,
            "per_page": min(limit, 20),
            "order_by": "publication_time"
        }
        if remote_only:
            params["schedule"] = "remote"
        if no_experience_only:
            params["experience"] = "noExperience"
        else:
            params["experience"] = "between1And3"

        url = f"https://api.hh.ru/vacancies?{urllib.parse.urlencode(params)}"
        headers = {"User-Agent": "JobSearchAgent/2.0 (student-portfolio-project)"}

        results = []
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("items", [])
                        for it in items:
                            sal = "Не указана"
                            sal_data = it.get("salary")
                            if sal_data:
                                f = sal_data.get("from")
                                t = sal_data.get("to")
                                cur = sal_data.get("currency", "RUR")
                                if f and t:
                                    sal = f"{f} - {t} {cur}"
                                elif f:
                                    sal = f"от {f} {cur}"
                                elif t:
                                    sal = f"до {t} {cur}"

                            area = it.get("area", {}).get("name", "РФ")
                            sched = it.get("schedule", {}).get("name", "Полная занятость")
                            req = it.get("snippet", {}).get("requirement", "") or ""
                            resp_text = it.get("snippet", {}).get("responsibility", "") or ""
                            snippet = f"{req} {resp_text}".replace("<highlighttext>", "").replace("</highlighttext>", "").strip()

                            results.append(JobSearchResult(
                                title=it.get("name", "Вакансия"),
                                company=it.get("employer", {}).get("name", "Компания"),
                                platform="hh.ru",
                                url=it.get("alternate_url", ""),
                                salary=sal,
                                location=area,
                                snippet=snippet[:250],
                                schedule=sched,
                                published_at=it.get("published_at", "")[:10]
                            ))
                    elif resp.status == 403:
                        # Fallback: парсинг HTML выдачи hh.ru
                        logger.info("hh.ru API вернул 403, переключаемся на HTML веб-выдачу hh.ru...")
                        web_headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        }
                        web_url = f"https://hh.ru/search/vacancy?text={urllib.parse.quote(query)}"
                        async with session.get(web_url, headers=web_headers, timeout=aiohttp.ClientTimeout(total=8)) as web_resp:
                            if web_resp.status == 200:
                                html = await web_resp.text()
                                soup = BeautifulSoup(html, "html.parser")
                                cards = soup.select("[data-qa='vacancy-serp__vacancy']") or soup.select(".vacancy-card--z_46n7AGnTf2Zigo")
                                seen_keys = set()
                                for c in cards:
                                    if len(results) >= limit:
                                        break
                                    title_elem = c.select_one("[data-qa='serp-item__title']") or c.select_one("a.bloko-link")
                                    comp_elem = c.select_one("[data-qa='vacancy-serp__vacancy-employer']")
                                    sal_elem = c.select_one("[data-qa='vacancy-serp__vacancy-compensation']")
                                    loc_elem = c.select_one("[data-qa='vacancy-serp__vacancy-address']")
                                    req_elem = c.select_one("[data-qa='vacancy-serp__vacancy_snippet_requirement']")
                                    resp_elem = c.select_one("[data-qa='vacancy-serp__vacancy_snippet_responsibility']")

                                    if title_elem:
                                        t_text = title_elem.get_text(strip=True)
                                        t_href = title_elem.get("href", "").split("?")[0]
                                        c_text = comp_elem.get_text(strip=True) if comp_elem else "Компания"
                                        # Разделяем слипшиеся ООО/АО и имя компании
                                        c_text = re.sub(r"^(ООО|АО|ПАО|ЗАО)(?=[А-ЯA-Z0-9])", r"\1 ", c_text)
                                        s_text = sal_elem.get_text(strip=True) if sal_elem else "Не указана"
                                        l_text = loc_elem.get_text(strip=True) if loc_elem else "Россия"

                                        # Извлекаем реальный сниппет требований
                                        snip_parts = []
                                        if req_elem:
                                            snip_parts.append(req_elem.get_text(strip=True))
                                        if resp_elem:
                                            snip_parts.append(resp_elem.get_text(strip=True))
                                        snip_text = " ".join(snip_parts).strip() or "Подробности в описании вакансии"

                                        # Дедупликация по паре (компания, должность)
                                        dedup_key = (c_text.lower()[:20], t_text.lower()[:25])
                                        if dedup_key in seen_keys:
                                            continue
                                        seen_keys.add(dedup_key)

                                        results.append(JobSearchResult(
                                            title=t_text,
                                            company=c_text,
                                            platform="hh.ru",
                                            url=t_href if t_href.startswith("http") else f"https://hh.ru{t_href}",
                                            salary=s_text,
                                            location=l_text,
                                            snippet=snip_text[:250],
                                            schedule="Полная занятость"
                                        ))
        except Exception as e:
            logger.warning(f"Ошибка поиска hh.ru: {e}")

        return results

    async def search_trudvsem(
        self,
        query: str,
        limit: int = 8
    ) -> List[JobSearchResult]:
        """Поиск по порталу 'Работа России' (trudvsem.ru) через официальный открытый API"""
        url = f"http://opendata.trudvsem.ru/api/v1/vacancies?text={urllib.parse.quote(query)}&limit={limit}"
        headers = {"User-Agent": "Mozilla/5.0"}

        results = []
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        vacancies = data.get("results", {}).get("vacancies", [])
                        for v_wrap in vacancies:
                            v = v_wrap.get("vacancy", {})
                            duty = v.get("duty", "") or ""
                            results.append(JobSearchResult(
                                title=v.get("job-name", "Вакансия"),
                                company=v.get("company", {}).get("name", "Предприятие / Организация"),
                                platform="Работа России (trudvsem)",
                                url=v.get("vac_url", ""),
                                salary=f"от {v.get('salary_min', 0)} до {v.get('salary_max', 0)} руб.",
                                location=v.get("region", {}).get("name", "РФ"),
                                snippet=duty[:250],
                                schedule=v.get("schedule", "Полная занятость")
                            ))
        except Exception as e:
            logger.warning(f"Ошибка поиска trudvsem.ru: {e}")

        return results

    async def search_habr_career(
        self,
        query: str,
        limit: int = 8
    ) -> List[JobSearchResult]:
        """Поиск по Хабр Карьере (аккредитованные IT-компании, стажировки)"""
        encoded_q = urllib.parse.quote(query)
        url = f"https://career.habr.com/vacancies?q={encoded_q}&type=all"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

        results = []
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, "html.parser")
                        cards = soup.select(".vacancy-card")
                        for card in cards[:limit]:
                            title_elem = card.select_one(".vacancy-card__title a")
                            company_elem = card.select_one(".vacancy-card__company-title a")
                            salary_elem = card.select_one(".vacancy-card__salary")
                            meta_elem = card.select_one(".vacancy-card__meta")

                            if title_elem:
                                title = title_elem.get_text(strip=True)
                                link = "https://career.habr.com" + title_elem.get("href", "")
                                company = company_elem.get_text(strip=True) if company_elem else "IT-компания"
                                salary = salary_elem.get_text(strip=True) if salary_elem else "Не указана"
                                meta = meta_elem.get_text(strip=True) if meta_elem else ""

                                results.append(JobSearchResult(
                                    title=title,
                                    company=company,
                                    platform="Хабр Карьера",
                                    url=link,
                                    salary=salary,
                                    location=meta or "РФ",
                                    snippet="Аккредитованная IT-компания на Хабр Карьере",
                                    schedule="Удаленно / Офис"
                                ))
        except Exception as e:
            logger.warning(f"Ошибка поиска Хабр Карьера: {e}")

        return results

    def get_corporate_internships(self) -> List[Dict[str, Any]]:
        """Возвращает каталог программ корпоративных стажировок (Сбер, Т-Банк, ИнфоТеКС, Яндекс и др.)"""
        return self.profile.get("corporate_internships_catalog", [])

    def get_recommended_telegram_channels(self) -> List[Dict[str, str]]:
        """Возвращает проверенные Telegram-каналы для Junior-вакансий и заказов на ботов/AI"""
        return [
            {
                "name": "Junior IT Вакансии / Джуниор разработчик",
                "link": "https://t.me/forjunior",
                "focus": "Junior Python, Backend, стажировки"
            },
            {
                "name": "Хабр Карьера — Вакансии",
                "link": "https://t.me/habr_career",
                "focus": "Аккредитованные IT-компании, стажировки и Junior"
            },
            {
                "name": "Заказы на чат-ботов и AI-автоматизацию",
                "link": "https://t.me/freelance_chatbots",
                "focus": "Фриланс-заказы на ботов (Telegram/aiogram), no-code и интеграции нейросетей"
            },
            {
                "name": "IT-стажировки в корпорациях (Сбер, Т-Банк, Яндекс, ИнфоТеКС)",
                "link": "https://t.me/it_internships_ru",
                "focus": "Отборы на оплачиваемые стажировки для студентов и выпускников СПО/ВУЗов"
            }
        ]

    def get_starter_roles(self) -> Dict[str, Any]:
        """Возвращает ролевую матрицу для старта карьеры"""
        return self.profile.get("starter_roles_matrix", {})

    def get_three_resumes(self) -> Dict[str, Any]:
        """Возвращает 3 базовых резюме под основные направления"""
        return self.profile.get("three_resume_templates", {})

    def get_dual_resumes(self) -> Dict[str, Any]:
        """Возвращает шаблоны резюме (для совместимости)"""
        return self.profile.get("three_resume_templates", {}) or self.profile.get("dual_resume_templates", {})

    async def search_all(
        self,
        query: str,
        remote_only: bool = False,
        limit_per_source: int = 5
    ) -> Dict[str, List[JobSearchResult]]:
        """Параллельный поиск по всем ключевым площадкам РФ"""
        hh_task = self.search_hh(query, remote_only=remote_only, limit=limit_per_source)
        trud_task = self.search_trudvsem(query, limit=limit_per_source)
        habr_task = self.search_habr_career(query, limit=limit_per_source)

        import asyncio
        hh_res, trud_res, habr_res = await asyncio.gather(
            hh_task, trud_task, habr_task, return_exceptions=True
        )

        return {
            "hh": hh_res if isinstance(hh_res, list) else [],
            "trudvsem": trud_res if isinstance(trud_res, list) else [],
            "habr": habr_res if isinstance(habr_res, list) else []
        }
