from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, Message

from zukko.database import Database, InMemoryLessonStore, QuizSession
from zukko.keyboards import quiz_keyboard, start_quiz_keyboard
from zukko.models import LessonPackage, evaluate_answer
from zukko.presentation import format_feedback, format_lesson, format_question
from zukko.services import GeminiClient, GeminiError, OfflineRepository, TTSService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Dependencies:
    gemini: GeminiClient
    offline: OfflineRepository
    tts: TTSService
    database: Database
    lessons: InMemoryLessonStore


def build_router(deps: Dependencies) -> Router:
    router = Router(name="zukko")

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        await message.answer(
            "Assalomu alaykum! Men <b>Zukko</b> — shaxsiy AI repetitoringman. 🧠\n\n"
            "Menga sinfing va tushunmayotgan mavzuni yoz yoki ovozli xabar yubor.\n"
            "Masalan: <i>8-sinfman, kvadrat ildizni tushunmayapman.</i>",
            parse_mode="HTML",
        )

    @router.message(Command("topics"))
    async def topics(message: Message) -> None:
        names = [
            "Kvadrat ildiz", "Pifagor teoremasi", "Nyutonning 2-qonuni",
            "Fotosintez", "Kasrlar", "Chiziqli tenglama", "Atom tuzilishi",
            "Suv aylanishi", "Gap bo‘laklari", "Present Simple",
        ]
        await message.answer(
            "🛡 <b>Internet uzilsa ham tayyor mavzular:</b>\n\n• "
            + "\n• ".join(names),
            parse_mode="HTML",
        )

    @router.message(F.voice)
    async def voice_message(message: Message, bot: Bot) -> None:
        if not deps.gemini.enabled:
            await message.answer(
                "Ovozli xabarni anglash uchun GEMINI_API_KEY kerak. Hozircha mavzuni "
                "matnda yozing — offline darslar ishlayveradi. 🛡"
            )
            return
        await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        try:
            file = await bot.get_file(message.voice.file_id)
            buffer = await bot.download_file(file.file_path)
            transcript = await deps.gemini.transcribe(
                buffer.read(), message.voice.mime_type or "audio/ogg"
            )
        except Exception as exc:
            logger.warning("Voice transcription failed: %s", exc)
            await message.answer(
                "Ovozni hozir tanib bo‘lmadi. Shu mavzuni bir jumlada yozib yuboring."
            )
            return
        await message.answer(f"🎙 <b>Eshitdim:</b> <i>{_escape(transcript)}</i>", parse_mode="HTML")
        await _deliver_lesson(message, transcript, deps, bot)

    @router.message(F.text & ~F.text.startswith("/"))
    async def text_message(message: Message, bot: Bot) -> None:
        await _deliver_lesson(message, message.text or "", deps, bot)

    @router.callback_query(F.data == "quiz:start")
    async def start_quiz(callback: CallbackQuery) -> None:
        session = _stored_session(callback, deps)
        if not session or session.started:
            await callback.answer("Dars eskirgan. Mavzuni qayta yuboring.", show_alert=True)
            return
        session.started = True
        lesson = session.lesson
        await callback.answer()
        await callback.message.answer(
            "Qani, miyangni sinab ko‘ramiz! 3 ta savol, taxminan 1 daqiqa. 🚀"
        )
        question = lesson.quiz[0]
        await callback.message.answer(
            format_question(question, 0),
            reply_markup=quiz_keyboard(question, 0),
            parse_mode="HTML",
        )

    @router.callback_query(F.data.startswith("q:"))
    async def answer_quiz(callback: CallbackQuery) -> None:
        session = _stored_session(callback, deps)
        if not session or not session.started:
            await callback.answer("Test eskirgan. Mavzuni qayta yuboring.", show_alert=True)
            return
        lesson = session.lesson
        try:
            _, raw_index, selected = (callback.data or "").split(":")
            index = int(raw_index)
            question = lesson.quiz[index]
            if index != session.next_index:
                await callback.answer("Bu savolga allaqachon javob berdingiz.", show_alert=True)
                return
            result = evaluate_answer(question, selected)
        except (ValueError, IndexError):
            await callback.answer("Noto‘g‘ri test holati.", show_alert=True)
            return

        session.next_index += 1
        if result.is_correct:
            session.correct_count += 1
        elif session.first_mistake is None:
            session.first_mistake = result.feedback
        await callback.answer()
        await callback.message.edit_reply_markup(reply_markup=None)
        await deps.database.record_attempt(
            callback.from_user.id,
            lesson.intent.topic_key,
            index,
            selected,
            result.is_correct,
        )
        await callback.message.answer(
            format_feedback(result.feedback, result.is_correct), parse_mode="HTML"
        )

        next_index = index + 1
        if next_index < len(lesson.quiz):
            await asyncio.sleep(0.35)
            next_question = lesson.quiz[next_index]
            await callback.message.answer(
                format_question(next_question, next_index),
                reply_markup=quiz_keyboard(next_question, next_index),
                parse_mode="HTML",
            )
        else:
            deps.lessons.pop(callback.message.chat.id, callback.from_user.id)
            review = (
                f"\n\n💡 <b>Qayta ko‘r:</b> {_escape(session.first_mistake)}"
                if session.first_mistake else "\n\n✨ Uchalasini ham aniq topding!"
            )
            await callback.message.answer(
                f"🏆 <b>Jang tugadi! {session.correct_count}/3 to‘g‘ri.</b>"
                f"{review}\n\nYana bir mavzuni yoz — uni ham birga yengamiz.",
                parse_mode="HTML",
            )

    return router


