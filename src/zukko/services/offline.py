from __future__ import annotations

import json
import re
import unicodedata
from importlib.resources import files
from pathlib import Path

from zukko.models import Intent, LessonPackage


def normalize(text: str) -> str:
    value = text.lower().replace("ʻ", "'").replace("’", "'").replace("`", "'")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9']+", " ", value).strip()


class OfflineRepository:
    """Fast, deterministic lesson fallback bundled with the application."""

    def __init__(self, data_path: Path | None = None) -> None:
        path = data_path or Path(str(files("zukko.data").joinpath("offline_topics.json")))
        with path.open("r", encoding="utf-8") as stream:
            raw = json.load(stream)
        self._lessons = {
            key: LessonPackage.model_validate({**value, "source": "offline"})
            for key, value in raw.items()
        }

    @property
    def topic_keys(self) -> tuple[str, ...]:
        return tuple(self._lessons)

    def get(self, topic_key: str) -> LessonPackage | None:
        lesson = self._lessons.get(topic_key)
        return lesson.model_copy(deep=True) if lesson else None

    def match(self, text: str) -> LessonPackage | None:
        haystack = normalize(text)
        best: tuple[int, LessonPackage] | None = None
        for lesson in self._lessons.values():
            aliases = [lesson.intent.topic, lesson.intent.topic_key]
            aliases.extend(_ALIASES.get(lesson.intent.topic_key, []))
            score = max(
                (len(normalize(alias)) for alias in aliases if normalize(alias) in haystack),
                default=0,
            )
            if score and (best is None or score > best[0]):
                best = (score, lesson)
        return best[1].model_copy(deep=True) if best else None

    def local_intent(self, text: str) -> Intent | None:
        lesson = self.match(text)
        if not lesson:
            return None
        grade_match = re.search(r"\b(1[01]|[1-9])\s*[- ]?sinf", normalize(text))
        intent = lesson.intent.model_copy(deep=True)
        if grade_match:
            intent.grade = int(grade_match.group(1))
        return intent


_ALIASES: dict[str, list[str]] = {
    "kvadrat_ildiz": ["kvadrat ildiz", "ildiz osti", "sqrt"],
    "pifagor_teoremasi": ["pifagor", "togri burchakli uchburchak", "gipotenuza"],
    "nyuton_ikkinchi_qonuni": ["nyuton 2", "f ma", "kuch massa tezlanish"],
    "fotosintez": ["fotosintez", "osimlik oziqlanishi", "xlorofill"],
    "kasrlar": ["kasr", "surat maxraj", "oddiy kasr"],
    "chiziqli_tenglama": ["chiziqli tenglama", "tenglama", "x ni top"],
    "atom_tuzilishi": ["atom", "proton neytron elektron"],
    "suv_aylanishi": ["suv aylanishi", "buglanish", "yogin"],
    "gap_bolaklari": ["gap bolaklari", "ega kesim", "ikkinchi darajali bolak"],
    "present_simple": ["present simple", "do does", "ingliz tili hozirgi oddiy zamon"],
}

