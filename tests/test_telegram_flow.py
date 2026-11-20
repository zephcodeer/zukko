from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from zukko.database import Database, InMemoryLessonStore
from zukko.handlers import Dependencies, _deliver_lesson, build_router
from zukko.services.offline import OfflineRepository


@pytest.mark.asyncio
async def test_quiz_callbacks_progress_once_and_store_three_answers(tmp_path: Path) -> None:
    offline = OfflineRepository()
    lesson = offline.get("kvadrat_ildiz")
    assert lesson is not None
    database = Database(tmp_path / "quiz.db")
    await database.initialize()
    store = InMemoryLessonStore()
    store.put(100, 200, lesson)
    deps = Dependencies(
        gemini=SimpleNamespace(enabled=False),  # type: ignore[arg-type]
        offline=offline,
        tts=SimpleNamespace(),  # type: ignore[arg-type]
        database=database,
        lessons=store,
    )
    router = build_router(deps)
    callbacks = {
        handler.callback.__name__: handler.callback
        for handler in router.callback_query.handlers
    }
    message = SimpleNamespace(
        chat=SimpleNamespace(id=100),
        answer=AsyncMock(),
        edit_reply_markup=AsyncMock(),
    )
    callback = SimpleNamespace(
        message=message,
        from_user=SimpleNamespace(id=200),
        answer=AsyncMock(),
        data="quiz:start",
    )
    await callbacks["start_quiz"](callback)
    assert store.get(100, 200).started
    assert message.answer.await_count == 2

    callback.data = "q:0:A"
    await callbacks["answer_quiz"](callback)
    assert store.get(100, 200).next_index == 1
    assert "2 ga bo‘lding" in message.answer.await_args_list[2].args[0]

    await callbacks["answer_quiz"](callback)
    assert store.get(100, 200).next_index == 1
    callback.data = "q:1:A"
    await callbacks["answer_quiz"](callback)
    callback.data = "q:2:C"
    await callbacks["answer_quiz"](callback)
    assert store.get(100, 200) is None
    assert "2/3 to‘g‘ri" in message.answer.await_args.args[0]
    assert "2 ga bo‘lding" in message.answer.await_args.args[0]

    import aiosqlite

    async with aiosqlite.connect(database.path) as connection:
        async with connection.execute("SELECT question_index FROM attempts ORDER BY id") as cursor:
            rows = await cursor.fetchall()
    assert rows == [(0,), (1,), (2,)]


@pytest.mark.asyncio
async def test_offline_lesson_sends_text_cached_voice_and_quiz(tmp_path: Path) -> None:
    offline = OfflineRepository()
    lesson = offline.get("kvadrat_ildiz")
    assert lesson is not None
    audio = tmp_path / "lesson.mp3"
    audio.write_bytes(b"ID3" + b"0" * 2048)
    tts = SimpleNamespace(synthesize=AsyncMock(return_value=audio))
    bot = SimpleNamespace(send_chat_action=AsyncMock())
    message = SimpleNamespace(
        chat=SimpleNamespace(id=99),
        from_user=SimpleNamespace(id=88),
        answer=AsyncMock(),
        answer_voice=AsyncMock(),
    )
    deps = Dependencies(
        gemini=SimpleNamespace(enabled=False),  # type: ignore[arg-type]
        offline=offline,
        tts=tts,  # type: ignore[arg-type]
        database=Database(tmp_path / "db.sqlite"),
        lessons=InMemoryLessonStore(),
    )
    await _deliver_lesson(message, "8-sinf kvadrat ildiz", deps, bot)
    assert message.answer.await_count == 2
    assert "Ko‘z oldingga keltir" in message.answer.await_args_list[0].args[0]
    assert message.answer_voice.await_count == 1
    assert message.answer_voice.await_args.kwargs["voice"].path == audio
    assert deps.lessons.get(99, 88).lesson.intent.grade == 8


@pytest.mark.asyncio
async def test_voice_message_transcript_enters_same_lesson_flow(tmp_path: Path) -> None:
    offline = OfflineRepository()
    audio = tmp_path / "speech.mp3"
    audio.write_bytes(b"ID3" + b"0" * 2048)
    gemini = SimpleNamespace(
        enabled=True,
        transcribe=AsyncMock(return_value="8-sinfman, kvadrat ildiz"),
        route=AsyncMock(side_effect=AssertionError("Offline topic should be instant")),
    )
    bot = SimpleNamespace(
        send_chat_action=AsyncMock(),
        get_file=AsyncMock(return_value=SimpleNamespace(file_path="voice.ogg")),
        download_file=AsyncMock(return_value=BytesIO(b"OggS-test")),
    )
    message = SimpleNamespace(
        chat=SimpleNamespace(id=77),
        from_user=SimpleNamespace(id=66),
        voice=SimpleNamespace(file_id="file-id", mime_type="audio/ogg"),
        answer=AsyncMock(),
        answer_voice=AsyncMock(),
    )
    deps = Dependencies(
        gemini=gemini,  # type: ignore[arg-type]
        offline=offline,
        tts=SimpleNamespace(synthesize=AsyncMock(return_value=audio)),  # type: ignore[arg-type]
        database=Database(tmp_path / "voice.db"),
        lessons=InMemoryLessonStore(),
    )
    router = build_router(deps)
    voice_handler = next(
        handler.callback for handler in router.message.handlers
        if handler.callback.__name__ == "voice_message"
    )
    await voice_handler(message, bot)
    gemini.transcribe.assert_awaited_once_with(b"OggS-test", "audio/ogg")
    assert "Eshitdim" in message.answer.await_args_list[0].args[0]
    assert message.answer_voice.await_count == 1
    assert deps.lessons.get(77, 66).lesson.intent.topic_key == "kvadrat_ildiz"
