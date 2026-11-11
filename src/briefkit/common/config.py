"""Settings read from environment variables, with defaults."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigError(Exception):
    """A setting is missing or invalid; the message says how to fix it."""


def _int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}") from None


@dataclass(frozen=True)
class Settings:
    ollama_model: str = "qwen3:8b"
    ollama_num_ctx: int = 8192
    news_window_days: int = 14
    filings_window_days: int = 90
    page_text_cap: int = 12000
    agent_call_budget: int = 8
    ledger_path: str = "data/ledger.sqlite"
    sec_user_agent: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        defaults = cls()
        sec = (env.get("SEC_USER_AGENT") or "").strip() or None
        return cls(
            ollama_model=(env.get("BRIEFKIT_OLLAMA_MODEL") or defaults.ollama_model).strip(),
            ollama_num_ctx=_int(env, "BRIEFKIT_OLLAMA_NUM_CTX", defaults.ollama_num_ctx),
            news_window_days=_int(env, "BRIEFKIT_NEWS_WINDOW_DAYS", defaults.news_window_days),
            filings_window_days=_int(
                env, "BRIEFKIT_FILINGS_WINDOW_DAYS", defaults.filings_window_days
            ),
            page_text_cap=_int(env, "BRIEFKIT_PAGE_TEXT_CAP", defaults.page_text_cap),
            agent_call_budget=_int(env, "BRIEFKIT_AGENT_CALL_BUDGET", defaults.agent_call_budget),
            ledger_path=(env.get("BRIEFKIT_LEDGER_PATH") or defaults.ledger_path).strip(),
            sec_user_agent=sec,
        )

    def require_sec_user_agent(self) -> str:
        if not self.sec_user_agent:
            raise ConfigError(
                "SEC_USER_AGENT is not set. The SEC requires a contact string on every request. "
                "Set it to something like 'YourName your-contact@example.org' in the environment "
                "that launches the news server."
            )
        return self.sec_user_agent
