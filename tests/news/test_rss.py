from datetime import date

from briefkit.news.rss import feed_url, parse_feed

FEED = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Fresh story</title><link>https://example.com/a</link>
<pubDate>Wed, 11 Nov 2026 15:53:45 +0000</pubDate><description>Summary A</description></item>
<item><title>Old story</title><link>https://example.com/b</link>
<pubDate>Mon, 01 Jun 2026 10:00:00 +0000</pubDate></item>
<item><title>Undated story</title><link>https://example.com/c</link></item>
<item><title>No link</title></item>
</channel></rss>"""


def test_feed_items_inside_the_window_carry_the_feed_date():
    got = parse_feed(FEED, 14, date(2026, 11, 11))
    assert [(c.title, c.published) for c in got] == [
        ("Fresh story", "2026-11-11"),
        ("Undated story", None),
    ]
    assert got[0].snippet == "Summary A"
    assert got[0].kind == "news"


def test_feed_url_uppercases_the_ticker():
    assert "s=NVDA" in feed_url("nvda")
