import json
from types import SimpleNamespace as NS

import pytest

from briefkit.common.config import Settings
from briefkit.news.agent import AgentUnavailable, run_agent
from briefkit.news.fetch import FetchedPage, FetchError
from briefkit.news.types import Candidate

CANDS = [
    Candidate("https://a.com/1", "A1", "news", "s", "2026-11-10"),
    Candidate("https://a.com/2", "A2", "news", "s", "2026-11-09"),
]


def call(name, **args):
    return NS(function=NS(name=name, arguments=args))


def reply(content="", tool_calls=None):
    return NS(message=NS(role="assistant", content=content, tool_calls=tool_calls))


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def chat(self, **kw):
        self.requests.append({**kw, "messages": list(kw["messages"])})
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeFetcher:
    def __init__(self):
        self.urls = []

    def fetch(self, url):
        self.urls.append(url)
        if url.endswith("/2"):
            raise FetchError("boom")
        return FetchedPage(url, "T", "page text", None)


FINAL = json.dumps({"items": [{"url": "https://a.com/1", "summary": "s"}]})


def run(replies, settings=None, fetcher=None):
    client = FakeClient(replies)
    fetcher = fetcher or FakeFetcher()
    return run_agent("NVDA", CANDS, fetcher, client, settings or Settings()), client, fetcher


def test_fetches_candidate_then_returns_items_and_sends_num_ctx():
    res, client, fetcher = run(
        [reply(tool_calls=[call("fetch_page", url="https://a.com/1")]), reply(FINAL)]
    )
    assert fetcher.urls == ["https://a.com/1"]
    assert list(res.fetched) == ["https://a.com/1"]
    assert res.items == [{"url": "https://a.com/1", "summary": "s"}]
    assert client.requests[0]["options"] == {"num_ctx": 8192}


def test_url_outside_the_candidate_list_is_refused_and_never_fetched():
    res, client, fetcher = run(
        [reply(tool_calls=[call("fetch_page", url="https://evil.com/x")]), reply(FINAL)]
    )
    assert fetcher.urls == [] and res.fetched == {}
    assert "not in the candidate list" in client.requests[1]["messages"][-1]["content"]


def test_fetch_failure_is_reported_to_the_model_not_raised():
    res, client, _ = run(
        [reply(tool_calls=[call("fetch_page", url="https://a.com/2")]), reply(FINAL)]
    )
    assert "Could not fetch" in client.requests[1]["messages"][-1]["content"]
    assert res.fetched == {}


def test_budget_stops_further_fetches_and_forces_an_answer():
    settings = Settings(agent_call_budget=1)
    replies = [
        reply(tool_calls=[call("fetch_page", url="https://a.com/1")]),
        reply(tool_calls=[call("fetch_page", url="https://a.com/2")]),
        reply(FINAL),
    ]
    res, client, fetcher = run(replies, settings)
    assert fetcher.urls == ["https://a.com/1"]
    assert client.requests[1]["tools"] is None
    assert any("budget" in w for w in res.warnings)


def test_one_malformed_call_is_retried_then_succeeds():
    replies = [
        reply(tool_calls=[call("fetch_page")]),
        reply(tool_calls=[call("fetch_page", url="https://a.com/1")]),
        reply(FINAL),
    ]
    res, _, fetcher = run(replies)
    assert fetcher.urls == ["https://a.com/1"] and res.items


def test_repeated_malformed_calls_stop_the_agent():
    replies = [
        reply(tool_calls=[call("fetch_page")]),
        reply(tool_calls=[call("fetch_page")]),
        reply(FINAL),
    ]
    res, _, fetcher = run(replies)
    assert fetcher.urls == [] and any("malformed" in w for w in res.warnings)


def test_unparsable_final_answer_gets_one_json_retry():
    res, client, _ = run([reply("here you go, no json"), reply(FINAL)])
    assert res.items and client.requests[1]["format"] == "json"


def test_still_unparsable_means_no_items_and_a_warning():
    res, _, _ = run([reply("nope"), reply("still nope")])
    assert res.items == [] and res.warnings


def test_unreachable_model_raises_agent_unavailable():
    with pytest.raises(AgentUnavailable, match="Ollama"):
        run([ConnectionError("refused")])
