from __future__ import annotations

from pathlib import Path
from time import perf_counter

import pytest

from zukko.database import Database, InMemoryLessonStore
from zukko.handlers import Dependencies, _resolve_lesson
from zukko.models import evaluate_answer
from zukko.services.offline import OfflineRepository


def test_all_ten_offline_topics_have_three_diagnostic_questions() -> None:
    repository = OfflineRepository()
    assert len(repository.topic_keys) == 10
    for key in repository.topic_keys:
        lesson = repository.get(key)
        assert lesson is not None
        assert lesson.source == "offline"
        assert len(lesson.quiz) == 3
        for question in lesson.quiz:
            wrong = [option for option in question.options if option.label != question.correct]
            assert len(wrong) == 3
            assert all(option.misconception and len(option.misconception) > 20 for option in wrong)
            assert question.option(question.correct).misconception is None


def test_kvadrat_ildiz_misconception_and_grade() -> None:
    repository = OfflineRepository()
    intent = repository.local_intent("8-sinfman, kvadrat ildiz nimaligini tushunmayapman")
    assert intent is not None
    assert intent.model_dump() == {
        "grade": 8,
        "subject": "algebra",
        "topic": "kvadrat ildiz",
        "topic_key": "kvadrat_ildiz",
    }
    lesson = repository.get("kvadrat_ildiz")
    assert lesson is not None
    answer = evaluate_answer(lesson.quiz[0], "A")
    assert not answer.is_correct
    assert "2 ga bo‘lding" in answer.feedback
    assert answer.correct_label == "B"


@pytest.mark.asyncio
async def test_known_topic_uses_offline_immediately_even_if_gemini_is_broken(
    tmp_path: Path,
) -> None:
    class BrokenGemini:
        enabled = True

        async def route(self, _: str) -> None:
            raise AssertionError("Known topic must not wait for API")

    class UnusedTTS:
        pass

    deps = Dependencies(
        gemini=BrokenGemini(),  # type: ignore[arg-type]
        offline=OfflineRepository(),
        tts=UnusedTTS(),  # type: ignore[arg-type]
        database=Database(tmp_path / "attempts.db"),
        lessons=InMemoryLessonStore(),
    )
    started = perf_counter()
    lesson = await _resolve_lesson("8-sinfman, kvadrat ildizni tushunmayapman", deps)
    assert perf_counter() - started < 0.1
    assert lesson is not None
    assert lesson.intent.grade == 8
    assert lesson.source == "offline"


@pytest.mark.asyncio
async def test_attempt_is_persisted(tmp_path: Path) -> None:
    database = Database(tmp_path / "attempts.db")
    await database.initialize()
    await database.record_attempt(123, "kvadrat_ildiz", 0, "A", False)
    import aiosqlite

    async with aiosqlite.connect(database.path) as connection:
        async with connection.execute(
            "SELECT user_id, topic_key, question_index, selected, is_correct FROM attempts"
        ) as cursor:
            rows = await cursor.fetchall()
    assert rows == [(123, "kvadrat_ildiz", 0, "A", 0)]
