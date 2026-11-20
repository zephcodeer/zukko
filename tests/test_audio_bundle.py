from __future__ import annotations

from pathlib import Path

import pytest

from zukko.services.offline import OfflineRepository
from zukko.services.tts import TTSService


@pytest.mark.asyncio
async def test_all_offline_topics_have_audio_without_network(tmp_path: Path, monkeypatch) -> None:
    def fail_if_online(*args, **kwargs):
        raise AssertionError("Bundled lessons must not contact Edge TTS")

    monkeypatch.setattr("zukko.services.tts.edge_tts.Communicate", fail_if_online)
    repository = OfflineRepository()
    tts = TTSService(tmp_path / "empty-cache", "uz-UZ-MadinaNeural")
    for topic_key in repository.topic_keys:
        lesson = repository.get(topic_key)
        assert lesson is not None
        audio = await tts.synthesize(lesson.podcast_text)
        assert audio.exists()
        assert audio.stat().st_size > 1024
        assert audio.suffix == ".mp3"
