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


def test_singular_and_plural_forms_match():
    from supportbot.text import tokenize
    assert tokenize("prices") == tokenize("price") == tokenize("pricing")
    assert tokenize("deliveries") == tokenize("delivery")
    assert tokenize("boxes") == tokenize("box")
    assert tokenize("ciudades") == tokenize("ciudad")
    assert tokenize("status") == ["status"]


def test_small_talk_detection():
    from supportbot.text import is_small_talk
    assert is_small_talk("Hola!") and is_small_talk("thanks a lot") and is_small_talk("Buenas tardes")
    assert not is_small_talk("hi, do you ship to Chile?")
    assert not is_small_talk("how much?") and not is_small_talk("is it good?") and not is_small_talk("")


def _tiny_pdf(text: str) -> bytes:
    """Builds a minimal one-page PDF with a line of text (no extra dependencies)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offsets)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)


def test_pdf_and_nested_html_headings_are_ingested(tmp_path):
    (tmp_path / "manual.pdf").write_bytes(_tiny_pdf("Warranty lasts 12 months for all grinders."))
    (tmp_path / "page.html").write_text("<h2>\n  <span>Opening</span> hours\n</h2><p>Mon to Fri, 9 to 18.</p>", encoding="utf-8")
    chunks = load_knowledge_base(tmp_path)
    assert any("Warranty lasts 12 months" in c.text and c.source == "manual.pdf" for c in chunks)
    assert any(c.title == "Opening hours" and "Mon to Fri" in c.text for c in chunks)


def test_one_huge_paragraph_is_split_at_sentences():
    body = " ".join(f"Sentence number {i} talks about shipping rules." for i in range(60))
    pieces = split_long(body, limit=400)
    assert len(pieces) > 5 and all(len(p) <= 400 for p in pieces)
    assert all(p.endswith(".") for p in pieces)
