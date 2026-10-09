import json
import logging
import re
from typing import Type, TypeVar, Optional, Any
from pydantic import BaseModel
from config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

def clean_json_string(raw: str) -> str:
    """Удаляет markdown блоки ```json ... ``` и лишние пробелы"""
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if match:
        return match.group(1).strip()
    return raw

def is_reasoning_model(model_name: str) -> bool:
    """Определяет, является ли модель reasoning-моделью (gpt-6, o1, o3, luna и др.)"""
    m = model_name.lower()
    return any(prefix in m for prefix in ["gpt-6", "luna", "o1", "o3", "reasoning"])

class LLMService:
    def __init__(self, system_instruction: str = ""):
        self.system_instruction = system_instruction
        self._detect_provider()
        self._gemini_client = None
        self._openai_client = None

        self._init_clients()

    def _detect_provider(self):
        """Определяет активного провайдера на основе настроек и наличия ключей"""
        configured_provider = (settings.LLM_PROVIDER or "").lower().strip()

        if configured_provider in ("openai", "chatgpt"):
            self.provider = "openai"
        elif configured_provider in ("gemini", "google"):
            self.provider = "gemini"
        elif settings.OPENAI_API_KEY:
            self.provider = "openai"
        elif settings.GEMINI_API_KEY:
            self.provider = "gemini"
        else:
            self.provider = "openai" if settings.OPENAI_API_KEY else "gemini"

    def _init_clients(self):
        if self.provider == "openai":
            api_key = settings.OPENAI_API_KEY
            if api_key:
                try:
                    from openai import AsyncOpenAI
                    self._openai_client = AsyncOpenAI(
                        api_key=api_key,
                        base_url=settings.OPENAI_BASE_URL
                    )
                    logger.info(
                        f"OpenAI client инициализирован (модель: {settings.OPENAI_MODEL}, "
                        f"reasoning_effort: {settings.OPENAI_REASONING_EFFORT}, URL: {settings.OPENAI_BASE_URL})"
                    )
                except Exception as e:
                    logger.error(f"Ошибка инициализации OpenAI client: {e}")
        elif self.provider == "gemini":
            api_key = settings.GEMINI_API_KEY
            if api_key:
                try:
                    from google import genai
                    self._gemini_client = genai.Client(api_key=api_key)
                    logger.info(f"Gemini client инициализирован (модель: {settings.GEMINI_MODEL})")
                except Exception as e:
                    logger.warning(f"Ошибка инициализации google-genai Client: {e}")
                    try:
                        import google.generativeai as gai
                        gai.configure(api_key=api_key)
                        self._gemini_client = "legacy"
                    except Exception as e2:
                        logger.error(f"Не удалось инициализировать Gemini: {e2}")

    async def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        """Генерирует структурированный ответ и валидирует через Pydantic схему"""
        raw_text = await self.generate_text(prompt, is_json=True)
        cleaned = clean_json_string(raw_text)
        try:
            data = json.loads(cleaned)
            return schema.model_validate(data)
        except Exception as e:
            logger.error(f"Ошибка парсинга JSON ответа: {e}\nСырой текст:\n{raw_text}")
            raise ValueError(f"Не удалось распарсить структурированный ответ от LLM: {e}")

    async def generate_text(self, prompt: str, is_json: bool = False) -> str:
        """Асинхронная генерация текстового ответа от LLM (Gemini или OpenAI)"""
        if self.provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError(
                    "❌ OPENAI_API_KEY не задан в .env файле!\n"
                    "Укажите ваш ключ OpenAI в .env (OPENAI_API_KEY=sk-...).\n"
                    "Либо переключитесь на Gemini (LLM_PROVIDER=gemini) и задайте GEMINI_API_KEY."
                )
            return await self._call_openai(prompt, is_json=is_json)
        elif self.provider == "gemini":
            if not settings.GEMINI_API_KEY:
                raise ValueError(
                    "❌ GEMINI_API_KEY не задан в .env файле!\n"
                    "Укажите ваш ключ в .env (GEMINI_API_KEY=...).\n"
                    "Либо переключитесь на OpenAI (LLM_PROVIDER=openai) и задайте OPENAI_API_KEY=sk-..."
                )
            return await self._call_gemini(prompt)
        else:
            raise ValueError(f"Неизвестный провайдер LLM: {self.provider}")

    async def _call_openai(self, prompt: str, is_json: bool = False) -> str:
        if not self._openai_client:
            self._init_clients()
            if not self._openai_client:
                raise ValueError("Клиент OpenAI не инициализирован. Проверьте OPENAI_API_KEY.")

        client = self._openai_client
        model = settings.OPENAI_MODEL
        reasoning = is_reasoning_model(model)

        messages = []
        sys_prompt = self.system_instruction or ""
        if is_json and "json" not in sys_prompt.lower():
            sys_prompt += "\nОтвечай строго в формате JSON."

        if sys_prompt:
            # Некоторые reasoning-модели предпочитают developer роль или system
            messages.append({"role": "system", "content": sys_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        # Настройка reasoning_effort и temperature:
        # Для reasoning моделей (gpt-6-luna, o1, o3) задаем reasoning_effort,
        # а параметр temperature не передается во избежание ошибки 400
        if reasoning:
            effort = settings.OPENAI_REASONING_EFFORT.lower().strip()
            if effort in ("low", "medium", "high"):
                kwargs["reasoning_effort"] = effort
        else:
            kwargs["temperature"] = 0.3

        if is_json:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception as e:
            err_msg = str(e).lower()
            # Graceful retry если провайдер отклонил reasoning_effort или response_format
            if "reasoning_effort" in err_msg and "reasoning_effort" in kwargs:
                logger.warning("Модель не приняла параметр reasoning_effort, повтор без него...")
                kwargs.pop("reasoning_effort", None)
                kwargs["temperature"] = 0.3
                response = await client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""
            elif "temperature" in err_msg and "temperature" in kwargs:
                logger.warning("Модель не поддерживает temperature, повтор без нее...")
                kwargs.pop("temperature", None)
                response = await client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""

            logger.error(f"OpenAI Chat GPT API error: {e}")
            raise

    async def _call_gemini(self, prompt: str) -> str:
        from google import genai
        from google.genai import types

        model_name = settings.GEMINI_MODEL
        try:
            client: genai.Client = self._gemini_client
            if client == "legacy":
                import google.generativeai as gai
                model = gai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=self.system_instruction or None
                )
                response = await model.generate_content_async(prompt)
                return response.text
            else:
                config = types.GenerateContentConfig(
                    system_instruction=self.system_instruction or None,
                    temperature=0.3,
                )
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config
                )
                return response.text
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise
