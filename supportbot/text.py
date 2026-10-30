"""Language-light text utilities that work for English and Spanish."""
from __future__ import annotations

import re
import unicodedata

STOPWORDS = set("""
a an and are as at be by can could do does for from had has have how i if in is it its me my
of on or our please should so than that the their them then there these they this to us was we
what when where which who why will with would you your yours about any get got want need tell
much many long often
el la los las un una unos unas y o de del al a en por para con sin que como cual cuales cuando
donde quien es son esta estan este esto ese eso se su sus mi mis tu tus le les lo me te nos
hay tiene tienen tengo puedo pueden puede hacer quiero necesito favor hola gracias si no mas
""".split())

# Courtesy words: a message made only of these is small talk, not a question for the docs
SMALL_TALK = set("""
hi hello hey hiya thanks thank thx ok okay cool great bye goodbye morning afternoon evening good lot much very so
buenas buenos buen dia tardes noches chau chao adios genial perfecto dale listo ok
""".split())

_WORD = re.compile(r"[a-z0-9]+")


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def stem(word: str) -> str:
    """Small suffix stripper that maps singular and plural forms to the same key.

    price/prices/pricing -> pric, box/boxes -> box, delivery/deliveries -> delivery,
    shipping/shipped/ships -> ship, envio/envios -> envio, ciudad/ciudades -> ciudad.
    """
    if len(word) > 4 and word.endswith("ies"):
        word = word[:-3] + "y"
    elif len(word) > 5 and word.endswith("ing"):
        word = word[:-3]
    elif len(word) > 5 and word.endswith("ed"):
        word = word[:-2]
    elif len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    if len(word) > 3 and word.endswith("e"):
        word = word[:-1]
    if len(word) > 4 and word[-1] == word[-2] and word[-1] not in "aeiou":  # shipp -> ship
        word = word[:-1]
    return word


def tokenize(text: str) -> list[str]:
    words = _WORD.findall(strip_accents(text.lower()))
    return [stem(w) for w in words if w not in STOPWORDS and len(w) > 1]


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip(" -*#\t") for p in parts if len(p.strip(" -*#\t")) > 2]


def is_small_talk(text: str) -> bool:
    """True for greetings and thanks ("hi", "hola!", "thanks a lot") that carry no question."""
    words = _WORD.findall(strip_accents(text.lower()))
    return all(w in STOPWORDS or w in SMALL_TALK for w in words)
