from __future__ import annotations

import base64
import json

import pytest

from zukko.models import evaluate_answer
from zukko.services.gemini import GeminiClient
from zukko.services.offline import OfflineRepository


class FakeResponse:
    status = 200

    def __init__(self, text: str) -> None:
        self.text = text

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    async def json(self) -> dict:
        return {"candidates": [{"content": {"parts": [{"text": self.text}]}}]}


class FakeSession:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.requests: list[tuple[str, dict]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.requests.append((url, kwargs))
        return FakeResponse(next(self.responses))


@pytest.mark.asyncio
async def test_gemini_voice_to_diagnostic_lesson_contract() -> None:
    sample = OfflineRepository().get("kvadrat_ildiz")
    assert sample is not None
    session = FakeSession([
        "8-sinfman, kvadrat ildizni tushunmayapman",
        json.dumps(sample.intent.model_dump(), ensure_ascii=False),
        json.dumps(sample.model_dump(exclude={"intent", "source"}), ensure_ascii=False),
    ])
    gemini = GeminiClient("test-key", "gemini-3.8-flash", 12, session)  # type: ignore[arg-type]

    transcript = await gemini.transcribe(b"OggS-voice", "audio/ogg")
    intent = await gemini.route(transcript)
    lesson = await gemini.build_lesson(intent)

    assert transcript == "8-sinfman, kvadrat ildizni tushunmayapman"
    assert intent.grade == 8
    assert lesson.source == "ai"
    assert len(lesson.quiz) == 3
    assert not evaluate_answer(lesson.quiz[0], "A").is_correct
    assert "2 ga bo‘lding" in evaluate_answer(lesson.quiz[0], "A").feedback
    assert all(url.endswith("/gemini-3.8-flash:generateContent") for url, _ in session.requests)
    assert all(kwargs["params"] == {"key": "test-key"} for _, kwargs in session.requests)
    voice_part = session.requests[0][1]["json"]["contents"][0]["parts"][1]
    assert voice_part["inline_data"]["mime_type"] == "audio/ogg"
    assert base64.b64decode(voice_part["inline_data"]["data"]) == b"OggS-voice"
    json_config = session.requests[1][1]["json"]["generationConfig"]
    assert json_config["responseMimeType"] == "application/json"
