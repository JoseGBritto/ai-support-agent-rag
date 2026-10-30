from supportbot.ingest import load_knowledge_base, split_long, split_sections
from supportbot.retriever import BM25Retriever
from supportbot.text import stem, tokenize

from conftest import KB


def test_tokenize_handles_accents_stopwords_and_stems():
    assert tokenize("¿Cuánto tardan los envíos?") == ["cuanto", "tardan", "envio"]
    assert stem("shipping") == "ship" and stem("shipped") == "ship"


def test_split_sections_keeps_heading_path():
    sections = split_sections("# Shipping\nintro\n## International\nChile text", "x")
    assert sections == [("Shipping", "intro"), ("Shipping > International", "Chile text")]


def test_split_long_respects_paragraph_boundaries():
    body = "\n\n".join(["word " * 60] * 5)
    pieces = split_long(body, limit=700)
    assert len(pieces) > 1 and all(len(p) <= 700 for p in pieces)


def test_knowledge_base_loads_markdown_and_html_without_scripts():
    chunks = load_knowledge_base(KB)
    sources = {c.source for c in chunks}
    assert {"shipping.md", "wholesale.html", "preguntas-frecuentes.md"} <= sources
    assert not any("console.log" in c.text for c in chunks)
    assert any(c.title == "Wholesale > Barista training" for c in chunks)


def test_retriever_ranks_the_right_section_in_both_languages():
    r = BM25Retriever(load_knowledge_base(KB))
    assert r.search("How long does shipping to Chile take?")[0].chunk.title == "Shipping > International"
    assert r.search("¿Puedo retirar en el local?")[0].chunk.title == "Preguntas frecuentes > Retiro en el local"
    assert r.search("refund mercado pago")[0].chunk.title == "Returns and refunds > Refund timing"


def test_coverage_is_low_for_unrelated_questions():
    r = BM25Retriever(load_knowledge_base(KB))
    q = "Do you have a store in Paris with live music?"
    assert r.coverage(q, r.search(q)) < 0.5
