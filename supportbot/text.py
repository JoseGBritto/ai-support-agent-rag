"""Language-light text utilities that work for English and Spanish."""
from __future__ import annotations

import re
import unicodedata

STOPWORDS = set("""
a an and are as at be by can could do does for from had has have how i if in is it its me my
of on or our please should so than that the their them then there these they this to us was we
what when where which who why will with would you your yours about any get got want need tell
el la los las un una unos unas y o de del al a en por para con sin que como cual cuales cuando
donde quien es son esta estan este esto ese eso se su sus mi mis tu tus le les lo me te nos
hay tiene tienen tengo puedo pueden puede hacer quiero necesito favor hola gracias si no mas
""".split())

_WORD = re.compile(r"[a-z0-9]+")


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def stem(word: str) -> str:
    """Very small suffix stripper: shipping/shipped/ships -> ship, envios -> envio."""
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            word = word[: -len(suffix)]
            break
    if len(word) > 4 and word[-1] == word[-2] and word[-1] not in "aeiou":  # shipp -> ship
        word = word[:-1]
    return word


def tokenize(text: str) -> list[str]:
    words = _WORD.findall(strip_accents(text.lower()))
    return [stem(w) for w in words if w not in STOPWORDS and len(w) > 1]


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip(" -*#\t") for p in parts if len(p.strip(" -*#\t")) > 2]
