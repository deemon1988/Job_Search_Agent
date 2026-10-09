import json
import logging
import re
from typing import Optional, Dict, Any
import aiohttp
from bs4 import BeautifulSoup

from agent.models import ParsedJob
from agent.llm import LLMService

logger = logging.getLogger(__name__)

PARSER_PROMPT = """Ты — экспертный парсер вакансий. Извлеки структурированную информацию из приведенного текста вакансии.

Текст вакансии:
\"\"\"{job_text}\"\"\"

Дополнительный контекст URL: {url}
Платформа: {platform}

Извлеки следующие поля строго в формате JSON:
{{
  "title": "Точное название должности",
  "company": "Название компании (если не найдено, указать 'Компания')",
  "platform": "{platform}",
  "url": "{url}",
  "salary_raw": "Зарплатная вилка (например, 'от 70 000 руб.' или 'Не указана')",
  "employment_type": "Удаленная работа / Офис / Гибрид / Полная занятость",
  "location": "Город или 'Удаленно'",
  "grade": "Стажер / Junior / Junior+ / Middle / Не указан",
  "key_skills": ["Python", "Django", "PostgreSQL", "Git"],
  "responsibilities": ["Обязанность 1", "Обязанность 2"],
  "requirements_hard": ["Требование Hard Skill 1", "Требование 2"],
  "requirements_soft": ["Командная работа", "Самостоятельность"],
  "benefits": ["ДМС", "Гибкий график", "Обучение"],
  "recruiter_name": "Имя рекрутера/контакта (если указано, иначе null)",
  "raw_text": ""
}}
"""