async def _deliver_lesson(message: Message, text: str, deps: Dependencies, bot: Bot) -> None:
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    lesson = await _resolve_lesson(text, deps)
    if not lesson:
        await message.answer(
            "Bu mavzu uchun internetdagi AI javobi ham, offline kesh ham topilmadi. "
            "Internetni tekshiring yoki /topics dagi mavzulardan birini yozing."
        )
        return

    user_id = message.from_user.id if message.from_user else message.chat.id
    deps.lessons.put(message.chat.id, user_id, lesson)
    await message.answer(format_lesson(lesson), parse_mode="HTML")

    audio_task = asyncio.create_task(deps.tts.synthesize(lesson.podcast_text))
    try:
        await bot.send_chat_action(message.chat.id, ChatAction.RECORD_VOICE)
        audio_path = await audio_task
        await message.answer_voice(
            voice=FSInputFile(audio_path),
            caption="🎧 35 soniyalik mini-podkast",
        )
    except Exception as exc:
        logger.warning("TTS generation failed: %s", exc)
        await message.answer(
            "🎧 Audio hozir tayyor bo‘lmadi, ammo dars va test ishlashda davom etadi."
        )

    await message.answer(
        "Tushunarli bo‘ldimi? Endi bilimni mustahkamlaymiz.",
        reply_markup=start_quiz_keyboard(),
    )


async def _resolve_lesson(text: str, deps: Dependencies) -> LessonPackage | None:
    cached = deps.offline.match(text)
    if cached:
        local_intent = deps.offline.local_intent(text)
        if local_intent:
            cached.intent.grade = local_intent.grade
        return cached
    if not deps.gemini.enabled:
        return None
    try:
        intent = await deps.gemini.route(text)
        exact_cache = deps.offline.get(intent.topic_key)
        if exact_cache:
            exact_cache.intent.grade = intent.grade
        return exact_cache or await deps.gemini.build_lesson(intent)
    except (GeminiError, ValueError, KeyError) as exc:
        logger.warning("AI lesson failed; using offline fallback: %s", exc)
        return cached


def _stored_session(callback: CallbackQuery, deps: Dependencies) -> QuizSession | None:
    if not callback.message:
        return None
    return deps.lessons.get(callback.message.chat.id, callback.from_user.id)


def _escape(value: str) -> str:
    from html import escape

    return escape(value)

