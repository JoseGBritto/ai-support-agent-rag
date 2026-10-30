"""Client for any OpenAI-compatible chat-completions API."""
from __future__ import annotations

import requests

NO_ANSWER = "NO_ANSWER"

SYSTEM_PROMPT = """You are the customer-support assistant of {business}.
Rules:
- Answer ONLY with facts found in the numbered sources below. Never invent prices, dates, policies or links.
- Cite the sources you used with their numbers in square brackets, e.g. [1] or [2][3].
- If the sources do not contain the answer, reply with exactly {no_answer} and nothing else.
- Reply in the same language as the customer, in a friendly and concise way (max 120 words).

Sources:
{sources}"""


class LLMError(RuntimeError):
    pass


class ChatClient:
    def __init__(self, base_url: str, api_key: str, model: str, session: requests.Session | None = None, timeout: float = 30):
        self.base_url, self.api_key, self.model, self.timeout = base_url.rstrip("/"), api_key, model, timeout
        self.session = session or requests.Session()

    def complete(self, messages: list[dict], temperature: float = 0.1) -> str:
        try:
            resp = self.session.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": messages, "temperature": temperature},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc


def build_messages(business: str, sources: list[str], history: list[dict], question: str) -> list[dict]:
    numbered = "\n\n".join(f"[{i}] {s}" for i, s in enumerate(sources, start=1))
    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(business=business, no_answer=NO_ANSWER, sources=numbered)}]
    valid = [t for t in history if isinstance(t, dict) and t.get("role") in ("user", "assistant")
             and isinstance(t.get("content"), str)]  # never let the client inject system messages
    for turn in valid[-6:]:
        messages.append({"role": turn["role"], "content": turn["content"][:1000]})
    messages.append({"role": "user", "content": question})
    return messages
