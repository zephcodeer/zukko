from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class Intent(BaseModel):
    grade: int = Field(default=7, ge=1, le=11)
    subject: str = Field(min_length=2, max_length=60)
    topic: str = Field(min_length=2, max_length=100)
    topic_key: str = Field(min_length=2, max_length=100)

    @field_validator("subject", "topic", "topic_key")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class Explanation(BaseModel):
    metaphor: str = Field(min_length=20, max_length=1600)
    rule: str = Field(min_length=10, max_length=1000)
    real_life: str = Field(min_length=10, max_length=1000)


class QuizOption(BaseModel):
    label: str = Field(pattern=r"^[ABCD]$")
    text: str = Field(min_length=1, max_length=250)
    misconception: str | None = Field(default=None, max_length=900)


class QuizQuestion(BaseModel):
    prompt: str = Field(min_length=3, max_length=500)
    options: list[QuizOption] = Field(min_length=4, max_length=4)
    correct: str = Field(pattern=r"^[ABCD]$")
    success_feedback: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def validate_options(self) -> QuizQuestion:
        labels = [option.label for option in self.options]
        if labels != ["A", "B", "C", "D"]:
            raise ValueError("Options must be ordered A, B, C, D")
        if self.correct not in labels:
            raise ValueError("Correct label is missing from options")
        for option in self.options:
            if option.label != self.correct and not option.misconception:
                raise ValueError(f"Wrong option {option.label} needs diagnostic feedback")
        return self

    def option(self, label: str) -> QuizOption:
        return next(option for option in self.options if option.label == label)


class LessonPackage(BaseModel):
    intent: Intent
    explanation: Explanation
    podcast_text: str = Field(min_length=40, max_length=1200)
    quiz: list[QuizQuestion] = Field(min_length=3, max_length=3)
    source: str = "ai"


class AnswerResult(BaseModel):
    is_correct: bool
    feedback: str
    correct_label: str
    correct_text: str


def evaluate_answer(question: QuizQuestion, selected: str) -> AnswerResult:
    chosen = question.option(selected)
    correct = question.option(question.correct)
    if selected == question.correct:
        return AnswerResult(
            is_correct=True,
            feedback=question.success_feedback,
            correct_label=question.correct,
            correct_text=correct.text,
        )
    feedback = chosen.misconception or (
        f"Bu variant mos kelmadi. {question.correct}) {correct.text} — to'g'ri javob."
    )
    return AnswerResult(
        is_correct=False,
        feedback=feedback,
        correct_label=question.correct,
        correct_text=correct.text,
    )
