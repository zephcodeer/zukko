from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from zukko.models import LessonPackage


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    topic_key TEXT NOT NULL,
                    question_index INTEGER NOT NULL,
                    selected TEXT NOT NULL,
                    is_correct INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_attempts_user_topic
                    ON attempts(user_id, topic_key);
                """
            )
            await db.commit()

    async def record_attempt(
        self,
        user_id: int,
        topic_key: str,
        question_index: int,
        selected: str,
        is_correct: bool,
    ) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO attempts
                    (user_id, topic_key, question_index, selected, is_correct, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    topic_key,
                    question_index,
                    selected,
                    int(is_correct),
                    datetime.now(UTC).isoformat(),
                ),
            )
            await db.commit()

    async def get_analytics(self, user_id: int = 0) -> dict:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT
                    COUNT(*) as total_attempts,
                    SUM(is_correct) as correct_attempts,
                    COUNT(DISTINCT topic_key) as unique_topics
                FROM attempts
                WHERE user_id = ?
                """,
                (user_id,),
            )
            overview = await cursor.fetchone()
            total = overview["total_attempts"] if overview and overview["total_attempts"] else 0
            correct = (
                overview["correct_attempts"] if overview and overview["correct_attempts"] else 0
            )
            unique_topics = (
                overview["unique_topics"] if overview and overview["unique_topics"] else 0
            )
            accuracy = round((correct / total * 100), 1) if total > 0 else 0.0

            cursor = await db.execute(
                """
                SELECT
                    topic_key,
                    COUNT(*) as total,
                    SUM(is_correct) as correct,
                    MAX(created_at) as last_attempt
                FROM attempts
                WHERE user_id = ?
                GROUP BY topic_key
                ORDER BY last_attempt DESC
                LIMIT 10
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()
            topic_stats = [
                {
                    "topic_key": row["topic_key"],
                    "total": row["total"],
                    "correct": row["correct"],
                    "accuracy": (
                        round((row["correct"] / row["total"] * 100), 1) if row["total"] > 0 else 0.0
                    ),
                    "last_attempt": row["last_attempt"],
                }
                for row in rows
            ]

            return {
                "total_attempts": total,
                "correct_attempts": correct,
                "unique_topics": unique_topics,
                "accuracy": accuracy,
                "xp": correct * 25 + total * 5,
                "streak_days": 1 if total > 0 else 0,
                "topic_stats": topic_stats,
            }

    async def reset_attempts(self, user_id: int = 0) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM attempts WHERE user_id = ?", (user_id,))
            await db.commit()


class InMemoryLessonStore:
    """Current quiz state; deliberately tiny and safe for a hackathon single process."""

    def __init__(self) -> None:
        self._items: dict[tuple[int, int], QuizSession] = {}

    def put(self, chat_id: int, user_id: int, lesson: LessonPackage) -> None:
        self._items[(chat_id, user_id)] = QuizSession(lesson=lesson)

    def get(self, chat_id: int, user_id: int) -> QuizSession | None:
        return self._items.get((chat_id, user_id))

    def pop(self, chat_id: int, user_id: int) -> QuizSession | None:
        return self._items.pop((chat_id, user_id), None)


class QuizSession:
    def __init__(self, lesson: LessonPackage) -> None:
        self.lesson = lesson
        self.next_index = 0
        self.started = False
        self.correct_count = 0
        self.first_mistake: str | None = None