class JobParser:
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm = llm_service or LLMService()

    def detect_platform(self, text_or_url: str) -> str:
        s = text_or_url.lower()
        if "hh.ru" in s or "headhunter" in s:
            return "hh.ru"
        elif "superjob.ru" in s:
            return "SuperJob"
        elif "habr.com" in s or "career.habr" in s:
            return "Хабр Карьера"
        elif "trudvsem.ru" in s:
            return "Работа России"
        elif "t.me" in s or "telegram" in s:
            return "Telegram"
        return "Прямой источник"

    async def parse_hh_api(self, vacancy_id: str, original_url: str) -> Optional[ParsedJob]:
        """Использует публичный REST API HeadHunter (не требует авторизации)"""
        api_url = f"https://api.hh.ru/vacancies/{vacancy_id}"
        headers = {"User-Agent": "JobSearchAgent/2.0 (student-portfolio-project)"}

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status != 200:
                        logger.warning(f"hh.ru API вернул статус {resp.status}")
                        return None
                    data = await resp.json()

            # Извлекаем данные
            title = data.get("name", "")
            employer = data.get("employer", {}).get("name", "Компания")

            # Зарплата
            sal_data = data.get("salary")
            salary_raw = "Не указана"
            if sal_data:
                f = sal_data.get("from")
                t = sal_data.get("to")
                cur = sal_data.get("currency", "RUR")
                if f and t:
                    salary_raw = f"{f} - {t} {cur}"
                elif f:
                    salary_raw = f"от {f} {cur}"
                elif t:
                    salary_raw = f"до {t} {cur}"

            # График и занятость
            schedule = data.get("schedule", {}).get("name", "")
            employment = data.get("employment", {}).get("name", "")
            emp_type = f"{schedule}, {employment}".strip(", ") or "Полная занятость"

            # Навыки
            skills = [s.get("name") for s in data.get("key_skills", []) if s.get("name")]

            # Очистка HTML описания
            desc_html = data.get("description", "")
            soup = BeautifulSoup(desc_html, "html.parser")
            clean_desc = soup.get_text(separator="\n").strip()

            area = data.get("area", {}).get("name", "")
            grade = "Junior"
            exp = data.get("experience", {}).get("name", "")
            if "нет опыта" in exp.lower() or "стажер" in title.lower():
                grade = "Стажер / Junior"
            elif "1–3 года" in exp.lower() or "1-3 года" in exp.lower():
                grade = "Junior / Junior+"
            elif "3–6 лет" in exp.lower():
                grade = "Middle"

            parsed = ParsedJob(
                title=title,
                company=employer,
                platform="hh.ru",
                url=original_url,
                salary_raw=salary_raw,
                employment_type=emp_type,
                location=area,
                grade=grade,
                key_skills=skills,
                responsibilities=[],
                requirements_hard=[f"Опыт: {exp}"] if exp else [],
                requirements_soft=[],
                benefits=[],
                raw_text=clean_desc
            )
            return parsed
        except Exception as e:
            logger.warning(f"Ошибка парсинга через hh.ru API: {e}")
            return None

    async def fetch_web_text(self, url: str) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        jar = aiohttp.CookieJar(unsafe=True)
        try:
            async with aiohttp.ClientSession(headers=headers, cookie_jar=jar) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, "html.parser")

                        # Специальная обработка для hh.ru
                        if "hh.ru" in url:
                            title_el = soup.find("h1")
                            title = title_el.get_text(strip=True) if title_el else ""
                            comp_el = soup.find(attrs={"data-qa": "vacancy-company-name"}) or soup.find(class_=re.compile("vacancy-company-name"))
                            comp = comp_el.get_text(strip=True) if comp_el else ""
                            sal_el = soup.find(attrs={"data-qa": "vacancy-salary"}) or soup.find(attrs={"data-qa": "vacancy-salary-compensation-type-net"})
                            sal = sal_el.get_text(strip=True) if sal_el else "Не указана"
                            desc_el = soup.find("div", class_=re.compile("vacancy-description")) or soup.find(attrs={"data-qa": "vacancy-description"})
                            desc = desc_el.get_text(separator="\n", strip=True) if desc_el else ""
                            skills = [s.get_text(strip=True) for s in soup.find_all(attrs={"data-qa": "bloko-tag__text"})]
                            skills_str = ", ".join(skills) if skills else ""

                            full_content = f"Вакансия: {title}\nКомпания: {comp}\nЗарплата: {sal}\n"
                            if skills_str:
                                full_content += f"Ключевые навыки: {skills_str}\n"
                            full_content += f"\nОписание вакансии:\n{desc}"
                            if len(full_content.strip()) > 80:
                                return full_content

                        # Очистка скриптов и навигации для универсальных страниц
                        for t in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
                            t.decompose()
                        text = soup.get_text(separator="\n")
                        lines = [line.strip() for line in text.splitlines() if line.strip()]
                        return "\n".join(lines[:300])
        except Exception as e:
            logger.warning(f"Ошибка загрузки HTML страницы {url}: {e}")
        return ""

    async def parse(self, text_or_url: str, url: Optional[str] = None) -> ParsedJob:
        text = text_or_url.strip()
        detected_url = url

        # 1. Проверяем, передан ли URL
        if not detected_url:
            url_match = re.search(r"https?://[^\s]+", text)
            if url_match:
                detected_url = url_match.group(0)

        # Очищаем URL от трекинговых параметров hh.ru
        canonical_url = detected_url
        if canonical_url and "hh.ru" in canonical_url:
            hh_id_match = re.search(r"/vacancy/(\d+)", canonical_url)
            if hh_id_match:
                canonical_url = f"https://hh.ru/vacancy/{hh_id_match.group(1)}"

        platform = self.detect_platform(canonical_url or detected_url or text)

        # 2. Попытка распарсить через официальный hh API при наличии hh.ru ссылки
        if canonical_url and "hh.ru" in canonical_url:
            hh_id_match = re.search(r"/vacancy/(\d+)", canonical_url)
            if hh_id_match:
                vacancy_id = hh_id_match.group(1)
                parsed = await self.parse_hh_api(vacancy_id, canonical_url)
                if parsed and parsed.raw_text:
                    # Дообогащаем через LLM для извлечения обязанностей и требований
                    prompt = PARSER_PROMPT.format(
                        job_text=parsed.raw_text[:3500],
                        url=canonical_url,
                        platform="hh.ru"
                    )
                    try:
                        llm_enriched = await self.llm.generate_structured(prompt, ParsedJob)
                        llm_enriched.url = canonical_url
                        llm_enriched.platform = "hh.ru"
                        if not llm_enriched.company or llm_enriched.company == "Компания":
                            llm_enriched.company = parsed.company
                        if not llm_enriched.title:
                            llm_enriched.title = parsed.title
                        if not llm_enriched.salary_raw:
                            llm_enriched.salary_raw = parsed.salary_raw
                        if not llm_enriched.key_skills and parsed.key_skills:
                            llm_enriched.key_skills = parsed.key_skills
                        llm_enriched.raw_text = parsed.raw_text
                        return llm_enriched
                    except Exception as e:
                        logger.warning(f"Ошибка LLM-обогащения: {e}")
                        return parsed

        # 3. Если hh API вернул ошибку (например, 403) или передан URL другого сайта:
        # Проверяем, состоит ли отправленный текст преимущественно из URL
        text_without_urls = re.sub(r"https?://[^\s]+", "", text).strip()
        target_fetch_url = canonical_url or detected_url
        if target_fetch_url and len(text_without_urls) < 40:
            web_text = await self.fetch_web_text(target_fetch_url)
            if len(web_text) > 50:
                text = web_text

        # 4. Универсальный LLM парсинг текста вакансии
        prompt = PARSER_PROMPT.format(
            job_text=text[:4000],
            url=canonical_url or detected_url or "",
            platform=platform
        )
        parsed_job: ParsedJob = await self.llm.generate_structured(prompt, ParsedJob)
        parsed_job.raw_text = text
        if canonical_url or detected_url:
            parsed_job.url = canonical_url or detected_url
        parsed_job.platform = platform
        return parsed_job

