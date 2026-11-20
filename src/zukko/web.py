"""Zukko web app: the same lessons, audio and diagnostics as the Telegram bot."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from typing import Annotated
from uuid import uuid4

import aiohttp
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from zukko.config import Settings, load_settings
from zukko.database import Database, InMemoryLessonStore
from zukko.handlers import Dependencies, _resolve_lesson
from zukko.models import LessonPackage, evaluate_answer
from zukko.services import GeminiClient, GeminiError, OfflineRepository, TTSService

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "web_static"
SESSION_TTL_SECONDS = 60 * 60
MAX_WEB_SESSIONS = 2048


class LessonRequest(BaseModel):
    text: str = Field(min_length=2, max_length=2000)


class AnswerRequest(BaseModel):
    lesson_id: str
    question_index: int = Field(ge=0, le=2)
    selected: str = Field(pattern=r"^[ABCD]$")


def _question_payload(lesson: LessonPackage, index: int) -> dict:
    question = lesson.quiz[index]
    return {
        "index": index,
        "prompt": question.prompt,
        "options": [{"label": option.label, "text": option.text} for option in question.options],
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database = Database(config.database_path)
        await database.initialize()
        offline = OfflineRepository()
        session = aiohttp.ClientSession()
        app.state.deps = Dependencies(
            gemini=GeminiClient(
                config.gemini_api_key, config.gemini_model,
                config.api_timeout_seconds, session,
            ),
            offline=offline,
            tts=TTSService(config.cache_dir, config.tts_voice),
            database=database,
            lessons=InMemoryLessonStore(),
        )
        app.state.web_lessons = {}
        try:
            yield
        finally:
            await session.close()

    app = FastAPI(title="Zukko", lifespan=lifespan)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/styles.css")
    async def styles() -> FileResponse:
        return FileResponse(STATIC_DIR / "styles.css", media_type="text/css")

    @app.get("/app.js")
    async def script() -> FileResponse:
        return FileResponse(STATIC_DIR / "app.js", media_type="application/javascript")

    @app.get("/api/topics")
    async def topics() -> list[dict]:
        repository: OfflineRepository = app.state.deps.offline
        return [
            {
                "key": key,
                "title": repository.get(key).intent.topic,
                "subject": repository.get(key).intent.subject,
                "grade": repository.get(key).intent.grade,
            }
            for key in repository.topic_keys
        ]

    @app.get("/api/status")
    async def status() -> dict:
        return {
            "gemini_configured": app.state.deps.gemini.enabled,
            "offline_topics": len(app.state.deps.offline.topic_keys),
        }

    @app.get("/api/analytics")
    async def analytics() -> dict:
        database: Database = app.state.deps.database
        return await database.get_analytics(user_id=0)

    @app.post("/api/reset-analytics")
    async def reset_analytics() -> dict:
        database: Database = app.state.deps.database
        await database.reset_attempts(user_id=0)
        return {"status": "ok"}

    @app.get("/api/summary/{lesson_id}")
    async def summary(lesson_id: str) -> PlainTextResponse:
        session = app.state.web_lessons.get(lesson_id)
        if session is None or monotonic() - session["created_at"] >= SESSION_TTL_SECONDS:
            raise HTTPException(status_code=404, detail="Dars topilmadi")
        lesson: LessonPackage = session["lesson"]
        intent = lesson.intent
        exp = lesson.explanation
        content = f"""# {intent.topic} ({intent.grade}-sinf, {intent.subject})
*Zukko Feynman uslubidagi konspekt*

---

## 1. Tasavvur qil (Metaphor)
{exp.metaphor}

## 2. Qoida va formula (Rule)
{exp.rule}

## 3. Hayotda qayerda kerak? (Real life)
{exp.real_life}

---

## 4. Ovozli xulosa
{lesson.podcast_text}

