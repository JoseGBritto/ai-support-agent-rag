import requests

from supportbot.llm import NO_ANSWER, ChatClient, LLMError, build_messages

from conftest import FakeLLM


def test_ai_answer_returns_only_cited_sources(make_agent):
    llm = FakeLLM("It takes 5 to 8 business days [2].")
    agent = make_agent(llm)
    reply = agent.ask("How long does shipping to Chile take?", "c1")
    assert reply.mode == "ai" and not reply.handoff
    assert len(reply.sources) == 1 and reply.sources[0]["n"] == 2
    system = llm.calls[0][0]["content"]
    assert "Andes Coffee Co." in system and "[1]" in system and NO_ANSWER in system


def test_no_answer_from_llm_triggers_handoff_and_webhook(make_agent):
    agent = make_agent(FakeLLM(NO_ANSWER))
    reply = agent.ask("Do you ship coffee to Chile in wooden boxes?", "c2")
    assert reply.handoff and reply.mode == "handoff"
    assert "wooden boxes" in agent.http.posts[0][1]["text"]
    assert agent.store.stats()["handoffs"] == 1


def test_low_coverage_hands_off_without_calling_the_llm(make_agent):
    llm = FakeLLM()
    agent = make_agent(llm)
    reply = agent.ask("Do you have a store in Paris with live music?", "c3")
    assert reply.handoff and llm.calls == []
    assert agent.store.knowledge_gaps()[0]["q"] == "do you have a store in paris with live music?"


def test_handoff_message_follows_customer_language(make_agent):
    reply = make_agent().ask("¿Hacen envíos a Marte en cohete?", "c4")
    assert reply.handoff and reply.answer.startswith("No tengo")


def test_demo_mode_quotes_the_best_source(make_agent):
    reply = make_agent().ask("Can I return an opened bag?", "c5")
    assert reply.mode == "demo"
    assert reply.answer.startswith("Opened coffee bags cannot be returned")
    assert reply.sources[0]["source"] == "returns.md"


def test_llm_failure_falls_back_to_demo_answer(make_agent):
    reply = make_agent(FakeLLM(LLMError("timeout"))).ask("How long does shipping to Chile take?", "c6")
    assert reply.mode == "demo" and "5 to 8" in reply.answer


def test_follow_up_question_uses_previous_message_for_retrieval(make_agent):
    llm = FakeLLM("Yes [1].")
    agent = make_agent(llm)
    history = [{"role": "user", "content": "How much is international shipping?"}, {"role": "assistant", "content": "USD 18 [1]."}]
    agent.ask("And Brazil?", "c7", history)
    assert "Shipping > International" in llm.calls[0][0]["content"]
    assert llm.calls[0][1] == history[0]


def test_contact_is_attached_to_the_pending_handoff(make_agent):
    agent = make_agent()
    agent.ask("Do you have a store in Paris with live music?", "c8")
    assert agent.add_contact("c8", "ana@example.com")
    assert not agent.add_contact("unknown", "ana@example.com")


def test_build_messages_limits_history():
    history = [{"role": "user", "content": f"m{i}"} for i in range(10)] + [{"role": "system", "content": "evil"}]
    msgs = build_messages("Biz", ["a"], history, "q")
    assert len(msgs) == 1 + 6 + 1 and all(m["content"] != "evil" for m in msgs[1:])


class Resp:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class Session:
    def __init__(self, resp):
        self.resp, self.request = resp, None

    def post(self, url, headers=None, json=None, timeout=None):
        self.request = (url, headers, json)
        return self.resp


def test_chat_client_calls_openai_compatible_endpoint():
    s = Session(Resp({"choices": [{"message": {"content": " Hello [1] "}}]}))
    out = ChatClient("https://api.groq.com/openai/v1/", "KEY", "llama", s).complete([{"role": "user", "content": "hi"}])
    url, headers, body = s.request
    assert out == "Hello [1]" and url == "https://api.groq.com/openai/v1/chat/completions"
    assert headers["Authorization"] == "Bearer KEY" and body["model"] == "llama"


def test_chat_client_wraps_errors():
    import pytest
    with pytest.raises(LLMError):
        ChatClient("https://x", "k", "m", Session(Resp({}, 500))).complete([])


def test_new_topic_is_not_hijacked_by_previous_question(make_agent):
    history = [{"role": "user", "content": "How long does shipping to Chile take?"}, {"role": "assistant", "content": "5 to 8 days [1]."}]
    reply = make_agent().ask("¿Tienen descuento para cafeterías?", "c9", history)
    assert reply.sources[0]["title"] == "Preguntas frecuentes > Descuento para cafeterías"


def test_vague_follow_up_borrows_context(make_agent):
    history = [{"role": "user", "content": "Do you have a coffee subscription?"}, {"role": "assistant", "content": "Yes [1]."}]
    reply = make_agent().ask("can I pause it?", "c10", history)
    assert not reply.handoff and reply.sources[0]["title"] == "Products > Subscription"


def test_unknown_topic_after_a_known_one_still_hands_off(make_agent):
    history = [{"role": "user", "content": "¿Tienen descuento para cafeterías?"}, {"role": "assistant", "content": "Sí [1]."}]
    assert make_agent().ask("Do you organize coffee tasting events?", "c11", history).handoff
