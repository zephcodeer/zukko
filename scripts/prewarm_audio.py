"""Generate the ten offline podcasts in advance for a quick stage demo."""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

from zukko.services import OfflineRepository, TTSService

BUNDLED_DIR = Path(__file__).resolve().parents[1] / "src" / "zukko" / "data" / "audio"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle", action="store_true", help="Copy generated audio into the application package"
    )
    args = parser.parse_args()
    load_dotenv()
    repository = OfflineRepository()
    tts = TTSService(
        Path(os.getenv("CACHE_DIR", "data/audio_cache")),
        os.getenv("TTS_VOICE", "uz-UZ-MadinaNeural"),
    )
    for topic_key in repository.topic_keys:
        lesson = repository.get(topic_key)
        assert lesson is not None
        path = await tts.synthesize(lesson.podcast_text)
        if args.bundle:
            BUNDLED_DIR.mkdir(parents=True, exist_ok=True)
            bundled_path = BUNDLED_DIR / path.name
            if path.resolve() != bundled_path.resolve():
                shutil.copy2(path, bundled_path)
        print(f"{topic_key}: {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
