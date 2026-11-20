from __future__ import annotations

import asyncio
import hashlib
from importlib.resources import files
from pathlib import Path

import edge_tts


class TTSService:
    def __init__(self, cache_dir: Path, voice: str, timeout_seconds: float = 18.0) -> None:
        self.cache_dir = cache_dir
        self.voice = voice
        self.timeout_seconds = timeout_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def synthesize(self, text: str) -> Path:
        rate = "-15%"
        key = hashlib.sha256(f"{self.voice}\0{rate}\0{text}".encode()).hexdigest()[:24]
        target = self.cache_dir / f"{key}.mp3"
        if target.exists() and target.stat().st_size > 1024:
            return target

        bundled = Path(str(files("zukko.data").joinpath("audio", f"{key}.mp3")))
        if await asyncio.to_thread(bundled.is_file) and (
            await asyncio.to_thread(bundled.stat)
        ).st_size > 1024:
            return bundled

        temporary = target.with_suffix(".tmp.mp3")
        communicate = edge_tts.Communicate(text=text, voice=self.voice, rate=rate)
        try:
            async with asyncio.timeout(self.timeout_seconds):
                await communicate.save(str(temporary))
            temporary.replace(target)
            return target
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

