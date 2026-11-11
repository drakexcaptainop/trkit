from briefkit.news.discovery import discover
from briefkit.news.types import Candidate, DiscoveryError


def cand(url, published):
    return Candidate(url=url, title=url, kind="news", source="t", published=published)


def test_candidates_are_deduplicated_and_sorted_newest_first():
    sources = {
        "a": lambda: [cand("u1", "2026-11-01"), cand("u2", "2026-11-09")],
        "b": lambda: [cand("u2", "2026-11-09"), cand("u3", None)],
    }
    got, warnings = discover(sources)
    assert [c.url for c in got] == ["u2", "u1", "u3"]
    assert warnings == []


def test_a_failing_source_becomes_a_warning_and_the_rest_still_work():
    def broken():
        raise DiscoveryError("EDGAR is down")

    got, warnings = discover({"SEC filings": broken, "News": lambda: [cand("u1", "2026-11-01")]})
    assert [c.url for c in got] == ["u1"]
    assert warnings == ["SEC filings: EDGAR is down"]


def test_limit_caps_the_list():
    got, _ = discover({"a": lambda: [cand(f"u{i}", f"2026-11-{i:02d}") for i in range(1, 9)]}, 3)
    assert len(got) == 3
