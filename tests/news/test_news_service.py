import json
from datetime import date
from types import SimpleNamespace as NS

import pytest

from briefkit.common.config import Settings
from briefkit.news.fetch import FetchedPage
from briefkit.news.service import NewsService
from briefkit.news.types import Candidate, DiscoveryError

TODAY = date(2026, 11, 11)
CAND = Candidate("https://a.com/1", "Story", "news", "rss", "2026-11-10")


class Client:
    def __init__(self, replies):
        self.replies = list(replies)

    def chat(self, **kw):
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class Fetcher:
    def fetch(self, url):
        return FetchedPage(url, "T", "text", None)


def msg(content="", tool_calls=None):
    return NS(message=NS(role="assistant", content=content, tool_calls=tool_calls))


def service(sources, replies):
    return NewsService(Settings(), lambda t, d: sources, Fetcher(), Client(replies), lambda: TODAY)


def fetch_then(final):
    call = NS(function=NS(name="fetch_page", arguments={"url": CAND.url}))
    return [msg(tool_calls=[call]), msg(final)]


def test_digest_keeps_only_fetched_dated_items_with_sources():
    final = json.dumps({"items": [{"url": CAND.url, "summary": "Did a thing"}]})
    env = service({"News": lambda: [CAND]}, fetch_then(final)).get_news_digest("nvda")
    d = env.to_dict()
    assert d["as_of"] == "2026-11-11"
    assert d["data"]["ticker"] == "NVDA" and d["data"]["content_is_untrusted"] is True
    assert [(i["url"], i["published"]) for i in d["data"]["items"]] == [(CAND.url, "2026-11-10")]


def test_item_the_agent_never_fetched_is_not_in_the_digest():
    final = json.dumps({"items": [{"url": CAND.url, "summary": "x"}]})
    env = service({"News": lambda: [CAND]}, [msg(final)]).get_news_digest("NVDA")
    assert env.data["items"] == [] and any("never fetched" in w for w in env.warnings)


def test_ollama_down_returns_unread_headlines_and_a_warning():
    env = service({"News": lambda: [CAND]}, [ConnectionError("refused")]).get_news_digest("NVDA")
    assert env.data["items"] == []
    assert env.data["headlines_unread"][0]["url"] == CAND.url
    assert any("Ollama" in w for w in env.warnings)


def test_no_candidates_is_reported_not_invented():
    env = service({"News": list}, []).get_news_digest("NVDA")
    assert env.data["items"] == [] and any("No recent" in w for w in env.warnings)


def test_a_failing_source_is_a_warning():
    def broken():
        raise DiscoveryError("EDGAR down")

    env = service({"SEC filings": broken}, []).get_news_digest("NVDA")
    assert any("EDGAR down" in w for w in env.warnings)


def test_invalid_ticker_is_rejected():
    with pytest.raises(ValueError, match="valid ticker"):
        service({}, []).get_news_digest("NVDA; rm -rf")
