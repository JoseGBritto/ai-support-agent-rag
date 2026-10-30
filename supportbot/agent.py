"""Orchestrates retrieval, the LLM call, citations and human handoff."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import requests

from .config import Settings
from .ingest import Chunk, load_knowledge_base
from .llm import NO_ANSWER, ChatClient, LLMError, build_messages
from .retriever import BM25Retriever, Hit
from .store import Store
from .text import is_small_talk, split_sentences, tokenize

log = logging.getLogger(__name__)

HANDOFF_TEXT = {
    "en": "I'm not sure about that one, so I've passed your question to our team. "
          "Leave your email and a person will get back to you.",
    "es": "No tengo esa información, así que le pasé tu consulta a nuestro equipo. "
          "Dejanos tu email y una persona te va a responder.",
}
SMALL_TALK_TEXT = {
    "en": "Hi! Ask me anything about {business}: orders, products, shipping, returns...",
    "es": "¡Hola! Preguntame lo que necesites sobre {business}: pedidos, productos, envíos, devoluciones...",
}
SPANISH_HINTS = set("hola buenas buen gracias que como cuanto cuando donde envio envios precio precios tienen hacen puedo quiero gracias devolucion pedido".split())


def detect_language(text: str) -> str:
    words = set(re.findall(r"[a-záéíóúñ]+", text.lower()))
    return "es" if words & SPANISH_HINTS or re.search(r"[¿¡ñáéíóú]", text.lower()) else "en"


@dataclass
class Reply:
    answer: str
    sources: list[dict] = field(default_factory=list)
    handoff: bool = False
    mode: str = "ai"   # "ai", "demo" (extractive, no LLM), "handoff" or "smalltalk"

    def to_dict(self) -> dict:
        return {"answer": self.answer, "sources": self.sources, "handoff": self.handoff, "mode": self.mode}


class SupportAgent:
    def __init__(self, settings: Settings, chunks: list[Chunk] | None = None, store: Store | None = None,
                 llm: ChatClient | None = None, http: requests.Session | None = None):
        self.settings = settings
        self.store = store or Store(settings.data_dir / "supportbot.sqlite3")
        self.http = http or requests.Session()
        self.llm = llm or (ChatClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
                           if settings.ai_enabled else None)
        self.reindex(chunks)

    def reindex(self, chunks: list[Chunk] | None = None) -> int:
        self.chunks = chunks if chunks is not None else load_knowledge_base(self.settings.knowledge_dir)
        self.retriever = BM25Retriever(self.chunks)
        log.info("Indexed %d chunks", len(self.chunks))
        return len(self.chunks)

    # ------------------------------------------------------------------ public API

    def ask(self, question: str, conversation_id: str = "anonymous", history: list[dict] | None = None) -> Reply:
        history = history or []
        lang = detect_language(question)
        if is_small_talk(question):  # "hi", "thanks!": answer politely, don't alert the team
            reply = Reply(answer=SMALL_TALK_TEXT[lang].format(business=self.settings.business_name), mode="smalltalk")
            self.store.log_message(conversation_id, question, reply.answer, True, [])
            return reply
        query, hits, coverage = self._retrieve(question, history)

        if not hits or coverage < self.settings.min_coverage:
            reply = self._handoff(question, conversation_id, lang)
        elif self.llm:
            reply = self._ai_answer(question, history, hits, conversation_id, lang)
        else:
            reply = self._extractive_answer(question, hits)

        self.store.log_message(conversation_id, question, reply.answer, not reply.handoff,
                               [s["source"] for s in reply.sources])
        return reply

    def add_contact(self, conversation_id: str, contact: str) -> bool:
        ok = self.store.set_handoff_contact(conversation_id, contact)
        if ok:
            self._notify(f"Contact left for conversation {conversation_id}: {contact}")
        return ok

    # ------------------------------------------------------------------ internals

    def _retrieve(self, question: str, history: list[dict]) -> tuple[str, list[Hit], float]:
        """Search with the question alone; only if that fails, add the previous customer message.

        This handles follow-ups such as "and how much does it cost?" without letting an old
        topic hijack a new, self-contained question.
        """
        k = self.settings.top_k
        hits = self.retriever.search(question, k=k)
        coverage = self.retriever.coverage(question, hits)
        if coverage >= self.settings.min_coverage:
            return question, hits, coverage
        previous = [t["content"] for t in history if isinstance(t, dict) and t.get("role") == "user"
                    and isinstance(t.get("content"), str)]
        if previous:
            combined = f"{previous[-1]} {question}"
            combined_hits = self.retriever.search(combined, k=k)
            combined_cov = self.retriever.coverage(combined, combined_hits)
            # the new question's own terms must be covered too, so an old topic can't answer a new one
            own_cov = self.retriever.coverage(question, combined_hits)
            if combined_cov >= self.settings.min_coverage and own_cov >= self.settings.min_coverage:
                return combined, combined_hits, combined_cov
        return question, hits, coverage

    def _ai_answer(self, question, history, hits: list[Hit], conversation_id, lang) -> Reply:
        sources = [f"({h.chunk.source} - {h.chunk.title})\n{h.chunk.text}" for h in hits]
        try:
            text = self.llm.complete(build_messages(self.settings.business_name, sources, history, question))
        except LLMError as exc:
            log.warning("%s - falling back to extractive answer", exc)
            return self._extractive_answer(question, hits)
        if NO_ANSWER in text:
            return self._handoff(question, conversation_id, lang)
        cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text) if 1 <= int(n) <= len(hits)})
        used = [hits[i - 1] for i in cited] or hits[:1]
        return Reply(answer=text, sources=[self._source(h, i) for i, h in zip(cited or [1], used)], mode="ai")

    def _extractive_answer(self, question: str, hits: list[Hit]) -> Reply:
        """Free demo mode: quote the most relevant sentences of the best source."""
        terms = set(tokenize(question))
        best = hits[0]
        if len(best.chunk.text) <= 450:  # short sections are clearer quoted whole
            text = " ".join(split_sentences(best.chunk.text))
            return Reply(answer=text + " [1]", sources=[self._source(best, 1)], mode="demo")
        ranked = sorted(split_sentences(best.chunk.text), key=lambda s: len(terms & set(tokenize(s))), reverse=True)
        picked = [s for s in ranked[:2] if terms & set(tokenize(s))] or ranked[:1]
        ordered = [s for s in split_sentences(best.chunk.text) if s in picked]
        return Reply(answer=" ".join(ordered) + " [1]", sources=[self._source(best, 1)], mode="demo")

    def _handoff(self, question: str, conversation_id: str, lang: str) -> Reply:
        self.store.log_handoff(conversation_id, question)
        self._notify(f"Customer question needs a human (conversation {conversation_id}): {question}")
        return Reply(answer=HANDOFF_TEXT[lang], handoff=True, mode="handoff")

    def _notify(self, text: str) -> None:
        url = self.settings.handoff_webhook_url
        if not url:
            return
        try:  # {"text": ...} is accepted by Slack, Mattermost, n8n, Make and Google Chat webhooks
            self.http.post(url, json={"text": f"[{self.settings.business_name}] {text}"}, timeout=5)
        except requests.RequestException as exc:
            log.warning("Handoff webhook failed: %s", exc)

    @staticmethod
    def _source(hit: Hit, number: int) -> dict:
        return {"n": number, "source": hit.chunk.source, "title": hit.chunk.title}
