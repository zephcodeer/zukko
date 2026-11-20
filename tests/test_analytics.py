from __future__ import annotations

from pathlib import Path

import pytest

from zukko.database import Database


@pytest.mark.asyncio
async def test_database_analytics_empty(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    await db.initialize()
    stats = await db.get_analytics(user_id=0)
    assert stats["total_attempts"] == 0
    assert stats["correct_attempts"] == 0
    assert stats["accuracy"] == 0.0
    assert stats["unique_topics"] == 0
    assert stats["topic_stats"] == []


@pytest.mark.asyncio
async def test_database_analytics_with_attempts(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    await db.initialize()
    await db.record_attempt(0, "fotosintez", 0, "A", True)
    await db.record_attempt(0, "fotosintez", 1, "B", False)
    await db.record_attempt(0, "kvadrat_ildiz", 0, "C", True)

    stats = await db.get_analytics(user_id=0)
    assert stats["total_attempts"] == 3
    assert stats["correct_attempts"] == 2
    assert stats["accuracy"] == 66.7
    assert stats["unique_topics"] == 2
    assert len(stats["topic_stats"]) == 2

    # Different user has independent stats
    other_user_stats = await db.get_analytics(user_id=999)
    assert other_user_stats["total_attempts"] == 0
