from __future__ import annotations

import base64
import json
from typing import Any

import aiohttp

from zukko.models import Explanation, Intent, LessonPackage, QuizQuestion


class GeminiError(RuntimeError):
    pass


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        session: aiohttp.ClientSession,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.session = session
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def route(self, text: str) -> Intent:
        prompt = f"""
Sen O'zbekiston maktablari uchun intent routersan. O'quvchi xabaridan sinf, fan va
mavzuni ajrat. Sinf aytilmagan bo'lsa mavzuga mos eng ehtimolli sinfni tanla.
topic_key faqat lotincha kichik harf va pastki chiziqdan iborat bo'lsin.

Xabar: {text!r}

Faqat quyidagi JSON shaklini qaytar:
{{"grade": 8, "subject": "algebra", "topic": "kvadrat ildiz", "topic_key": "kvadrat_ildiz"}}
"""
        data = await self._generate_json(prompt)
        return Intent.model_validate(data)

    async def build_lesson(self, intent: Intent) -> LessonPackage:
        prompt = f"""
Sen mehribon, aniq va qisqa O'zbekcha repetitorsan. {intent.grade}-sinf,
{intent.subject} fanidagi "{intent.topic}" mavzusi uchun dars yarat.

Talablar:
- explanation aynan uch qism: hayotiy metaphor, qisqa formula/qoida, real hayot misoli;
- podcast_text tabiiy og'zaki O'zbekcha, taxminan 30-40 soniyada o'qiladigan 65-90 so'z;
- quiz aynan 3 ta, osondan qiyinga; har birida A/B/C/D variant;
- har bir XATO variantning misconception maydonida bola nega shuni tanlaganini aniq
  taxmin qil, so'ng noto'g'ri fikrni sodda tuzat;
- to'g'ri variant misconception=null;
- matematik belgilarda Telegram HTML emas, oddiy Unicode/Markdown ishlat.

Faqat JSON qaytar:
{{
  "explanation": {{"metaphor":"...", "rule":"...", "real_life":"..."}},
  "podcast_text":"...",
  "quiz":[
    {{"prompt":"...", "options":[
      {{"label":"A","text":"...","misconception":"..."}},
      {{"label":"B","text":"...","misconception":null}},
      {{"label":"C","text":"...","misconception":"..."}},
      {{"label":"D","text":"...","misconception":"..."}}
    ], "correct":"B", "success_feedback":"..."}}
  ]
}}
"""
        data = await self._generate_json(prompt)
        explanation = Explanation.model_validate(data["explanation"])
        quiz = [QuizQuestion.model_validate(item) for item in data["quiz"]]
        return LessonPackage(
            intent=intent,
            explanation=explanation,
            podcast_text=data["podcast_text"],
            quiz=quiz,
            source="ai",
        )

    async def transcribe(self, audio: bytes, mime_type: str = "audio/ogg") -> str:
        prompt = (
            "Bu o'zbek tilidagi o'quvchi ovozli xabari. Uni aniq matnga ko'chir. "
            "Faqat transkripsiyani qaytar, izoh yozma."
        )
        payload = {
            "contents": [{
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {"inline_data": {
                        "mime_type": mime_type,
                        "data": base64.b64encode(audio).decode("ascii"),
                    }},
                ],
            }],
            "generationConfig": {"temperature": 0.1},
        }
        return (await self._request(payload)).strip()

    async def _generate_json(self, prompt: str) -> dict[str, Any]:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.35,
                "responseMimeType": "application/json",
            },
        }
        text = await self._request(payload)
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GeminiError("Gemini yaroqsiz JSON qaytardi") from exc
        if not isinstance(value, dict):
            raise GeminiError("Gemini JSON obyekti qaytarmadi")
        return value

    async def _request(self, payload: dict[str, Any]) -> str:
        if not self.enabled:
            raise GeminiError("GEMINI_API_KEY sozlanmagan")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        try:
            async with self.session.post(
                url,
                params={"key": self.api_key},
                json=payload,
                timeout=self.timeout,
            ) as response:
                if response.status >= 400:
                    detail = (await response.text())[:300]
                    raise GeminiError(f"Gemini HTTP {response.status}: {detail}")
                result = await response.json()
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise GeminiError(f"Gemini bilan aloqa uzildi: {exc}") from exc

        try:
            parts = result["candidates"][0]["content"]["parts"]
            answer = "".join(
                part["text"] for part in parts if "text" in part and not part.get("thought")
            )
            if answer:
                return answer
            raise KeyError("text")
        except (KeyError, IndexError, TypeError) as exc:
            raise GeminiError("Gemini javobida matn topilmadi") from exc

