"""Per-ticker news discovery from an RSS feed."""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta

import feedparser

from briefkit.news.types import Candidate

FEED_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
SOURCE = "yahoo-finance-rss"


def feed_url(ticker: str) -> str:
    return FEED_URL.format(ticker=ticker.upper())


def parse_feed(text: str, window_days: int, today: date) -> list[Candidate]:
    cutoff = today - timedelta(days=window_days)
    out: list[Candidate] = []
    for entry in feedparser.parse(text).entries:
        link = entry.get("link")
        title = entry.get("title")
        if not link or not title:
            continue
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        published = datetime.fromtimestamp(calendar.timegm(stamp), UTC).date() if stamp else None
        if published is not None and published < cutoff:
            continue
        out.append(
            Candidate(
                url=link,
                title=title,
                kind="news",
                source=SOURCE,
                published=published.isoformat() if published else None,
                snippet=(entry.get("summary") or "")[:400],
            )
        )
    return out
