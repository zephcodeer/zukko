from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from zukko.models import QuizQuestion


def quiz_keyboard(question: QuizQuestion, index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{option.label}) {option.text[:26]}",
                    callback_data=f"q:{index}:{option.label}",
                )
            ]
            for option in question.options
        ]
    )


def start_quiz_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚔️ 3 savolni boshlash", callback_data="quiz:start")]
        ]
    )