---
*Yaratildi: Zukko AI repetitori*
"""
        return PlainTextResponse(
            content=content,
            headers={
                "Content-Disposition": f'attachment; filename="zukko_{intent.topic_key}.md"',
                "Content-Type": "text/markdown; charset=utf-8",
            },
        )

    async def package_lesson(text: str) -> dict:
        deps: Dependencies = app.state.deps
        lesson = await _resolve_lesson(text, deps)
        if lesson is None:
            raise HTTPException(
                status_code=503,
                detail="Bu mavzu hozir topilmadi. Tayyor mavzulardan birini tanlang.",
            )
        lesson_id = uuid4().hex
        now = monotonic()
        sessions = app.state.web_lessons
        for old_id, old_session in list(sessions.items()):
            if now - old_session["created_at"] >= SESSION_TTL_SECONDS:
                del sessions[old_id]
        if len(sessions) >= MAX_WEB_SESSIONS:
            oldest_id = min(sessions, key=lambda key: sessions[key]["created_at"])
            del sessions[oldest_id]
        sessions[lesson_id] = {
            "lesson": lesson,
            "next_index": 0,
            "correct_count": 0,
            "first_mistake": None,
            "created_at": now,
        }
        return {
            "lesson_id": lesson_id,
            "intent": lesson.intent.model_dump(),
            "explanation": lesson.explanation.model_dump(),
            "podcast_text": lesson.podcast_text,
            "source": lesson.source,
            "question": _question_payload(lesson, 0),
        }

    @app.post("/api/lesson")
    async def lesson_route(request: LessonRequest) -> dict:
        return await package_lesson(request.text)

    @app.post("/api/voice")
    async def voice_route(
        audio: Annotated[UploadFile, File()],
        mime_type: Annotated[str, Form()] = "audio/webm",
    ) -> dict:
        deps: Dependencies = app.state.deps
        if not deps.gemini.enabled:
            raise HTTPException(status_code=503, detail="Ovozni tanish uchun Gemini API kerak.")
        content = await audio.read(8_000_001)
        if len(content) > 8_000_000:
            raise HTTPException(status_code=413, detail="Ovozli xabar 8 MB dan kichik bo‘lsin.")
        if not content:
            raise HTTPException(status_code=400, detail="Ovozli xabar bo‘sh.")
        try:
            transcript = await deps.gemini.transcribe(content, mime_type)
        except GeminiError as exc:
            logger.warning("Web transcription failed: %s", exc)
            raise HTTPException(
                status_code=503, detail="Ovoz tanilmadi. Matn yozib ko‘ring."
            ) from exc
        result = await package_lesson(transcript)
        result["transcript"] = transcript
        return result

    @app.get("/api/audio/{lesson_id}")
    async def audio_route(lesson_id: str) -> FileResponse:
        session = app.state.web_lessons.get(lesson_id)
        if session is None or monotonic() - session["created_at"] >= SESSION_TTL_SECONDS:
            raise HTTPException(status_code=404, detail="Dars topilmadi")
        try:
            audio_path = await app.state.deps.tts.synthesize(session["lesson"].podcast_text)
        except Exception as exc:
            logger.warning("Web TTS failed: %s", exc)
            raise HTTPException(status_code=503, detail="Audio hozir tayyor emas.") from exc
        return FileResponse(audio_path, media_type="audio/mpeg")

    @app.post("/api/answer")
    async def answer_route(request: AnswerRequest) -> dict:
        session = app.state.web_lessons.get(request.lesson_id)
        if session is None or monotonic() - session["created_at"] >= SESSION_TTL_SECONDS:
            raise HTTPException(status_code=404, detail="Dars topilmadi")
        if request.question_index != session["next_index"]:
            raise HTTPException(status_code=409, detail="Bu savolga javob berilgan")
        lesson: LessonPackage = session["lesson"]
        question = lesson.quiz[request.question_index]
        result = evaluate_answer(question, request.selected)
        session["next_index"] += 1
        if result.is_correct:
            session["correct_count"] += 1
        elif session["first_mistake"] is None:
            session["first_mistake"] = result.feedback
        await app.state.deps.database.record_attempt(
            0, lesson.intent.topic_key, request.question_index,
            request.selected, result.is_correct,
        )
        next_index = session["next_index"]
        response = {
            "is_correct": result.is_correct,
            "feedback": result.feedback,
            "correct_label": result.correct_label,
            "correct_text": result.correct_text,
            "question": _question_payload(lesson, next_index) if next_index < 3 else None,
            "finished": next_index == 3,
            "summary": (
                {
                    "score": session["correct_count"],
                    "total": 3,
                    "review_tip": session["first_mistake"],
                }
                if next_index == 3 else None
            ),
        }
        return response

    return app


def run() -> None:
    import uvicorn

    uvicorn.run("zukko.web:create_app", factory=True, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run()
