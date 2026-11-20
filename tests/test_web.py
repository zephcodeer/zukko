from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from zukko.config import Settings
from zukko.web import create_app


def test_web_lesson_and_three_diagnostic_answers(tmp_path: Path) -> None:
    app = create_app(Settings(database_path=tmp_path / "web.db", cache_dir=tmp_path / "audio"))
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/styles.css").status_code == 200
        assert client.get("/app.js").status_code == 200
        assert client.get("/assets/hero-book.png").status_code == 200
        assert client.get("/assets/insight-cube.png").status_code == 200
        assert client.get("/assets/icons.svg").status_code == 200
        topics = client.get("/api/topics").json()
        assert len(topics) == 10
        assert client.get("/api/status").json() == {
            "gemini_configured": False,
            "offline_topics": 10,
        }

        lesson_response = client.post(
            "/api/lesson", json={"text": "8-sinfman, kvadrat ildizni tushunmayapman"}
        )
        assert lesson_response.status_code == 200
        lesson = lesson_response.json()
        assert lesson["source"] == "offline"
        assert lesson["intent"]["grade"] == 8
        assert lesson["question"]["prompt"] == "√16 = ?"
        assert "correct" not in lesson["question"]

        first = client.post(
            "/api/answer",
            json={"lesson_id": lesson["lesson_id"], "question_index": 0, "selected": "A"},
        )
        assert first.status_code == 200
        assert not first.json()["is_correct"]
        assert "2 ga bo‘lding" in first.json()["feedback"]
        assert first.json()["question"]["index"] == 1
        assert client.post(
            "/api/answer",
            json={"lesson_id": lesson["lesson_id"], "question_index": 0, "selected": "B"},
        ).status_code == 409
        for index, selected in [(1, "A"), (2, "C")]:
            result = client.post(
                "/api/answer",
                json={
                    "lesson_id": lesson["lesson_id"],
                    "question_index": index,
                    "selected": selected,
                },
            )
            assert result.status_code == 200
        assert result.json()["finished"]
        assert result.json()["summary"]["score"] == 2
        assert "2 ga bo‘lding" in result.json()["summary"]["review_tip"]
        audio = client.get(f"/api/audio/{lesson['lesson_id']}")
        assert audio.status_code == 200
        assert audio.headers["content-type"] == "audio/mpeg"
        assert client.post(
            "/api/answer",
            json={"lesson_id": lesson["lesson_id"], "question_index": 2, "selected": "C"},
        ).status_code == 409

        analytics = client.get("/api/analytics").json()
        assert analytics["total_attempts"] == 3
        assert analytics["correct_attempts"] == 2
        assert analytics["accuracy"] == 66.7
        assert analytics["unique_topics"] == 1
        assert len(analytics["topic_stats"]) == 1

        summary_resp = client.get(f"/api/summary/{lesson['lesson_id']}")
        assert summary_resp.status_code == 200
        assert "text/markdown" in summary_resp.headers["content-type"]
        assert "Tasavvur qil" in summary_resp.text

        reset_resp = client.post("/api/reset-analytics")
        assert reset_resp.status_code == 200
        after_reset = client.get("/api/analytics").json()
        assert after_reset["total_attempts"] == 0


def test_expired_web_lesson_is_rejected(tmp_path: Path) -> None:
    app = create_app(Settings(database_path=tmp_path / "web.db", cache_dir=tmp_path / "audio"))
    with TestClient(app) as client:
        lesson_id = client.post("/api/lesson", json={"text": "fotosintez"}).json()["lesson_id"]
        app.state.web_lessons[lesson_id]["created_at"] -= 3601
        assert client.get(f"/api/audio/{lesson_id}").status_code == 404
        assert client.post(
            "/api/answer",
            json={"lesson_id": lesson_id, "question_index": 0, "selected": "B"},
        ).status_code == 404


def test_web_voice_transcript_creates_offline_lesson(tmp_path: Path) -> None:
    app = create_app(Settings(database_path=tmp_path / "web.db", cache_dir=tmp_path / "audio"))
    with TestClient(app) as client:
        transcribe = AsyncMock(return_value="8-sinfman, fotosintezni tushunmayapman")
        app.state.deps.gemini = SimpleNamespace(enabled=True, transcribe=transcribe)
        response = client.post(
            "/api/voice",
            files={"audio": ("savol.webm", b"sample audio", "audio/webm")},
            data={"mime_type": "audio/webm"},
        )
        assert response.status_code == 200
        assert response.json()["source"] == "offline"
        assert response.json()["intent"]["topic_key"] == "fotosintez"
        assert response.json()["transcript"] == "8-sinfman, fotosintezni tushunmayapman"
        transcribe.assert_awaited_once_with(b"sample audio", "audio/webm")

        too_large = client.post(
            "/api/voice",
            files={"audio": ("savol.webm", b"x" * 8_000_001, "audio/webm")},
            data={"mime_type": "audio/webm"},
        )
        assert too_large.status_code == 413
        transcribe.assert_awaited_once()
