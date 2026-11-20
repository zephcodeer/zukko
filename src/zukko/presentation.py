from __future__ import annotations

from html import escape

from zukko.models import LessonPackage, QuizQuestion


def format_lesson(lesson: LessonPackage) -> str:
    source_note = "\n\n🛡 <i>Offline keshdan olindi</i>" if lesson.source == "offline" else ""
    return (
        f"🧠 <b>{escape(lesson.intent.topic.title())}</b>\n\n"
        f"🎬 <b>Ko‘z oldingga keltir</b>\n{escape(lesson.explanation.metaphor)}\n\n"
        f"📐 <b>Formula va qoida</b>\n{escape(lesson.explanation.rule)}\n\n"
        f"🌍 <b>Hayotda qayerda kerak?</b>\n{escape(lesson.explanation.real_life)}"
        f"{source_note}"
    )


def format_question(question: QuizQuestion, index: int) -> str:
    options = "\n".join(
        f"{option.label}) {escape(option.text)}" for option in question.options
    )
    return (
        f"⚔️ <b>{index + 1}/3-savol</b>\n\n"
        f"{escape(question.prompt)}\n\n{options}"
    )


def format_feedback(feedback: str, is_correct: bool) -> str:
    icon = "✅" if is_correct else "⚠️"
    title = "Zo‘r!" if is_correct else "To‘xta, shu joy muhim!"
    return f"{icon} <b>{title}</b>\n{escape(feedback)}"

