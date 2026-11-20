from __future__ import annotations

import asyncio
import logging

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from zukko.config import load_settings
from zukko.database import Database, InMemoryLessonStore
from zukko.handlers import Dependencies, build_router
from zukko.services import GeminiClient, OfflineRepository, TTSService


async def main() -> None:
    settings = load_settings()
    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN .env faylida sozlanmagan")
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    database = Database(settings.database_path)
    await database.initialize()
    offline = OfflineRepository()
    tts = TTSService(settings.cache_dir, settings.tts_voice)

    async with aiohttp.ClientSession() as session:
        gemini = GeminiClient(
            settings.gemini_api_key,
            settings.gemini_model,
            settings.api_timeout_seconds,
            session,
        )
        deps = Dependencies(gemini, offline, tts, database, InMemoryLessonStore())
        dispatcher = Dispatcher()
        dispatcher.include_router(build_router(deps))
        bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            await dispatcher.start_polling(
                bot, allowed_updates=dispatcher.resolve_used_update_types()
            )
        finally:
            await bot.session.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
