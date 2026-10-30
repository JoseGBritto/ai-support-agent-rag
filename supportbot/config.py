"""Settings from environment variables (or a .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Settings:
    business_name: str = "Our company"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    handoff_webhook_url: str = ""
    admin_token: str = ""
    allowed_origins: list[str] = field(default_factory=lambda: ["*"])
    knowledge_dir: Path = Path("knowledge_base")
    data_dir: Path = Path("data")
    top_k: int = 4
    min_coverage: float = 0.5        # share of the question's key terms that must appear in the sources
    rate_limit_per_minute: int = 20
    max_question_chars: int = 1000

    @property
    def ai_enabled(self) -> bool:
        return bool(self.llm_api_key)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        env = os.environ.get
        return cls(
            business_name=env("BUSINESS_NAME", cls.business_name),
            llm_base_url=env("LLM_BASE_URL", cls.llm_base_url).rstrip("/"),
            llm_api_key=env("LLM_API_KEY", ""),
            llm_model=env("LLM_MODEL", cls.llm_model),
            handoff_webhook_url=env("HANDOFF_WEBHOOK_URL", ""),
            admin_token=env("ADMIN_TOKEN", ""),
            allowed_origins=[o.strip() for o in env("ALLOWED_ORIGINS", "*").split(",") if o.strip()],
            knowledge_dir=Path(env("KNOWLEDGE_DIR", "knowledge_base")),
            data_dir=Path(env("DATA_DIR", "data")),
        )
