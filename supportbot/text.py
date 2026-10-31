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

# Courtesy words. A message counts as small talk only if it contains one of these and every other
# word is filler, so "how much?" or "is it good?" are still treated as real questions.
GREETING_WORDS = set("hi hello hey hiya morning afternoon evening hola buenas buenos buen dia tardes noches".split())
THANKS_WORDS = set("thanks thank thx gracias".split())
BYE_WORDS = set("bye goodbye chau chao adios".split())
FILLER_WORDS = set("good a lot very much so you ok okay cool great perfect genial perfecto dale listo muchas muchisimas mil and y".split())

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


def small_talk_kind(text: str) -> str | None:
    """"greeting", "thanks" or "bye" for courtesy-only messages ("hola!", "thanks a lot"); otherwise None."""
    words = _WORD.findall(strip_accents(text.lower()))
    courtesy = GREETING_WORDS | THANKS_WORDS | BYE_WORDS
    if not words or not any(w in courtesy for w in words) or not all(w in courtesy | FILLER_WORDS for w in words):
        return None
    if any(w in THANKS_WORDS for w in words):
        return "thanks"
    if any(w in BYE_WORDS for w in words):
        return "bye"
    return "greeting"


def is_small_talk(text: str) -> bool:
    return small_talk_kind(text) is not None
