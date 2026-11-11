import pytest

from briefkit.common.config import ConfigError, Settings


def test_defaults_when_environment_is_empty():
    s = Settings.from_env({})
    assert s.news_window_days == 14
    assert s.filings_window_days == 90
    assert s.ledger_path.endswith("ledger.sqlite")
    assert s.ollama_model
    assert s.sec_user_agent is None


def test_environment_overrides_defaults():
    s = Settings.from_env(
        {
            "BRIEFKIT_NEWS_WINDOW_DAYS": "7",
            "BRIEFKIT_OLLAMA_MODEL": "llama3.1:8b",
            "SEC_USER_AGENT": "Research Bot research@example.org",
        }
    )
    assert s.news_window_days == 7
    assert s.ollama_model == "llama3.1:8b"
    assert s.sec_user_agent == "Research Bot research@example.org"


def test_missing_sec_user_agent_error_names_the_setting():
    s = Settings.from_env({})
    with pytest.raises(ConfigError, match="SEC_USER_AGENT"):
        s.require_sec_user_agent()


def test_blank_sec_user_agent_counts_as_unset():
    s = Settings.from_env({"SEC_USER_AGENT": "   "})
    with pytest.raises(ConfigError, match="SEC_USER_AGENT"):
        s.require_sec_user_agent()


def test_invalid_integer_setting_is_a_clear_error():
    with pytest.raises(ConfigError, match="BRIEFKIT_NEWS_WINDOW_DAYS"):
        Settings.from_env({"BRIEFKIT_NEWS_WINDOW_DAYS": "soon"})
