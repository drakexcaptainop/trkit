from datetime import date

from briefkit.news.fetch import FetchedPage
from briefkit.news.types import Candidate
from briefkit.news.validate import validate

TODAY = date(2026, 11, 11)


def cand(url, published="2026-11-10", kind="news"):
    return Candidate(url=url, title=f"T {url}", kind=kind, source="s", published=published)


def page(url, published=None):
    return FetchedPage(url=url, title=None, text="body", published=published)


def run(items, candidates, pages, **kw):
    return validate(
        items,
        {c.url: c for c in candidates},
        {p.url: p for p in pages},
        today=TODAY,
        news_window_days=14,
        filings_window_days=90,
        **kw,
    )


def test_item_whose_page_was_fetched_is_kept_with_the_feed_date():
    kept, warnings = run([{"url": "u1", "summary": "ok"}], [cand("u1")], [page("u1")])
    assert [(k["url"], k["published"], k["summary"]) for k in kept] == [("u1", "2026-11-10", "ok")]
    assert warnings == []


def test_item_never_fetched_is_dropped_with_a_warning():
    kept, warnings = run([{"url": "u1", "summary": "ok"}], [cand("u1")], [])
    assert kept == []
    assert "u1" in warnings[0]


def test_url_the_model_invented_is_dropped():
    kept, _ = run([{"url": "evil", "summary": "x"}], [cand("u1")], [page("evil")])
    assert kept == []


def test_model_written_date_is_ignored_and_page_metadata_fills_a_missing_feed_date():
    items = [{"url": "u1", "summary": "s", "published": "2026-11-11"}]
    kept, _ = run(items, [cand("u1", published=None)], [page("u1", published="2026-11-03")])
    assert kept[0]["published"] == "2026-11-03"


def test_feed_date_wins_over_page_metadata():
    kept, _ = run(
        [{"url": "u1", "summary": "s"}], [cand("u1")], [page("u1", published="2026-11-01")]
    )
    assert kept[0]["published"] == "2026-11-10"


def test_item_with_no_trustworthy_date_is_dropped():
    kept, warnings = run([{"url": "u1", "summary": "s"}], [cand("u1", None)], [page("u1")])
    assert kept == []
    assert "date" in warnings[0]


def test_stale_news_is_dropped_but_a_filing_of_the_same_age_is_kept():
    old = "2026-09-01"
    news, _ = run([{"url": "u1", "summary": "s"}], [cand("u1", old)], [page("u1")])
    filing, _ = run([{"url": "u2", "summary": "s"}], [cand("u2", old, kind="filing")], [page("u2")])
    assert news == [] and len(filing) == 1


def test_long_summaries_are_truncated_and_duplicates_collapsed():
    items = [{"url": "u1", "summary": "x" * 2000}, {"url": "u1", "summary": "again"}]
    kept, _ = run(items, [cand("u1")], [page("u1")])
    assert len(kept) == 1 and len(kept[0]["summary"]) <= 600


def test_malformed_items_are_skipped():
    kept, _ = run(["nope", {"summary": "no url"}, {"url": "u1"}], [cand("u1")], [page("u1")])
    assert [k["url"] for k in kept] == ["u1"] and kept[0]["summary"] == ""
