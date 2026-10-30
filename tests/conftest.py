import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from supportbot.agent import SupportAgent  # noqa: E402
from supportbot.config import Settings  # noqa: E402
from supportbot.store import Store  # noqa: E402

KB = ROOT / "knowledge_base"


class FakeLLM:
    def __init__(self, reply="Delivery to Chile takes 5 to 8 business days [1]."):
        self.reply, self.calls = reply, []

    def complete(self, messages, temperature=0.1):
        self.calls.append(messages)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class FakeHTTP:
    def __init__(self):
        self.posts = []

    def post(self, url, json=None, timeout=None):
        self.posts.append((url, json))


@pytest.fixture
def settings(tmp_path):
    return Settings(business_name="Andes Coffee Co.", knowledge_dir=KB, data_dir=tmp_path,
                    admin_token="secret", handoff_webhook_url="https://hooks.example/handoff")


@pytest.fixture
def make_agent(settings):
    def factory(llm=None):
        return SupportAgent(settings, store=Store(), llm=llm, http=FakeHTTP())
    return factory
